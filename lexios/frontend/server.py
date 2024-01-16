# lexios/api/routes.py
import os
import json
import asyncio

from pydantic import BaseModel

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from contextlib import asynccontextmanager
from fastapi import File, UploadFile, Path
from fastapi.responses import HTMLResponse, JSONResponse

from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi.middleware.cors import CORSMiddleware

from lexios.frontend.session_data import cookie, verifier, LexiSessionData
from lexios.frontend.web_proxy import get_link_icon_and_title
from lexios.frontend.messages_frontend import listen_to_redis
from lexios.core.consent import _consent_backend

from lexios.frontend.service import PROJECT_FOLDER, lexi, templates

from lexios.frontend.login_routes import login_router
from lexios.frontend.messages_frontend import messages_router
from lexios.frontend.user_settings import settings_router
from lexios.frontend.conversations import conversations_router
from lexios.frontend.file_services import files_router


# Define logic at startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup

    # Start the listen_to_redis function as a background task on startup
    app.redis_listener_task = asyncio.create_task(listen_to_redis())
        
    # Start LexiTaskScheduler listener
    app.scheduler_task = asyncio.create_task(lexi.scheduler.check_pending_tasks())
    
    yield # Server running

    # Cancel the background task when the FastAPI application is shutting down
    app.redis_listener_task.cancel()
    await app.redis_listener_task

    await asyncio.sleep(0.1)
    # Cancel TaskScheduler
    app.scheduler_task.cancel()
    await app.scheduler_task

    print("Background tasks closed.")

# Define the main app
app = FastAPI(lifespan=lifespan)

# Routes to the frontend services
app.include_router(login_router)
app.include_router(messages_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(files_router)

# CORS set up
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        # Send message to Lexi and get response
        await lexi.process_user_request(data=message)

        return JSONResponse(content={"status": "Message sent to Lexi."})
    
    except Exception as e:
        print(f"Error processing message: {e}")
        return JSONResponse(content={"error": "An error occurred processing your message."})
    

@app.post('/reset_user_thread_request', response_class=JSONResponse, dependencies=[Depends(cookie)])
async def reset_user_thread_request(
    session_data : LexiSessionData = Depends(verifier),
):
    try:
        # Send command to Lexi:
        await lexi.reset_user_thread_request(
            user_id= session_data.user_id, 
            conversation_id= session_data.conversation_id_focus
            )

        # Immediately return a success response
        return JSONResponse({"status": "Message sent to Lexi."})

    except Exception as e:
        print("Problem at 'reset_user_thread_request: ",e)
        # Immediately return a success response
        return JSONResponse({"status": "Error reseting thread"})

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