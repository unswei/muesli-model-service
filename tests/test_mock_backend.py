from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.dispatcher import Dispatcher


async def test_mock_action_chunker_returns_deterministic_outputs(dispatcher: Dispatcher) -> None:
    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            capability="cap.vla.action_chunk.v1",
            input={},
        )
    )

    first = await dispatcher.dispatch(
        RequestEnvelope(id="step-1", op=Operation.STEP, session_id=start.session_id)
    )
    second = await dispatcher.dispatch(
        RequestEnvelope(id="step-2", op=Operation.STEP, session_id=start.session_id)
    )
    third = await dispatcher.dispatch(
        RequestEnvelope(id="step-3", op=Operation.STEP, session_id=start.session_id)
    )

    assert first.status == ProtocolStatus.ACTION_CHUNK
    assert first.output["actions"][0]["values"] == [0.10, 0.40, -0.20]
    assert second.output["actions"][0]["type"] == "gripper"
    assert third.status == ProtocolStatus.SUCCESS


async def test_mock_world_model_returns_deterministic_rollout(dispatcher: Dispatcher) -> None:
    result = await dispatcher.dispatch(
        RequestEnvelope(
            id="rollout",
            op=Operation.INVOKE,
            capability="cap.model.world.rollout.v1",
            input={
                "state": {"vector": [0.0, 1.0]},
                "actions": [{"type": "joint_targets", "values": [0.1, 0.3], "dt_ms": 20}],
                "horizon": 1,
            },
        )
    )

    assert result.status == ProtocolStatus.SUCCESS
    assert result.output["predicted_states"] == [{"vector": [0.2, 1.2]}]


async def test_mock_scoring_returns_deterministic_scalar(dispatcher: Dispatcher) -> None:
    result = await dispatcher.dispatch(
        RequestEnvelope(
            id="score",
            op=Operation.INVOKE,
            capability="cap.model.world.score_trajectory.v1",
            input={"trajectory": [{"vector": [0.2, 0.3]}]},
        )
    )

    assert result.status == ProtocolStatus.SUCCESS
    assert result.output["score"] == 0.666667


async def test_mock_nav_goal_returns_public_capability_metadata(dispatcher: Dispatcher) -> None:
    result = await dispatcher.dispatch(
        RequestEnvelope(
            id="nav-goal",
            op=Operation.INVOKE,
            capability="cap.vla.propose_nav_goal.v1",
            input={"goal_hint": {"x": 2.0, "y": 3.0, "theta": 0.5}},
        )
    )

    assert result.status == ProtocolStatus.SUCCESS
    assert result.output["goal"]["x"] == 2.0
    assert result.metadata["capability"] == "cap.vla.propose_nav_goal.v1"
    assert result.metadata["backend"] == "mock-nav-goal"
