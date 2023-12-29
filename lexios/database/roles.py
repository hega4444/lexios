from lexios.database.models import Session, Role

# Function to retrieve scheduled tasks
def get_assigned_roles_by_user_id(user_id: int):
   # Function to retrieve scheduled tasks
    session = Session()
    try:
        return session.query(Role).filter_by(user_id=user_id).all()
    
    finally:
        # Close the session when you're done
        session.close() 
