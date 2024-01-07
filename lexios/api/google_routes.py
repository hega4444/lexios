from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException
from fastapi_csrf_protect import CsrfProtect

from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests as google_auth_request

from lexios.settings.main import *
from lexios.api.session_data import backend, cookie, verifier, LexiSessionData
from lexios.core.builtin.functions.email import GmailClient
from lexios.core.builtin.functions.calendar import GoogleCalendar

# Define router and backend components
google_router = APIRouter()
google_backend = {} # Backend data storage for managing user authentication


# Google authentication initial screen
@google_router.get('/auth/google', response_class=HTMLResponse)
async def google_auth():

    # Define Flow object to manager user session by google
    flow = Flow.from_client_secrets_file(
        'lexios/settings/secret.json',  # Path to your client secret file downloaded from Google Cloud Console
        scopes = [
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/calendar',  # Add calendar scope
            'https://www.googleapis.com/auth/gmail.modify',  # Add Gmail scope
            "https://www.googleapis.com/auth/contacts.readonly",
        ],
        redirect_uri=REDIRECT_URI
    )

    # Set additional parameters after initializing the flow
    flow.access_type = 'offline'  # Request offline access
    flow.prompt = 'consent'  # Force the consent screen to be displayed

    authorization_url, state = flow.authorization_url(prompt='select_account')

    # Update the google-specific bin-memory backend
    google_backend[state] = {}
    google_backend[state]['flow'] = flow

    # Redirect to the google consent screen
    return RedirectResponse(authorization_url)

# Google callback
@google_router.get('/google_callback', response_class=HTMLResponse)
async def google_callback(
    request: Request,
):
    
    # Retrieve the session_id that initiated the login request in main window
    state = request.query_params.get('state', default=None)

    # Check valid state        
    if state not in google_backend:
        raise HTTPException(status_code=401, detail='Invalid OAuth state')

    flow = google_backend.get(state).get("flow")

    if flow:
        
        #Extract the URL from the request 
        url = str(request.url)
        # Fetch the token using the new flow
        flow.fetch_token(authorization_response= url)

        # Retrieve the refresh token
        refresh_token = flow.credentials.refresh_token
        
        # Retrieve account info
        req = google_auth_request.Request()
        id_token_info = id_token.verify_oauth2_token(
            flow.credentials.id_token, req, flow.credentials.client_id)

        # Load the user info
        google_details = id_token_info
        google_details['refresh_token'] = refresh_token
        google_details['flow'] = flow
        google_details['state'] = state

        # Register the logged account in the in-memory backend
        google_backend[state]['details'] = google_details

        # Close the popup and redirect to the main screen
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Google Callback</title>
        </head>
        <body>
            <script>
                // Close the popup and redirect to the main screen
                window.opener.location.href = '/google_submit_login/?state={state}&google_callback_success={True}';
                window.close();
            </script>
        </body>
        </html>
        """

        # Return HTMLResponse with inline HTML content

        return HTMLResponse(content=html_content, status_code=200)
        
    # Otherwise redirect to main screen
    return RedirectResponse("/")
