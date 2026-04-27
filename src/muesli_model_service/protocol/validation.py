from typing import Any

from pydantic import ValidationError

from muesli_model_service.protocol.envelope import RequestEnvelope, ResponseEnvelope
from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus


def parse_request(
    raw: Any, *, fallback_id: str = "invalid-request"
) -> RequestEnvelope | ResponseEnvelope:
    try:
        return RequestEnvelope.model_validate(raw)
    except ValidationError as exc:
        request_id = raw.get("id", fallback_id) if isinstance(raw, dict) else fallback_id
        return ResponseEnvelope(
            id=str(request_id or fallback_id),
            status=ProtocolStatus.INVALID_REQUEST,
            error=error(
                "invalid_request",
                "Request envelope failed validation",
                details={"errors": exc.errors()},
            ),
        )
