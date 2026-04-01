from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterBoxRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)


class RegisterBoxResponse(BaseModel):
    secret_key: str


class ValidateBoxRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    secret_key: str = Field(..., min_length=1, max_length=255)


class ValidateBoxResponse(BaseModel):
    token: str
    expiresAt: str | None = None


class MessageUploadResponse(BaseModel):
    """Legacy shape: empty object on success (matches previous Java client)."""

    uuid: str | None = None
    fileName: str | None = None
    fileType: str | None = None
    size: int | None = None


class MessageUploadBase64Request(BaseModel):
    data_base64: str = Field(..., min_length=1, description="Base64-encoded raw file bytes")
    filename: str | None = Field(default=None, description="Optional filename to store")
    content_type: str | None = Field(default=None, description="Optional MIME type to store")


class MessageUploadTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Plain UTF-8 text body")
    filename: str | None = Field(default=None, description="Optional filename (default message.txt)")


class MessageReadBase64Response(BaseModel):
    fileType: str | None = None
    fileName: str | None = None
    messageUuid: str | None = None
    data_base64: str


class MessageReadTextResponse(BaseModel):
    """Latest queue message when it is text/* (peek; same semantics as read_base64)."""

    fileType: str | None = None
    fileName: str | None = None
    messageUuid: str | None = None
    text: str


class MessageAckRequest(BaseModel):
    messageUuid: str = Field(..., min_length=1)
    leaseId: str | None = Field(default=None, min_length=1)


class MessageLeaseResponse(BaseModel):
    messageUuid: str
    leaseId: str
    leaseExpiresAt: str
    fileType: str | None = None
    fileName: str | None = None
    data_base64: str | None = None
    text: str | None = None
