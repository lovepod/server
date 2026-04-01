from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.exceptions import BadRequestError
from app.deps import get_box_service, get_message_service
from app.main import app


@contextmanager
def override_dependencies(overrides: dict | None = None):
    original = app.dependency_overrides.copy()
    app.dependency_overrides.update(overrides or {})
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides = original


def test_heartbeat_endpoint_returns_expected_value() -> None:
    with override_dependencies() as client:
        response = client.get("/api/v1/monitoring/heartbeat")

    assert response.status_code == 200
    assert response.json() == "Hearts Still Beating"
    assert "x-request-id" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_register_box_route_delegates_to_service() -> None:
    service = SimpleNamespace(register=lambda body: SimpleNamespace(secret_key="AB12CD34"))

    with override_dependencies({get_box_service: lambda: service}) as client:
        response = client.post("/api/v1/box/register", json={"email": "test@example.com", "name": "Bedroom"})

    assert response.status_code == 200
    assert response.json() == {"secret_key": "AB12CD34"}


def test_validate_box_route_delegates_to_service() -> None:
    service = SimpleNamespace(validate=lambda body: SimpleNamespace(token="upload-token", expiresAt="2030-01-01T00:00:00+00:00"))

    with override_dependencies({get_box_service: lambda: service}) as client:
        response = client.post("/api/v1/box/validate", json={"secret_key": "AB12CD34"})

    assert response.status_code == 200
    assert response.json() == {"token": "upload-token", "expiresAt": "2030-01-01T00:00:00+00:00"}


def test_upload_route_passes_header_and_file_to_service() -> None:
    captured = {}

    def upload(*, api_token, raw, filename, content_type):
        captured.update(
            api_token=api_token,
            raw=raw,
            filename=filename,
            content_type=content_type,
        )
        return SimpleNamespace(uuid=None, fileName=None, fileType=None, size=None)

    service = SimpleNamespace(upload=upload)

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.post(
            "/api/v1/message/upload",
            headers={"x-api-key": "token-1"},
            files={"file": ("hello.txt", BytesIO(b"hello"), "text/plain")},
        )

    assert response.status_code == 200
    assert response.json() == {}
    assert captured == {
        "api_token": "token-1",
        "raw": b"hello",
        "filename": "hello.txt",
        "content_type": "text/plain",
    }


def test_upload_base64_route_delegates_to_service() -> None:
    captured = {}

    def upload_base64(*, api_token, data_base64, filename, content_type):
        captured.update(
            api_token=api_token,
            data_base64=data_base64,
            filename=filename,
            content_type=content_type,
        )
        return SimpleNamespace(uuid=None, fileName=None, fileType=None, size=None)

    service = SimpleNamespace(upload_base64=upload_base64)

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.post(
            "/api/v1/message/upload_base64",
            headers={"x-api-key": "token-2"},
            json={"data_base64": "aGVsbG8=", "filename": "hello.txt", "content_type": "text/plain"},
        )

    assert response.status_code == 200
    assert response.json() == {}
    assert captured["api_token"] == "token-2"
    assert captured["data_base64"] == "aGVsbG8="


def test_upload_text_route_delegates_to_service() -> None:
    captured = {}

    def upload_text(*, api_token, text, filename):
        captured.update(api_token=api_token, text=text, filename=filename)
        return SimpleNamespace(uuid=None, fileName=None, fileType=None, size=None)

    service = SimpleNamespace(upload_text=upload_text)

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.post(
            "/api/v1/message/upload_text",
            headers={"x-api-key": "token-3"},
            json={"text": "Volim te", "filename": "message.txt"},
        )

    assert response.status_code == 200
    assert response.json() == {}
    assert captured == {"api_token": "token-3", "text": "Volim te", "filename": "message.txt"}


def test_read_route_returns_raw_response() -> None:
    service = SimpleNamespace(read_latest_blob=lambda secret_key: (b"binary", "image/png"))

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.get("/api/v1/message/read", headers={"secret-key": "AB12CD34"})

    assert response.status_code == 200
    assert response.content == b"binary"
    assert response.headers["content-type"].startswith("image/png")


def test_lease_route_returns_unified_payload() -> None:
    service = SimpleNamespace(
        lease_next_message=lambda secret_key: (
            "msg-lease",
            "lease-1",
            "2030-01-01T00:00:00+00:00",
            "text/plain",
            "message.txt",
            None,
            "Volim te",
        )
    )

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.get("/api/v1/message/lease", headers={"secret-key": "AB12CD34"})

    assert response.status_code == 200
    assert response.json() == {
        "messageUuid": "msg-lease",
        "leaseId": "lease-1",
        "leaseExpiresAt": "2030-01-01T00:00:00+00:00",
        "fileType": "text/plain",
        "fileName": "message.txt",
        "text": "Volim te",
    }


def test_read_text_route_returns_text_payload() -> None:
    service = SimpleNamespace(
        read_latest_text_message=lambda secret_key: ("text/plain", "Volim te", "message.txt", "msg-1")
    )

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.get("/api/v1/message/read_text", headers={"secret-key": "AB12CD34"})

    assert response.status_code == 200
    assert response.json() == {
        "fileType": "text/plain",
        "fileName": "message.txt",
        "messageUuid": "msg-1",
        "text": "Volim te",
    }


def test_read_base64_route_returns_payload() -> None:
    service = SimpleNamespace(read_latest_blob_base64=lambda secret_key: ("image/png", "aGVsbG8=", "x.png", "msg-2"))

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.get("/api/v1/message/read_base64", headers={"secret-key": "AB12CD34"})

    assert response.status_code == 200
    assert response.json()["messageUuid"] == "msg-2"


def test_consume_base64_route_returns_payload() -> None:
    service = SimpleNamespace(
        consume_latest_blob_base64=lambda secret_key: ("image/png", "aGVsbG8=", "x.png", "msg-3")
    )

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.get("/api/v1/message/consume_base64", headers={"secret-key": "AB12CD34"})

    assert response.status_code == 200
    assert response.json()["messageUuid"] == "msg-3"


def test_ack_route_returns_ok() -> None:
    captured = {}

    def acknowledge_message(*, secret_key, message_uuid, lease_id=None):
        captured.update(secret_key=secret_key, message_uuid=message_uuid, lease_id=lease_id)

    service = SimpleNamespace(acknowledge_message=acknowledge_message)

    with override_dependencies({get_message_service: lambda: service}) as client:
        response = client.post(
            "/api/v1/message/ack",
            headers={"secret-key": "AB12CD34"},
            json={"messageUuid": "msg-4", "leaseId": "lease-4"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured == {"secret_key": "AB12CD34", "message_uuid": "msg-4", "lease_id": "lease-4"}


def test_app_error_handler_returns_domain_error_shape() -> None:
    service = SimpleNamespace(register=lambda body: (_ for _ in ()).throw(BadRequestError("Nope")))

    with override_dependencies({get_box_service: lambda: service}) as client:
        response = client.post("/api/v1/box/register", json={"email": "test@example.com", "name": "Bedroom"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Nope"}


def test_live_ready_and_metrics_endpoints_work() -> None:
    with override_dependencies() as client:
        live = client.get("/api/v1/monitoring/live")
        ready = client.get("/api/v1/monitoring/ready")
        metrics = client.get("/api/v1/monitoring/metrics")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    assert metrics.status_code == 200
    assert "requests_total" in metrics.json()
