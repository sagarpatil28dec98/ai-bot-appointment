import logging
import httpx
from app.core.config import settings

logger = logging.getLogger("HealthAI.OpenWA")

class OpenWAService:
    """
    OpenWA Client for session status check and outbound WhatsApp message delivery.
    """

    def __init__(self):
        self.base_url = settings.OPENWA_URL
        self.api_key = settings.OPENWA_API_KEY

    async def send_message(self, to_phone: str, message: str) -> bool:
        """
        Sends an outbound WhatsApp text message via OpenWA REST API.
        """
        # Format phone to WhatsApp JID if necessary (e.g., 919876543210@c.us)
        jid = to_phone if "@c.us" in to_phone else f"{to_phone}@c.us"

        url = f"{self.base_url}/api/send-message"
        headers = {
            "api_key": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "to": jid,
            "content": message
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    logger.info(f"WhatsApp message successfully dispatched to {to_phone}")
                    return True
                else:
                    logger.warning(f"OpenWA returned {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.warning(f"Failed to communicate with OpenWA container at {self.base_url}: {e}")
            return False

    async def get_session_status(self) -> dict:
        url = f"{self.base_url}/api/get-connection-state"
        headers = {"api_key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "offline", "code": resp.status_code}
        except Exception as e:
            return {"status": "disconnected", "error": str(e)}

openwa_service = OpenWAService()
