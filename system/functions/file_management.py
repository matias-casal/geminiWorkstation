import os


def create_file(file_path, content=''):
    """
    Create a new file with optional initial content.
    This function creates a new file at the specified path and can optionally write initial content to it.

    Args:
        file_path (str): The path where the new file will be created.
        content (str): Optional initial content to write to the file.

    Returns:
        bool: True if the file was created successfully, False otherwise.
    """
    with open(file_path, 'w') as file:
        file.write(content)
    return True


def delete_file(file_path):
    """
    Delete a file at a specified path.
    This function deletes the file located at the specified path.

    Args:
        file_path (str): The path to the file that will be deleted.

    Returns:
        bool: True if the file was deleted successfully, False otherwise.
    """
    os.remove(file_path)
    return True
