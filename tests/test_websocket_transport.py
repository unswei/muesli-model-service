from fastapi.testclient import TestClient

from muesli_model_service.app import create_app
from muesli_model_service.config import Settings


def test_websocket_describe_start_step_until_success_and_cancel() -> None:
    client = TestClient(create_app(Settings()))
    with client.websocket_connect("/v1/ws") as websocket:
        websocket.send_json({"version": "0.1", "id": "describe", "op": "describe", "payload": {}})
        describe = websocket.receive_json()
        assert describe["status"] == "success"

        websocket.send_json(
            {
                "version": "0.1",
                "id": "start",
                "op": "start",
                "payload": {"capability": "mock-action-chunker", "method": "act", "input": {}},
            }
        )
        start = websocket.receive_json()
        session = start["payload"]["session"]

        statuses = []
        for index in range(3):
            websocket.send_json(
                {
                    "version": "0.1",
                    "id": f"step-{index}",
                    "op": "step",
                    "payload": {"session": session},
                }
            )
            statuses.append(websocket.receive_json()["status"])

        assert statuses == ["action_chunk", "action_chunk", "success"]

        websocket.send_json(
            {
                "version": "0.1",
                "id": "start-cancel",
                "op": "start",
                "payload": {"capability": "mock-action-chunker", "method": "act", "input": {}},
            }
        )
        cancel_session = websocket.receive_json()["payload"]["session"]
        websocket.send_json(
            {
                "version": "0.1",
                "id": "cancel",
                "op": "cancel",
                "payload": {"session": cancel_session},
            }
        )
        assert websocket.receive_json()["status"] == "cancelled"


def test_websocket_invalid_json_returns_invalid_request() -> None:
    client = TestClient(create_app(Settings()))
    with client.websocket_connect("/v1/ws") as websocket:
        websocket.send_text("{")
        response = websocket.receive_json()

    assert response["status"] == "invalid_request"
    assert response["error"]["code"] == "invalid_json"
