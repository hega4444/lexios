
# login_router.py
from lexios.frontend.service import templates, session_manager, frontend_active_users
from uuid import uuid4

from fastapi import Query, Depends, Form, Request, APIRouter
from fastapi_csrf_protect import CsrfProtect
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.exceptions import HTTPException

from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from google.auth.transport import requests as google_auth_request
from googleapiclient.discovery import build

from lexios.settings.main import *
from lexios.frontend.session_data import LexiSessionData, verifier, cookie, backend
from lexios.core.security import UserAuthentication
from lexios.database.users import update_user_data_in_db

GOOGLE_ID = 'GOOGLE_ID'

# Google cloud dedicated backend
google_backend = {} 

# Router for login routes
login_router = APIRouter()

# Endpoint to render the HTML form
@login_router.get("/", response_class=HTMLResponse)
async def root(
    request: Request, 
    csrf_protect: CsrfProtect = Depends()
):
    
    # Create session id
    session = uuid4()
    data = LexiSessionData(session_id=session)

    # Save sessiondata to in-memory backend
    await backend.create(session, data)
    
    # Generate CSRF token
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = templates.TemplateResponse(
        "login.html",
        {"request": request, "csrf_token": csrf_token}
    )

    # Attach session cookie
    cookie.attach_to_response(response, session)
    csrf_protect.set_csrf_cookie(signed_token, response)
    
    return response

# In-house Lexi Login
@login_router.post("/submit_login/", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def submit_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_protect: CsrfProtect = Depends(), 
    session_data: LexiSessionData = Depends(verifier)
):
    
    try:
        await csrf_protect.validate_csrf(request)
    except Exception as e:
       pass

    response: JSONResponse = JSONResponse(status_code=200, content={"detail": "OK"})
    csrf_protect.unset_csrf_cookie(response)  # prevent token reuse


    try:
        # Security # Check if the user exists and the password is correct
        user = UserAuthentication()(email, password)
    
    except PermissionError as e:
        user = None
   
    if user:

        # Validate user and attach session id
        user.session_id = session_data.session_id
        user.validated = True

        # Update backend
        await backend.update(session_data.session_id, user)
        
        # Update active users
        frontend_active_users[user.user_id] = user

        # Append identifiers to request and redirect to dashboard screen
        try:
            
            return JSONResponse({
                'session_id': str(session_data.session_id), 
                }
            )

        except Exception as e:
            pass
        
    else:
        # If authentication fails, raise an HTTPException with a 401 status code
        raise HTTPException(status_code=401, detail="Invalid credentials")

# Google oauth2 login submit
@login_router.get("/google_submit_login/", response_class=RedirectResponse, dependencies=[Depends(cookie)])
async def google_submit_login(
    request: Request,
    csrf_protect: CsrfProtect = Depends(), 
    session_data: LexiSessionData = Depends(verifier),
):

    # Validate the token
    try:
        await csrf_protect.validate_csrf(request)
    except Exception as e:
        pass

    #Retrieve the parameters from the request
    state = request.query_params.get('state', default=None)
    google_success = request.query_params.get('google_callback_success', default=None)

    # Access the google backend
    if state and google_success:
        google_details = google_backend.get(state).get('details')
    
        response: JSONResponse = JSONResponse(status_code=200, content={"detail": "OK"})
        csrf_protect.unset_csrf_cookie(response)  # prevent token reuse

        if google_details:

            email = google_details.get('email')


            try:
                # Security # Check if the user exists and the password is correct
                # If Google Authentication process goes ok it creates a new Lexi account

                user = UserAuthentication()(email, GOOGLE_ID, google_details)

            except PermissionError as e:
                user = None
    
            if user:

                # Validate user and attach session id
                user.session_id = session_data.session_id
                user.validated = True

                # Update backend
                await backend.update(session_data.session_id, user)
                
                # Update active users
                frontend_active_users[user.user_id] = user

                # Append identifiers to request and redirect to dashboard screen
                try:
                    
                    return RedirectResponse(f"/dashboard#{session_data.session_id}")

                except Exception as e:
                    pass

    # Raise an exception otherwise
    raise HTTPException(status_code=401, detail="Invalid credentials")


# Google authentication initial screen
@login_router.get('/auth/google', response_class=HTMLResponse)
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
@login_router.get('/google_callback', response_class=HTMLResponse)
async def google_callback(
    request: Request,
):
    
    # Retrieve the session_id that initiated the login request in main window
    state = request.query_params.get('state', default=None)

    # Check valid state        
    if state not in google_backend:
        raise HTTPException(status_code=401, detail='Invalid OAuth state.')

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
            flow.credentials.id_token, 
            req, 
            flow.credentials.client_id,
            clock_skew_in_seconds=5,
        )

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

# User log out
@login_router.get('/logout', response_class=RedirectResponse, dependencies=[Depends(cookie)])
async def logout(
    session_data: LexiSessionData = Depends(verifier)
):

    # Save user data
    update_user_data_in_db(session_data)    

    # Conversation history 
    session_manager.close_session(session_data.user_id)

    # Remove from active users 
    frontend_active_users.pop(session_data.user_id, None)

    return RedirectResponse(url='/')
