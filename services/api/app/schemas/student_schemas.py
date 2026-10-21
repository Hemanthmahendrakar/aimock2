from pydantic import BaseModel, EmailStr, Field


class CreateStudentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    roll_number: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=128)
    batch: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    campus_id: str | None = None
    course: str | None = Field(default=None, max_length=180)
    graduation_year: int | None = Field(default=None, ge=1950, le=2200)
    experience_level: str | None = Field(default=None, max_length=64)


class UpdateStudentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    roll_number: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=128)
    batch: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    status: str | None = None
    campus_id: str | None = None
    course: str | None = Field(default=None, max_length=180)
    graduation_year: int | None = Field(default=None, ge=1950, le=2200)
    experience_level: str | None = Field(default=None, max_length=64)
