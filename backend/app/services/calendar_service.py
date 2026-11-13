import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger("HealthAI.CalendarService")

class GoogleCalendarService:
    """
    Dedicated Service for Google Calendar integration.
    Supports both real Google Calendar API (via Service Account / OAuth)
    and a stateful Mock mode for local testing without requiring active GCP credentials.
    """

    def __init__(self):
        self.use_mock = settings.USE_MOCK_GOOGLE_CALENDAR
        self.timezone = settings.GOOGLE_CALENDAR_TIMEZONE
        self.service = None

        if not self.use_mock:
            self._init_google_client()

    def _init_google_client(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            
            scopes = ['https://www.googleapis.com/auth/calendar']
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_CALENDAR_CREDENTIALS_PATH, scopes=scopes
            )
            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("Successfully connected to Google Calendar API")
        except Exception as e:
            logger.warning(f"Could not initialize Google Calendar Client: {e}. Falling back to Mock mode.")
            self.use_mock = True

    async def create_event(
        self,
        calendar_id: str,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendee_email: Optional[str] = None
    ) -> str:
        """
        Creates an event in Google Calendar and returns the google event ID.
        """
        if self.use_mock:
            mock_id = f"gcal_evt_{uuid.uuid4().hex[:12]}"
            logger.info(f"[MOCK GCAL] Created event '{summary}' at {start_time} (ID: {mock_id})")
            return mock_id

        event_body = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': self.timezone,
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': self.timezone,
            },
        }
        if attendee_email:
            event_body['attendees'] = [{'email': attendee_email}]

        try:
            event = self.service.events().insert(calendarId=calendar_id, body=event_body).execute()
            return event.get('id')
        except Exception as e:
            logger.error(f"Error creating event in Google Calendar: {e}")
            raise RuntimeError(f"Google Calendar API error: {str(e)}")

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        start_time: datetime,
        end_time: datetime,
        summary: Optional[str] = None
    ) -> bool:
        if self.use_mock:
            logger.info(f"[MOCK GCAL] Updated event {event_id} to new slot: {start_time}")
            return True

        try:
            event = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            event['start']['dateTime'] = start_time.isoformat()
            event['end']['dateTime'] = end_time.isoformat()
            if summary:
                event['summary'] = summary
            self.service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating Google Calendar event {event_id}: {e}")
            return False

    async def delete_event(self, calendar_id: str, event_id: str) -> bool:
        if self.use_mock:
            logger.info(f"[MOCK GCAL] Cancelled/Deleted event {event_id}")
            return True

        try:
            self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting event {event_id} from Google Calendar: {e}")
            return False

calendar_service = GoogleCalendarService()
