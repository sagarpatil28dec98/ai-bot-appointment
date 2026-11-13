from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.database.session import get_db
from app.database.models import Appointment, Doctor
from app.schemas.all_schemas import (
    SlotCheckRequest,
    TimeSlot,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentReschedule,
    AppointmentCancel
)
from app.services.appointment_service import appointment_service

router = APIRouter(prefix="/appointments", tags=["Appointments"])

@router.post("/availability", response_model=List[TimeSlot])
async def check_availability(
    request: SlotCheckRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Check doctor slot availability for a specified date.
    """
    target_date = date.fromisoformat(request.date)
    doctor_id = request.doctor_id

    if not doctor_id and request.specialization:
        docs = await appointment_service.get_available_doctors(db, request.specialization)
        if not docs:
            return []
        doctor_id = docs[0].id

    if not doctor_id:
        # Fallback to first active doctor
        docs = await appointment_service.get_available_doctors(db)
        if not docs:
            return []
        doctor_id = docs[0].id

    return await appointment_service.get_doctor_available_slots(db, doctor_id, target_date)

@router.post("/book", response_model=AppointmentResponse)
async def book_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Book an appointment. Verifies slot availability and synchronizes with Google Calendar.
    """
    appt = await appointment_service.book_appointment(
        db=db,
        patient_phone=payload.patient_phone,
        doctor_id=payload.doctor_id,
        start_time=payload.start_time,
        patient_name=payload.patient_name,
        symptoms_notes=payload.symptoms_notes
    )
    return appt

@router.post("/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    payload: AppointmentReschedule,
    db: AsyncSession = Depends(get_db)
):
    return await appointment_service.reschedule_appointment(
        db=db,
        appointment_id=payload.appointment_id,
        new_start_time=payload.new_start_time
    )

@router.post("/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    payload: AppointmentCancel,
    db: AsyncSession = Depends(get_db)
):
    return await appointment_service.cancel_appointment(
        db=db,
        appointment_id=payload.appointment_id,
        reason=payload.reason
    )

@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    appt = await db.get(Appointment, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt

@router.get("/", response_model=List[AppointmentResponse])
async def list_appointments(
    doctor_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Appointment).order_by(Appointment.start_time.desc()).limit(limit)
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if status:
        query = query.where(Appointment.status == status)

    result = await db.execute(query)
    return list(result.scalars().all())
