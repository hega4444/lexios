# roles.py
from typing import List

from lexios.database.setup import Session
from lexios.database.models import Role


def get_assigned_roles_by_user_id(user_id: int) -> List[Role]:
    """
    Retrieve the roles assigned to a user_id.
    
    Parameters:
    - `user_id` (int): User identification.
    - `role_name` (str): Role to be assigned.
    """
    session = Session()
    try:
        return session.query(Role).filter_by(user_id=user_id).all()
    
    finally:
        # Close the session when you're done
        session.close() 

def assign_role(user_id: int, role_name: str, read: bool, write: bool, execute: bool):
    """
    Assign a role to a user_id
    
    Parameters:
    - `user_id` (int): User identification.
    - `role_name` (str): Role to be assigned.
    - `read`, `write`, `execute` (bool): Permissions assigned within the role.
    
    """
    try:
        session = Session()

        new_role = Role(
            user_id=user_id,
            name=role_name,
            read=read,
            write=write,
            execute=execute,
        )

        # Query the database to check if the user_id-role pair already exists
        existing_role = session.query(Role).filter_by(user_id=user_id, name=role_name).first()

        if existing_role:
            # Update the existing role's attributes
            existing_role.user_id = user_id
            existing_role.name = role_name
            existing_role.read = read
            existing_role.write = write
            existing_role.execute = execute

            session.commit()  # Commit the changes
        else:
            session.add(new_role)
            session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()

def delete_role(user_id: int, role_name: str):
    """ 
    Delete a role assigned to a user_id

    Parameters:
    - `user_id` (int): User identification.
    - `role_name` (str): Role to be deleted from the user.
    """
    try:
        session = Session()

        # Query the database to get the role to delete
        role_to_delete = session.query(Role).filter_by(user_id=user_id, name=role_name).first()

        if role_to_delete:
            session.delete(role_to_delete)
            session.commit()
        else:
            print(f"Role with user_id={user_id} and name={role_name} not found.")
    except Exception as e:
        session.rollback()
        print(f"Error deleting role: {e}")
    finally:
        session.close()


