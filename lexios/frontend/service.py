# service.py
from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

from admin.verify_folder import find_project_folder

from lexios.globals import Globals
from lexios.core.signatures import _LexiOS_Backend, _LexiSessionManager
from lexios.integrations.make import get_lexi_backend_instance


# Set up Lexi backend features
frontend_active_users = {}

lexi: _LexiOS_Backend = get_lexi_backend_instance(

    active_users= frontend_active_users
)

# Update lexi in Globals
Globals(lexi=lexi)

# Retrieve a reference to the session manager
session_manager :_LexiSessionManager = lexi.session_manager

PROJECT_FOLDER = find_project_folder()
GOOGLE_ID = 'GOOGLE_ID'

lexi: _LexiOS_Backend = get_lexi_backend_instance(

    active_users= frontend_active_users
)

# Update lexi in Globals
Globals(lexi=lexi)

# Retrieve a reference to the session manager
session_manager :_LexiSessionManager = lexi.session_manager

# FRONTEND SETUP #


# ROUTERS #

# Google cloud services
login_router = APIRouter()

# Websocket connections, both for message exchange and session login / logout events
messages_router = APIRouter()

# Conversations routes
conversations_router = APIRouter() 

# Settings
settings_router = APIRouter()

# Uploads / Downloads
files_router = APIRouter()

# Define a directory for templates
templates = Jinja2Templates(directory="lexios/frontend/templates")







