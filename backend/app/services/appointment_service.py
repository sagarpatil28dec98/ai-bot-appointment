import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date, time, timedelta
import pytz
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.database.models import Doctor, DoctorSchedule, Appointment, Patient, AppointmentStatus, ConversationSession, ConversationState
from app.schemas.all_schemas import TimeSlot, AppointmentCreate, AppointmentResponse
from app.services.calendar_service import calendar_service
from app.services.n8n_service import n8n_service
from app.core.config import settings

logger = logging.getLogger("HealthAI.AppointmentService")

class AppointmentService:

    @staticmethod
    async def get_available_doctors(db: AsyncSession, specialization: Optional[str] = None) -> List[Doctor]:
        query = select(Doctor).where(Doctor.is_active == True)
        if specialization:
            query = query.where(Doctor.specialization.ilike(f"%{specialization}%"))
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_doctor_available_slots(
        db: AsyncSession,
        doctor_id: UUID,
        target_date: date
    ) -> List[TimeSlot]:
        """
        Calculates open slots for a doctor on a given calendar date based on
        active working hours and existing confirmed appointments.
        """
        # 1. Fetch doctor details
        doctor = await db.get(Doctor, doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(status_code=404, detail="Doctor not found or inactive")

        # 2. Get schedule for day of week (0=Monday, 6=Sunday)
        day_of_week = target_date.weekday()
        sched_query = select(DoctorSchedule).where(
            and_(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.day_of_week == day_of_week,
                DoctorSchedule.is_active == True
            )
        )
        res = await db.execute(sched_query)
        schedule = res.scalar_one_or_none()

        if not schedule:
            # Doctor does not work on this day
            return []

        # 3. Retrieve booked appointments for this doctor on target_date
        tz = pytz.timezone(settings.GOOGLE_CALENDAR_TIMEZONE)
        day_start = tz.localize(datetime.combine(target_date, time.min))
        day_end = tz.localize(datetime.combine(target_date, time.max))

        appt_query = select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
                Appointment.start_time >= day_start,
                Appointment.end_time <= day_end
            )
        )
        appt_res = await db.execute(appt_query)
        existing_appts = list(appt_res.scalars().all())

        # 4. Generate time slot intervals
        slots: List[TimeSlot] = []
        slot_duration = timedelta(minutes=doctor.slot_duration_minutes)
        buffer_duration = timedelta(minutes=doctor.buffer_time_minutes)

        current_start = tz.localize(datetime.combine(target_date, schedule.start_time))
        schedule_end = tz.localize(datetime.combine(target_date, schedule.end_time))

        now_in_tz = datetime.now(tz)

        while current_start + slot_duration <= schedule_end:
            slot_end = current_start + slot_duration

            # Slot must be in future
            is_in_future = current_start > now_in_tz

            # Check overlap with existing appointments
            is_booked = any(
                (current_start < appt.end_time and slot_end > appt.start_time)
                for appt in existing_appts
            )

            is_available = is_in_future and not is_booked

            slots.append(
                TimeSlot(
                    doctor_id=doctor.id,
                    doctor_name=doctor.full_name,
                    start_time=current_start,
                    end_time=slot_end,
                    is_available=is_available
                )
            )

            current_start = slot_end + buffer_duration

        return slots

    @staticmethod
    async def book_appointment(
        db: AsyncSession,
        patient_phone: str,
        doctor_id: UUID,
        start_time: datetime,
        patient_name: Optional[str] = None,
        symptoms_notes: Optional[str] = None
    ) -> Appointment:
        """
        Concurrency-safe appointment booking with PostgreSQL row-level checks & Google Calendar sync.
        """
        doctor = await db.get(Doctor, doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(status_code=404, detail="Selected doctor is not available")

        slot_duration = timedelta(minutes=doctor.slot_duration_minutes)
        end_time = start_time + slot_duration

        # 1. Conflict check inside transaction
        conflict_query = select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.start_time < end_time,
                Appointment.end_time > start_time
            )
        ).with_for_update()

        conflict_res = await db.execute(conflict_query)
        if conflict_res.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The requested time slot has already been booked. Please choose another time."
            )

        # 2. Get or create Patient record
        patient_query = select(Patient).where(Patient.phone_number == patient_phone)
        patient_res = await db.execute(patient_query)
        patient = patient_res.scalar_one_or_none()

        if not patient:
            patient = Patient(
                phone_number=patient_phone,
                full_name=patient_name or "WhatsApp Patient",
            )
            db.add(patient)
            await db.flush()
        elif patient_name and (not patient.full_name or patient.full_name == "WhatsApp Patient"):
            patient.full_name = patient_name
            await db.flush()

        # 3. Create Appointment in DB
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.CONFIRMED,
            symptoms_notes=symptoms_notes
        )
        db.add(appointment)
        await db.flush()

        # 4. Synchronize with n8n (Google Calendar & Confirmation Workflow)
        try:
            await n8n_service.trigger_booking_confirmed({
                "appointment_id": str(appointment.id),
                "doctor_name": doctor.full_name,
                "specialization": doctor.specialization,
                "patient_name": patient.full_name,
                "patient_phone": patient.phone_number,
                "patient_email": getattr(patient, "email", "") or f"{patient.phone_number}@clinic.com",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "notes": symptoms_notes or "Consultation booked via WhatsApp"
            })
        except Exception as e:
            logger.error(f"Failed to trigger n8n booking workflow: {e}")

        # 5. Local calendar backup sync
        try:
            summary = f"Doctor Appointment: {doctor.full_name} / {patient.full_name}"
            desc = f"HealthAI Booking\nPatient Phone: {patient.phone_number}\nSymptoms: {symptoms_notes or 'N/A'}"
            gcal_event_id = await calendar_service.create_event(
                calendar_id=doctor.google_calendar_id,
                summary=summary,
                description=desc,
                start_time=start_time,
                end_time=end_time
            )
            appointment.google_calendar_event_id = gcal_event_id
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}. Proceeding with DB booking.")

        await db.commit()
        await db.refresh(appointment)
        return appointment

    @staticmethod
    async def cancel_appointment(
        db: AsyncSession,
        appointment_id: UUID,
        reason: Optional[str] = "Cancelled by patient"
    ) -> Appointment:
        appt = await db.get(Appointment, appointment_id)
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")

        appt.status = AppointmentStatus.CANCELLED
        appt.cancellation_reason = reason

        # Delete / cancel on Google Calendar
        if appt.google_calendar_event_id:
            doctor = await db.get(Doctor, appt.doctor_id)
            if doctor:
                await calendar_service.delete_event(doctor.google_calendar_id, appt.google_calendar_event_id)

        await db.commit()
        await db.refresh(appt)
        return appt

    @staticmethod
    async def reschedule_appointment(
        db: AsyncSession,
        appointment_id: UUID,
        new_start_time: datetime
    ) -> Appointment:
        appt = await db.get(Appointment, appointment_id)
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")

        doctor = await db.get(Doctor, appt.doctor_id)
        slot_duration = timedelta(minutes=doctor.slot_duration_minutes)
        new_end_time = new_start_time + slot_duration

        # Conflict check
        conflict_query = select(Appointment).where(
            and_(
                Appointment.doctor_id == doctor.id,
                Appointment.id != appointment_id,
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.start_time < new_end_time,
                Appointment.end_time > new_start_time
            )
        )
        res = await db.execute(conflict_query)
        if res.first():
            raise HTTPException(status_code=409, detail="Selected reschedule slot is already booked.")

        appt.start_time = new_start_time
        appt.end_time = new_end_time
        appt.status = AppointmentStatus.CONFIRMED

        # Sync Google Calendar update
        if appt.google_calendar_event_id:
            await calendar_service.update_event(
                calendar_id=doctor.google_calendar_id,
                event_id=appt.google_calendar_event_id,
                start_time=new_start_time,
                end_time=new_end_time
            )

        await db.commit()
        await db.refresh(appt)
        return appt

appointment_service = AppointmentService()
