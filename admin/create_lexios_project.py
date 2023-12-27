# lexios/admin.py

import os
import sys
from shutil import  copy2
from admin.settings import update_constant_value

def __main__():
    if len(sys.argv) != 2:
        print("Usage: new_lexios_project <project_name>")
        sys.exit(1)

    project_name = sys.argv[1]
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    project_dir = os.path.join(base_dir, project_name)


    # Create project directory
    try:
        os.makedirs(project_dir)
    except FileExistsError:
        print(f"Project folder {project_name} already exists. Please try with another identifier.")

    # Create __init__.py files
    open(os.path.join(project_dir, "__init__.py"), "a").close()

    # Create backend_logs folder
    os.makedirs(os.path.join(project_dir, "backlogs"))

    # Create integrations directory
    integrations_dir = os.path.join(project_dir, "integrations")
    os.makedirs(integrations_dir)
    open(os.path.join(integrations_dir, "__init__.py"), "a").close()

    # Create temporal uploads directory
    os.makedirs(os.path.join(project_dir, "temp_uploads"))

    # Create temporal uploads directory
    os.makedirs(os.path.join(project_dir, "temp_downloads"))

    

    # Create main.py file
    main_file_path = os.path.join(project_dir, "main.py")
    with open(main_file_path, "w") as main_file:
        main_file.write(
            f'# my_async_script.py\n'
            f'from lexios import lexiOS\n\n'
            f'def main():\n'
            f'    server = lexiOS()\n\n'
            f'if __name__ == "__main__":\n'
            f'    main()\n'
        )

    # Create example.py in integrations directory
    example_file_path = os.path.join(integrations_dir, "example.py")
    with open(example_file_path, "w") as example_file:
        example_file.write(
            f'from lexios.integrations.tools import external_command\n'
            f'\n'
            f'"""\n'
            f'@external_command\n'
            f'def getCurrentWeather(location, unit: str = "c"):\n'
            f'# summ: Get the weather in location\n'
            f'# keys: location unit\n'
            f"# unit 'enum': ['c', 'f']\n"
            f"# unit 'enum': ['c', 'f']\n"
            f"# location 'description': 'some text'\n"
            f'  pass\n'
            f'"""\n'
        )
    
    # Copy the template settings file into the new project folder
    copy2(os.path.join(base_dir, "lexios", "settings", "settings_template.py"), os.path.join(project_dir, "settings.py"))

    # Custom values for new project
    update_constant_value(os.path.join(project_dir, "settings.py"), "LOG_FOLDER", f"'{project_name}/backlogs'")
    update_constant_value(os.path.join(project_dir, "settings.py"), "UPLOAD_FOLDER", f"'{project_name}/temp_uploads'")
    update_constant_value(os.path.join(project_dir, "settings.py"), "DOWNLOAD_FOLDER", f"'{project_name}/temp_downloads'")
    update_constant_value(os.path.join(project_dir, "settings.py"), "LEXI_DATABASE_NAME", f"'{project_name}_database'")

    # Setup database
    try:
        from lexios.database.models import initial_database_setup

        initial_database_setup()
        print(f"Database for '{project_name}' was created.")
    except Exception as e:
        print(f"Could not create database models for {project_name}. Details: {e}")

    # Create data folder
    os.makedirs(os.path.join(project_dir, "data"))

    print(f"Lexios project '{project_name}' created successfully!")

if __name__ == "__main__":
    __main__()
