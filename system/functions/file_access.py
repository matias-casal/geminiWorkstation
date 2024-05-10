import os


def access_to_file(file_path: str) -> str:
    """Access to a file and return the content. Be extra careful with the file path, and the file type.."""
    if not os.path.exists(file_path):
        # Try adding '/' at the beginning if it does not exist
        if not os.path.exists('/' + file_path):
            # Try adding './' at the beginning if it does not exist
            if not os.path.exists('./' + file_path):
                return f"[file_path]{file_path}[/file_path][result_error]No such file or directory: {file_path}[/result_error]"
            else:
                file_path = './' + file_path
        else:
            file_path = '/' + file_path

    try:
        with open(file_path, 'r') as file:
            content = file.read()
    except Exception as e:
        return f"[file_path]{file_path}[/file_path][result_error]{str(e)}[/result_error]"
    return f"[file_path]{file_path}[/file_path][result_content]{str(content)}[/result_content]"


functions_declaration = [{
    "name": "access_to_file",
    "description": "Open a file and return the content. Be extra careful with the file path, respect the users input, do not change the file path. The will be read like 'file.read()' in python, so be aware of compatibility",
    "parameters": [{
        "file_path": {"type": "string", "description": "The path to the file to be accessed."}
    }]
}]
