from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    phone: str
    password: str = Field(min_length=8)
    terms_accepted: bool
    terms_version: str = "2026-09-01"


class UserLogin(BaseModel):
    phone: str
    password: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    phone: str | None
    is_active: bool
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
