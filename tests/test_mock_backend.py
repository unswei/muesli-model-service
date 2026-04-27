from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.dispatcher import Dispatcher


async def test_mock_action_chunker_returns_deterministic_outputs(dispatcher: Dispatcher) -> None:
    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            payload={"capability": "mock-action-chunker", "method": "act", "input": {}},
        )
    )

    first = await dispatcher.dispatch(
        RequestEnvelope(
            id="step-1", op=Operation.STEP, payload={"session": start.payload["session"]}
        )
    )
    second = await dispatcher.dispatch(
        RequestEnvelope(
            id="step-2", op=Operation.STEP, payload={"session": start.payload["session"]}
        )
    )
    third = await dispatcher.dispatch(
        RequestEnvelope(
            id="step-3", op=Operation.STEP, payload={"session": start.payload["session"]}
        )
    )

    assert first.status == ProtocolStatus.ACTION_CHUNK
    assert first.payload["output"]["actions"][0]["values"] == [0.10, 0.40, -0.20]
    assert second.payload["output"]["actions"][0]["type"] == "gripper"
    assert third.status == ProtocolStatus.SUCCESS


async def test_mock_world_model_returns_deterministic_rollout(dispatcher: Dispatcher) -> None:
    result = await dispatcher.dispatch(
        RequestEnvelope(
            id="rollout",
            op=Operation.INVOKE,
            payload={
                "capability": "mock-world-model",
                "method": "rollout",
                "input": {
                    "state": {"vector": [0.0, 1.0]},
                    "actions": [{"type": "joint_targets", "values": [0.1, 0.3], "dt_ms": 20}],
                    "horizon": 1,
                },
            },
        )
    )

    assert result.status == ProtocolStatus.SUCCESS
    assert result.payload["output"]["predicted_states"] == [{"vector": [0.2, 1.2]}]


async def test_mock_scoring_returns_deterministic_scalar(dispatcher: Dispatcher) -> None:
    result = await dispatcher.dispatch(
        RequestEnvelope(
            id="score",
            op=Operation.INVOKE,
            payload={
                "capability": "mock-world-model",
                "method": "score_trajectory",
                "input": {"trajectory": [{"vector": [0.2, 0.3]}]},
            },
        )
    )

    assert result.status == ProtocolStatus.SUCCESS
    assert result.payload["output"]["score"] == 0.666667
