# database/make.py

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from lexios.core.common_tools import *
from lexios.core.builtin.engines.SQLEngine import SimpleSQL
from lexios.database.setup import Base
from lexios.database.users import User
from lexios.database.roles import Role

# This function is called by the admin tool when creating a new project to have a separate database
def initial_database_setup(database_name="lexi_template", remake: bool = False):
    """
    This function is called by the admin tool when creating a new project to have a dedicated/pre-built database.

    Parameters:
    - `database_name` (str): By default it will become the project's name.
    - `remake` (bool): (default) False. If True it erases any previous version of the Database.
    """

    try:
        # Determine the database name
        db_name = database_name.lower() + '_database'

        # Define the database URI
    # Define the database URI
        DATABASE_URI = (
            f"{LEXI_DATABASE_ENGINE.lower()}://{LEXI_DB_ADMIN_USER}:{LEXI_DB_ADMIN_PASS}@"
            f"{LEXI_DATABASE_HOST}/{db_name}"
        )

        # Create the database engine
        # Set the isolation level to "Read committed" to improve accuracy and consistency
        engine = create_engine(DATABASE_URI, isolation_level="READ COMMITTED")

        # Define a sessionmaker with the engine details to interact with the database
        Session = sessionmaker(bind=engine)

        # Create and open a session
        session = Session()

        options = {
            "force" : TEST_MODE,
            "db_name" : db_name,
            "user": LEXI_DB_ADMIN_USER,
            "password" : LEXI_DB_ADMIN_PASS,
            "port": LEXI_DB_ADMIN_PORT,
            "load_setup_script": "",
            "drop_after" : remake,  # Set it True to DROP the database, False for creating it again.
        }

        # Run SimpleSQL context manager with the above settings, if remake is true it will DROP the database
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
        root_name=  str(database_name) + "_admin"

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

    except IntegrityError as e :
        raise ValueError(f"The database '{database_name}' already exists. For rebuilding it, use command lexios-admin rebuild <project_name>")
    except Exception as e:
        raise ValueError(f"Unexpected exception: {e}")


# Lexi internal database set up -----------------------------------------------------------------------------------------------------#

if __name__ == '__main__':

    initial_database_setup(database_name="test_hernan", remake=True)

    print("models generated.")

# Lexi internal database set up -----------------------------------------------------------------------------------------------------#
