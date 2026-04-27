from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.runtime.dispatcher import Dispatcher


async def test_session_lifecycle(dispatcher: Dispatcher) -> None:
    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            payload={"capability": "mock-action-chunker", "method": "act", "input": {}},
        )
    )
    session = start.payload["session"]

    step = await dispatcher.dispatch(
        RequestEnvelope(id="step", op=Operation.STEP, payload={"session": session})
    )
    status = await dispatcher.dispatch(
        RequestEnvelope(id="status", op=Operation.STATUS, payload={"session": session})
    )
    close = await dispatcher.dispatch(
        RequestEnvelope(id="close", op=Operation.CLOSE, payload={"session": session})
    )
    unknown = await dispatcher.dispatch(
        RequestEnvelope(id="unknown", op=Operation.STATUS, payload={"session": session})
    )

    assert start.status == ProtocolStatus.RUNNING
    assert step.status == ProtocolStatus.ACTION_CHUNK
    assert status.payload["session"] == session
    assert close.status == ProtocolStatus.SUCCESS
    assert unknown.status == ProtocolStatus.INVALID_REQUEST


async def test_cancel_cancels_session(dispatcher: Dispatcher) -> None:
    start = await dispatcher.dispatch(
        RequestEnvelope(
            id="start",
            op=Operation.START,
            payload={"capability": "mock-action-chunker", "method": "act", "input": {}},
        )
    )

    cancel = await dispatcher.dispatch(
        RequestEnvelope(
            id="cancel", op=Operation.CANCEL, payload={"session": start.payload["session"]}
        )
    )

    assert cancel.status == ProtocolStatus.CANCELLED


async def test_unknown_session_returns_invalid_request(dispatcher: Dispatcher) -> None:
    result = await dispatcher.dispatch(
        RequestEnvelope(id="missing", op=Operation.STATUS, payload={"session": "sess-missing"})
    )

    assert result.status == ProtocolStatus.INVALID_REQUEST
    assert result.error is not None
    assert result.error.code == "session_not_found"
