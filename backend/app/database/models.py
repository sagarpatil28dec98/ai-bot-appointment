import uuid
from datetime import datetime, time
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    ForeignKey,
    DateTime,
    Time,
    Text,
    Enum,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database.session import Base
import enum

class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class ConversationState(str, enum.Enum):
    NEW = "NEW"
    IDENTIFYING_INTENT = "IDENTIFYING_INTENT"
    COLLECTING_DOCTOR = "COLLECTING_DOCTOR"
    COLLECTING_DATE = "COLLECTING_DATE"
    COLLECTING_TIME = "COLLECTING_TIME"
    COLLECTING_PATIENT_DETAILS = "COLLECTING_PATIENT_DETAILS"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    BOOKING_IN_PROGRESS = "BOOKING_IN_PROGRESS"
    BOOKED = "BOOKED"
    RESCHEDULING = "RESCHEDULING"
    CANCELLING = "CANCELLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class MessageDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"

# Admin User Model
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.ADMIN, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# 1. Patient Model
class Patient(Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(50), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    date_of_birth = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    sessions = relationship("ConversationSession", back_populates="patient")

# 2. Doctor Model
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True)
    specialization = Column(String(100), nullable=False, index=True)
    slot_duration_minutes = Column(Integer, default=30, nullable=False)
    buffer_time_minutes = Column(Integer, default=5, nullable=False)
    google_calendar_id = Column(String(255), default="primary", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")

# 3. Doctor Schedules
class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    start_time = Column(Time, nullable=False)      # e.g., 09:00:00
    end_time = Column(Time, nullable=False)        # e.g., 17:00:00
    is_active = Column(Boolean, default=True, nullable=False)

    doctor = relationship("Doctor", back_populates="schedules")

# 4. Appointment Model
class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.CONFIRMED, nullable=False, index=True)
    google_calendar_event_id = Column(String(255), nullable=True)
    symptoms_notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    notifications = relationship("NotificationLog", back_populates="appointment")

    __table_args__ = (
        Index("idx_doctor_slot_active", "doctor_id", "start_time", "end_time", "status"),
    )

# 5. Conversation Session
class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True)
    phone_number = Column(String(50), nullable=False, index=True)
    current_state = Column(Enum(ConversationState), default=ConversationState.NEW, nullable=False)
    context_data = Column(JSONB, default=dict, nullable=False)
    last_interaction_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")

# 6. Conversation Messages
class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(Enum(MessageDirection), nullable=False)
    message_text = Column(Text, nullable=False)
    payload_metadata = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    session = relationship("ConversationSession", back_populates="messages")

# 7. Notification Logs
class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), default="WHATSAPP", nullable=False)
    status = Column(String(50), default="SENT", nullable=False)
    message_body = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="notifications")

# 8. Audit Logs
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor = Column(String(100), default="SYSTEM", nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    changes = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
