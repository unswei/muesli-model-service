from fastapi.testclient import TestClient

from muesli_model_service.app import create_app
from muesli_model_service.config import Settings


def test_put_frame_stores_frame_and_returns_refs(tmp_path) -> None:
    app = create_app(Settings(frame_store_root=str(tmp_path / "frames")))
    client = TestClient(app)

    response = client.put(
        "/v1/frames/camera1",
        content=b"fake-jpeg-bytes",
        headers={
            "content-type": "image/jpeg",
            "x-mms-timestamp-ns": "123456789",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ref"] == "frame://camera1/123456789"
    assert payload["latest_ref"] == "frame://camera1/latest"
    assert payload["media_type"] == "image/jpeg"
    assert payload["encoding"] == "jpeg"
    assert payload["size_bytes"] == len(b"fake-jpeg-bytes")

    frame_store = app.state.frame_store
    latest = frame_store.resolve("frame://camera1/latest")
    assert latest.ref == "frame://camera1/123456789"
    assert latest.path.exists()


def test_put_frame_rejects_empty_content(tmp_path) -> None:
    client = TestClient(create_app(Settings(frame_store_root=str(tmp_path / "frames"))))

    response = client.put(
        "/v1/frames/camera1",
        content=b"",
        headers={"content-type": "image/jpeg"},
    )

    assert response.status_code == 400
    assert "must not be empty" in response.json()["detail"]


def test_put_frame_rejects_unsafe_name(tmp_path) -> None:
    client = TestClient(create_app(Settings(frame_store_root=str(tmp_path / "frames"))))

    response = client.put(
        "/v1/frames/../camera1",
        content=b"fake",
        headers={"content-type": "image/jpeg"},
    )

    assert response.status_code in {400, 404}
