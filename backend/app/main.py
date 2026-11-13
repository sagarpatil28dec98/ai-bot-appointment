from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from sqlalchemy import select
from datetime import time

from app.core.config import settings
from app.database.session import engine, Base, AsyncSessionLocal
from app.database.models import User, Doctor, DoctorSchedule, UserRole
from app.security.authentication import get_password_hash
from app.api.v1 import chat, appointments, doctors, patients, admin, mcp_routes

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("HealthAI")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if not present and seed initial data
    logger.info("Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed Admin and Sample Doctors if empty
    async with AsyncSessionLocal() as db:
        user_check = await db.execute(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
        if not user_check.scalar_one_or_none():
            admin_user = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                full_name="Clinic System Administrator",
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin_user)
            logger.info(f"Seeded default administrator: {settings.DEFAULT_ADMIN_EMAIL}")

        doc_check = await db.execute(select(Doctor))
        if not doc_check.scalars().first():
            # Seed default doctors
            doc1 = Doctor(
                full_name="Sarah Jenkins",
                email="dr.jenkins@clinic.com",
                specialization="Cardiologist",
                slot_duration_minutes=30,
                buffer_time_minutes=5,
                google_calendar_id="primary",
                is_active=True
            )
            doc2 = Doctor(
                full_name="David Chen",
                email="dr.chen@clinic.com",
                specialization="General Physician",
                slot_duration_minutes=20,
                buffer_time_minutes=5,
                google_calendar_id="primary",
                is_active=True
            )
            doc3 = Doctor(
                full_name="Elena Rostova",
                email="dr.rostova@clinic.com",
                specialization="Dermatologist",
                slot_duration_minutes=30,
                buffer_time_minutes=5,
                google_calendar_id="primary",
                is_active=True
            )
            db.add_all([doc1, doc2, doc3])
            await db.flush()

            # Add schedules Monday - Friday 09:00 - 17:00
            for doc in [doc1, doc2, doc3]:
                for day in range(0, 6):  # Mon through Sat
                    sched = DoctorSchedule(
                        doctor_id=doc.id,
                        day_of_week=day,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                        is_active=True
                    )
                    db.add(sched)
            logger.info("Seeded default clinic doctors and schedules")

        await db.commit()

    yield
    # Shutdown
    logger.info("Shutting down HealthAI services...")
    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Production HealthAI Assistant for WhatsApp Appointment Automation",
    lifespan=lifespan
)

# CORS middleware for React Admin Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }

# Register API v1 routes
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
app.include_router(appointments.router, prefix=settings.API_V1_PREFIX)
app.include_router(doctors.router, prefix=settings.API_V1_PREFIX)
app.include_router(patients.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(mcp_routes.router, prefix=settings.API_V1_PREFIX)
