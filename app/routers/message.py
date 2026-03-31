from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response

from app.deps import get_message_service
from app.schemas import (
    MessageAckRequest,
    MessageReadBase64Response,
    MessageUploadBase64Request,
    MessageUploadResponse,
)
from app.services.message_service import MessageService

router = APIRouter(prefix="/v1/message", tags=["message"])


@router.post("/upload", response_model=MessageUploadResponse, response_model_exclude_none=True)
async def upload_message(
    service: MessageService = Depends(get_message_service),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    file: UploadFile = File(...),
) -> MessageUploadResponse:
    raw = await file.read()
    return service.upload(
        api_token=x_api_key,
        raw=raw,
        filename=file.filename,
        content_type=file.content_type,
    )


@router.post("/upload_base64", response_model=MessageUploadResponse, response_model_exclude_none=True)
async def upload_message_base64(
    body: MessageUploadBase64Request,
    service: MessageService = Depends(get_message_service),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> MessageUploadResponse:
    return service.upload_base64(
        api_token=x_api_key,
        data_base64=body.data_base64,
        filename=body.filename,
        content_type=body.content_type,
    )


@router.get("/read")
def read_message(
    service: MessageService = Depends(get_message_service),
    secret_key: str | None = Header(default=None, alias="secret-key"),
) -> Response:
    blob, file_type = service.read_latest_blob(secret_key)
    return Response(content=blob, media_type=file_type or "application/octet-stream")


@router.get("/read_base64", response_model=MessageReadBase64Response)
def read_message_base64(
    service: MessageService = Depends(get_message_service),
    secret_key: str | None = Header(default=None, alias="secret-key"),
) -> MessageReadBase64Response:
    file_type, data_base64, file_name, message_uuid = service.read_latest_blob_base64(secret_key)
    return MessageReadBase64Response(
        fileType=file_type,
        fileName=file_name,
        messageUuid=message_uuid,
        data_base64=data_base64,
    )


@router.get("/consume_base64", response_model=MessageReadBase64Response)
def consume_message_base64(
    service: MessageService = Depends(get_message_service),
    secret_key: str | None = Header(default=None, alias="secret-key"),
) -> MessageReadBase64Response:
    file_type, data_base64, file_name, message_uuid = service.consume_latest_blob_base64(secret_key)
    return MessageReadBase64Response(
        fileType=file_type,
        fileName=file_name,
        messageUuid=message_uuid,
        data_base64=data_base64,
    )


@router.post("/ack")
def acknowledge_message(
    body: MessageAckRequest,
    service: MessageService = Depends(get_message_service),
    secret_key: str | None = Header(default=None, alias="secret-key"),
) -> dict[str, bool]:
    service.acknowledge_message(secret_key=secret_key, message_uuid=body.messageUuid)
    return {"ok": True}
