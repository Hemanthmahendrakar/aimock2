"""
Pydantic schemas for institute profile/branding routes. All fields are
optional on update — PATCH semantics, only supplied fields change.
"""
import re

from pydantic import BaseModel, Field, field_validator

_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


class UpdateInstituteProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=255)

    @field_validator("website")
    @classmethod
    def website_looks_like_url(cls, v: str | None) -> str | None:
        if v and not re.match(r"^https?://", v):
            raise ValueError("Website must start with http:// or https://")
        return v


class UpdateBrandingRequest(BaseModel):
    primary_color: str | None = None
    secondary_color: str | None = None

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def valid_hex(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("Must be a hex color like #1F6F5C.")
        return v
