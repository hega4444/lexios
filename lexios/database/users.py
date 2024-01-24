# User data and User specific data
import bcrypt
import json
from typing import Dict, Any, List
from cryptography.fernet import Fernet
from sqlalchemy import or_

from lexios.settings.main import *
from lexios.frontend.session_data import LexiSessionData
from lexios.database.models import Session, User, UserSpecificData, UserSpecificDataORM

def create_user_account_in_db(email: str, password: str, user_data: LexiSessionData = None , google_data: dict = None):
    """ 
    Create a new account in the database 
    
    Parameters:
    - `email`(str): User email account.
    - `password`(str): User password.
    - `user_data`(LexiSessionData) The user profile details.
    - `google_data`(dict): The Goole identification details (email, and refresh token) when logging in with Google.
    """
    session = Session()
    try:
        if google_data:
            try:
                name_first = google_data.get('given_name')
                name_last = google_data.get('family_name')
                email = google_data.get('email')
            except Exception:
                pass
            password = 'GMAIL_ACCOUNT'
        if not name_first:
            name_first = email
            name_last = email

        # Create a new user and add it to the database
        new_user = User(
            name_first=name_first, 
            name_last=name_last, 
            username=email, 
            password=password,
            google_id=google_data['email'],
            google_details={
                'refresh_token': google_data['refresh_token'],
                'state': google_data['state'],                
                # Add more if needed
            },
            conversation_index=0)
        session.add(new_user)
        session.commit()

        # Retrieve from database to keep consistency 
        user = session.query(User).filter_by(username=email).first()
        return user
    
    finally:
        session.close()

def validate_password_in_db(email: str, password: str) ->User:
    """
    It checks whether the user credentials are valid.

    Parameters:
    - `email`(str): User's email address.
    - `password`(str): User's password or constant "GOOGLE_ID" meaning the user has been validated with Google services.
    """
    # Create a session
    session = Session()
    try:
        # Query the database to retrieve the salt and hashed_password for the given email
        user = session.query(User).filter_by(username=email).first()

        # Lexi log-in:
        if password != 'GOOGLE_ID':   
                if user:
                    # Use the retrieved salt to hash the entered password
                    entered_password_hashed = bcrypt.hashpw(password.encode('utf-8'), user.salt.encode('utf-8'))[:60]

                    # Compare the entered hashed password with the stored hashed password
                    if entered_password_hashed == user.hashed_password.encode('utf-8'):
                        return user  # Password is valid
                    else:
                        return None  # Password is invalid
        
        # Google log-in, just needs email
        else:
            # Check if the user exists:
            if user:
                return user
            else:
                return 'NEW_GOOGLE_ACCOUNT'
            
    finally:
        # Close the session
        session.close()

def get_user_data_by_user_id(user_id: int) -> LexiSessionData:
    """ 
    Returns the user data by user id.

    Parameters:
    - `user_id`(int): User identifier.

    Returns:
    - LexiSessionData record.
    """
    # Create a session
    session = Session()

    try:
        user = session.query(User).filter_by(user_id = user_id).first()

        # Convert data to pydantic model
        if user:

            user_data = user.__dict__

            # Descrypt google account data if any
            if user_data.get("encrypted_google_details"):
                cipher_suite = Fernet(GOOGLE_ID_SECURE_KEY)
                user_data['google_details'] = json.loads(cipher_suite.decrypt(user.encrypted_google_details))
            
            return LexiSessionData.model_validate(user_data)

    finally:
        # Close session
        session.close()
def retrieve_users_with_background_tasks() -> List[LexiSessionData]:
    """ 
    Returns a list of users(LexiSessionData) with any active background tasks.

    """
    # Create a session
    session = Session()

    try:
        users = (
            session.query(User)
            .filter(or_(User.gmail_access == True, User.google_calendar_access == True))
            .all()
)
        # Convert data to pydantic model
        users_descrpyted = []
        for user in users:
            user_data = user.__dict__

            # Descrypt google account data if any
            if user_data.get("encrypted_google_details"):
                cipher_suite = Fernet(GOOGLE_ID_SECURE_KEY)
                user_data['google_details'] = json.loads(cipher_suite.decrypt(user.encrypted_google_details))
            
            users_descrpyted.append(LexiSessionData.model_validate(user_data))

        return users_descrpyted
    
    finally:
        # Close session
        session.close()

# Update user data in the database
def update_user_data_in_db(lexi_user: LexiSessionData):
    """
    Updates user profile and settings in the Database.

    Parameters:
    - `lexi_user`(LexiSessionData): The user data to be updated.
    """

    # Create a session
    session = Session()

    try:
        user = session.query(User).filter_by(user_id=lexi_user.user_id).first()
        if user:

            # Encrypt google_details
            if lexi_user.google_details:
                cipher_suite = Fernet(GOOGLE_ID_SECURE_KEY)
                encrypted_google_details = cipher_suite.encrypt(json.dumps(lexi_user.google_details).encode('utf-8'))

            else:
                encrypted_google_details = None

            # Update user data
            user.conversation_index = lexi_user.conversation_index
            user.name_first = lexi_user.name_first
            user.name_last = lexi_user.name_last
            user.location = lexi_user.location
            user.google_id = lexi_user.google_id
            user.encrypted_google_details = encrypted_google_details
            user.bing_searches = lexi_user.bing_searches
            user.lexi_learns = lexi_user.lexi_learns
            user.gmail_access = lexi_user.gmail_access
            user.google_calendar_access = lexi_user.google_calendar_access
            user.theme_selection = lexi_user.theme_selection
            user.text_color = lexi_user.text_color
            user.background_color = lexi_user.background_color

            session.commit()
    except Exception as e:
        pass  # Handle the exception as needed, for now, it's ignored
        session.rollback()
    finally:
        # Close session
        session.close()

# Methods for managing user specifc data

def create_user_specific_data(user_specific_data: UserSpecificData):
    """
    Creates a record in the database containing user specific data.

    Parameters:
    - `user_specific_data`(UserSpecificData): The object to be recorded.
    """
    session = Session()
    try:
        db_user_specific_data = UserSpecificDataORM(**user_specific_data.model_dump())
        session.add(db_user_specific_data)
        session.commit()
        session.refresh(db_user_specific_data)
        return db_user_specific_data
    
    except Exception as e:
        pass

    finally:
        session.close()

def update_user_specific_data(user_id: int, data_id: str, new_data: Dict[str, Any]):
    """
    Updates a record of user specific data in the Database.

     Parameters:
    - `user_id` (int): Identifier for the user whose data needs to be updated.
    - `data_id` (str): Identifier for the specific data record to be updated.
    - `new_data` (Dict[str, Any]): Dictionary containing the new data to be applied.

    Returns:
    - None.
    """

    session = Session()
    try:
        db_user_specific_data = session.query(UserSpecificDataORM).filter_by(user_id=user_id, data_id=data_id).first()
        if db_user_specific_data:
            for key, value in new_data.items():
                setattr(db_user_specific_data, key, value)
            session.commit()
            session.refresh(db_user_specific_data)
        return db_user_specific_data
    finally:
        session.close()

def delete_user_specific_data(user_id: int, data_id: str):
    """
    Deletes a record of user-specific data from the Database.

    Parameters:
    - `user_id` (int): Identifier for the user whose data needs to be deleted.
    - `data_id` (str): Identifier for the specific data record to be deleted.

    Returns:
    - None: The function does not return anything; it deletes the specified data from the Database.
    """

    session = Session()
    try:
        db_user_specific_data = session.query(UserSpecificDataORM).filter_by(user_id=user_id, data_id=data_id).first()
        if db_user_specific_data:
            session.delete(db_user_specific_data)
            session.commit()
        return db_user_specific_data
    
    except Exception as e:
        raise ValueError("Not found.")

    finally:
        session.close()

def retrieve_existing_data_categories(user_id: int) -> List[str]:
    """
    Retrieves a list of existing data categories associated with a user.

    Parameters:
    - `user_id` (int): Identifier for the user whose data categories are to be retrieved.

    Returns:
    - List[str]: A list of strings representing existing data categories for the specified user.
    """
    db = Session()
    try:
        categories = (
            db.query(UserSpecificDataORM.data_category)
            .filter_by(user_id=user_id)
            .distinct()
            .all()
        )
        return [category[0] for category in categories]
    finally:
        db.close()

def retrieve_category_content(user_id: int, data_category: str) -> List[UserSpecificData]:
    """
    Retrieves all the records associated to a specific user id and data_category key.

    Parameters:
    - `user_id`(int): Identifier for the user.
    - `data_category`(str): The label identifier of the data category to retrieve ('reminders', 'preferences', etc.)

    Returns:
    - A list of records matching the criteria.
    """

    # Create a session to interact with the database
    session = Session()

    try:
        # Query the UserSpecificDataORM table for the specific user and category
        category_data = session.query(UserSpecificDataORM).filter_by(user_id=user_id, data_category=data_category).all()

        # Convert the query result to a list of Pydantic objects
        pydantic_objects = [UserSpecificData(**dict(data.__dict__)) for data in category_data]

        return pydantic_objects

    finally:
        # Close the session when you're done
        session.close()

def retrieve_content_by_id(user_id: int, data_id: str) -> UserSpecificData: 
    """
    Retrieves a record associated to a specific user id and data_id key.

    Parameters:
    - `user_id`(int): Identifier for the user.
    - `data_id`(str): The identifier of the data element to retrieve (it is a string repr. of a UUID4)

    Returns:
    - The requested data record or None if not found.
    """

    # Create a session to interact with the database
    session = Session()

    try:
        # Query the UserSpecificDataORM table for the specific user and data_id
        data = session.query(UserSpecificDataORM).filter_by(user_id=user_id, data_id=data_id).first()

        if data:
            # If data is found, return the content
            return UserSpecificData(**dict(data.__dict__)) 
        else:
            # If no data is found, return None or raise an exception based on your needs
            return None
    finally:
        # Close the session when you're done
        session.close()
