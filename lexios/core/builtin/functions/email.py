# email.py
import base64
import json
import uuid
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi.responses import JSONResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from lexios.core.aitools import ai_assistant_request
from lexios.core.logger import CustomLogger
from lexios.database.users import retrieve_category_content, create_user_specific_data
from lexios.database.models import UserSpecificData
from lexios.settings.main import *


class GmailClient():
    # Class to access Gmail data, read and send emails

    # Define how often is the email checked
    check_frequency = timedelta(minutes=10) 

    def __init__(self, **kwargs) -> None:

        if "user" in kwargs:
            self.user = kwargs.get("user")
        
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
                "scopes": [
                    "https://www.googleapis.com/auth/gmail.modify",
                    "https://www.googleapis.com/auth/contacts.readonly",
                ],
            }
            credentials = Credentials.from_authorized_user_info(credentials_info)

            # If credentials are expired, refresh them
            if credentials.expired:
                credentials.refresh(Request())

            # Build the Gmail API service
            self.gmail_service = build('gmail', 'v1', credentials=credentials)

            # Build the People API service
            self.people_service = build('people', 'v1', credentials=credentials)

        else:
            raise AttributeError("User has not granted access to Gmail data.")

    async def retrieve_unread_emails(self):

        # Calculate the date 24 hours ago from the current time
        date_24_hours_ago = (datetime.utcnow() - timedelta(hours=24)).strftime('%Y/%m/%d')

        # List unread messages excluding promotions category from the last 24 hours
        # Exclude promotions
        unread_messages = self.gmail_service.users().messages().list(userId='me', 
                                                                     q=f'is:unread -category:promotions after:{date_24_hours_ago}',
                                                                     ).execute()

        # Get the list of unread message IDs
        unread_message_ids = [message['id'] for message in unread_messages.get('messages', [])]
        ## Fetch details of each unread message
        unread_messages_data = []

        for message_id in unread_message_ids:

            # Retrieve message from the API
            message = self.gmail_service.users().messages().get(userId='me', id=message_id).execute()

            # Extract subject from headers
            subject = next((header['value'] for header in message['payload']['headers'] if header['name'].lower() == 'subject'), None)

            # Extract 'Date' from headers
            date_str = next((header['value'] for header in message['payload']['headers'] if header['name'].lower() == 'date'), None)
            
            # Parse the date string to datetime object
            datetime_received = parsedate_to_datetime(date_str)

            # Extract 'from' from headers
            sender = next((header['value'] for header in message['payload']['headers'] if header['name'].lower() == 'from'), None)

            # Check if 'body' dictionary has 'data' key
            body_data = message['payload']['body'].get('data', '')
            
            # Decode the base64-encoded body
            body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')

            unread_messages_data.append({
                'id': message_id,
                'datetime': datetime_received, 
                'subject': subject,
                'sender': sender,
                'snippet': message['snippet'],
                'body' : body_text,
                # Add more fields as needed
            })

        # Return the messages
        return unread_messages_data
    
    async def send_email(self, to_address: str, subject: str, body: str):
        # SUMM: Send an email using the Gmail API
        # to_adsress 'description': email addresss
        # Replace name annotation
        body= body.replace("[Your Name]", ' '.join([self.user.name_first, self.user.name_last]))

        # Create a MIME message for sending
        message = MIMEMultipart()
        message['to'] = to_address
        message['subject'] = subject

        # Attach the body as plain text
        message.attach(MIMEText(body, 'plain'))

        # Convert the MIME message to a string
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        try:
            # Send the email
            sent_message = self.gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            return sent_message
        except Exception as e:
            # Handle the exception as needed
            return None

    async def reply_to_email(self, original_message_id, reply_body, reply_subject = None):
        # Step 1: Retrieve the original message
        original_message = self.gmail_service.users().messages().get(userId='me', id=original_message_id).execute()

        # Step 2: Extract information from the original message
        sender_email = next((header['value'] for header in original_message['payload']['headers'] if header['name'].lower() == 'from'), None)
        subject_prefix = "Re: "  # You might want to customize this based on your needs

        # Step 3: Compose a reply message
        reply_message = MIMEMultipart()
        reply_message['to'] = sender_email
        reply_message['subject'] = subject_prefix + original_message['payload']['headers'][18]['value']

        # Attach the reply body as plain text
        reply_message.attach(MIMEText(reply_body, 'plain'))

        # In the case of a thread, set the `threadId` to maintain the thread context
        reply_message['threadId'] = original_message['threadId']

        # Step 4: Send the reply message
        raw_reply_message = base64.urlsafe_b64encode(reply_message.as_bytes()).decode('utf-8')
        sent_reply_message = self.gmail_service.users().messages().send(userId='me', body={'raw': raw_reply_message}).execute()

        return sent_reply_message

    async def execute_applying_rules(self):

        # Get already processed messages
        processed_emails = retrieve_category_content(self.user.user_id, "processed_emails")
        messages_ids = [json.loads(email.data_content).get("id") for email in processed_emails]

        # Get the list of unread
        unread_messages = await self.retrieve_unread_emails()

        # Filter messages that were already replied
        unread_messages = [message for message in unread_messages if message.get("id") not in messages_ids]

        # Retrieve the existing rules applying for the user
        rules = retrieve_category_content(self.user.user_id, "automated_email_responses")

        rules = [json.loads(rule.data_content) for rule in rules]

        if unread_messages and rules:

            for message in unread_messages:

                for rule in rules:
                # Check if there is any rule set for messages coming from a specifc sender

                    if rule.get("sender") and rule.get("sender") in message.get("sender", ""):
                        
                        # Generate reply content
                        message_body = await self.generate_automated_email_content(
                            sender = message.get("sender"),
                            original_message= message.get("snippet") + message.get("body"),
                            user_request = rule.get("original_user_request"),
                        )
                        
                        # Reply email
                        await self.reply_to_email(
                            original_message_id = message.get("id"),
                            reply_body= message_body.get("output"), 
                        )

                        # Save in database as processed
                        new_data_id = str(uuid.uuid4())
                        create_user_specific_data(UserSpecificData(
                            data_id= new_data_id,
                            user_id= self.user.user_id,
                            data_category= "processed_emails", 
                            data_content= json.dumps({    
                                'id' : message.get("id"),
                                'status': "processed",
                            }), 
                            )
                        )
        
    async def generate_automated_email_content(self, sender: str, original_message: str, user_request: str):
        # Creates a dynamic response to an email

        response = await ai_assistant_request(
                            user_id= self.user.user_id,

                            request=f"Write and return the reply content to this email: {original_message}"
                                f"received from: {sender}"
                                f"Here is the original request from the user: {user_request}"

                                "Example output:"
                                '"""'
                                f"Dear (direct the message to {sender}),"
                                "<body>"
                                ""
                                f"(Sign email as {' '.join([self.user.name_first, self.user.name_last])} "
                                '"""',

                            instructions= "You are a tool that generates the text content for an email reply"
                                'Your answer must be hust the email response enclosed in """ .',
        )
        
        return response

    async def search_email_by_name(self, name: str):
        # SUMM: Search for an email address among the gmail contacts

        try:
            # Use the People API to search for contacts by name
            page_token = None

            while True:
                # Make the API request with the current page token
                connections = self.people_service.people().connections().list(
                    resourceName='people/me',
                    personFields='names,emailAddresses,nicknames',  # Include names, nicknames, and email addresses
                    pageSize=200,  # Set a larger page size to retrieve more results at once
                    pageToken=page_token,  # Set the page token for the next page
                ).execute()

                # Extract the connections from the response
                connections_list = connections.get('connections', [])

                for connection in connections_list:
                    # Extract names
                    names = connection.get('names', [])
                    for n in names:
                        if 'displayName' in n and name.lower() in n['displayName'].lower():
            
                            # Check if email is directly under 'emailAddresses'
                            emails = connection.get('emailAddresses', [])
                            if emails:
                                # Prefer the first email address; you can modify this logic based on your requirements
                                return emails[0].get('value')

                            # Check if email is under 'emailAddresses.value'
                            email_value = connection.get('emailAddresses.value')
                            if email_value:
                                return email_value

                            # Check if email is under nested structures like 'emailAddresses[0].value'
                            nested_email = connection.get('emailAddresses', [])
                            if isinstance(nested_email, list) and nested_email:
                                return nested_email[0].get('value')

                # Check if there are more pages to retrieve
                page_token = connections.get('nextPageToken')
                if not page_token:
                    break  # No more pages

            return None

        except Exception as e:
            print(f"An error occurred while searching for email by name: {e}")
            return None
