# Lexi Configuration file:
#-----------------------------------------------------------------------------------#

TEST_LOGIN_USER = 'user@example.com'
TEST_LOGIN_PASS = 'password'

OPENAI_KEY = "YOUR_KEY_HERE"

LEXI_ALIAS = "Lexi"
LEXI_GPT_MODEL = "gpt-3.5-turbo-1106"
LEXI_GPT_TEMPERATURE = 0.8

UPLOAD_FOLDER = 'temp/uploads'
DOWNLOAD_FOLDER = 'temp/downloads'
TIME_ZONE = "Europe/Berlin"
TIME_DELTA = 0 # Adjust time zone if neccesary (min)
LOG_FOLDER = "<new>/backend_logs"

# Design settings 
NEW_CHAT_PROMPT = "new chat.."
DEFAULT_THEME_TEXT_COLOR = '#FDFDF6'
DEFAULT_THEME_BACKGROUND_COLOR = '#C4660E'

# Dev tools
TEST_MODE = True
LOGS_VERBOSITY_LEVEL = "DEBUG" #accepcted: DEBUG, INFO, WARNING, ERROR, CRITICAL
CONSOLE_VERBOSITY_LEVEL = "ERROR"

# Lexi_app server settings
#-----------------------------------------------------------------------------------#
SERVER_IP = '127.0.0.1' #'192.168.1.108'
SERVER_PORT = 8000
ENABLE_SSL = False
SSL_KEYFILE = "<new>/ssl/key.pem"
SSL_CERTFILE = "<new>/ssl/cert.pem"

# Message broker - Redis
#-----------------------------------------------------------------------------------#
"redis-server"
BROKER_PATH = "redis-server"
BROKER_URL = "redis://localhost:6379/0"
RESULT_BACKEND = "redis://localhost:6379/0"
DEBUG_MODE = True

# Components
#-----------------------------------------------------------------------------------#
SEARCH_ENGINE = True
DATABASE_TOOLS = True
MINING_TOOLS = True
USER_DATA_MANAGER = True

# Inner Lexi database connection
LEXI_DATABASE_ENGINE = 'PostgreSQL'
LEXI_DATABASE_HOST = 'localhost'
LEXI_DATABASE_NAME = 'lexi_database'
LEXI_DB_ADMIN_USER = 'postgres'
LEXI_DB_ADMIN_PASS = 'postgres'
LEXI_DB_ADMIN_PORT = 5432

LEXI_AUTOMATIC_DB_SETUP = False  # True will wipe database !!!

#-----------------------------------------------------------------------------------#
# Google Sign-in Cdentials
# Google API credentials
CLIENT_ID = "265411892111-kdm2k7agd7mj39a8pr9dq9g93lpf9ljk.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = 'https://localhost:5000/google_callback'  # Replace with your actual redirect URI
GOOGLE_ID_SECURE_KEY = b'kh8cmWibLiiDbihxp-XtCq6TLOj6Kog3YMLubh9F9S0='


