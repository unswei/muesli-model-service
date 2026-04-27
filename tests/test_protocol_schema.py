import pytest
from pydantic import ValidationError

from muesli_model_service.protocol.envelope import Operation, RequestEnvelope, ResponseEnvelope
from muesli_model_service.protocol.errors import ErrorObject
from muesli_model_service.protocol.statuses import ProtocolStatus


def test_valid_request_envelope_parses() -> None:
    request = RequestEnvelope.model_validate(
        {
            "version": "0.1",
            "id": "req-1",
            "op": "invoke",
            "payload": {"capability": "x", "method": "y"},
        }
    )

    assert request.op == Operation.INVOKE
    assert request.id == "req-1"


def test_invalid_operation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RequestEnvelope.model_validate(
            {"version": "0.1", "id": "req-1", "op": "bad", "payload": {}}
        )


def test_missing_request_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RequestEnvelope.model_validate({"version": "0.1", "op": "describe", "payload": {}})


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ResponseEnvelope.model_validate(
            {"version": "0.1", "id": "req-1", "status": "weird", "payload": {}}
        )


def test_response_envelope_echoes_request_id() -> None:
    request = RequestEnvelope(id="req-1", op=Operation.DESCRIBE)
    response = ResponseEnvelope(id=request.id, status=ProtocolStatus.SUCCESS)

    assert response.id == request.id


def test_error_response_requires_code_message_retryable() -> None:
    response = ResponseEnvelope(
        id="req-1",
        status=ProtocolStatus.INVALID_REQUEST,
        error=ErrorObject(code="invalid", message="bad request", retryable=False),
    )

    assert response.error is not None
    assert response.error.code == "invalid"
    assert response.error.retryable is False
