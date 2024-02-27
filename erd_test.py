import psycopg2
from psycopg2 import sql

def retrieve_database_erd(connection):
    try:
        # Create a cursor object
        cursor = connection.cursor()

        # Query to retrieve table names, primary and foreign keys
        query = sql.SQL("""
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                tc.constraint_type,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM
                information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            LEFT JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE
                tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
        """)

        # Execute the query
        cursor.execute(query)

        # Fetch all rows as a list of tuples
        table_info = cursor.fetchall()

        # Organize the information into a dictionary
        json_model = {}
        for schema, table, column, constraint_type, foreign_schema, foreign_table, foreign_column in table_info:
            if schema not in json_model:
                json_model[schema] = {}
            if table not in json_model[schema]:
                json_model[schema][table] = []
            json_model[schema][table].append({
                "column_name": column,
                "constraint_type": constraint_type,
                "foreign_table_schema": foreign_schema,
                "foreign_table_name": foreign_table,
                "foreign_column_name": foreign_column
            })

        # Close the cursor
        cursor.close()

        return json_model

    except psycopg2.Error as e:
        print("Error retrieving database ERD:", e)
        return None

def main():
    # Connect to the PostgreSQL database
    try:
        connection = psycopg2.connect(
            dbname="Adventureworks",
            user="postgres",
            password="postgres",
            host="localhost",
            port="5432"
        )
        print("Connected to the database.")

        # Retrieve the database ERD
        erd = retrieve_database_erd(connection)
        if erd:
            print("Database ERD:")
            print(erd)
        else:
            print("Failed to retrieve database ERD.")

        # Close the connection
        connection.close()
        print("Connection closed.")

    except psycopg2.Error as e:
        print("Error connecting to the database:", e)

if __name__ == "__main__":
    main()
