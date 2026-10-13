"""
Pydantic request/response schemas for the auth routes. Validating here
keeps route handlers thin and gives consistent 400 errors on bad input.
"""
import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_MIN_LENGTH = 10


def _validate_password_strength(password: str) -> str:
    if len(password) < _PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {_PASSWORD_MIN_LENGTH} characters.")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one digit.")
    return password


class RegisterInstituteRequest(BaseModel):
    institute_name: str = Field(min_length=2, max_length=255)
    institute_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=255)
    admin_email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
