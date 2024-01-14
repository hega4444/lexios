from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.session_verifier import SessionVerifier
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
from uuid import UUID

class LexiSessionData(BaseModel):
    session_id: Optional[UUID] = None
    user_id: Optional[int] = None
    is_active: bool = True  # here could be implemented a logic for blocking user id i.e.
    validated: bool = False
    name_first: Optional[str] = None
    name_last: Optional[str] = None
    username: Optional[str] = None
    birth_date: Optional[date] = None
    conversation_index: int = 0
    conversation_id_focus: int = 0
    location: Optional[str] = None
    bing_searches: bool = False
    lexi_learns: bool = False
    google_id: Optional[str] = None
    oauth_state: Optional[str] = None
    google_details: Optional[dict] = None
    gmail_access: bool = False
    google_calendar_access: bool = False
    theme_selection: str = 'Lexi default Theme'
    text_color: str = '#fdf6f6'
    background_color: str = '#771840'

    def get_conversation_index(self):
        self.conversation_index += 1
        return str(self.conversation_index).zfill(4)

    def get_id(self):
        return str(self.id)
    
    @property
    def is_authenticated(self):
        return self.is_active and self.validated

    class Config:
        arbitrary_types_allowed = True
    
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        # Check if the session_id already exists in the backend
        session_exists = await backend.read(self.session_id)

        if session_exists:
            # Perform an update if the session_id exists
            await backend.update(self.session_id, self)
        else:
            # Perform a create if the session_id does not exist
            await backend.create(self.session_id, self)

# Session verifier 
class CustomDataVerifier(SessionVerifier[UUID, LexiSessionData]):
    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        backend: InMemoryBackend[UUID, LexiSessionData],
        auth_http_exception: HTTPException,
    ):
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self):
        return self._identifier

    @property
    def backend(self):
        return self._backend

    @property
    def auto_error(self):
        return self._auto_error

    @property
    def auth_http_exception(self):
        return self._auth_http_exception

    def verify_session(self, model: LexiSessionData) -> bool:
        """If the session exists, it is valid"""
        return True

# __________________________________________________________________#   

# Define backend setup

# Cookies
cookie_params = CookieParameters()

# Define in-memory backend
backend = InMemoryBackend[UUID, LexiSessionData]()

verifier = CustomDataVerifier(
    identifier="lexi_general_verifier",
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)

# Uses UUID
cookie = SessionCookie(
    cookie_name="cookie",
    identifier="lexi_general_verifier",
    auto_error=True,
    secret_key="DONOTUSE",
    cookie_params=cookie_params,
)

def read_session_data_from_backend(user_id: int):

    for session_data in backend.data.values():

        if session_data.user_id == user_id:

            return session_data
    
    return None