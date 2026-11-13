from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from uuid import UUID
from app.database.models import AppointmentStatus, ConversationState, MessageDirection, UserRole

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True

# Doctor Schedule
class DoctorScheduleBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    is_active: bool = True

class DoctorScheduleCreate(DoctorScheduleBase):
    pass

class DoctorScheduleResponse(DoctorScheduleBase):
    id: UUID
    doctor_id: UUID

    class Config:
        from_attributes = True

# Doctor
class DoctorBase(BaseModel):
    full_name: str
    email: EmailStr
    specialization: str
    slot_duration_minutes: int = 30
    buffer_time_minutes: int = 5
    google_calendar_id: str = "primary"
    is_active: bool = True

class DoctorCreate(DoctorBase):
    schedules: Optional[List[DoctorScheduleCreate]] = None

class DoctorResponse(DoctorBase):
    id: UUID
    created_at: datetime
    schedules: List[DoctorScheduleResponse] = []

    class Config:
        from_attributes = True

# Patient
class PatientBase(BaseModel):
    phone_number: str
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    date_of_birth: Optional[str] = None
    notes: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# Appointment
class SlotCheckRequest(BaseModel):
    doctor_id: Optional[UUID] = None
    specialization: Optional[str] = None
    date: str = Field(..., description="Date formatted as YYYY-MM-DD")

class TimeSlot(BaseModel):
    doctor_id: UUID
    doctor_name: str
    start_time: datetime
    end_time: datetime
    is_available: bool

class AppointmentCreate(BaseModel):
    patient_phone: str
    patient_name: Optional[str] = None
    doctor_id: UUID
    start_time: datetime
    symptoms_notes: Optional[str] = None

class AppointmentReschedule(BaseModel):
    appointment_id: UUID
    new_start_time: datetime

class AppointmentCancel(BaseModel):
    appointment_id: UUID
    reason: Optional[str] = "Patient requested cancellation"

class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    doctor_id: UUID
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    google_calendar_event_id: Optional[str] = None
    symptoms_notes: Optional[str] = None
    doctor_name: Optional[str] = None
    patient_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Chat / Webhook Request
class InboundChatMessage(BaseModel):
    from_number: str = Field(..., description="WhatsApp sender phone number e.g. '919876543210'")
    message_text: str = Field(..., description="Message string sent by user")
    sender_name: Optional[str] = None
    message_id: Optional[str] = None

class OutboundChatResponse(BaseModel):
    to_number: str
    reply_text: str
    intent: Optional[str] = None
    state: ConversationState
    suggested_actions: Optional[List[str]] = None
