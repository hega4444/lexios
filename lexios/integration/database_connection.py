from typing import List

from lexios.integration.plugin import PluginTemplate

class DatabaseConnection(PluginTemplate):
    """
    A class representing a database connection.

    Parameters:

    `engine` (str): The type of database engine (default is 'PostgreSQL').
    `database_name` (str): The name of the database.
    `admin_user` (str): The username for administrative access.
    `admin_pass` (str): The password for administrative access.
    `host` (str): The host address of the database server.
    `port` (int): The port number for the database connection.
    `test_mode` (bool): A flag indicating whether to use the database in test mode (default is False).
    `load_setup_script` (bool): A flag indicating whether to load the setup script (default is False).
    `security_object`: Can be used to register the database and reestric the access to different users.
    `load_files` (List[str]): A list of files to load into the database.
    `force` (bool): Forces the creation of the DB and deletes after finishing execution, only for test mode. (default is False).

    """

    def __init__( 
        self,
        database_name: str,
        admin_user: str,
        admin_pass: str,
        host: str,
        port: int,
        engine: str = 'PostgreSQL',
        test_mode: bool = False,
        load_setup_script = False,
        secutiry_object = None,
        load_files: List[str] = None,
        force: bool = False,
        
    ) -> 'DatabaseConnection':
        
        # Save settings
        self.settings =  {
                    "test_mode" : test_mode,
                    "db_name" : database_name,
                    "load_setup_script": load_setup_script,
                    "db_host" : host, 
                    "db_user" : admin_user,
                    "db_password" : admin_pass,
                    "db_port": port,
                    "security_object" : secutiry_object,
                    "load_files" : load_files,
                    "force": force,
            }

        # Keep a list of files to load in the database at startup
        self.files = load_files

        # Call construtor of the PluginTemplate class
        super().__init__(plugin_name= DatabaseConnection.__name__)

    def load_file(self, filename, tablename):
        # Append file to inner state
        if self.files:
            self.files.append((filename, tablename))
        else:
            self.files = [(filename, tablename)]

        if self.settings['load_files']:
             self.settings['load_files'].append((filename, tablename))
        
        else:
             self.settings['load_files'] = [(filename, tablename)]


