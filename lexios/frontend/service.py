# service.py

from fastapi.templating import Jinja2Templates

from admin.verify_folder import find_project_folder

from lexios.globals import Globals
from lexios.core.session_manager import LexiSessionManager
from lexios.core.lexios_main import LexiOS_Backend
from lexios.integration.make import get_lexi_backend_instance

# Create the instance of Lexi backend
Lexi: LexiOS_Backend = get_lexi_backend_instance()

# Update lexi in Globals
Globals(lexi= Lexi)

# Retrieve a reference to the session manager
Session_manager : LexiSessionManager = Lexi.session_manager

PROJECT_FOLDER = find_project_folder()

# Define a directory for templates
templates = Jinja2Templates(directory="lexios/frontend/templates")



