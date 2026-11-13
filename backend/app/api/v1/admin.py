from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database.session import get_db
from app.database.models import User, Doctor, Patient, Appointment, ConversationSession, AppointmentStatus
from app.schemas.all_schemas import UserLogin, Token, UserResponse
from app.security.authentication import verify_password, create_access_token, get_password_hash
from app.services.openwa_service import openwa_service

router = APIRouter(prefix="/admin", tags=["Admin & Metrics"])

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role.value})
    return Token(access_token=token)

@router.get("/dashboard-stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Summary metrics for the admin overview dashboard."""
    total_appts = await db.scalar(select(func.count(Appointment.id))) or 0
    confirmed_appts = await db.scalar(select(func.count(Appointment.id)).where(Appointment.status == AppointmentStatus.CONFIRMED)) or 0
    cancelled_appts = await db.scalar(select(func.count(Appointment.id)).where(Appointment.status == AppointmentStatus.CANCELLED)) or 0
    
    total_doctors = await db.scalar(select(func.count(Doctor.id)).where(Doctor.is_active == True)) or 0
    total_patients = await db.scalar(select(func.count(Patient.id))) or 0
    total_conversations = await db.scalar(select(func.count(ConversationSession.id))) or 0

    # System status check
    openwa_stat = await openwa_service.get_session_status()

    return {
        "metrics": {
            "total_appointments": total_appts,
            "confirmed_appointments": confirmed_appts,
            "cancelled_appointments": cancelled_appts,
            "active_doctors": total_doctors,
            "registered_patients": total_patients,
            "conversations_handled": total_conversations
        },
        "system_status": {
            "database": "connected",
            "openwa": openwa_stat,
            "calendar": "ready"
        }
    }
