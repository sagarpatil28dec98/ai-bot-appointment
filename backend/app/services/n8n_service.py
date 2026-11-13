"""
n8n Integration Service.
Dispatches confirmed bookings, notifications, and calendar sync tasks to self-hosted n8n.
"""

import logging
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("HealthAI.n8n")

class N8nService:
    """
    Client for triggering asynchronous workflows on n8n (https://n8n.geetrix.com).
    """

    def __init__(self):
        self.webhook_url = getattr(
            settings,
            "N8N_CONFIRMATION_WEBHOOK_URL",
            "https://n8n.geetrix.com/webhook/booking-confirmed"
        )

    async def trigger_booking_confirmed(self, payload: Dict[str, Any]) -> bool:
        """
        Sends confirmed appointment payload to n8n for Google Calendar invite & email dispatch.
        Expected keys:
            - doctor_name
            - specialization
            - patient_name
            - patient_phone
            - patient_email
            - start_time (ISO 8601 string)
            - end_time (ISO 8601 string)
            - notes
        """
        logger.info(f"Triggering n8n booking workflow for: {payload.get('patient_name')} ({self.webhook_url})")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code in [200, 201]:
                    logger.info("Successfully notified n8n of confirmed booking")
                    return True
                else:
                    logger.warning(f"n8n webhook returned status {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.warning(f"Failed to reach n8n webhook at {self.webhook_url}: {e}")
            return False

n8n_service = N8nService()
