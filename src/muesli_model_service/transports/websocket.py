import json

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from muesli_model_service.protocol.envelope import ResponseEnvelope
from muesli_model_service.protocol.errors import error
from muesli_model_service.protocol.statuses import ProtocolStatus
from muesli_model_service.protocol.validation import parse_request
from muesli_model_service.runtime.dispatcher import Dispatcher


async def websocket_endpoint(websocket: WebSocket, dispatcher: Dispatcher) -> None:
    await websocket.accept()
    while True:
        try:
            raw_text = await websocket.receive_text()
        except WebSocketDisconnect:
            break
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            await websocket.send_text(
                ResponseEnvelope(
                    id="invalid-json",
                    status=ProtocolStatus.INVALID_REQUEST,
                    error=error(
                        "invalid_json", "Message is not valid JSON", details={"message": str(exc)}
                    ),
                ).model_dump_json()
            )
            continue
        parsed = parse_request(raw)
        if isinstance(parsed, ResponseEnvelope):
            await websocket.send_text(parsed.model_dump_json())
            continue
        try:
            response = await dispatcher.dispatch(parsed)
        except ValidationError as exc:
            response = ResponseEnvelope(
                id=parsed.id,
                status=ProtocolStatus.INVALID_REQUEST,
                error=error(
                    "invalid_request", "Request failed validation", details={"errors": exc.errors()}
                ),
            )
        await websocket.send_text(response.model_dump_json())
