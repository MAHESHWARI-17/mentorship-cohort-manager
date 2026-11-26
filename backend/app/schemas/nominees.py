from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.schemas.identity_validation import validate_employee_id_format, validate_mphasis_email_format

class TraineeInMentor(BaseModel):
    id: str
    name: str
    email: EmailStr
    employeeId: Optional[str] = ""
    department: Optional[str] = ""
    percentComplete: Optional[float] = 0.0
    status: Optional[str] = None
    location: Optional[str] = None
    droppedOutAt: Optional[datetime] = None
    dropoutReason: Optional[str] = None

class MentorNomineeCreate(BaseModel):
    name: str
    email: EmailStr
    department: Optional[str] = ""
    employeeId: str = Field(min_length=1, max_length=64)
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = []

    @field_validator("email")
    @classmethod
    def validate_corporate_email(cls, value):
        return validate_mphasis_email_format(value)

    @field_validator("employeeId")
    @classmethod
    def validate_employee_id(cls, value):
        return validate_employee_id_format(value)

class CohortRef(BaseModel):
    id: str
    name: str
    status: Optional[str] = "active"

class MentorNomineeResponse(BaseModel):
    """Mentor as seen by admin / inside a cohort."""
    id: str
    cohortId: Optional[str] = None
    cohortIds: Optional[List[str]] = []
    cohortNames: Optional[List[str]] = []
    assignedCohorts: Optional[List[CohortRef]] = []
    nominatedBy: Optional[str] = "admin"
    nominatorName: Optional[str] = "Admin"
    name: str
    email: EmailStr
    department: Optional[str] = ""
    employeeId: Optional[str] = ""
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = []
    userId: Optional[str] = None
    isLoginActive: bool = False
    isAccountActive: bool = True
    isCohortAccessActive: bool = True
    isActive: bool = True
    status: Optional[str] = "pending"
    assignedTraineesCount: Optional[int] = 0
    assignedTrainees: Optional[List[TraineeInMentor]] = []
    createdAt: datetime

class MentorCohortsUpdateRequest(BaseModel):
    cohortIds: List[str]

class TraineeCohortUpdateRequest(BaseModel):
    cohortId: Optional[str] = None

class MentorAssignCohortsRequest(BaseModel):
    cohortIds: List[str]

class TraineeNomineeCreate(BaseModel):
    name: str
    email: EmailStr
    employeeId: str
    department: Optional[str] = ""
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = []

    @field_validator("email")
    @classmethod
    def validate_corporate_email(cls, value):
        return validate_mphasis_email_format(value)

    @field_validator("employeeId")
    @classmethod
    def validate_employee_id(cls, value):
        return validate_employee_id_format(value)

class TraineeNomineeResponse(BaseModel):
    """Trainee as seen by admin / inside a cohort."""
    id: str
    cohortId: Optional[str] = None
    nominatedBy: Optional[str] = "admin"
    nominatorName: Optional[str] = "Admin"
    name: str
    email: EmailStr
    employeeId: str
    department: Optional[str] = ""
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = []
    status: Optional[str] = "pending"
    droppedOutAt: Optional[datetime] = None
    droppedOutBy: Optional[str] = None
    dropoutReason: Optional[str] = None
    mentorId: Optional[str] = None
    mentorName: Optional[str] = None
    percentComplete: Optional[float] = 0.0
    createdAt: datetime

class MyNomineeResponse(BaseModel):
    """What a nominator sees about their own nominees. Deliberately has NO
    cohort, mentor or progress information."""
    id: str
    type: str  # "mentor" | "trainee"
    name: str
    email: EmailStr
    employeeId: Optional[str] = ""
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = []
    createdAt: datetime

class _NomineeUpdateBase(BaseModel):
    """Editable nominee profile fields. Only fields that are sent are changed.

    System fields (id, nominator, status, cohort/mentor assignment, createdAt)
    are deliberately absent: unknown keys in a request are ignored.
    """
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    employeeId: Optional[str] = Field(default=None, max_length=64)
    department: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience: Optional[str] = None
    skills: Optional[List[str]] = None

    @field_validator("name", "employeeId")
    @classmethod
    def _not_blank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def validate_corporate_email(cls, value):
        return validate_mphasis_email_format(value) if value is not None else value

    @field_validator("employeeId")
    @classmethod
    def validate_employee_id(cls, value):
        return validate_employee_id_format(value) if value is not None else value


class MentorNomineeUpdate(_NomineeUpdateBase):
    pass


class TraineeNomineeUpdate(_NomineeUpdateBase):
    pass


class AllocateRequest(BaseModel):
    ids: List[str]

class MentorAssignmentRequest(BaseModel):
    mentorId: str
