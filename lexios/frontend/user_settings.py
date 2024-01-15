# user_settings.py

from fastapi import Depends, Form, Request, Query, APIRouter
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi_csrf_protect import CsrfProtect

from lexios.frontend.service import templates
from lexios.frontend.session_data import LexiSessionData, verifier, cookie

# Settings
settings_router = APIRouter()

# Endpoint to render the main Dashboard
@settings_router.get("/settings", response_class=HTMLResponse, dependencies=[Depends(cookie)])
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
 
# Get the color combination for a specific theme
@settings_router.get("/get_theme_colors", response_class=JSONResponse)
async def get_theme_colors(theme: str = Query(..., description="The name of the theme")):

    theme_colors = {
        'lexi_default': {'background': '#C4660E', 'text': '#FDFDF6'},
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
@settings_router.get("/get_theme_user_colors", response_class=JSONResponse, dependencies=[Depends(cookie)])
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


# Get user settings:
@settings_router.get('/get_user_settings', response_class=JSONResponse, dependencies=[Depends(cookie)])
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
@settings_router.post("/update_user_settings", response_class=JSONResponse, dependencies=[Depends(cookie)])
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