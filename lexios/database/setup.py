# database/setup.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from lexios.core.common_tools import *

# ----------------------------------------------------------------------------------- #
"""Here is defined the database connection for the current running project."""

# Define a common base class for the ORM models
Base = declarative_base()

# Define the database URI
DATABASE_URI = (
    f"{LEXI_DATABASE_ENGINE.lower()}://{LEXI_DB_ADMIN_USER}:{LEXI_DB_ADMIN_PASS}@"
    f"{LEXI_DATABASE_HOST}/{LEXI_DATABASE_NAME}"
)


# Create the database engine:

# Set isolation level to "Read committed" to improve accuracy and consistency
engine = create_engine(DATABASE_URI, isolation_level="READ COMMITTED")

# Define a sessionmaker with the engine details to interact with the database
Session = sessionmaker(bind=engine)

# ----------------------------------------------------------------------------------- #



