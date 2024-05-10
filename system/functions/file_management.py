import os


def create_file(file_path: str, content: str = ''):
    with open(file_path, 'w') as file:
        file.write(content)
    return f"[file_created]{file_path}[/file_created]"


def delete_file(file_path: str):
    os.remove(file_path)
    return f"[file_deleted]{file_path}[/file_deleted]"


functions_declaration = [{
    "name": "create_file",
    "description": "Create a new file with optional initial content.",
    "parameters": [{
        "file_path": {"type": "string", "description": "The path to the file where lines will be replaced."},
        "content": {"type": "string", "description": "The content to insert in place of the specified lines."}
    }]
}, {
    "name": "delete_file",
    "description": "Delete a file at a specified path.",
    "parameters": [{
        "file_path": {"type": "string", "description": "The path to the file that will be deleted."}
    }]
}]
