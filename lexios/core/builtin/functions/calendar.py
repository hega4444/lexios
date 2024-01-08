# email.py
import base64
from datetime import timedelta, datetime

from fastapi.responses import JSONResponse
from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from lexios.settings.main import *

class GoogleCalendar():

    check_frequency = timedelta(minutes=30)

    def __init__(self, **kwargs) -> None:

        if "user" in kwargs:
            self.user = kwargs.get("user")

        self.events = [] 
        
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
    
    def create_google_calendar_event(self, summary:str, start_datetime:str, end_datetime:str, description=None):
        # SUMM: Create an event in google calendar
        # summary 'description': Name for the event
        # description 'description': A more detailed description of the event

        if not self.user.google_calendar_access:
            raise AttributeError('User has not granted permission to access calendar data.')
        
         # Convert date strings to datetime objects
        start_datetime = datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M:%S') + timedelta(minutes=TIME_DELTA)
        end_datetime = datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M:%S') + timedelta(minutes=TIME_DELTA)

        # Create google event data structure
        event_data = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_datetime.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 30},
                    {'method': 'email', 'minutes': 60},
                ],
            },
            # Additional fields can be added as needed
            # ...
        }

        try:
            event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event_data
            ).execute()

            # Update the internal events list with the new event
            self.update_calendar_with([event])

            return {'event': event}

        except HttpError as e:
            raise HTTPException(status_code=e.resp.status, detail=f'Error creating event: {str(e)}')
        
    def update_event(self):
        pass