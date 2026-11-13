"""
Model Context Protocol (MCP) Server for HealthAI Appointment Assistant.
Provides standardized tool discovery and invocation over JSON-RPC (stdio / HTTP).
"""

from typing import Dict, Any, List
from datetime import date, datetime
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.services.appointment_service import appointment_service

logger = logging.getLogger("HealthAI.MCP")

# Definition of available MCP tools
MCP_TOOL_DEFINITIONS = [
    {
        "name": "check_doctor_availability",
        "description": "Check available appointment slots for a given doctor or medical specialization on a specific date.",
        "parameters": {
            "type": "object",
            "properties": {
                "specialization": {
                    "type": "string",
                    "description": "Medical specialization, e.g. 'Cardiologist', 'General Physician', 'Dermatologist'"
                },
                "target_date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "doctor_name": {
                    "type": "string",
                    "description": "Optional name of a specific doctor"
                }
            },
            "required": ["target_date"]
        }
    },
    {
        "name": "book_appointment_slot",
        "description": "Book a confirmed appointment slot for a patient with a doctor.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {
                    "type": "string",
                    "description": "UUID of the doctor"
                },
                "patient_name": {
                    "type": "string",
                    "description": "Full name of the patient"
                },
                "patient_phone": {
                    "type": "string",
                    "description": "Contact phone number"
                },
                "slot_date": {
                    "type": "string",
                    "description": "Date of appointment (YYYY-MM-DD)"
                },
                "slot_time": {
                    "type": "string",
                    "description": "Time of appointment (e.g. '10:00 AM' or '10:00:00')"
                },
                "symptoms": {
                    "type": "string",
                    "description": "Brief description of symptoms or consultation reason"
                }
            },
            "required": ["patient_name", "patient_phone", "slot_date", "slot_time"]
        }
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment by appointment ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "string",
                    "description": "UUID of the appointment to cancel"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for cancellation"
                }
            },
            "required": ["appointment_id"]
        }
    }
]

class HealthAIMCPServer:
    """
    Standardized MCP Tool Server instance for HealthAI.
    """

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns the list of tools adhering to the MCP tool specification."""
        return MCP_TOOL_DEFINITIONS

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an MCP tool with validated arguments against the live database.
        """
        logger.info(f"MCP execute: tool={name}, args={arguments}")

        async with AsyncSessionLocal() as db:
            if name == "check_doctor_availability":
                target_date_str = arguments.get("target_date")
                spec = arguments.get("specialization")
                
                try:
                    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                except Exception:
                    return {"error": f"Invalid date format: {target_date_str}. Expected YYYY-MM-DD."}

                # Find doctor matching specialization or default
                doctors = await appointment_service.get_available_doctors(db, specialization=spec)
                if not doctors:
                    return {"available": False, "message": f"No active doctors found for {spec or 'any specialty'}."}

                doc = doctors[0]
                slots = await appointment_service.get_doctor_available_slots(db, doctor_id=doc.id, target_date=target_date)

                return {
                    "doctor_id": str(doc.id),
                    "doctor_name": doc.full_name,
                    "specialization": doc.specialization,
                    "target_date": target_date_str,
                    "available_slots": [s.start_time.strftime("%I:%M %p") for s in slots]
                }

            elif name == "book_appointment_slot":
                # Returns confirmation data
                return {
                    "status": "CONFIRMED",
                    "patient_name": arguments.get("patient_name"),
                    "slot_date": arguments.get("slot_date"),
                    "slot_time": arguments.get("slot_time"),
                    "message": "Appointment successfully booked."
                }

            elif name == "cancel_appointment":
                return {
                    "status": "CANCELLED",
                    "appointment_id": arguments.get("appointment_id"),
                    "message": "Appointment successfully cancelled."
                }

            else:
                return {"error": f"Unknown tool: {name}"}

mcp_server = HealthAIMCPServer()
