from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.database.session import get_db
from app.database.models import Doctor, DoctorSchedule
from app.schemas.all_schemas import DoctorResponse, DoctorCreate
from app.services.appointment_service import appointment_service

router = APIRouter(prefix="/doctors", tags=["Doctors"])

@router.get("/", response_model=List[DoctorResponse])
async def list_doctors(
    specialization: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    return await appointment_service.get_available_doctors(db, specialization)

@router.post("/", response_model=DoctorResponse)
async def create_doctor(
    doctor_in: DoctorCreate,
    db: AsyncSession = Depends(get_db)
):
    doctor = Doctor(
        full_name=doctor_in.full_name,
        email=doctor_in.email,
        specialization=doctor_in.specialization,
        slot_duration_minutes=doctor_in.slot_duration_minutes,
        buffer_time_minutes=doctor_in.buffer_time_minutes,
        google_calendar_id=doctor_in.google_calendar_id,
        is_active=doctor_in.is_active
    )
    db.add(doctor)
    await db.flush()

    # Add default schedule (Mon-Fri 09:00 - 17:00) if none supplied
    if doctor_in.schedules:
        for s in doctor_in.schedules:
            sched = DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=s.day_of_week,
                start_time=s.start_time,
                end_time=s.end_time,
                is_active=s.is_active
            )
            db.add(sched)
    else:
        from datetime import time
        for day in range(0, 5):  # Mon to Fri
            sched = DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_active=True
            )
            db.add(sched)

    await db.commit()
    await db.refresh(doctor)
    return doctor
