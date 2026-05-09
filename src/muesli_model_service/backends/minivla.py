import json
import math
import re
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

MINIVLA_BASE_MODEL = "Stanford-ILIAD/minivla-vq-bridge-prismatic"


class MiniVLAProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_map: dict[str, str] = Field(default_factory=dict)
    image_order: list[str] = Field(default_factory=list)
    state_key: str = "observation.state"
    task_key: str = "prompt"
    robot_type_key: str = "robot_type"
    prompt_template: str = "{instruction}"
    action_key: str = "actions"

    @classmethod
    def from_path(cls, path: str | Path | None) -> "MiniVLAProfile":
        if path is None:
            return cls()
        return cls.model_validate(json.loads(Path(path).read_text()))


@dataclass(frozen=True)
class MiniVLACallInput:
    instruction: str
    observation: dict[str, Any]


@dataclass(frozen=True)
class MiniVLAPrediction:
    actions: list[list[float]]
    action_dim: int
    chunk_length: int
    metadata: dict[str, Any]


class MiniVLAAdapter(Protocol):
    @property
    def required_image_names(self) -> tuple[str, ...]: ...

    @property
    def metadata(self) -> dict[str, Any]: ...

    def predict_action_chunk(self, call: MiniVLACallInput) -> MiniVLAPrediction: ...


class MiniVLADependencyError(RuntimeError):
    pass


class MiniVLAInvalidOutputError(RuntimeError):
    pass


class MiniVLABackend(CapabilityBackend):
    def __init__(
        self,
        sessions: SessionManager,
        *,
        model_path: str = MINIVLA_BASE_MODEL,
        device: str = "cuda",
        profile_path: str | Path | None = None,
        action_type: str = ActionType.JOINT_TARGETS.value,
        dt_ms: int = 200,
        unnorm_key: str = "",
        dtype: str = "bfloat16",
        backend_key: str = "minivla",
        adapter: MiniVLAAdapter | None = None,
        frame_store: FrameStore | None = None,
    ) -> None:
        self.sessions = sessions
        self.model_path = model_path
        self.device = device
        self.profile = MiniVLAProfile.from_path(profile_path)
        self.action_type = ActionType(action_type)
        self.dt_ms = dt_ms
        self.unnorm_key = unnorm_key
        self.dtype = dtype
        self.backend_key = backend_key
        self.frame_store = frame_store
        self._adapter = adapter

    def describe(self) -> list[CapabilityDescriptor]:
        return [
            CapabilityDescriptor(
                id="cap.vla.action_chunk.v1",
                kind="action_model",
                description="OpenVLA-Mini action chunk proposal capability",
                mode=MethodMode.SESSION,
                input_schema="mms://schemas/cap.vla.action_chunk.request.v1",
                output_schema="mms://schemas/cap.vla.action_chunk.result.v1",
                supports_cancel=True,
                freshness={"expects_fresh_observation": True},
                replay={"supported": False},
                metadata={
                    "backend": "minivla",
                    "adapter": "openvla-mini",
                    "model_path": self.model_path,
                    "device": self.device,
                    "dtype": self.dtype,
                    "unnorm_key": self.unnorm_key,
                    "requires_gpu": self.device == "cuda",
                    "base_model": self.model_path == MINIVLA_BASE_MODEL,
                    **self._adapter_metadata(),
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
            metadata=self._response_metadata(),
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
        except (
            MiniVLADependencyError,
            MiniVLAInvalidOutputError,
            ValidationError,
            ValueError,
        ) as exc:
            return response(
                request.id,
                ProtocolStatus.INVALID_OUTPUT,
                session_id=session.id,
                error=error("invalid_minivla_output", str(exc), retryable=False),
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
    ) -> MiniVLACallInput | ResponseEnvelope:
        instruction = payload.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            return self._invalid_request(
                request_id, "missing_instruction", "MiniVLA requests require instruction"
            )

        observation = payload.get("observation")
        if not isinstance(observation, dict):
            return self._invalid_request(
                request_id, "missing_observation", "MiniVLA requests require observation"
            )

        state = observation.get("state")
        if not _is_number_sequence(state):
            return self._invalid_request(
                request_id, "invalid_state", "MiniVLA observation.state must be a numeric array"
            )

        images = observation.get("images")
        if not isinstance(images, dict):
            return self._invalid_request(
                request_id, "missing_images", "MiniVLA observation.images is required"
            )

        resolved_images: dict[str, Any] = dict(images)
        resolved_refs: dict[str, str] = {}
        for image_name in self._required_image_names():
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

        return MiniVLACallInput(instruction=instruction.strip(), observation=resolved_observation)

    def _resolve_image_input(
        self, image_name: str, image_ref: Any, request_id: str
    ) -> dict[str, Any] | ResponseEnvelope:
        if not isinstance(image_ref, dict):
            return self._invalid_request(
                request_id,
                "missing_image",
                f"MiniVLA observation.images.{image_name} must be an object",
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
                    "MiniVLA image refs require a configured frame store",
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
            f"MiniVLA observation.images.{image_name}.path or .ref is required",
            details={"image": image_name},
        )

    def _format_prediction(self, prediction: MiniVLAPrediction) -> dict[str, Any]:
        if prediction.chunk_length <= 0 or prediction.action_dim <= 0:
            raise MiniVLAInvalidOutputError("MiniVLA returned an empty action chunk")

        actions = []
        for values in prediction.actions:
            if not values:
                raise MiniVLAInvalidOutputError("MiniVLA returned an action with no values")
            if not all(math.isfinite(value) for value in values):
                raise MiniVLAInvalidOutputError("MiniVLA returned a non-finite action value")
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

    def _response_metadata(self, prediction: MiniVLAPrediction | None = None) -> dict[str, Any]:
        metadata = {
            "backend": "minivla",
            "adapter": "openvla-mini",
            "model_path": self.model_path,
            "device": self.device,
            "dtype": self.dtype,
            "unnorm_key": self.unnorm_key,
            "base_model": self.model_path == MINIVLA_BASE_MODEL,
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
            metadata={"backend": "minivla", "adapter": "openvla-mini"},
        )

    @property
    def adapter(self) -> MiniVLAAdapter:
        if self._adapter is None:
            self._adapter = OpenVLAMiniAdapter(
                model_path=self.model_path,
                device=self.device,
                profile=self.profile,
                unnorm_key=self.unnorm_key,
                dtype=self.dtype,
            )
        return self._adapter

    def _adapter_metadata(self) -> dict[str, Any]:
        if self._adapter is not None:
            return self._adapter.metadata
        return {
            "required_images": list(self._required_image_names()),
            "state_key": self.profile.state_key,
            "prompt_template": self.profile.prompt_template,
            "lazy_load": True,
        }

    def _required_image_names(self) -> tuple[str, ...]:
        if self._adapter is not None:
            return self._adapter.required_image_names
        if self.profile.image_map:
            return tuple(self.profile.image_map.keys())
        if self.profile.image_order:
            return tuple(self.profile.image_order)
        return ("camera1",)


class OpenVLAMiniAdapter:
    def __init__(
        self,
        *,
        model_path: str,
        device: str,
        profile: MiniVLAProfile,
        unnorm_key: str,
        dtype: str,
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.profile = profile
        self.unnorm_key = unnorm_key
        self.dtype = dtype
        self._torch = self._import_torch()
        if device == "cuda" and not self._torch.cuda.is_available():
            raise MiniVLADependencyError("MMS_MINIVLA_DEVICE=cuda requires a CUDA-capable torch")
        transformers = self._import_transformers()
        self.processor = transformers.AutoProcessor.from_pretrained(
            model_path, trust_remote_code=True
        )
        model_cls = self._resolve_model_class(transformers)
        self.model = model_cls.from_pretrained(
            model_path,
            torch_dtype=self._resolve_dtype(),
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        if hasattr(self.model, "to"):
            self.model.to(device)
        if hasattr(self.model, "eval"):
            self.model.eval()
        self.image_map = self._resolve_image_map()

    @property
    def required_image_names(self) -> tuple[str, ...]:
        return tuple(self.image_map.keys())

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "required_images": list(self.required_image_names),
            "state_key": self.profile.state_key,
            "prompt_template": self.profile.prompt_template,
        }

    def predict_action_chunk(self, call: MiniVLACallInput) -> MiniVLAPrediction:
        prompt = self.profile.prompt_template.format(instruction=call.instruction)
        images = self._load_images(call)
        raw_output = self._predict_with_model_methods(call, images, prompt)
        if raw_output is None:
            raw_output = self._predict_with_generation(images, prompt)
        rows = _model_output_to_action_rows(raw_output, self.profile.action_key)
        if not rows:
            raise MiniVLAInvalidOutputError("MiniVLA produced no action rows")
        return MiniVLAPrediction(
            actions=rows,
            action_dim=len(rows[0]),
            chunk_length=len(rows),
            metadata={},
        )

    def _predict_with_model_methods(
        self, call: MiniVLACallInput, images: list[Any], prompt: str
    ) -> Any | None:
        batch = self._build_raw_batch(call, images, prompt)
        for method_name in ("predict_action_chunk", "predict_action"):
            method = getattr(self.model, method_name, None)
            if not callable(method):
                continue
            attempts = (
                lambda method=method: method(batch, unnorm_key=self.unnorm_key or None),
                lambda method=method: method(batch),
                lambda method=method: method(images, prompt, unnorm_key=self.unnorm_key or None),
                lambda method=method: method(
                    prompt, images=images, unnorm_key=self.unnorm_key or None
                ),
            )
            for attempt in attempts:
                try:
                    return attempt()
                except TypeError:
                    continue
        return None

    def _predict_with_generation(self, images: list[Any], prompt: str) -> Any:
        image_input: Any = images if len(images) != 1 else images[0]
        try:
            encoded = self.processor(
                text=prompt,
                images=image_input,
                return_tensors="pt",
            )
        except TypeError:
            encoded = self.processor(prompt, image_input, return_tensors="pt")
        encoded = self._move_tensors_to_device(encoded)
        with self._torch.inference_mode():
            generated = self.model.generate(**encoded, max_new_tokens=256)
        if hasattr(self.processor, "batch_decode"):
            return self.processor.batch_decode(generated, skip_special_tokens=True)[0]
        tokenizer = getattr(self.processor, "tokenizer", None)
        if tokenizer is not None and hasattr(tokenizer, "decode"):
            return tokenizer.decode(generated[0], skip_special_tokens=True)
        return generated

    def _build_raw_batch(
        self, call: MiniVLACallInput, images: list[Any], prompt: str
    ) -> dict[str, Any]:
        observation = call.observation
        batch: dict[str, Any] = {
            self.profile.state_key: self._torch.tensor(
                [observation["state"]], dtype=self._torch.float32, device=self.device
            ),
            self.profile.task_key: [prompt],
            "images": images,
        }
        robot_type = observation.get("robot_type")
        if isinstance(robot_type, str):
            batch[self.profile.robot_type_key] = [robot_type]
        return batch

    def _load_images(self, call: MiniVLACallInput) -> list[Any]:
        try:
            image_module = import_module("PIL.Image")
        except ImportError as exc:
            raise MiniVLADependencyError("MiniVLA image loading requires Pillow") from exc

        images = call.observation["images"]
        loaded = []
        for request_key in self.required_image_names:
            loaded.append(image_module.open(images[request_key]["path"]).convert("RGB"))
        return loaded

    def _move_tensors_to_device(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: item.to(self.device) if hasattr(item, "to") else item
                for key, item in value.items()
            }
        return value.to(self.device) if hasattr(value, "to") else value

    def _resolve_image_map(self) -> dict[str, str]:
        if self.profile.image_map:
            return self.profile.image_map
        if self.profile.image_order:
            return {name: name for name in self.profile.image_order}
        return {"camera1": "camera1"}

    def _resolve_dtype(self) -> Any:
        if self.dtype in {"auto", ""}:
            return "auto"
        dtype = getattr(self._torch, self.dtype, None)
        if dtype is None:
            raise MiniVLADependencyError(f"Unsupported MMS_MINIVLA_DTYPE={self.dtype!r}")
        return dtype

    def _resolve_model_class(self, transformers: Any) -> Any:
        for name in ("AutoModelForVision2Seq", "AutoModelForCausalLM", "AutoModel"):
            model_cls = getattr(transformers, name, None)
            if model_cls is not None:
                return model_cls
        raise MiniVLADependencyError("transformers does not expose a supported AutoModel class")

    def _import_torch(self) -> Any:
        try:
            return import_module("torch")
        except ImportError as exc:
            raise MiniVLADependencyError(
                "Install the optional minivla extra to enable the MiniVLA backend"
            ) from exc

    def _import_transformers(self) -> Any:
        try:
            return import_module("transformers")
        except ImportError as exc:
            raise MiniVLADependencyError(
                "Install the optional minivla extra to enable the MiniVLA backend"
            ) from exc


def _is_number_sequence(value: Any) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, str | bytes)
        and all(isinstance(item, int | float) and math.isfinite(float(item)) for item in value)
    )


def _model_output_to_action_rows(value: Any, action_key: str) -> list[list[float]]:
    if hasattr(value, "detach"):
        value = value.detach().cpu().tolist()
    if isinstance(value, str):
        value = _parse_text_action_output(value)
    if isinstance(value, Mapping):
        for key in (action_key, "actions", "action", "action_chunk"):
            if key in value:
                return _model_output_to_action_rows(value[key], action_key)
        raise MiniVLAInvalidOutputError("MiniVLA action output has no action field")
    if not isinstance(value, list):
        raise MiniVLAInvalidOutputError("MiniVLA action output is not an array")
    while value and isinstance(value[0], list) and len(value) == 1:
        value = value[0]
    if not value:
        return []
    if all(isinstance(item, int | float) for item in value):
        return [[float(item) for item in value]]
    rows = []
    for row in value:
        if not isinstance(row, list) or not all(isinstance(item, int | float) for item in row):
            raise MiniVLAInvalidOutputError("MiniVLA action output has an unsupported shape")
        rows.append([float(item) for item in row])
    return rows


def _parse_text_action_output(value: str) -> Any:
    text = value.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\[\s*(?:[-+0-9.eE,\s\[\]]+)\])", text)
    if match is None:
        raise MiniVLAInvalidOutputError("MiniVLA text output did not contain an action array")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise MiniVLAInvalidOutputError("MiniVLA text action array is invalid JSON") from exc
