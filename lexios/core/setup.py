# lexios_setup.py

from uuid import uuid4

from lexios.core.common_tools import *
from lexios.core.lexios_main import LexiOS_Backend
# Appends the builtin commands of lexi as baseline

def _append_basic_IO(lexi: LexiOS_Backend):
    """
    Appends the basic commands for time and location, Internet search, and 
    updated prices and weather data.
    
    """
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

            schedule_tasks = LexiExternalCommand(
                    LexiTaskScheduler.schedule_new_task, 
                    requires_dynamic_object=LexiTaskScheduler,
                    show_return_to_user=False,
            )
            # Create a required scope
            schedule_tasks.add_consent_scope(
                scope_name="create_reminder",
                template='Schedule this action: "{description}"',
                vars=["description"],
            )

            lexi.append_command(schedule_tasks)
        
        if USER_DATA_MANAGER:

            # This component handles the user specif data, preferences, rules for
            # automating their requests. It also supports other services built on 
            # top of it, like reminders. It offers a safe storage place for new 
            # functionalities to store user related data.
            from lexios.core.builtin.engines.userDataEngine import UserDataManager

            # Google suite for Email and Calendar built-in tools
            from lexios.core.builtin.functions.calendar import GoogleCalendar
            from lexios.core.builtin.functions.email import GmailClient 
            
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
            raise LexiException(f"Problem setting up builtin features: {e}")

def _set_up_db_integration(lexios: LexiOS_Backend):
    # Sets up the integration steps for exchanging data with a local database

    from lexios.core.external_command import LexiExternalCommand

    if DATABASE_TOOLS:

        # Include LexiDatabase - Full access to Postgress SQL and Linear Regression/ ML tools for DM 
        from lexios.core.builtin.engines.SQLEngine import LexiDatabase

        try:

            for db_connection in lexios.databases or []:
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
                    if lexios.sql_engine.table_analyser:
                        # The SQL Engine provides a customized external command with additional content when executed
                        lexios.append_command(
                            lexios.sql_engine.table_analyser
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
                raise LexiException(f"Problem setting up SQL / Mining features: {e}")

def _set_up_virtual_agents_and_routing(lexi: LexiOS_Backend):
    """ 
    Set up the virtual agents functionality
    Automatic routing for switching between assistants
    """
    try:
        from lexios.core.external_command import LexiExternalCommand

        if lexi.virtual_agents:

            # Include Virtual Agents component
            from lexios.core.agents_router import AgentsRouter
            from lexios.integration.virtual_agents import VirtualAgent

            # Retrieve the current list of agents
            agents = AgentsRouter(lexi.virtual_agents)._virtual_agents

            # Create root assistant
            Lexi = VirtualAgent(

                name= LEXI_ALIAS,
                as_user_id=ROOT_ID,
                roles=['root'],
                instructions= lexi.instructions,
                can_be_cloned=True,
                can_be_replaced=True, 
                retrieval=True,
                interpreter=True,  
            )
            # For some reason (yet to be understood), agents list gets updated just by invoking the contructor
            # of Virtual Agent, probably because the Integration Manager is collecting the object. This was
            # a good unexpected side effect. 
  
            # Store the initiated router 
            lexi.agents_router = AgentsRouter(agents) 

            # Append routing to root assistand command
            lexi.append_command(LexiExternalCommand(
                AgentsRouter.route_to_main_assistant,
                requires_dynamic_object= AgentsRouter,
                before=f"{LEXI_ALIAS} is gonna be here in a second ..."
                ),
                required_by_lexi= True,
            )

            # Append List virtual agents command
            lexi.append_command(LexiExternalCommand(
                 AgentsRouter.list_virtual_agents,
                 requires_dynamic_object=AgentsRouter,
                ),
                required_by_lexi= True,
            )

            # Define Route message command
            route_message_to_agent = LexiExternalCommand(
                AgentsRouter.route_to_virtual_agent,
                requires_dynamic_object= AgentsRouter,
            )

            # Update command specs to include the agents names
            route_message_to_agent.add_key_spec(
                param="virtual_agent_name", 
                tag="enum", 
                value= AgentsRouter()._agent_names,
            )

            # Append route message command
            lexi.append_command(
                command=route_message_to_agent,
                required_by_lexi=True
            )

            # Custom sorting function
            def custom_sort(virtual_agent):
                return virtual_agent.name.lower() != LEXI_ALIAS.lower() , virtual_agent.name

            # Sort the list to keep Lexi (or alias) on top
            sorted_agents = sorted(lexi.virtual_agents, key=custom_sort)

            # Get a shorter version of the setting
            CONNECT_ALL = LEXI_VIRTUAL_AGENTS_CONNECT_ALL

            agent: VirtualAgent
            # Initate main instances for each agent  
            for agent in sorted_agents:

                try:

                    for other_agent in sorted_agents:
                        # Avoid connect the agent to itself
                        if agent.name != other_agent.name:

                            # Check if there is a conflicting configuration for the nodes
                            if ((agent.get_neighbors() or CONNECT_ALL) and not agent.can_be_replaced):
                                    # Friendly message
                                    LexiWarning(f"Virtual Agent: {agent.name}. Conflicting configuration. Either setting LEXI_VIRTUAL_AGENTS_CONNECT_ALL "
                                                "is True or the agent has explicitly defined neighbour agents, "
                                                "however attribute 'can_be_reaplaced' was set to False.", WARNING)
                                               
                                    # Facts
                                    raise LexiException
                            
                            # If connect_all is enabled or the agent 
                            if (CONNECT_ALL or
                                  # included a reference to the next agent
                            other_agent in agent.get_neighbors() ):

                                # Add relationship
                                agent.link_to_agent(other_agent)

                    # Start virtual agent service
                    try:
                        # Register a token for the agent
                        agent.id = uuid4()

                        # Build service thread
                        service = lexi._build_thread(
                            user_id= agent.as_user_id,
                            conversation_id= str(agent.channel),
                            virtual_agent= agent,
                        )

                        # Load the thread on the virtual agent
                        agent.main_thread = service

                        # Start the service
                        agent._start_service()

                        LexiLogging(f"VirtualAgent {agent.name: <10} channel @{agent.channel} . Service started")

                    except Exception as e:
                         LexiException(f"Service for virtual Agent {agent.name} could not be started. {e}")           

                except Exception as e:
                     LexiException(f"Lexios Setup. At loading the routes: {e}", WARNING)   
        
    except Exception as e:
            raise LexiException(f"Lexios, at setup virtual agents: {e}.")
    



    