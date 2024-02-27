from prettytable import PrettyTable
import psycopg2
import datetime
import csv
import sys
import json
from decimal import Decimal
from stringcolor import cs


from lexios.settings.main import *
# Tools
from lexios.core.common_tools import *

from lexios.core.builtin.engines.miningEngine import ANN_MODEL, LINEAR_MODEL, SimpleMiner_ANN, SimpleMiner_Linear

from lexios.core.external_command import LexiExternalCommand


# Print SQL query results in the command line // Mostly here to keep working SimpleSQL class without much interference, needs revision

class printSql():

    def __init__(self, cursor) -> None:
        self.cur = cursor
        self.saved_options = None
    
    def execute(self, query, *args):
        try:
            return self.cur.execute(query, args)
        except Exception as e:
            print(cs(f"WARNING - SQL syntax error: {e}", color="Red"))
 
    def load_style(self, options):
        self.saved_options = options
    
    def reset_style(self):
        self.saved_options = {}
        
    def print(self, sql_block="", title="", color = None, options = None):
        #Prints a table with the results of a query

        #Execute the query
        try:
            self.cur.execute(sql_block)
        except Exception:
            self.cur.execute("rollback;")
            try:
                self.cur.execute(sql_block)
            except Exception:
                pass
                
        try:
            #Get data
            data = self.cur.fetchall()
            
            #Get the titles of that specifc query
            column_names = [desc[0].capitalize() for desc in self.cur.description]

        except Exception:
            data = [['No data to show.']]
            column_names = ['--']
        
        if options == None and self.saved_options:
            options = self.saved_options
        
        if color == None and (options==None or 'color' not in options) and \
            self.saved_options and 'color' in self.saved_options:
            color = self.saved_options['color']
        elif color == None and options and 'color' in options:
            color = options['color']

        if color:
            if options:
                options['color'] = color
            else:
                options = {'color': color}

        #if isinstance(color, str):
        #    options['color'] = color

        if options:
            table = PrettyTable(**options)
            
        else:
            table = PrettyTable()
        table.field_names = column_names
        for row in data:
            table.add_row(row)
        print(cs(f"{title}", color if color else f"{title}:"))
        print(table)
    
# SimpleSQL Class // manages the connection to the DB and creates a python friendly access to it

class SimpleSQL():
    """
    This is a simple class to open/ connect (or create if does not exists) to a Database and query it without manually handling connections.
    """
    def __init__(self, db_name = None, force = True, load_setup_script = None, drop_after = False, user = None, password = None, port = None) -> None:

        self.db_name = db_name
        self.force = force
        self.conn = None
        self.cur = None
        self.printer = None
        self.drop_after = drop_after
        self.load_file = load_setup_script
        self.interface = None

        # Connection settings
        self.user = user
        self.password = password
        self.port = port
    
    def connect_to_postgres(self):
        #Connect to posgress as ADMIN to access and connect with the DB
        return psycopg2.connect(dbname='postgres',
                                user='postgres',
                                password='postgres',
                                host='localhost',
                                port=5432)

    def create_database(self):
        #Method to create new DB (in case it does not exists) 
        conn = self.connect_to_postgres()
        conn.autocommit = True
        cursor = conn.cursor()
        try:
            cursor.execute(f'CREATE DATABASE {self.db_name}')
        except psycopg2.Error as e:
            print(f'Failed to create DB. {e}')
            return None
        
        cursor.close()
        conn.close()
    
    def drop_database(self, msg = True):
        #Method to drop new DB (in case it was just for a demo / test) 
        conn = self.connect_to_postgres()
        conn.autocommit = True
        cursor = conn.cursor()
        try:
            cursor.execute(f'DROP DATABASE {self.db_name}')
        except psycopg2.Error as e:
            if msg is True:
                print(f'Failed at deleting DB {self.db_name}. {e}')
            return None
        
        cursor.close()
        conn.close()
        
    def connect_to_database(self, user='postgres', password='postgres', port=5432 ):
        #Connect to database
        try:
            connection = psycopg2.connect(dbname=self.db_name,
                                    user= user,
                                    password= password,
                                    host='localhost',
                                    port= port)
            
            return connection

        except Exception:
            if self.force:
                try:
                    self.create_database() #database not found and force is True, then creates a new one
                except Exception:
                    print(cs(f"WARNING-simpleQL : Failing at creating Database {self.db_name}.", color="Red"))
                return psycopg2.connect(dbname=self.db_name,
                        user= user,
                        password= password,
                        host='localhost',
                        port= port)
            else:
                print(cs(f"WARNING-simpleQL : Database {self.db_name} does not exist.", color="Red"))
    
    def print(self, sql_block="", title="", color=None, options=None):  #revisar
        
        if not options:
            res = self.printer.print(sql_block, title, color)
        else:
            res = self.printer.print(sql_block, title, color, options)

        if "SELECT" not in sql_block.upper():   #probably an UPDATE or DELETE
            self.conn.commit()                  #commit changes just in case

        return res
    
    def execute(self, query, *args): #revisar
        try:
            res = self.cur.execute(query, args)
            
            if "SELECT" not in query.upper():   #probably an UPDATE or DELETE
                self.conn.commit()                  #commit changes just in case

            return res
        except Exception as e:
            print(cs(f"WARNING-simpleQL : {e}", color="Red"))
            if self.conn:
                self.conn.rollback()
          
    def run_file(self, file_name):
        try:
            with open(file_name, "r") as file:
                lines = file.readlines()
                sql_script_file = ''.join(lines)
        except FileNotFoundError:
            print(cs(f"WARNING-simpleSQL : file {file_name} not found.", color="Red"))
            return

        self.execute(sql_script_file)
    
    def check_table_exists(self, table_name):
        self.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s);", (table_name,))
        return self.cur.fetchone()[0]
    
    def get_table_names(self):
        self.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        try:
            return [row[0] for row in self.cur.fetchall()]
        except psycopg2.ProgrammingError as e:
            self.conn.rollback()
        return

    def get_table_name_from_oid(self, table_oid):
        self.cur.execute("""
            SELECT relname
            FROM pg_class
            WHERE oid = %s;
        """, (table_oid,))
        return self.cur.fetchone()[0]
        
    def get_primary_key_columns(self, table_name):
        self.cur.execute("""
            SELECT
                kcu.column_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
            WHERE
                tc.table_name = %s
                AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY
                kcu.ordinal_position;
        """, (table_name,))
        return [row[0] for row in self.cur.fetchall()]
    
    def print_tables_names(self):
        self.print("""SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;""", options={'align':'l', 'color':'Multi1'})
        
    def get_table_fields(self, schema_name, table_name, capitalize = True):
        self.execute(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = '{schema_name}'
                        AND table_name = '{table_name}';
            """)
        records = self.cur.fetchall()
        fields = [name[0] for name in records]

        if capitalize:
            fields = [f.capitalize() for f in fields]

        return fields

    def print_table_fields(self, table_name):
        try:
            self.print(f"""
                        SELECT c.column_name, c.data_type,
                            CASE WHEN k.column_name IS NOT NULL THEN 'Primary Key' ELSE '' END AS key_type
                        FROM information_schema.columns c
                        LEFT JOIN information_schema.key_column_usage k
                        ON c.column_name = k.column_name
                        AND c.table_name = k.table_name
                        AND c.table_schema = k.table_schema
                        WHERE c.table_name = '{table_name}';
                """, 
                title=f"\nTable {table_name} - Fields",
                options={'align' : 'l'})
        except Exception:
            pass
          
    def get_table_size(self, table_name):
        try:
            self.execute(f"""
                SELECT pg_size_pretty(pg_relation_size('{table_name}')) AS table_size;
                """)
            records = self.cur.fetchall()
            return records[0][0]
        except Exception:
            return 0
        
    def get_table_length(self, table_name):
        try:
            self.execute(f"""
                SELECT COUNT(*) FROM {table_name};
                """)
            records = self.cur.fetchall()
            return records[0][0]
        except Exception:
            return 0

    def preview(self):

        print(f'Preview of database {self.db_name}\n')
        tables = self.get_table_names()

        self.print_tables_names()
        
        if tables:
            for table in tables:
                self.print(f"SELECT * from {table} LIMIT 1;", title=f"Preview of table {table}:")
    

    def into_dict(self, sql_block):
        #Executes a SELECT query and saves it into a dictionary
        try:
            self.cur.execute(sql_block)
            records = self.cur.fetchall()
            #if len(records) == 0:
            #    return {}

            self.execute(sql_block)
            rows = self.cur.fetchall()
            #Get the titles of that specifc query
            column_names = [desc[0].capitalize() for desc in self.cur.description] 
            #column_names = [desc[0] for desc in self.cur.description] #capitalize was creating confussion in the pandas DF
            result = {}

            #Check for primary key:
            # Get the table name from the cursor description (assuming single table query)
            table_name = self.get_table_name_from_oid(self.cur.description[0].table_oid)
            pri_key = None
            pri_key = self.get_primary_key_columns(table_name)
            
            use_pri_key = False
            if pri_key[0] == column_names[0].lower():
                use_pri_key = True
                
            for n, row in enumerate(rows):
                new_record = {}
                for i, column_name in enumerate(column_names):
                    new_record[column_name] = row[i]                
                
                key = row[0] if use_pri_key is True else n

                result[key] = new_record #uses the row number for indexing the dictionary

            return result

        except Exception as e:
            return {}
        
    def create_table_from_dict(self, dictionary, table_name, create_pri_key = False):

        def data_type(var):

            if isinstance(var, str):
                return "VARCHAR"
            
            elif isinstance(var, int):
                return "INT"
            
            elif isinstance(var, float):
                return "DECIMAL"
            
            elif isinstance(var, bool):
                return "BOOLEAN"
            
            elif isinstance(var, datetime.datetime):
                return "TIMESTAMP"
            
            elif isinstance(var, datetime.date):
                return "DATE"
            
            elif isinstance(var, datetime.time):
                return "TIME"
                
        pri_key = []
        use_dictionary_values_as_key = False

        records = list(dictionary.values())
        sample = records[0]
        n_fields = len(sample)
        max_lenghts = [0] * n_fields

        create = False

        if self.check_table_exists(table_name) is not True: #only if table does not exist
            
            create = True
            for record in records:
                if len(record) != n_fields:
                    raise ValueError(cs(f"ERROR-simpleSQL : Dictionary records differ in column numbers.", color="Red"))

                #Verify if the first value can be used as primary key
                pri_key.append(list(record.values())[0])

                #Check for appropiate size of field
                for i, field_value in enumerate(record.values()):
                    #only for VARCHAR (for now)
                    if isinstance(field_value, str) and (l:=len(field_value)) > max_lenghts[i]:
                        max_lenghts[i] = l
            
            #Truncate size fields to a multiple of 10
            max_lenghts = [max + (10 - max % 10) if max > 0 else 0 for max in max_lenghts]

            if len(dictionary) == len(list(set(pri_key))):
                use_dictionary_values_as_key = True
            
            use_dictionary_values_as_key = use_dictionary_values_as_key and not create_pri_key

            try:
                column_names = list(sample.keys())
            except Exception:
                raise ValueError(cs(f"ERROR-simpleSQL : Dictionary format is incorrect.", color="Red"))

            #Begin to build the structure of the SQL statement 
            sql_create_block = f"CREATE TABLE {table_name} (\n"

            if use_dictionary_values_as_key:
                field_type = data_type(list(sample.values())[0])
                pri_key_def = f"{column_names[0].lower()} {field_type} PRIMARY KEY,\n"
                start = 1
            else:
                pri_key_def = "id INT PRIMARY KEY,\n"               #here we need to consider change to SERIAL and forget about numbering!!!!!
                start = 0
            
            sql_create_block += pri_key_def

            for i, field in enumerate(list(sample.values())):
                if i >= start:
                    field_type = data_type(field)
                    field_def = f"{column_names[i].lower()} "
                    if field_type == 'VARCHAR':
                        field_type += f'({max_lenghts[i]})'

                    field_def += f'{field_type}{"," if i<len(sample)-1 else ""} \n'

                    sql_create_block += field_def
            
            sql_create_block += ");"
            
            #Table creation ----------------------------------------------------------------

        for record in records:
            if len(record) != n_fields:
                raise ValueError(cs(f"ERROR-simpleSQL : Dictionary records differ in column numbers.", color="Red"))

            #Verify if the first value can be used as primary key
            pri_key.append(list(record.values())[0])

            #Check for appropiate size of field
            for i, field_value in enumerate(record.values()):
                #only for VARCHAR (for now)
                if isinstance(field_value, str) and (l:=len(field_value)) > max_lenghts[i]:
                    max_lenghts[i] = l
        
        #Truncate size fields to a multiple of 10
        max_lenghts = [max + (10 - max % 10) if max > 0 else 0 for max in max_lenghts]

        if len(dictionary) == len(list(set(pri_key))):
            use_dictionary_values_as_key = True

        try:
            column_names = list(sample.keys())
        except Exception:
            raise ValueError(cs(f"ERROR-simpleSQL : Dictionary format is incorrect.", color="Red"))

        #Begin to build the structure of the SQL statement 
        sql_create_block = f"CREATE TABLE {table_name} (\n"

        if use_dictionary_values_as_key:
            field_type = data_type(list(sample.values())[0])
            pri_key_def = f"{column_names[0].lower()} {field_type} PRIMARY KEY,\n"
            start = 1
        else:
            pri_key_def = "id INT PRIMARY KEY,\n"
            start = 0
        
        sql_create_block += pri_key_def

        for i, field in enumerate(list(sample.values())):
            if i >= start:
                field_type = data_type(field)
                field_def = f"{column_names[i].lower()} "
                if field_type == 'VARCHAR':
                    field_type += f'({max_lenghts[i]})'

                field_def += f'{field_type}{"," if i<len(sample)-1 else ""} \n'

                sql_create_block += field_def
        
        sql_create_block += ");"
        
        #Table creation
        if self.check_table_exists(table_name) is not True: #only if table does not exist

            try:  
                self.execute(sql_create_block)

            except Exception as e:
                print(cs(f"WARNING - SQL syntax error: {e}", color="Red"))
        
            
        #Check if the sample record matches number of fields and types
        self.cur.execute(f"""SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}';
                        """)

        table_details = self.cur.fetchall()
        column_names = list(sample.keys())
        sample = list(sample.values())
        #check if table has at least one record to compare

        if len(table_details) == len(sample):  #dictionary has correct number of fields
            start = 1
        elif len(table_details) == len(sample) + 1: #additional index probably
            start = 0
        else:
            print(cs(f"WARNING-simpleSQL : Dictionary fields do not comply with table.", color="Red"))
            return

        next_index = 0
        if not create and start == 0: #find last record to update index:
            self.cur.execute(f"SELECT max(id) FROM {table_name} LIMIT 1;")
            try:
                max_recovered = self.cur.fetchall()[0]
                max_recovered = max_recovered[0]
                next_index = max_recovered +1
            except Exception:
                print(cs(f"WARNING-simpleSQL : Error trying to resolve index for new entries", color="Red"))

        #Load records 
        sql_insert_block = f"INSERT INTO {table_name} ("
        if start == 0: # Needs an additional field for index
            sql_insert_block += "id, "

        for i, field_name in enumerate(column_names):
            sql_insert_block += field_name.lower() + (", " if i<len(column_names)-1 else ")\n")
        
        sql_insert_block += "VALUES\n"
        #values
        for n, record in enumerate(records):
            record_def = "("

            if start == 0:
                record_def += str(next_index + n) + ", "

            for i, field_value in enumerate(list(record.values())):

                if isinstance(field_value, (int, float)):
                    record_def += str(field_value)
                else:
                    field_value = field_value.replace("'", "''")
                    record_def += f"'{field_value}'"

                record_def += f'{", " if i<len(sample)-1 else ")"}'

            record_def += f'{"," if n<len(records)-1 else ";"}\n' #end of each record
            
            sql_insert_block += record_def

        try:
            self.execute(sql_insert_block)

        except Exception as e:
            print(cs(f"WARNING! - SQL syntax error: {e}", color="Red"))
            return

    def create_table_from_csv(self, file_name, table_name = None, create_pri_key = None):

        def determine_numeric_type(s):
            try:
                int_value = int(s)
                float_value = float(s)
                return "integer"  # The string can be stored as both an integer and a float
            except ValueError:
                try:
                    float_value = float(s)
                    return "float"  # The string can be stored as a float
                except ValueError:
                    return False  # The string is not numeric

        table_data = {}
        try:
            with open(file_name, "r") as file:
                csv_records = csv.DictReader(file)

                table_data = {}

                for n, record in enumerate(csv_records):

                    key = n
                    cleaned_record = {}

                    for i, field in enumerate(record.keys()):

                        if determine_numeric_type(record[field]) == "integer":
                            try:
                                cleaned_record[field] = int(record[field])
                            except Exception:
                                try:
                                    cleaned_record[field] = float(record[field])
                                except Exception:
                                    print(cs(f"WARNING! - SQL Error converting CSV values.", color="Red"))

                        elif determine_numeric_type(record[field]) == "float":
                            try:
                                cleaned_record[field] = float(record[field])
                            except Exception:
                                    print(cs(f"WARNING! - SQL Error converting CSV values.", color="Red"))
                        
                        else:
                            cleaned_record[field] = record[field]

                    table_data[key]=(dict(cleaned_record))

        except FileNotFoundError:
            print(cs(f"WARNING! - SQL CSV File {file_name} not found.", color="Red"))
            return

        self.create_table_from_dict(table_data, table_name = table_name, create_pri_key = create_pri_key)

    def new_model(self, model_type, schema_name, table_name):

        if model_type == LINEAR_MODEL:
            return SimpleMiner_Linear(db_object = self,
                                      schema_name = schema_name,
                                      table_name = table_name, 
                                      )
        
        elif model_type == ANN_MODEL:
            return SimpleMiner_ANN(db_object = self,
                                      schema_name = schema_name,
                                      table_name = table_name, 
                                      )
        
        
    def __enter__(self):
        return self.open()

    def open(self):   
        #Handler for openning a new connection to DB

        if self.db_name.lower() != self.db_name:
            print(cs("Avoid CAPs when choosing Database name. Program terminated" , color='yellow'))
            #sys.exit(1)

        try:
            if self.drop_after is True:
                self.drop_database()
        except Exception as e:
            pass

        try:
            self.conn = self.connect_to_database() 
            self.cur = self.conn.cursor()

        except Exception as e:
            print(cs(e , color='yellow'))
            return

        if self.load_file:
            self.run_file(self.load_file)

        self.printer = printSql(cursor=self.cur)

        return self #returns a SimpleSQL object that can execute any query and print results in tables
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        #Handler to close connection to DB
        try:
            self.conn.commit()
            self.cur.close()
            self.conn.close()

            if self.drop_after is True:
                self.drop_database()
        except Exception:
            pass

# LexiDatabase Class // creates an additional abstraction level for communicating with an AI model

class LexiDatabase(SimpleSQL):
    """
    This component serves as a brigde for the Ai model to interact with SQL databases in a flexible
    yet secure way. It lets the Ai model execute queries on data and create predictive models to help
    on user requests related to such data. 

    Important:\n
    For now it only accepts Postgres database connections. 
    
    """
    
    def __init__(self, **kwargs) -> None:

        # Check the SQL Engine defined, in the future it could have more flexibility
        if LEXI_DATABASE_ENGINE not in ['PostgreSQL']:
            raise ValueError("SQL integration expects a 'PostgreSQL' Database Engine.")
        
        params = kwargs
        # Extract configuration from parameters:

        self.lexi = params.get("lexi", None)
        test_mode = params.get("test_mode", False)
        db_name = params.get("db_name", None)
        load_setup_script = params.get("load_file", None)
        db_user = params.get("db_user", None)
        db_password = params.get("db_password", None)
        db_port = params.get("db_port", None)
        load_files = params.get("load_files", None)
        force = params.get("force", False)

        # SimpleSQL connection:
        super().__init__(
            db_name = db_name, 
            force = force, 
            load_setup_script = load_setup_script, 
            drop_after = test_mode,
            user= db_user,
            password= db_password,
            port= db_port,
            )
        
        # Activate integration with Data Mining tools
        self.mining_module = params.get("mining_module", False)

        # Open connection
        self.open()

        # Keep track of the predictive models active in the system
        self.models_for_table = {}
        self.models = {}
        self._model_counter = 0

        # Some options for loading_ mostly for test reasons now

        # Load files at setup
        if load_files:
            for file in load_files:
                try:
                    path, tablename = 0, 1

                    # Check if thable exists
                    if not self.check_table_exists(file[tablename]):

                        self.create_table_from_csv(
                                    file_name= file[path], 
                                    table_name= file[tablename] ,
                                    create_pri_key = True
                                    )
                    
                except Exception as e:
                    print(f"Could not load file '{file[tablename]}. Details: {e}'")

        # Define the external commands that need special treatment
        self.table_analyser = LexiExternalCommand(self.run_data_analysis_on_table)

        
    def execute_fetch_sql_query(self, query:str , fetch_one = False) ->str:
        """
        Executes a query over the database.

        Parameters:
        - `query`  A valid Postgres SQL query.

        Returns:
        - The output from the given query in JSON format or None.

        """
        # KEYS: SQL query SELECT EXECUTE
        # SUMM: Executes a SQL query and retrieves the fetchall() result in json format
        # query 'description': IMPORTANT: USE PostgreSQL syntax ONLY
        # fetch_one 'description': True Retrieves only one record or False all found
        # fetch_one 'enum': ["True", "False"]
        
        try:
            try:
                self.execute(query= query)
                
                #Get data
                data = self.cur.fetchall()
            except Exception as e:
                raise ValueError("Could not execute the query. Details: ", e)
                
            #Get the titles of that specifc query
            column_names = [desc[0].capitalize() for desc in self.cur.description]

            # Create a list of dictionaries where each dictionary represents a row
            result_list = []
            for row in data:
                row_dict = {}
                for i in range(len(column_names)):
                    row_dict[column_names[i]] = row[i]
                result_list.append(row_dict)

            # Serialize the list of dictionaries to JSON
            json_data = json.dumps(result_list, indent=4, cls=DecimalEncoder)

            # Return the JSON data or use it as needed
            return json_data
        except Exception as e:
            return {'status': 'Failed', 'details':e, 'suggestion':'Enforce Postgres SQL syntax.'}

    def retrieve_database_erd(self) -> str:
        # KEYS: database erd
        # SUMM: Retrieves a detailed description of the Database ERD    


        # References header
        references = {
            "s": "Schema",
            "t": "Table",
            "cn": "Column",
            "r": "Constraint",
            "td": "TableDescription",
            "cd": "ColumnDescription"
        }

        # Initialize the structure with the keys dictionary
        erd_structure = {"keys": references}

        query = """
            SELECT
                tc.table_schema AS s,
                tc.table_name AS t,
                kcu.column_name AS cn,
                CASE 
                    WHEN tc.constraint_type = 'PRIMARY KEY' THEN 'PK'
                    ELSE 'FK'
                END AS r,
                obj_description((tc.table_schema || '.' || tc.table_name)::regclass) AS td,
                col_description((tc.table_schema || '.' || tc.table_name)::regclass, kcu.ordinal_position) AS cd
            FROM
                information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE
                tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
        """
        
        self.cur.execute(query)
        rows = self.cur.fetchall()
        
        json_model = {}
        for row in rows:
            schema, table, column, constraint_type, table_desc, column_desc = row
            if schema not in json_model:
                json_model[schema] = {}
            if table not in json_model[schema]:
                json_model[schema][table] = {"td": table_desc, "columns": []}
            json_model[schema][table]["columns"].append({"cn": column, "cd": column_desc, "r": constraint_type})

        # Compress keys
        compressed_model = {}
        for schema, tables in json_model.items():
            compressed_model[schema] = {}
            for table, info in tables.items():
                compressed_model[schema][table] = {
                    references[key]: value for key, value in info.items() if key != "columns"
                }
                if "columns" in info:
                    compressed_model[schema][table]["cols"] = [
                        {key: value for key, value in col.items()} for col in info["columns"]
                    ]

        erd_structure.update(compressed_model)
        return json.dumps(erd_structure, separators=(',', ':'))

    def show_predictive_models_for_table(self, table_name: str) ->str:
        # KEYS: prediction forescat values future decision
        # SUMM: Retrieves all the available prediction models for the especified table_name
        # table_name 'description': table name in the dabatabase    
        try:
            # Check if there are models available
            models_available = self.models_for_table.get(table_name, None)

            if models_available:
                
                # Convert to JSON and send
                return json.dumps(models_available)
            
            else:
                # Inform there are no models available
                return f"No predictive models found for table {table_name}. You can use function 'analyse_table' for creating new model."
            
        except Exception as e:
            # Inform the service is not available
            raise ValueError(f"Service is not available now. Details: {e}")

    def run_data_analysis_on_table(self, schema_name: str, table_name: str, target_field: str, model_type) ->str:
        # KEYS: prediction predictive model ann linear features fields analyse analysis 
        # SUMM: Checks possible combinations of input features (table fields) to determine best predictive combination 
        # SUMM: Retrieves the model with best performance
        # schema_name 'description': Indicate the associated table schema when needed.
        # table_name 'description': Table to analyse data from.
        # target_field 'description': The target field that to predict, must be present in table_name
        # model_type 'description': The kind of algorithm to use (ANN_MODEL or LINEAR_MODEL)
        # model_type 'enum': ["ANN_MODEL", "LINEAR_MODEL"]

        # Determine the kind of model to create
        if "ann" in model_type.lower():
            model_type = ANN_MODEL
            model_str = "ann"
        elif "linear" in model_type.lower():
            model_type = LINEAR_MODEL
            model_str = "linear"
        else:
            return "Model type not recognized. enum: ['ANN_MODEL', 'LINEAR_MODEL']"
        
        try:
            # Create a new model
            new_model = self.new_model(
                model_type = model_type,
                schema_name = schema_name,
                table_name = table_name,
            )

            # Name the model 
            self._model_counter += 1
            new_model.model_name = f"{self._model_counter}_{table_name}_{target_field}_{model_str}"

            try:
                # Run an automated data analysis
                r2_scoring = new_model.analyse_field_relationships(
                    target= target_field,
                    hide_unfit=True,
                    show_details=False
                )
                # Automatic features set up using best combination found
                set_features = [f[0] for f in r2_scoring]
                new_model.define_model_features(
                    features=set_features,
                    target=[target_field.capitalize()]
                )
                
                # Create a dictionary with expected values (useful when predicting)
                input_specs = self._generate_input_specs(new_model)

                # Create an example:
                example = {}
                for field in input_specs:
                    example[field] = input_specs[field]['example']

                # Remove example keys from the specs
                for field in input_specs.values():
                    field.pop('example')

            except Exception as e:
                raise ValueError(f"Problem setting up the model. Details: {e}")

            new_model_record = {
                    'model_name' : new_model.model_name,
                    'model_type': new_model.model_type,
                    'input_features' : new_model.current_features,
                    'target_feature': new_model.current_target,
                    'performance_mae' : round(new_model.mae, 3),
                    'performance_mse' : round(new_model.mse, 3),
                    'performance_r2'  : round(new_model.r2, 3),
                    'model_input_values_spec' : input_specs,
                    'use_example' : example,
                }
            
            # Save an example in the model
            new_model.example_use = example

            # Append model to inner dictionary
            if table_name in self.models_for_table:
                self.models_for_table[table_name].append(new_model_record)
            else:
                self.models_for_table[table_name] = [new_model_record]
            
            self.models[new_model.model_name] = new_model

            # Retrieve the model plots
            features_img = new_model.features_plot()
            performance_img = new_model.performance_plot()

            # Stablish a message to be shown to the user after running the analysis
            self.table_analyser.update_custom_messages(
                event_type='after',
                text= 'Below you can see the graphics this model has generated. The first describes the features inference on the predicted result. The second is a performance chart.',
                images= {
                    'features.png': features_img,
                    'performance.png': performance_img,
                }
            )

            # Finally, return the model performance
            return json.dumps(new_model_record)

        except Exception as e:
            raise ValueError(f"Could not analyse data in table {table_name}. Details: {e}.")

    def _generate_input_specs(self, model) -> str:
        # Creates a JSON structure that aims to clarify a predictive model expected input values
        
        schema_name = model.schema_name
        table_name = model.table_name
        column_names = model.current_features

        results_dict = {}

        db_table_fields = self.get_table_fields(schema_name=schema_name, table_name=table_name, capitalize=False)
        column_names_lower = [c_name_.lower() for c_name_ in column_names]

        selected_columns = [c_name for c_name in db_table_fields if c_name.lower() in column_names_lower]

        # Loop through the column names and retrieve distinct values and data types
        for column_name in selected_columns:
            
            try:
                self.execute(f"SELECT data_type FROM information_schema.columns "
                             f"WHERE table_schema = '{schema_name}' AND "
                             f"table_name = '{table_name}' AND "
                             f"column_name = '{column_name}'"
                )
                
                # Fetch the results
                results = self.cur.fetchall()

            except psycopg2.ProgrammingError:
                raise ValueError("Could not create input specs correctly.")

            # Store results in the dictionary
            db_data_type = results[0][0]

            # Convert data type description for strings
            if 'char' in db_data_type:
                db_data_type = 'string'
            
            results_dict[column_name] = {}
            # Load the data type
            results_dict[column_name]['data_type'] = db_data_type

            # Add an example value
            self.execute(f"SELECT {column_name} FROM {schema_name}.{table_name} ORDER BY random() LIMIT 1;")
            results = self.cur.fetchone()
            ref_value = results[0]

            results_dict[column_name]['example'] = ref_value 
            
            # For strings, try to gather the possible values accepted 
            if db_data_type == "string":
                # Check how many distinct values can accept the field

                self.execute(f"SELECT DISTINCT {column_name} FROM {table_name};")
                # Fetch the results
                normalized_values = [value[0] for value in self.cur.fetchall()]

                results_dict[column_name]['normalized_values'] = normalized_values            
            
        return results_dict

    def make_prediction_using_model(self, model_name, input_values) -> str:
        # KEYS: prediction forecast data analysis
        # SUMM: Make a prediction for the target field using the selected model
        # model 'description': model_name should be a valid model from function 'show_predictive_models_for_table'
        # input_values 'description': translate user input into JSON format including features names.
        try:
            if model_name not in self.models:
                return f"Model {model_name} does not exist. Check function 'show_predictive_models_for_table'."
            
            # Retrieve the model
            model = self.models[model_name]

            # Retrieve a model usage example
            model_example = model.example_use

            # Validate input values
            if not isinstance(input_values, dict):
                try:
                    input_values_dict = json.loads(input_values)
                except json.JSONDecodeError as e:
                    raise ValueError(e)
            else:
                input_values_dict = input_values

            # Gather the input values for prediction
            prediction_args = {}
            for feature in model.current_features:

                # Verify the input value for feature was provided
                feature_value = input_values_dict.get(feature, None)
                if not feature_value:
                    feature_value = input_values_dict.get(feature.lower(), None)
                    
                    if not feature_value:
                        # If it becomes troublesome, send an example of the expected input.
                        raise ValueError()
                
                # Convert to the proper data type
                prediction_args[feature] = self.__convert_input_to_data_type(feature_value)

            # Run prediction
            try:                 
                result = model.predict(prediction_args)
            except ValueError:
                # Try capitalizing the input str values
                for arg in prediction_args:
                    if isinstance(prediction_args[arg], str):
                        prediction_args[arg] = prediction_args[arg].capitalize()

                        # 2nd Chance
                        result = model.predict(prediction_args)

            # Return the value
            return f"Predicted output: '{round(result, 4)}'"
        
        except Exception as e:
            # Explain there was a problem
            return f"Error details: {e}. Example of expected input: {model_example}"            

    def __convert_input_to_data_type(self, value):
        try:
            # First, try to convert the string to a float
            float_value = float(value)
            
            # If it's an integer (e.g., "5.0"), it will still be considered a float, so check if it's also an integer
            if float_value.is_integer():
                return int(value)
            else:
                return float(value)
            
        except ValueError:
            # If converting to a float raises a ValueError, it's not a number
            return str(value)

# Auxiliary classes
class DecimalEncoder(json.JSONEncoder):
        # Helps when encoding decimal values to JSON

        def default(self, o):
            if isinstance(o, Decimal):
                return str(o)  # Convert Decimal to a string
            return super(DecimalEncoder, self).default(o)


# Unit test
if __name__ == "__main__":

    options = {
    "test_mode" : True,
    "db_name" : "Adventureworks",
    "load_file": ""
    }


    with LexiDatabase(**options) as lexi_db:

        """
        #Read and create new table in DB
        lexi_db.create_table_from_csv("data/SalaryData2.csv", 
                            table_name= "salaries" ,
                            create_pri_key = True
                            )
        
       

        print(lexi_db.retrieve_database_erd())

        """


        print(lexi_db.run_data_analysis_on_table(
            schema_name="sales", 
            table_name="salesorderdetail", 
            target_field="orderqty", 
            model_type="linear"
            )
        )

"""
        print(lexi_db.execute_fetch_sql_query("SELECT DISTINCT column_name, data_type FROM information_schema.columns WHERE table_name = 'salaries' AND column_name = 'Age'"))

        print(lexi_db.execute_fetch_sql_query("SELECT AVG(age) AS average_age FROM salaries;"))

"""