import json
from pathlib import Path

from muesli_model_service.backends.replay import ReplayBackend, load_replay_fixtures
from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.dispatcher import Dispatcher
from muesli_model_service.runtime.registry import CapabilityRegistry
from muesli_model_service.runtime.sessions import SessionManager


def write_replay(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "capability": "cap.vla.action_chunk.v1",
                "mode": "session",
                "steps": [
                    {
                        "status": "action_chunk",
                        "output": {
                            "actions": [
                                {"type": "joint_targets", "values": [0.1, 0.2], "dt_ms": 20}
                            ]
                        },
                    },
                    {"status": "success", "output": {"message": "replay complete"}},
                ],
            }
        )
    )


def make_replay_dispatcher(path: Path) -> Dispatcher:
    sessions = SessionManager()
    registry = CapabilityRegistry()
    registry.register("replay", ReplayBackend(sessions, load_replay_fixtures(path)))
    return Dispatcher(registry)


async def test_valid_replay_files_load(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    write_replay(path)

    fixtures = load_replay_fixtures(path)

    assert fixtures[0].capability == "cap.vla.action_chunk.v1"


async def test_replay_capability_appears_in_describe(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    write_replay(path)
    dispatcher = make_replay_dispatcher(path)

    result = await dispatcher.dispatch(RequestEnvelope(id="describe", op=Operation.DESCRIBE))

    ids = {item["id"] for item in result.output["capabilities"]}
    assert "cap.vla.action_chunk.v1" in ids


async def test_session_steps_return_replayed_outputs(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    write_replay(path)
    dispatcher = make_replay_dispatcher(path)

    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input={},
        )
    )
    step = await dispatcher.dispatch(
        RequestEnvelope(id="step", op=Operation.STEP, session_id=start.session_id)
    )

    assert step.status == ProtocolStatus.ACTION_CHUNK
    assert step.output["actions"][0]["values"] == [0.1, 0.2]


async def test_replay_exhaustion_is_handled_clearly(tmp_path: Path) -> None:
    path = tmp_path / "replay.json"
    write_replay(path)
    dispatcher = make_replay_dispatcher(path)
    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input={},
        )
    )

    for index in range(3):
        result = await dispatcher.dispatch(
            RequestEnvelope(id=f"step-{index}", op=Operation.STEP, session_id=start.session_id)
        )

    assert result.status == ProtocolStatus.FAILURE
    assert result.error is not None
    assert result.error.code == "replay_exhausted"
