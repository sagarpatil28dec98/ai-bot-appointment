from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.database.session import get_db
from app.database.models import Patient
from app.schemas.all_schemas import PatientResponse, PatientCreate

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.get("/", response_model=List[PatientResponse])
async def list_patients(
    search: str = Query(None),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Patient).order_by(Patient.created_at.desc()).limit(limit)
    if search:
        query = query.where(
            (Patient.full_name.ilike(f"%{search}%")) | (Patient.phone_number.ilike(f"%{search}%"))
        )
    result = await db.execute(query)
    return list(result.scalars().all())

@router.post("/", response_model=PatientResponse)
async def create_patient(
    patient_in: PatientCreate,
    db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(select(Patient).where(Patient.phone_number == patient_in.phone_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Patient with this phone number already exists")

    patient = Patient(
        phone_number=patient_in.phone_number,
        full_name=patient_in.full_name,
        email=patient_in.email,
        date_of_birth=patient_in.date_of_birth,
        notes=patient_in.notes
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient
