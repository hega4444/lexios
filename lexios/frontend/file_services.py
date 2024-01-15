# file_exchange.py
import os

from fastapi import Path, Depends, APIRouter
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse

from lexios.frontend.service import PROJECT_FOLDER

from lexios.settings.main import DOWNLOAD_FOLDER
from lexios.frontend.session_data import LexiSessionData, verifier, cookie

# Uploads / Downloads
files_router = APIRouter()

# Make temporal downloads available to user
@files_router.get('/temporal_downloads/{user_id}/{filename}')
async def download_file(
    user_id: str = Path(...), 
    filename: str = Path(...)
):

    download_folder = os.path.join(os.getcwd(), DOWNLOAD_FOLDER)
    subfolder_name = user_id[:5]
    folder_path = os.path.join(download_folder, subfolder_name)
    file_path = os.path.join(folder_path, filename)

    return FileResponse(file_path, filename=filename, content_disposition_type='attachment')

    
# Temporal downloads
# Protect your route with the dependency
@files_router.get("/downloads/{user_id}/{filename}", response_class=FileResponse, dependencies=[Depends(cookie)])
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