# lexios_builtin.py

from lexios.settings.main import *
from lexios.core.external_command import LexiExternalCommand
from lexios.core.logger import CustomLogger

# Appends the builtin commands of lexi as baseline

# Lexi's Engines 
from lexios.core.builtin.engines.SQLEngine import LexiDatabase
from lexios.core.builtin.engines.searchEngine import SearchEngine
from lexios.core.builtin.engines.userDataEngine import UserDataManager
from lexios.core.task_scheduler import LexiTaskScheduler

# Built-in tools
from lexios.core.builtin.functions.calendar import GoogleCalendar
from lexios.core.builtin.functions.email import GmailClient 


def append_basic_IO(lexios):

    # Append internal basic I/O methods / protocols

    try:

        # Time / Location:
        lexios.append_command(
            LexiExternalCommand(
                func=SearchEngine.time_and_location,
                show_return_to_user=False
            )
        )

        if SEARCH_ENGINE:
            # Search on the Internet:
            lexios.append_command(
                LexiExternalCommand(
                    func=SearchEngine.bing_search,
                    printer=SearchEngine.bing_search_printer,
                    show_return_to_user=False,
                )
            )
            # Extract URL content:
            lexios.append_command(
                LexiExternalCommand(
                    SearchEngine.access_website_content, show_return_to_user=False
                )
            )
            # Read a RSS channel:
            lexios.append_command(
                LexiExternalCommand(SearchEngine.read_rss, show_return_to_user=False)
            )
            # Check Stock prices:
            lexios.append_command(
                LexiExternalCommand(SearchEngine.get_stock_price_by_symbol, show_return_to_user=False)
            )
            # Check Weather Forecast:
            lexios.append_command(
                LexiExternalCommand(
                    SearchEngine.get_weather_forecast, 
                    show_return_to_user=False,
                    before="Weather data by Open-Meteo.com")
            )
            # Schedule an action:
            lexios.append_command(
                LexiExternalCommand(
                    LexiTaskScheduler.schedule_new_action, show_return_to_user=False
                )
            )
        
        if USER_DATA_MANAGER:
            # Create reminders, alarms, alerts
            create_reminder = LexiExternalCommand(
                    UserDataManager.schedule_reminder,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            lexios.append_command(create_reminder)

            create_reminder.add_consent_scope(
                scope_name="create_reminder",
                template='Create reminder with subject "{subject}"',
                vars=["subject"],
            )

            # Delete reminders, alarms, alerts
            lexios.append_command(
                LexiExternalCommand(
                    UserDataManager.delete_reminder,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Create other user specific data
            lexios.append_command(
                LexiExternalCommand(
                    UserDataManager.add_user_specific_data,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Retrieve the current categories for user_specific_data
            lexios.append_command(
                LexiExternalCommand(
                    UserDataManager.retrieve_user_data_categories,
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            # Retrieve all the content related to a certain category
            lexios.append_command(
                LexiExternalCommand(
                    UserDataManager.read_user_data_category_content, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            # Retrieve a specific data element by its data_id
            lexios.append_command(
                LexiExternalCommand(
                    UserDataManager.retrieve_user_data_content_by_id, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            
            # Create automated email responses 
            create_email_rule = LexiExternalCommand(
                    UserDataManager.create_automated_email_response_rule, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="gmail_access",
                    
                )
            lexios.append_command(create_email_rule)

            create_email_rule.add_consent_scope(
                scope_name="create_email_rules",
                template="Generate automatic responses to emails from :{sender_email_address}.",
                vars=["sender_email_address"]
            )

            # Send email
            send_email_command = LexiExternalCommand(
                    GmailClient.send_email, 
                    requires_dynamic_object=GmailClient, 
                    show_return_to_user=False,
                    session_data_check="gmail_access",
                )
            
            # Add a dynamic consent scope
            send_email_command.add_consent_scope(
                scope_name= "send_email_response",
                template= "Send automated e-mail to '{to_address}'.",
                vars = ["to_address"],
            )

            lexios.append_command(send_email_command)

            # Seacrh for a contact
            lexios.append_command(
                LexiExternalCommand(
                    GmailClient.search_email_by_name, 
                    requires_dynamic_object=GmailClient, 
                    show_return_to_user=False,
                    session_data_check="gmail_access",
                )
            )
            # Create automated email responses
            new_event =  LexiExternalCommand(
                    GoogleCalendar.create_google_calendar_event, 
                    requires_dynamic_object=GoogleCalendar, 
                    show_return_to_user=False,
                    session_data_check="google_calendar_access",
                )
            lexios.append_command(new_event)

            new_event.add_consent_scope(
                scope_name="new_calendar_event",
                template='Create a Google Calendar event with subject "{summary}" at: {start_datetime}',
                vars=["summary", "start_datetime"],
            )
    
    except Exception as e:
        with CustomLogger("lexios") as log:
            log.error(f"Problem setting up builtin features: {e}")

def set_up_db_integration(lexios):
    # Sets up the integration steps for exchanging data with a local database

    if DATABASE_TOOLS:
        try:

            for db_connection in lexios.databases_list:
                lexios.sql_engine = LexiDatabase(**db_connection.settings)

            if lexios.sql_engine:
            # Get a Database Entity Relationship Diagram - ERD
                lexios.append_command(
                    LexiExternalCommand(
                        LexiDatabase.retrieve_database_erd,
                        requires_object=lexios.sql_engine,
                        show_return_to_user= False
                    )
                )

                # Execute queries in the Database & exctract results
                lexios.append_command(
                    LexiExternalCommand(
                        LexiDatabase.execute_fetch_sql_query,
                        requires_object=lexios.sql_engine,
                        show_return_to_user= False
                    )
                )

                if MINING_TOOLS:
                    # Execute queries in the Database & exctract results
                    lexios.append_command(
                        LexiExternalCommand(
                            LexiDatabase.show_predictive_models_for_table,
                            requires_object=lexios.sql_engine,
                            show_return_to_user= False
                        )
                    )
                    
                    # Run automated data analysis on tables
                    if lexios.sql_engine.table_analyzer:
                        # The SQL Engine provides a customized external command with additional content when executed
                        lexios.append_command(
                            lexios.sql_engine.table_analyzer
                        )

                    # Make predictions using a model
                    lexios.append_command(
                        LexiExternalCommand(
                            LexiDatabase.make_prediction_using_model,
                            requires_object=lexios.sql_engine,
                            show_return_to_user= False
                        )
                    )   

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"Problem setting up SQL / Mining features: {e}")
