from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class MeOrganization(BaseModel):
    id: str
    name: str
    role: str


class MeResponse(BaseModel):
    id: str
    email: str
    has_profile: bool
    organizations: list[MeOrganization]


class MessageResponse(BaseModel):
    message: str
