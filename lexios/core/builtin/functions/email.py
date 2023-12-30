# email.py
import base64
from datetime import timedelta

from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from lexios.settings.main import *
from lexios.api.session_data import LexiSessionData

class GmailReader():
    # Class to access Gmail data, read and send emails

    def __init__(self, user: LexiSessionData) -> None:

        self.user = user
        self.check_frequency = timedelta(minutes=5) 

        if self.user.gmail_access and self.user.google_details:

            # Check if a refresh token is available in the session
            refresh_token = self.user.google_details.get('refresh_token')

            if not refresh_token:
                return JSONResponse({'error': 'Refresh token not found in session'})

            # Load stored credentials with the specified scopes
            credentials_info = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": ["https://www.googleapis.com/auth/gmail.modify"],
            }

            credentials = Credentials.from_authorized_user_info(credentials_info)

            # If credentials are expired, refresh them
            if credentials.expired:
                credentials.refresh(Request())

            # Build the Gmail API service
            self.gmail_service = build('gmail', 'v1', credentials=credentials)

        else:
            raise AttributeError("User has not granted access to Gmail data.")


    async def get_unread_emails(self):

        # List unread messages
        unread_messages = self.gmail_service.users().messages().list(userId='me', q='is:unread').execute()
        # Get the list of unread message IDs
        unread_message_ids = [message['id'] for message in unread_messages.get('messages', [])]
        ## Fetch details of each unread message
        unread_messages_data = []

        for message_id in unread_message_ids:

            # Retrieve message from the API
            message = self.gmail_service.users().messages().get(userId='me', id=message_id).execute()

            # Extract subject from headers
            subject = next((header['value'] for header in message['payload']['headers'] if header['name'].lower() == 'subject'), None)

            # Extract 'from' from headers
            sender = next((header['value'] for header in message['payload']['headers'] if header['name'].lower() == 'from'), None)

            # Check if 'body' dictionary has 'data' key
            body_data = message['payload']['body'].get('data', '')
            
            # Decode the base64-encoded body
            body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')

            unread_messages_data.append({
                'id': message_id,
                'subject': subject,
                'from': sender,
                'snippet': message['snippet'],
                'body' : body_text,
                # Add more fields as needed
            })

        # Return the messages
        return JSONResponse({'messages': unread_messages_data})
    
class GmailBackgroundTask():

    def __init__(self) -> None:
        pass
