import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from muesli_model_service.backends.base import CapabilityBackend
from muesli_model_service.protocol.actions import ActionChunkOutput, ActionType
from muesli_model_service.protocol.capabilities import CapabilityDescriptor, MethodMode
from muesli_model_service.protocol.envelope import RequestEnvelope, ResponseEnvelope, response
from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.sessions import (
    SessionManager,
    SessionState,
    unknown_session_response,
)
from muesli_model_service.store.frames import FrameStore, FrameStoreError

SMOLVLA_BASE_MODEL = "lerobot/smolvla_base"


class SmolVLAProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_map: dict[str, str] = Field(default_factory=dict)
    state_key: str = "observation.state"
    task_key: str = "task"
    robot_type_key: str = "robot_type"

    @classmethod
    def from_path(cls, path: str | Path | None) -> "SmolVLAProfile":
        if path is None:
            return cls()
        return cls.model_validate(json.loads(Path(path).read_text()))


@dataclass(frozen=True)
class SmolVLACallInput:
    instruction: str
    observation: dict[str, Any]


@dataclass(frozen=True)
class SmolVLAPrediction:
    actions: list[list[float]]
    action_dim: int
    chunk_length: int
    metadata: dict[str, Any]


class SmolVLAAdapter(Protocol):
    @property
    def required_image_names(self) -> tuple[str, ...]: ...

    @property
    def metadata(self) -> dict[str, Any]: ...

    def predict_action_chunk(self, call: SmolVLACallInput) -> SmolVLAPrediction: ...


class SmolVLADependencyError(RuntimeError):
    pass


class SmolVLAInvalidOutputError(RuntimeError):
    pass


class SmolVLABackend(CapabilityBackend):
    def __init__(
        self,
        sessions: SessionManager,
        *,
        model_path: str = SMOLVLA_BASE_MODEL,
        device: str = "cuda",
        profile_path: str | Path | None = None,
        action_type: str = ActionType.JOINT_TARGETS.value,
        dt_ms: int = 33,
        backend_key: str = "smolvla",
        adapter: SmolVLAAdapter | None = None,
        frame_store: FrameStore | None = None,
    ) -> None:
        self.sessions = sessions
        self.model_path = model_path
        self.device = device
        self.profile = SmolVLAProfile.from_path(profile_path)
        self.action_type = ActionType(action_type)
        self.dt_ms = dt_ms
        self.backend_key = backend_key
        self.frame_store = frame_store
        self.adapter = adapter or LeRobotSmolVLAAdapter(
            model_path=model_path,
            device=device,
            profile=self.profile,
        )

    def describe(self) -> list[CapabilityDescriptor]:
        return [
            CapabilityDescriptor(
                id="cap.vla.action_chunk.v1",
                kind="action_model",
                description="LeRobot SmolVLA action chunk proposal capability",
                mode=MethodMode.SESSION,
                input_schema="mms://schemas/cap.vla.action_chunk.request.v1",
                output_schema="mms://schemas/cap.vla.action_chunk.result.v1",
                supports_cancel=True,
                freshness={"expects_fresh_observation": True},
                replay={"supported": False},
                metadata={
                    "backend": "smolvla",
                    "adapter": "lerobot",
                    "model_path": self.model_path,
                    "device": self.device,
                    "requires_gpu": self.device == "cuda",
                    "base_model": self.model_path == SMOLVLA_BASE_MODEL,
                    **self.adapter.metadata,
                },
            )
        ]

    async def start(self, request: RequestEnvelope) -> ResponseEnvelope:
        parsed = self._parse_call_input(request.input, request_id=request.id)
        if isinstance(parsed, ResponseEnvelope):
            return parsed
        session = self.sessions.create(
            backend_key=self.backend_key,
            capability=str(request.capability),
            method="session",
            data={"input": request.input},
        )
        return response(
            request.id,
            ProtocolStatus.RUNNING,
            session_id=session.id,
            metadata={
                "capability": session.capability,
                "backend": "smolvla",
                "adapter": "lerobot",
                "model_path": self.model_path,
                "device": self.device,
                "base_model": self.model_path == SMOLVLA_BASE_MODEL,
            },
        )

    async def step(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.mark_step(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        if session.state == SessionState.CANCELLED:
            return response(request.id, ProtocolStatus.CANCELLED, session_id=session.id)

        call_payload = request.input or session.data["input"]
        parsed = self._parse_call_input(call_payload, request_id=request.id)
        if isinstance(parsed, ResponseEnvelope):
            return parsed

        try:
            prediction = self.adapter.predict_action_chunk(parsed)
            output = self._format_prediction(prediction)
        except (SmolVLAInvalidOutputError, ValidationError, ValueError) as exc:
            return response(
                request.id,
                ProtocolStatus.INVALID_OUTPUT,
                session_id=session.id,
                error=error("invalid_smolvla_output", str(exc), retryable=False),
                metadata=self._response_metadata(),
            )

        return response(
            request.id,
            ProtocolStatus.ACTION_CHUNK,
            output=output,
            session_id=session.id,
            metadata=self._response_metadata(prediction),
        )

    async def cancel(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.require(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        session.state = SessionState.CANCELLED
        return response(request.id, ProtocolStatus.CANCELLED, session_id=session.id)

    async def status(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.require(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        if session.state == SessionState.CANCELLED:
            return response(request.id, ProtocolStatus.CANCELLED, session_id=session.id)
        return response(
            request.id,
            ProtocolStatus.RUNNING,
            output=self.sessions.to_payload(session),
            session_id=session.id,
        )

    async def close(self, request: RequestEnvelope) -> ResponseEnvelope:
        session_id = str(request.session_id or "")
        try:
            session = self.sessions.close(session_id)
        except KeyError:
            return unknown_session_response(request.id, session_id)
        return response(request.id, ProtocolStatus.SUCCESS, session_id=session.id)

    def _parse_call_input(
        self, payload: dict[str, Any], *, request_id: str
    ) -> SmolVLACallInput | ResponseEnvelope:
        instruction = payload.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            return self._invalid_request(
                request_id, "missing_instruction", "SmolVLA requests require instruction"
            )

        observation = payload.get("observation")
        if not isinstance(observation, dict):
            return self._invalid_request(
                request_id, "missing_observation", "SmolVLA requests require observation"
            )

        state = observation.get("state")
        if not _is_number_sequence(state):
            return self._invalid_request(
                request_id, "invalid_state", "SmolVLA observation.state must be a numeric array"
            )

        images = observation.get("images")
        if not isinstance(images, dict):
            return self._invalid_request(
                request_id, "missing_images", "SmolVLA observation.images is required"
            )

        resolved_images: dict[str, Any] = dict(images)
        resolved_refs: dict[str, str] = {}
        for image_name in self.adapter.required_image_names:
            image_ref = images.get(image_name)
            resolved_image = self._resolve_image_input(image_name, image_ref, request_id)
            if isinstance(resolved_image, ResponseEnvelope):
                return resolved_image
            resolved_images[image_name] = resolved_image
            if isinstance(resolved_image.get("resolved_ref"), str):
                resolved_refs[image_name] = str(resolved_image["resolved_ref"])

        resolved_observation = dict(observation)
        resolved_observation["images"] = resolved_images
        if resolved_refs:
            resolved_observation["resolved_refs"] = resolved_refs

        return SmolVLACallInput(instruction=instruction.strip(), observation=resolved_observation)

    def _resolve_image_input(
        self, image_name: str, image_ref: Any, request_id: str
    ) -> dict[str, Any] | ResponseEnvelope:
        if not isinstance(image_ref, dict):
            return self._invalid_request(
                request_id,
                "missing_image",
                f"SmolVLA observation.images.{image_name} must be an object",
                details={"image": image_name},
            )

        if isinstance(image_ref.get("path"), str):
            return dict(image_ref)

        ref = image_ref.get("ref")
        if isinstance(ref, str):
            if self.frame_store is None:
                return self._invalid_request(
                    request_id,
                    "frame_store_unavailable",
                    "SmolVLA image refs require a configured frame store",
                    details={"image": image_name},
                )
            try:
                record = self.frame_store.resolve(ref)
            except FrameStoreError as exc:
                return self._invalid_request(
                    request_id,
                    "frame_ref_not_found",
                    str(exc),
                    details={"image": image_name, "ref": ref},
                )
            resolved = dict(image_ref)
            resolved["path"] = str(record.path)
            resolved["resolved_ref"] = record.ref
            resolved["media_type"] = record.media_type
            resolved["timestamp_ns"] = record.timestamp_ns
            resolved["sha256"] = record.sha256
            return resolved

        return self._invalid_request(
            request_id,
            "missing_image",
            f"SmolVLA observation.images.{image_name}.path or .ref is required",
            details={"image": image_name},
        )

    def _format_prediction(self, prediction: SmolVLAPrediction) -> dict[str, Any]:
        if prediction.chunk_length <= 0 or prediction.action_dim <= 0:
            raise SmolVLAInvalidOutputError("SmolVLA returned an empty action chunk")

        actions = []
        for values in prediction.actions:
            if not values:
                raise SmolVLAInvalidOutputError("SmolVLA returned an action with no values")
            if not all(math.isfinite(value) for value in values):
                raise SmolVLAInvalidOutputError("SmolVLA returned a non-finite action value")
            actions.append(
                {
                    "type": self.action_type.value,
                    "values": values,
                    "dt_ms": self.dt_ms,
                }
            )
        output = {"actions": actions}
        ActionChunkOutput.model_validate(output)
        return output

    def _response_metadata(self, prediction: SmolVLAPrediction | None = None) -> dict[str, Any]:
        metadata = {
            "backend": "smolvla",
            "adapter": "lerobot",
            "model_path": self.model_path,
            "device": self.device,
            "base_model": self.model_path == SMOLVLA_BASE_MODEL,
        }
        if prediction is not None:
            metadata.update(
                {
                    "action_dim": prediction.action_dim,
                    "chunk_length": prediction.chunk_length,
                    **prediction.metadata,
                }
            )
        return metadata

    def _invalid_request(
        self, request_id: str, code: str, message: str, *, details: dict[str, Any] | None = None
    ) -> ResponseEnvelope:
        return response(
            request_id,
            ProtocolStatus.INVALID_REQUEST,
            error=error(code, message, details=details),
            metadata={"backend": "smolvla", "adapter": "lerobot"},
        )


class LeRobotSmolVLAAdapter:
    def __init__(self, *, model_path: str, device: str, profile: SmolVLAProfile) -> None:
        self.model_path = model_path
        self.device = device
        self.profile = profile
        self._torch = self._import_torch()
        if device == "cuda" and not self._torch.cuda.is_available():
            raise SmolVLADependencyError("MMS_SMOLVLA_DEVICE=cuda requires a CUDA-capable torch")
        policy_cls, make_processors = self._import_lerobot()
        self.policy = policy_cls.from_pretrained(model_path)
        self.policy.to(device)
        self.policy.eval()
        self.preprocess, self.postprocess = self._make_processors(make_processors)
        self.image_map = self._resolve_image_map()

    @property
    def required_image_names(self) -> tuple[str, ...]:
        return tuple(self.image_map.keys())

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "required_images": list(self.required_image_names),
            "state_key": self.profile.state_key,
        }

    def predict_action_chunk(self, call: SmolVLACallInput) -> SmolVLAPrediction:
        batch = self.preprocess(self._build_raw_batch(call))
        with self._torch.inference_mode():
            if hasattr(self.policy, "predict_action_chunk"):
                actions = self.policy.predict_action_chunk(batch)
            else:
                actions = self.policy.select_action(batch)
        actions = self.postprocess(actions)
        rows = _tensor_to_action_rows(actions)
        if not rows:
            raise SmolVLAInvalidOutputError("SmolVLA produced no action rows")
        return SmolVLAPrediction(
            actions=rows,
            action_dim=len(rows[0]),
            chunk_length=len(rows),
            metadata={},
        )

    def _make_processors(self, make_processors: Any) -> tuple[Any, Any]:
        try:
            return make_processors(
                self.policy.config,
                self.model_path,
                preprocessor_overrides={"device_processor": {"device": str(self.device)}},
            )
        except TypeError:
            return make_processors(self.policy.config, pretrained_path=self.model_path)

    def _build_raw_batch(self, call: SmolVLACallInput) -> dict[str, Any]:
        observation = call.observation
        batch: dict[str, Any] = {
            self.profile.state_key: self._torch.tensor(
                [observation["state"]], dtype=self._torch.float32, device=self.device
            ),
            self.profile.task_key: [call.instruction],
        }
        robot_type = observation.get("robot_type")
        if isinstance(robot_type, str):
            batch[self.profile.robot_type_key] = [robot_type]
        images = observation["images"]
        for request_key, feature_key in self.image_map.items():
            batch[feature_key] = self._load_image_tensor(images[request_key]["path"])
        return batch

    def _load_image_tensor(self, path: str) -> Any:
        try:
            image_module = import_module("PIL.Image")
        except ImportError as exc:
            raise SmolVLADependencyError("SmolVLA image loading requires Pillow") from exc

        image = image_module.open(path).convert("RGB")
        width, height = image.size
        data = self._torch.tensor(
            list(image.getdata()), dtype=self._torch.float32, device=self.device
        ).reshape(height, width, 3)
        return data.permute(2, 0, 1).unsqueeze(0) / 255.0

    def _resolve_image_map(self) -> dict[str, str]:
        if self.profile.image_map:
            return self.profile.image_map
        feature_keys = list(getattr(self.policy.config, "image_features", {}).keys())
        return {key.rsplit(".", maxsplit=1)[-1]: key for key in feature_keys}

    def _import_torch(self) -> Any:
        try:
            return import_module("torch")
        except ImportError as exc:
            raise SmolVLADependencyError(
                "Install the optional smolvla extra to enable the SmolVLA backend"
            ) from exc

    def _import_lerobot(self) -> tuple[Any, Any]:
        try:
            policies = import_module("lerobot.policies")
            smolvla = import_module("lerobot.policies.smolvla")
        except ImportError as exc:
            return self._import_lerobot_fallback(exc)
        policy_cls = getattr(smolvla, "SmolVLAPolicy", None)
        make_processors = getattr(policies, "make_pre_post_processors", None)
        if policy_cls is None or make_processors is None:
            return self._import_lerobot_fallback(
                ImportError("LeRobot SmolVLA policy factory is not exported at top level")
            )
        return policy_cls, make_processors

    def _import_lerobot_fallback(self, original: ImportError) -> tuple[Any, Any]:
        try:
            policies = import_module("lerobot.policies.factory")
            smolvla = import_module("lerobot.policies.smolvla.modeling_smolvla")
        except ImportError as exc:
            dependency_error = SmolVLADependencyError(
                "Install the optional smolvla extra to enable the SmolVLA backend"
            )
            if original.name != "lerobot.policies":
                raise dependency_error from original
            raise dependency_error from exc
        return smolvla.SmolVLAPolicy, policies.make_pre_post_processors


def _is_number_sequence(value: Any) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, str | bytes)
        and all(isinstance(item, int | float) and math.isfinite(float(item)) for item in value)
    )


def _tensor_to_action_rows(value: Any) -> list[list[float]]:
    if hasattr(value, "detach"):
        value = value.detach().cpu().tolist()
    if isinstance(value, Mapping) and "action" in value:
        return _tensor_to_action_rows(value["action"])
    if not isinstance(value, list):
        raise SmolVLAInvalidOutputError("SmolVLA action output is not an array")
    while value and isinstance(value[0], list) and len(value) == 1:
        value = value[0]
    if not value:
        return []
    if all(isinstance(item, int | float) for item in value):
        return [[float(item) for item in value]]
    rows = []
    for row in value:
        if not isinstance(row, list) or not all(isinstance(item, int | float) for item in row):
            raise SmolVLAInvalidOutputError("SmolVLA action output has an unsupported shape")
        rows.append([float(item) for item in row])
    return rows
