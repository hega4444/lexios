from typing import List

from lexios.integration.plugin import PluginTemplate

class DatabaseConnection(PluginTemplate):

    def __init__( 
        self,
        engine: str = 'PostgreSQL',
        database_name: str = None,
        admin_user: str = None,
        admin_pass: str = None,
        host: str = None,
        port: int = None,
        test_mode: bool = False,
        load_setup_script = False,
        secutiry_object = None,
        load_files: List[str] = None,
        force: bool = False,
    ):
        
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
        super().__init__(plugin_name= "DatabaseConnection")

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


