from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.exceptions import HTTPException
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests as google_auth_request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from lexios.settings.main import *
from lexios.api.session_data import cookie, verifier, LexiSessionData

google_router = APIRouter()
google_backend = {} # Backend data storage for managing user authentication


# Replace this with your actual Google authentication route
@google_router.get('/auth/google', response_class=HTMLResponse, dependencies=[Depends(cookie)])
async def google_auth(
    session_data: LexiSessionData = Depends(verifier), 
):
    async with session_data:
        session_id = session_data.session_id
        flow = Flow.from_client_secrets_file(
            'lexios/settings/secret.json',  # Path to your client secret file downloaded from Google Cloud Console
            scopes = [
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/calendar',  # Add calendar scope
                'https://www.googleapis.com/auth/gmail.modify',  # Add Gmail scope
            ],
            redirect_uri=REDIRECT_URI
        )

        # Set additional parameters after initializing the flow
        flow.access_type = 'offline'  # Request offline access
        flow.prompt = 'consent'  # Force the consent screen to be displayed

        authorization_url, state = flow.authorization_url(prompt='select_account')

        # Update the google-specific bin-memory backend
        google_backend[session_id] = {}
        google_backend[session_id]['flow'] = flow
        google_backend[session_id]['state'] = state

        # Redirect to the google consent screen
        return RedirectResponse(authorization_url)

@google_router.get('/google_callback', response_class=HTMLResponse, dependencies=[Depends(cookie)])
async def google_callback(
    request: Request,
    session_data: LexiSessionData = Depends(verifier), 
):
    async with session_data:

        session_id = session_data.session_id

        # Retrieve the state given by the server and validate with the one stored in the backend
        state = request.query.get('state', default=None)
        stored_state = google_backend.get(session_id).get('state')

        if state != stored_state:
            raise HTTPException(status_code=401, detail='Invalid OAuth state')

        flow = google_backend.get(session_data.session_id).get('flow')

        if flow:

            # Fetch the token using the new flow
            flow.fetch_token(authorization_response=request.url)

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
            google_backend[session_id]['details'] = google_details

            # Close the popup and redirect to the main screen
            return HTMLResponse('google_callback.html', session_id=session_id, google_callback_success=True)
        
        # Otherwise return False
        return HTMLResponse('google_callback.html', session_id=session_id, google_callback_success=False)

