# models.py

import json
import bcrypt
from typing import Optional

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime
from cryptography.fernet import Fernet
from pydantic import BaseModel, field_validator
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, ForeignKey, Text, LargeBinary, Boolean, JSON

from lexios.globals import GENERAL_VIRTUAL_AGENT_LABEL
from lexios.settings.main import *
from lexios.core.builtin.engines.SQLEngine import SimpleSQL

# Define the database URI for PostgreSQL
DATABASE_URI = f"{LEXI_DATABASE_ENGINE.lower()}://{LEXI_DB_ADMIN_USER}:{LEXI_DB_ADMIN_PASS}@{LEXI_DATABASE_HOST}/{LEXI_DATABASE_NAME}"

# Create the database engine
# Set the isolation level to "Read committed" to improve accuracy and consistency
engine = create_engine(DATABASE_URI, isolation_level="READ COMMITTED")

# Create a session to interact with the database
Session = sessionmaker(bind=engine)

# Define base class for ORM models
Base = declarative_base()

# Define base class for pydantic models
class CustomModelPydantic(BaseModel):
    @field_validator("created_at", mode="before", check_fields=False)
    def transform(cls, input) -> str:
        if isinstance(input, datetime):
            return input.isoformat()
        return input

# User model (there is an associated pydantic model in lexios.api.session_data )
class User(Base):
    """
    Database model for user profile and settings.
    """
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name_first = Column(String(50), nullable=False)
    name_last = Column(String(50), nullable=False)
    location = Column(String(50), default=None)

    username = Column(String(50), unique=True, nullable=False)
    salt = Column(String(29), nullable=False)  # Store the salt as a string
    hashed_password = Column(String(60), nullable=False)  # Store the hashed password
    birth_date = Column(Date, default=None)
    conversation_index = Column(Integer, nullable=False)

    # Additional fields for checks/features
    bing_searches = Column(Boolean, default=False)
    lexi_learns = Column(Boolean, default=False)

    # Google ID data
    encrypted_google_details = Column(LargeBinary)
    google_id = Column(String(50), default=None)
    gmail_access = Column(Boolean, default=False)
    google_calendar_access = Column(Boolean, default=False)

    theme_selection = Column(String(50), default='Lexi default Theme')  # Assuming a default theme is 'light'
    text_color = Column(String(7), default='#000000')  # Default text color is black
    background_color = Column(String(7), default='#FFFFFF')  # Default background color is white

    def __init__(self, name_first, name_last, username, password, 
                 conversation_index, birth_date=None, location=None,
                 bing_searches=False, lexi_learns=False, google_id=None, google_details=None, 
                 gmail_access=False, google_calendar_access=False,
                 theme_selection='lexi_default', text_color=DEFAULT_THEME_TEXT_COLOR, 
                 background_color=DEFAULT_THEME_BACKGROUND_COLOR):
        
        # Encrypt google_details
        if google_details:
            cipher_suite = Fernet(GOOGLE_ID_SECURE_KEY)
            encrypted_google_details = cipher_suite.encrypt(json.dumps(google_details).encode('utf-8'))
            self.encrypted_google_details = encrypted_google_details

        self.name_first = name_first
        self.name_last = name_last
        self.location = location
        self.username = username
        self.birth_date = birth_date
        self.conversation_index = conversation_index
        self.bing_searches = bing_searches
        self.lexi_learns = lexi_learns
        self.google_id = google_id
        self.gmail_access = gmail_access
        self.google_calendar_access = google_calendar_access
        self.theme_selection = theme_selection
        self.text_color = text_color
        self.background_color = background_color

         # Encrypt password data
        gen_salt = bcrypt.gensalt()
        self.salt = gen_salt.decode('utf-8')  # Store the salt as a string
        gen_hashed_password = bcrypt.hashpw(password.encode('utf-8'), gen_salt)[:60]

        # Truncate hashed password
        self.hashed_password = gen_hashed_password.decode('utf-8')  # Store the hashed password

    # Define table relationships
    conversations = relationship('Conversation', back_populates='user')
    scheduled_tasks = relationship('ScheduledTaskORM', back_populates='user')
    user_specific_data = relationship('UserSpecificDataORM', back_populates='user')
    roles = relationship('Role', back_populates='user')

class Role(Base):
    """ 
    Roles assigned to an user_id
    """
    __tablename__ = 'roles'

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    name = Column(String, nullable=False)
    read = Column(Boolean, default=False)
    write = Column(Boolean, default=False)
    execute = Column(Boolean, default=False)

    user = relationship('User', back_populates='roles')

    def __init__(self, user_id, name, read=False, write=False, execute=False):
        self.user_id = user_id
        self.name = name
        self.read = read
        self.write = write
        self.execute = execute


# User conversations
class Conversation(Base):
    """
    Database model for storing conversation messages.
    """
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    created_on = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.user_id')) 
    conversation_id = Column(String(6), unique=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    title = Column(String(255))
    virtual_agent_name = Column(String(50), default=None, nullable=True)
    app_messages_content = Column(JSON)
    model_root_assistant_id = Column(String(32), nullable=True)
    model_root_thread_id = Column(String(32), nullable=True)
    model_loaded_assistant_id = Column(String(32), nullable=True)
    model_loaded_thread_id = Column(String(32), nullable=True)
    model_messages = Column(LargeBinary)  # Use LargeBinary to store binary data
    metrics = Column(LargeBinary)  # Use LargeBinary to store binary data

    # Define the relationship to users
    user = relationship('User', back_populates='conversations')

    def __init__(
            self, user_id, 
            conversation_id, 
            title, app_messages_content = [], 
            root_assistant_id = None,
            root_thread_id = None,
            loaded_assistant_id = None, 
            loaded_thread_id = None, 
            model_messages = None, 
            metrics = None,
            virtual_agent_name = None,
    ):
        
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.title = title
        self.app_messages_content = app_messages_content
        self.virtual_agent_name = virtual_agent_name
        self.model_root_assistant_id = root_assistant_id
        self.model_root_thread_id = root_thread_id
        self.model_loaded_assistant_id = loaded_assistant_id
        self.model_loaded_thread_id = loaded_thread_id
        self.model_messages = model_messages
        self.metrics = metrics

# Store user specifc data 
class UserSpecificDataORM(Base):
    __tablename__ = 'user_specific_data'

    data_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id')) 
    data_category = Column(String)  # e.g., 'reminder', 'preference', 'rule', 'user_data'
    data_content = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Define the relationship to users
    user = relationship('User', back_populates='user_specific_data')

# Pydantic model
class UserSpecificData(CustomModelPydantic):
    """
    User specific data model

    It provides a flexible way of storing user data and preferences easy to access for
    the AI model.
    """
    data_id: str
    user_id: int
    data_category: Optional[str]
    data_content: Optional[str]
    created_at: Optional[str] = None

class ScheduledTaskORM(Base):
    """
    Task Database model for sotring scheduled tasks and reminders.
    """
    __tablename__ = 'scheduled_tasks'
    
    task_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id')) 
    data_id = Column(String, nullable=True)
    conversation_id = Column(String(4))
    function_name = Column(String, nullable=True)
    arguments = Column(JSONB, nullable=True)
    annotations = Column(Text, nullable=True)
    status = Column(String, default='scheduled') 
    repeat_each = Column(Integer, nullable=True) 
    category = Column(String, nullable=True)
    notify_to = Column(String, nullable=True)
    start_at = Column(DateTime)
    end_at = Column(DateTime, nullable=True)

    # Define the relationship to users
    user = relationship('User', back_populates='scheduled_tasks')

# Define a pydantic model for the tasks (so it is easier to move between memory - db)
class ScheduledTaskPydantic(BaseModel):
    task_id: str
    user_id: int
    conversation_id: Optional[str] = None
    function_name: Optional[str] = None
    arguments: Optional[dict] = None
    annotations: Optional[str] = None
    status: Optional[str] = None
    data_id: Optional[str] = None
    repeat_each: Optional[int] = None
    category: Optional[str] = None
    notify_to: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

# This function is called by the admin tool when creating a new project to have a separate database
def initial_database_setup(name="lexi_template", remake: bool = False):
    """
    This function is called by the admin tool when creating a new project to have a deicated database.

    Parameters:
    - `name` (str): Project name.
    - `remake` (bool): (default) False. If True it erases any previous version of the Database.
    """

    session = Session()

    options = {
        "force" : TEST_MODE,
        "db_name" : LEXI_DATABASE_NAME,
        "user": LEXI_DB_ADMIN_USER,
        "password" : LEXI_DB_ADMIN_PASS,
        "port": LEXI_DB_ADMIN_PORT,
        "load_setup_script": "",
        "drop_after" : remake,  # Set it True to wipe the database, False for creating the data model again
    }

    # load simple sql with the settings, if remake is true wipes the database
    with SimpleSQL(**options):
        pass

    if remake:
        # Run again for creation
        options['drop_after'] = False
        with SimpleSQL(**options):
            pass  
        
    # Create models
    Base.metadata.create_all(engine)

    # Define root username
    root_name=  str(name) + "_ADMIN"

    # USER_ID 1 = SYSTEM USER
    # Create a new user and add it to the database
    root = User(name_first=LEXI_ALIAS, name_last=LEXI_ALIAS, username=root_name, password=LEXI_DB_ADMIN_PASS , birth_date=date(2024, 4, 4), conversation_index=0)
    session.add(root)
    session.commit()
    
    # USER_ID 1 = SYSTEM USER / ROLE ROOT_ACCESS 
    # Define / Assign a role for system use only
    root_role = Role(user_id=root.user_id, name='root', read=True, write=True, execute=True)
    session.add(root_role)
    session.commit()
    
    # USER_ID 2 = VIRTUAL AGENT
    # Create a new user and add it to the database
    agent = User(name_first=GENERAL_VIRTUAL_AGENT_LABEL, name_last="", username="virtual_agent", password=LEXI_DB_ADMIN_PASS , birth_date=date(2024, 4, 4), conversation_index=0)
    session.add(agent)
    session.commit()

    # USER_ID 2 = VIRTUAL AGENT / ROLE VIRTUAL_AGENT_ACCESS
    # Define / Assign a role for system use only
    agent_role = Role(user_id=agent.user_id, name='virtual_agent', read=True, write=True, execute=True)
    session.add(agent_role)
    session.commit()

    # Test user
    new_user = User(name_first='Hernan', name_last='Garcia', username=TEST_LOGIN_USER, password=TEST_LOGIN_PASS, birth_date=date(1987, 2, 22), conversation_index=0)
    session.add(new_user)
    session.commit()

    # Define a baseline role for a user
    user_role = Role(user_id=new_user.user_id, name='user', read=True, write=True, execute=False)
    session.add(user_role)
    session.commit()

    # Close the session when you're done
    session.close()



# Lexi internal database set up -----------------------------------------------------------------------------------------------------#

if __name__ == '__main__':

    initial_database_setup(remake=True)

    print("models generated.")

# Lexi internal database set up -----------------------------------------------------------------------------------------------------#


