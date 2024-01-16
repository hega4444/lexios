# lexios_builtin.py

from lexios.globals import ROOT_ID
from lexios.settings.main import *
from lexios.core.logger import CustomLogger
from lexios.core.lexios_main import LexiOS_Backend

# Appends the builtin commands of lexi as baseline

def append_basic_IO(lexi: LexiOS_Backend):

    # External commands definition
    from lexios.core.external_command import LexiExternalCommand

    # Append internal basic I/O methods / protocols

    # Scheduler creates a clock for managing events, run tasks in background and support
    # other components like reminders, automatic replies and automated actions.
    from lexios.core.task_scheduler import LexiTaskScheduler

    # Search Engine is the base component for creating context for the model
    from lexios.core.builtin.engines.searchEngine import SearchEngine

    try:

        # Time / Location:
        lexi.append_command(
            LexiExternalCommand(
                func=SearchEngine.time_and_location,
                show_return_to_user=False
            ),
            required_by_lexi = True,
        )

        if SEARCH_ENGINE:
            # Search on the Internet:
            lexi.append_command(
                LexiExternalCommand(
                    func=SearchEngine.bing_search,
                    printer=SearchEngine.bing_search_printer,
                    show_return_to_user=False,
                )
            )
            # Extract URL content:
            lexi.append_command(
                LexiExternalCommand(
                    SearchEngine.read_external_url_content, show_return_to_user=False
                )
            )
            # Read a RSS channel:
            lexi.append_command(
                LexiExternalCommand(SearchEngine.read_rss, show_return_to_user=False)
            )
            # Check Stock prices:
            lexi.append_command(
                LexiExternalCommand(SearchEngine.get_stock_price_by_symbol, show_return_to_user=False)
            )
            # Check Weather Forecast:
            lexi.append_command(
                LexiExternalCommand(
                    SearchEngine.get_weather_forecast, 
                    show_return_to_user=False,
                    before="Weather data by Open-Meteo.com")
            )
            # Schedule an action:
            lexi.append_command(
                LexiExternalCommand(
                    LexiTaskScheduler.schedule_new_action, show_return_to_user=False
                )
            )
        
        if USER_DATA_MANAGER:

            # This component handles the user specif data, preferences, rules for
            # automating their requests. It also supports other services built on 
            # top of it, like reminders. It offers a safe storage place for new 
            # functionalities to store user related data.
            from lexios.core.builtin.engines.userDataEngine import UserDataManager

            # Google suite for Email and Calendar built-in tools
            from lexios.core.builtin.functions.calendar import GoogleCalendar
            from lexios.core.builtin.functions.email import GmailClient 

            # Create reminders, alarms, alerts
            create_reminder = LexiExternalCommand(
                    UserDataManager.schedule_reminder,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            lexi.append_command(create_reminder)

            create_reminder.add_consent_scope(
                scope_name="create_reminder",
                template='Create reminder with subject "{subject}"',
                vars=["subject"],
            )

            # Delete reminders, alarms, alerts
            lexi.append_command(
                LexiExternalCommand(
                    UserDataManager.delete_reminder,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Create other user specific data
            lexi.append_command(
                LexiExternalCommand(
                    UserDataManager.add_user_specific_data,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Retrieve the current categories for user_specific_data
            lexi.append_command(
                LexiExternalCommand(
                    UserDataManager.retrieve_user_data_categories,
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            # Retrieve all the content related to a certain category
            lexi.append_command(
                LexiExternalCommand(
                    UserDataManager.read_user_data_category_content, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            # Retrieve a specific data element by its data_id
            lexi.append_command(
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
            lexi.append_command(create_email_rule)

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

            lexi.append_command(send_email_command)

            # Seacrh for a contact
            lexi.append_command(
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
            lexi.append_command(new_event)

            new_event.add_consent_scope(
                scope_name="new_calendar_event",
                template='Create a Google Calendar event with subject "{summary}" at: {start_datetime}',
                vars=["summary", "start_datetime"],
            )
    
    except Exception as e:
        with CustomLogger("lexios") as log:
            log.error(f"Problem setting up builtin features: {e}")

def set_up_db_integration(lexios: LexiOS_Backend):
    # Sets up the integration steps for exchanging data with a local database

    from lexios.core.external_command import LexiExternalCommand

    if DATABASE_TOOLS:

        # Include LexiDatabase - Full access to Postgress SQL and Linear Regression/ ML tools for DM 
        from lexios.core.builtin.engines.SQLEngine import LexiDatabase

        try:

            for db_connection in lexios.databases:
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

def set_up_virtual_agents_and_routing(lexi: LexiOS_Backend):
    # Set up the virtual agents functionality
    # Automatic routing for switching between assistants

    try:
        from lexios.core.external_command import LexiExternalCommand

        if lexi.virtual_agents:

            # Include Virtual Agents component
            from lexios.integration.virtual_agents import VirtualAgentsRouter, VirtualAgent

            # Retrieve the current list of agents
            agents = VirtualAgentsRouter(lexi.virtual_agents)._virtual_agents

            # Create and append root assistant
            agents.append(VirtualAgent(

                name= LEXI_ALIAS,
                as_user_id=ROOT_ID,
                roles=['root'],
                instructions= lexi.instructions,
                can_be_cloned=True,
                can_be_replaced=True, 
                retrieval=True,
                interpreter=True,  
            ))

            # Store the initiated router 
            lexi.agents_router = VirtualAgentsRouter(agents) 

            # Append routing to root assistand command
            lexi.append_command(LexiExternalCommand(
                VirtualAgentsRouter.route_to_main_assistant,
                requires_dynamic_object= VirtualAgentsRouter,
                ),
                required_by_lexi= True,
            )

            # Define Route message command
            route_message_to_agent = LexiExternalCommand(
                VirtualAgentsRouter.route_to_virtual_agent,
                requires_dynamic_object= VirtualAgentsRouter,
            )

            # Update command specs to include the agents names
            route_message_to_agent.add_key_spec(
                param="virtual_agent_name", 
                tag="enum", 
                value= VirtualAgentsRouter()._agent_names,
            )

            # Append command
            lexi.append_command(
                command=route_message_to_agent,
                required_by_lexi=True
            )

            agent: VirtualAgent
            # Initate main instances for each agent  
            for agent in lexi.virtual_agents:

                agent.start_service(lexi)
            
        
    except Exception as e:
        with CustomLogger("lexios") as log:
            log.error(f"Virtual Agents LexiOS setup: {e}")