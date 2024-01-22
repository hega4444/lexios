# service.py

from fastapi.templating import Jinja2Templates

from admin.verify_folder import find_project_folder

from lexios.globals import Globals
from lexios.core.session_manager import LexiSessionManager
from lexios.core.lexios_main import LexiOS_Backend
from lexios.integration.make import get_lexi_backend_instance

# Define a in-memory backend for the users logged
frontend_active_users = {}

# Create the instance of Lexi backend
lexi: LexiOS_Backend = get_lexi_backend_instance(active_users = frontend_active_users)

# Update lexi in Globals
Globals(lexi=lexi)

# Retrieve a reference to the session manager
session_manager : LexiSessionManager = lexi.session_manager

PROJECT_FOLDER = find_project_folder()

# Define a directory for templates
templates = Jinja2Templates(directory="lexios/frontend/templates")



