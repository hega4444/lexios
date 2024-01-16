from lexios.database.models import Session, ScheduledTaskPydantic, ScheduledTaskORM

def save_scheduled_task_in_db(action: ScheduledTaskPydantic):
    # Function to add a scheduled task to the database
    session = Session()
    try:

        # Convert Pydantic instance to ORM instance
        task_orm = ScheduledTaskORM(**action.model_dump())

        # Save to the database
        session.add(task_orm)
        session.commit()
        
    except Exception as e:
        session.rollback()
    finally:
        # Close the session when you're done
        session.close()


def update_task_status(task_id, new_status, new_start_at=None, new_end_at=None, new_repeat_each=None, new_arguments=None):
    # Function to update the status (and optionally start_at) of a task
    session = Session()
    try:
        update_data = {'status': new_status}
        
        if new_start_at is not None:
            update_data['start_at'] = new_start_at
        if new_end_at is not None:
            update_data['end_at'] = new_end_at
        if new_repeat_each is not None:
            update_data['repeat_each'] = new_repeat_each
        if new_arguments is not None:
            update_data['arguments'] = new_arguments

        session.query(ScheduledTaskORM).filter_by(task_id=task_id).update(update_data)
        session.commit()

    except Exception as e:
        session.rollback()
    finally:
        # Close the session when you're done
        session.close()

# Function to retrieve scheduled tasks
def get_all_scheduled_tasks():
   # Function to retrieve scheduled tasks
    session = Session()
    try:
        return session.query(ScheduledTaskORM).filter_by(status='scheduled').all()
    
    except Exception as e:
        session.rollback()
    finally:
        # Close the session when you're done
        session.close() 
