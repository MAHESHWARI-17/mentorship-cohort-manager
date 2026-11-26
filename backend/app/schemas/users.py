from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.schemas.identity_validation import validate_employee_id_format, validate_mphasis_email_format

class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str  # "admin" | "nominator" | "mentor"
    isActive: bool = True

class UserCreate(UserBase):
    password: str

class UserCreateWithTempPassword(BaseModel):
    """Used by admin to create users with temporary passwords"""
    name: str
    email: EmailStr
    employeeId: str = Field(min_length=1, max_length=64)
    role: str  # "nominator" | "mentor" | "trainee"
    location: Optional[str] = None
    timezone: Optional[str] = None
    createdBy: str  # admin user id

    @field_validator("email")
    @classmethod
    def validate_corporate_email(cls, value):
        return validate_mphasis_email_format(value)

    @field_validator("employeeId")
    @classmethod
    def validate_employee_id(cls, value):
        return validate_employee_id_format(value)

class NominatorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    employeeId: str = Field(min_length=1, max_length=64)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_corporate_email(cls, value):
        return validate_mphasis_email_format(value)

    @field_validator("employeeId")
    @classmethod
    def validate_employee_id(cls, value):
        return validate_employee_id_format(value)

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    employeeId: Optional[str] = None
    isActive: bool
    createdAt: datetime
    firstLoginPasswordReset: bool = False

class ActivateMentorLoginRequest(BaseModel):
    password: str

class ResetPasswordRequest(BaseModel):
    """First login password reset"""
    email: Optional[EmailStr] = None
    tempPassword: str
    newPassword: str
    confirmPassword: str

class ChangePasswordRequest(BaseModel):
    """Subsequent password changes"""
    currentPassword: str
    newPassword: str
    confirmPassword: str

class FirstLoginResponse(BaseModel):
    requiresPasswordReset: bool
    message: str
