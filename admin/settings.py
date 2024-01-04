import ast

def edit_constant_value_in_script(file_path, constant_name, new_value):
    """
    Update the value of a constant in a Python file.

    Args:
        file_path (str): Path to the Python file.
        constant_name (str): Name of the constant to update.
        new_value: New value for the constant.
    """

    # Read the content of the Python file
    with open(file_path, 'r') as file:
        content = file.read()

    # Parse the abstract syntax tree (AST) of the code
    tree = ast.parse(content)

    # Find assignments to the specified constant
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == constant_name:
                    # Update the value of the constant
                    node.value = ast.parse(repr(new_value)).body[0].value

    # Generate the modified code
    updated_code = ast.unparse(tree)

    # Write the updated content back to the file
    with open(file_path, 'w') as file:
        file.write(updated_code)


def edit_constant_value_in_script(file_path, constant_name, new_value):
    updated_lines = []

    with open(file_path, 'r') as file:
        for line in file:
            if f"{constant_name} =" in line:
                # Update the line containing the constant
                updated_lines.append(f"{constant_name} = {new_value}\n")
            else:
                updated_lines.append(line)

    # Write the updated lines back to the file
    with open(file_path, 'w') as file:
        file.writelines(updated_lines)

