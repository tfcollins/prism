"""Auth request/response schemas."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    auth_provider: str = "local"
    is_admin: bool = False
