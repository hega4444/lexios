# email.py
import base64
from datetime import timedelta, datetime

from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from lexios.settings.main import *
from lexios.api.session_data import LexiSessionData

class GoogleCalendar():

    def __init__(self, user: LexiSessionData) -> None:
        self.user = user
        self.events = [] 
        self.check_frequency = timedelta(minutes=30)

        if self.user.google_calendar_access:
            # Check if a refresh token is available in the session
            refresh_token = self.user.google_details.get('refresh_token')

            if not refresh_token:
                return JSONResponse({'error': 'Refresh token not found in session'}), 401

            # Load stored credentials with the specified scopes
            credentials_info = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/calendar"],
            }

            credentials = Credentials.from_authorized_user_info(credentials_info)

            # If credentials are expired, refresh them
            if credentials.expired:
                credentials.refresh(Request())

            # Build the Calendar API service
            self.calendar_service = build('calendar', 'v3', credentials=credentials)
        
        else:
            raise AttributeError('User has not granted permission to access calendar data.')

    def update_calendar_with(self, events):
        # Append retrieved events
        for event in events:
            if event not in self.events:
                self.events.append(event)
        print (events)

    async def get_calendar_data(self, days: int = 10):
        # Example: Retrieve the next 10 events from the user's primary calendar

        events_result = self.calendar_service.events()
        events_result = self.calendar_service.events().list(
            calendarId='primary', timeMin=datetime.utcnow().isoformat() + 'Z',
            maxResults=days, singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])

        # Process the events as needed
        return JSONResponse({'events': events})
    
    def create_event(self):
        pass

    def update_event(self):
        pass