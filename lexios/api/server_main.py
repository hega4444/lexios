# lexios/api/routes.py
import os
import asyncio
import json
from uuid import uuid4
from pydantic import BaseModel
from typing import List

from fastapi import FastAPI, Request, Depends, Form, HTTPException, Body
from fastapi import File, UploadFile, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi.middleware.cors import CORSMiddleware

from admin.verify_folder import find_project_folder
PROJECT_FOLDER = find_project_folder()

from lexios.settings.main import *
from lexios.api.globals import Globals
from lexios.api.session_data import backend, cookie, verifier, LexiSessionData
from lexios.api.redis_websocket import messages_router, listen_to_redis
from lexios.api.google_routes import google_router, google_backend
from lexios.api.web_proxy import get_link_icon_and_title
from lexios.database.conversations import get_user_conversations
from lexios.database.users import update_user_data_in_db
from lexios.integrations.make import get_lexi_backend_instance
from lexios.core.consent import _consent_backend

# set up lexi backend features
frontend_active_users = {}
lexi = get_lexi_backend_instance(

    active_users= frontend_active_users
)

# Retrieve a reference to the session manager
session_manager = lexi.session_manager

app = FastAPI()
app.include_router(messages_router)
app.include_router(google_router)
templates = Jinja2Templates(directory="lexios/api/templates")

# CORS set up
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def on_startup():
    # Start the listen_to_redis function as a background task on startup
    asyncio.create_task(listen_to_redis())

# Assign event handler
app.add_event_handler("startup", on_startup)

# Set up session cookies settings
class CsrfSettings(BaseModel):
  secret_key:str = 'REPLACE FOR A REAL KEY HERE'

@CsrfProtect.load_config
def get_csrf_config():
  return CsrfSettings()

# Mount the static files
folder = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=folder+"/static", html=True), name="static")

# Define the folder path for serving static files
temp_folder_path = os.path.join(PROJECT_FOLDER, "temp", "downloads")  # Adjust the path as needed

# Define a response for token validation errors
@app.exception_handler(CsrfProtectError)
def csrf_protect_exception_handler(request: Request, exc: CsrfProtectError):
  return JSONResponse(status_code=exc.status_code, content={ 'detail':  exc.message })

# Return validation errors details
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("request:", request)
    print("details:", exc)
    return JSONResponse(content={"detail": "Validation Error, check console"}, status_code=422)



# Endpoint to render the HTML form
@app.get("/", response_class=HTMLResponse)
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
@app.post("/submit_login/", response_class=JSONResponse, dependencies=[Depends(cookie)])
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

    # Check if the user exists and the password is correct
    user = session_manager.validate_user_profile(email, password)
   
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
@app.get("/google_submit_login/", response_class=RedirectResponse, dependencies=[Depends(cookie)])
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

            # Try to recover profile from Lexi too
            user = session_manager.validate_user_profile(
                email= email, 
                password= 'GOOGLE_ID',
                gmail_data= google_details
                )
    
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

# Retrieve the user_id:
@app.get('/get_session_id', response_class=JSONResponse, dependencies=[Depends(cookie)])
async def get_user_id(session_data: LexiSessionData = Depends(verifier)):
    return JSONResponse({"session_id": str(session_data.session_id)})

# Endpoint to render the main Dashboard
@app.get("/dashboard", response_class=HTMLResponse, dependencies=[Depends(cookie)])
async def dashboard(
    request: Request,
    csrf_protect: CsrfProtect = Depends(), 
    session_data: LexiSessionData = Depends(verifier),
):
    if session_data.is_authenticated:

        # Generate CSRF token
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()

        # Assuming you have a user_name attribute in your LexiSessionData
        user_name = session_data.name_first

        response = templates.TemplateResponse(
            "main.html",
            {"request": request, "csrf_token": csrf_token, "user_name": user_name}
        )

        # Attach CSRF token to the response
        csrf_protect.set_csrf_cookie(signed_token, response)

        return response

    
# Retrieve the conversation data and focus:
@app.get("/get_conversation_data", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def get_conversation_data(
    select_conversation_id: str = Query(default=None),
    session_data: LexiSessionData = Depends(verifier)
):
    async with session_data:

        if select_conversation_id:
            session_data.conversation_id_focus = select_conversation_id
            messages = session_manager.rerieve_conversation(session_data.user_id, select_conversation_id)

            if messages:
                if not isinstance(messages, list):
                    messages = json.loads(messages)  # Temporal fix while debugging main cause of issue

                conversation_data = {
                    'messages': messages,
                }

                # Return conversation messages
                return JSONResponse(conversation_data)
            
            else:
                raise HTTPException(status_code=404)

        else:
            # Recover stored conversations too
            conversations = get_user_conversations(session_data.user_id)

            # Retrieve stored conversations
            if conversations:

                # Find the conversation with the newest last_updated timestamp
                newest_conversation = max(conversations, key=lambda c: c.last_updated)
                conversation_index = newest_conversation.conversation_id

                conversations_list = []
                for conversation in conversations:
                    # Create conversations list

                    conversations_list.append([
                        conversation.title,
                        conversation.conversation_id
                    ]
                    )

                    # Link the loaded conversations to the User session
                    session_manager.load_conversation(conversation)

                # Set the focus on the latest conversation             
                session_data.conversation_id_focus = conversation_index
                
                conversation_data = {
                    'conversations_list' : conversations_list,
                    'conversation_focus': conversation_index,
                }
                return JSONResponse(conversation_data)

            else:
                # No saved chats
                # Determine next conversation index number
                conversation_index = session_data.get_conversation_index()

                # Set the focus on the new conversation
                session_data.conversation_id_focus = conversation_index

                # Prepare return 
                conversation_data = {
                        'conversations_list' : [['new chat..', conversation_index]],
                        'conversation_focus': conversation_index,
                }
                return JSONResponse(conversation_data)

# Update conversation title:
@app.post('/update_conversation_title', response_class=JSONResponse, dependencies=[Depends(cookie)])
async def update_conversation_title(
    conversation_id: str = Form(...),
    new_title: str = Form(...),
    csrf_protect: CsrfProtect = Depends(), 
    session_data: LexiSessionData = Depends(verifier),
):

    session_manager.update_converstion_title(session_data.user_id, conversation_id, new_title)

    return JSONResponse({'message': 'Conversation title updated successfully'})

# New conversation request
@app.get('/get_next_conversation_id', response_class=JSONResponse, dependencies=[Depends(cookie)])
async def get_next_conversation_id(
    session_data: LexiSessionData = Depends(verifier),
):
    async with session_data:
        # Get next index number for user_id
        convesation_id = session_data.get_conversation_index()

        # Update conversation focus
        session_data.conversation_id_focus = convesation_id

        # Return the value to the frontend
        return JSONResponse({"next_conversation_id": convesation_id})

# Get conversation focus:
@app.get('/get_conversation_id_focus', response_class=JSONResponse, dependencies=[Depends(cookie)])
def get_conversation_id_focus(
    session_data: LexiSessionData = Depends(verifier)
):
    return JSONResponse({'conversation_id_focus': session_data.conversation_id_focus})

# Delete conversation request
@app.post('/delete_conversation_id', response_class=JSONResponse, dependencies=[Depends(cookie)])
def delete_conversation(
    conversation_id: str = Form(...),
    session_data : LexiSessionData = Depends(verifier),
):
    # Call lexi session manager to take care of the task
    session_manager.delete_conversation(session_data.user_id, conversation_id)
    return JSONResponse({'message': 'Conversation deleted successfully'})
    
# Get the color combination for a specific theme
@app.get("/get_theme_colors", response_class=JSONResponse)
async def get_theme_colors(theme: str = Query(..., description="The name of the theme")):

    theme_colors = {
        'lexi_default': {'background': '#e25a5a', 'text': '#fdf6f6'},
        'night_sky': {'background': '#000000', 'text': '#FFFFFF'},
        'moonlight_serenade': {'background': '#001F3F', 'text': '#E6E6E6'},
        'daybreak_delight': {'background': '#FDF6E3', 'text': '#333333'},
        'deep_sea': {'background': '#001848', 'text': '#00BFFF'},
        'sunset_bliss': {'background': '#FF6F61', 'text': '#2F4F4F'},
        'forest_canopy': {'background': '#006400', 'text': '#F5F5DC'},
        'cherry_blossom': {'background': '#FFB6C1', 'text': '#4B0082'},
        'golden_hour': {'background': '#FFD700', 'text': '#8B4513'},
        'polar_breeze': {'background': '#FFFFFF', 'text': '#40E0D0'},
        'midnight_mystery': {'background': '#191970', 'text': '#7B68EE'},
        'tropical_paradise': {'background': '#008000', 'text': '#FFD700'},
        'vintage_vibes': {'background': '#7B68EE', 'text': '#FFE4B5'},
    }

    # Check if the theme name exists in the theme_colors dictionary
    if theme in theme_colors:
        # Return the theme colors as JSON
        return JSONResponse(content=theme_colors[theme])
    else:
        # If the theme name is not found, return an error response
        return JSONResponse(content={'error': 'Theme not found'}, status_code=404)

# Retrieve user color preferences
@app.get("/get_theme_user_colors", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def get_theme_user_colors(session_data: LexiSessionData = Depends(verifier)):

    if session_data.is_authenticated:

        # Get user preferences
        text_color = session_data.text_color
        background_color = session_data.background_color
        return JSONResponse(content={
            'textColor': text_color,
            'backgroundColor': background_color,           
        })
    
    else:
        # Return Lexi default colors
        return JSONResponse(content={
            'textColor': '#fdf6f6',
            'backgroundColor': '#e25a5a',
        })

# Make temporal downloads available to user
@app.get('/temporal_downloads/{user_id}/{filename}')
async def download_file(
    user_id: str = Path(...), 
    filename: str = Path(...)
):

    download_folder = os.path.join(os.getcwd(), DOWNLOAD_FOLDER)
    subfolder_name = user_id[:5]
    folder_path = os.path.join(download_folder, subfolder_name)
    file_path = os.path.join(folder_path, filename)

    return FileResponse(file_path, filename=filename, content_disposition_type='attachment')

# Route to handle form submission
@app.post("/process_input", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def process_input(
    session_id: str = Form(default=None),
    user_input: str = Form(default=None),
    file_upload: UploadFile = File(None),
    session_data: LexiSessionData = Depends(verifier),
):
    # Validate the session
    if not session_data.is_authenticated:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Access the user ID using current_user.id
    user_id = session_data.user_id

    # Get or create session_id
    session_id = str(session_data.session_id)

    # Handle file upload
    file_path = None
    if file_upload:

        # Create the user directory if it doesn't exist
        user_uploads = os.path.join(PROJECT_FOLDER, "temp", "uploads", str(session_data.user_id).zfill(5))
        os.makedirs(user_uploads, exist_ok=True)

        # Create filepath
        filename = file_upload.filename
        file_path = os.path.join(user_uploads, filename)

        # Save user file in its temporal folder
        with open(file_path, "wb") as f:
            f.write(file_upload.file.read())

    # Log new message
    print(f"Lexi_API - new message (ses_id_{session_id})", user_input)

    # Prepare structure for sending to Lexi:
    message = {
        "user_id": user_id,
        "conversation_id": session_data.conversation_id_focus,
        "user_input": user_input,
        "filename": file_path,
    }

    try:

        # Update the global variables
        Globals(user_input=user_input)

        # Send message to Lexi and get response
        await lexi.process_user_request(data=message)

        return JSONResponse(content={"status": "Message sent to Lexi."})
    
    except Exception as e:
        print(f"Error processing message: {e}")
        return JSONResponse(content={"error": "An error occurred processing your message."})
    

@app.post('/reset_user_thread_request', response_class=JSONResponse, dependencies=[Depends(cookie)])
def reset_user_thread_request(
    session_data : LexiSessionData = Depends(verifier),
):
    try:
        # Send command to Lexi:
        lexi.reset_user_thread_request(
            user_id= session_data.user_id, 
            conversation_id= session_data.conversation_id_focus
            )

        # Immediately return a success response
        return JSONResponse({"status": "Message sent to Lexi."})

    except Exception as e:
        print("Problem at 'reset_user_thread_request: ",e)
        # Immediately return a success response
        return JSONResponse({"status": "Error reseting thread"})

# Endpoint to render the main Dashboard
@app.get("/settings", response_class=HTMLResponse, dependencies=[Depends(cookie)])
async def settings(
    request: Request,
    csrf_protect: CsrfProtect = Depends(), 
    session_data: LexiSessionData = Depends(verifier),
):
    if session_data.is_authenticated:

        # Generate CSRF token
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()

        # Assuming you have a user_name attribute in your LexiSessionData
        user_name = session_data.name_first

        response = templates.TemplateResponse(
            "settings.html",
            {"request": request, "csrf_token": csrf_token, "user_name": user_name}
        )

        # Attach CSRF token to the response
        csrf_protect.set_csrf_cookie(signed_token, response)

        return response

# Get user settings:
@app.get('/get_user_settings', response_class=JSONResponse, dependencies=[Depends(cookie)])
def get_user_settings(
    session_data : LexiSessionData = Depends(verifier),
):
    if session_data.is_authenticated:
        # Assuming LexiUser is the user class you defined
        user_settings = {
            'name_first': session_data.name_first,
            'name_last': session_data.name_last,
            'location': session_data.location,
            'bing_searches': session_data.bing_searches,
            'lexi_learns': session_data.lexi_learns,
            'google_id': session_data.google_id,
            'gmail_access': session_data.gmail_access,
            'google_calendar_access': session_data.google_calendar_access,
            'theme_selection': session_data.theme_selection,
            'text_color': session_data.text_color,
            'background_color': session_data.background_color,
        }

        return JSONResponse(user_settings)
    else:
        # Handle the case when the user is not authenticated
        return JSONResponse({'error': 'User not authenticated'}), 401

# Update user settings
@app.post("/update_user_settings", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def update_user_settings(
    request: Request,
    name_first: str = Form(default=None),
    name_last: str = Form(default=None),
    location: str = Form(default=None),
    google_id: str = Form(default=None),
    bing_searches: bool = Form(default=None),
    lexi_learns: bool = Form(default=None),
    gmail_access: bool = Form(default=None),
    google_calendar_access: bool = Form(default=None),
    theme_selection: str = Form(default=None),
    text_color: str = Form(default=None),
    background_color: str = Form(default=None),
    csrf_protect: CsrfProtect = Depends(),
    session_data: LexiSessionData = Depends(verifier),  # Assuming you have a dependency for session verification
):
    if session_data.is_authenticated:
        try:
            async with session_data:
        
                # Update user settings based on the received form data
                session_data.name_first = name_first if name_first is not None else session_data.name_first
                session_data.name_last = name_last if name_last is not None else session_data.name_last
                session_data.location = location if location is not None else session_data.location
                session_data.google_id = google_id if google_id is not None else session_data.google_id
                session_data.bing_searches = bing_searches if bing_searches is not None else session_data.bing_searches
                session_data.lexi_learns = lexi_learns if lexi_learns is not None else session_data.lexi_learns
                session_data.gmail_access = gmail_access if gmail_access is not None else session_data.gmail_access
                session_data.google_calendar_access = google_calendar_access if google_calendar_access is not None else session_data.google_calendar_access
                session_data.theme_selection = theme_selection if theme_selection is not None else session_data.theme_selection
                session_data.text_color = text_color if text_color is not None else session_data.text_color
                session_data.background_color = background_color if background_color is not None else session_data.background_color

            return JSONResponse({'success': True})
            
        except Exception as e:
            return JSONResponse({'error': str(e)}, status_code=500)
    else:
        # Handle the case when the user is not authenticated
        return JSONResponse({'error': 'User not authenticated'}, status_code=401)
    
# Temporal downloads
# Protect your route with the dependency
@app.get("/downloads/{user_id}/{filename}", response_class=FileResponse, dependencies=[Depends(cookie)])
async def download_file(
    user_id: str, 
    filename: str,
    session_data : LexiSessionData = Depends(verifier),
):
    # Check if user_id is authorized to access the file
    if session_data.is_authenticated:

        # Construct the file path
        file_path = os.path.join(PROJECT_FOLDER, "temp", "downloads", user_id, filename)

        # Serve file
        return FileResponse(file_path)
    
    else:
        raise HTTPException(status_code=401, detail="Not authorized.")

# User log out
@app.get('/logout', response_class=RedirectResponse, dependencies=[Depends(cookie)])
async def logout(
    session_data: LexiSessionData = Depends(verifier)
):

    # Save user data
    update_user_data_in_db(session_data)    

    # conversation history 
    session_manager.close_session(session_data.user_id)
    return RedirectResponse(url='/')

@app.get("/test", response_class=HTMLResponse)
async def test(
    request: Request,
):
    return templates.TemplateResponse(
        "test.html",    
        {"request": request},
        )


@app.get("/url/{url:path}", response_class=JSONResponse)
async def proxy(url: str, request: Request):
    # Return the icon and title of a given href 
    
    if url:

        data = await get_link_icon_and_title(url)

        response = JSONResponse(data)
        
        return response
    
# Process a consent screen confirmation
@app.post("/confirm_consent_screen", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def confirm_consent_screen(
        choices: str = Form(...),
        consent_token: str = Form(...),
        status: str = Form(...),
        csrf_protect: CsrfProtect = Depends(),
        session_data: LexiSessionData = Depends(verifier),
):
    # Validate token

    # Update the backend
    _consent_backend[consent_token] = {
        'status' : status,
        'choices': json.loads(choices),
        }
    
    return JSONResponse(content={"message": "Consent updated."})