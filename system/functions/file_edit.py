def replace_lines(file_path: str, start_line: int, end_line: int, content: str):
    """
    Replace lines in a file from start_line to end_line with the provided content.
    This function reads all lines from the file, replaces the specified range with new content,
    and writes the changes back to the file.

    Args:
        file_path (str): The path to the file where lines will be replaced.
        start_line (int): The starting line number for the replacement (1-based index).
        end_line (int): The ending line number for the replacement (1-based index).
        content (str): The content to insert in place of the specified lines.

    Returns:
        list: The updated list of lines after replacement.
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()
    lines[start_line-1:end_line] = [content + '\n']
    with open(file_path, 'w') as file:
        file.writelines(lines)
    return lines


def insert_lines(file_path: str, start_line: int, content: str):
    """
    Insert lines into a file at the specified line number.
    This function reads all lines from the file, inserts new content at the specified line number,
    and writes the changes back to the file.

    Args:
        file_path (str): The path to the file where lines will be inserted.
        start_line (int): The line number at which the content will be inserted (1-based index).
        content (str): The content to insert into the file.

    Returns:
        list: The updated list of lines after insertion.
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()
    lines.insert(start_line - 1, content + '\n')
    with open(file_path, 'w') as file:
        file.writelines(lines)
    return lines


def delete_lines(file_path: str, start_line: int, end_line: int):
    """
    Delete lines from a file from start_line to end_line.
    This function reads all lines from the file, removes the specified range of lines,
    and writes the remaining lines back to the file.

    Args:
        file_path (str): The path to the file from which lines will be deleted.
        start_line (int): The starting line number for the deletion (1-based index).
        end_line (int): The ending line number for the deletion (1-based index).

    Returns:
        list: The updated list of lines after deletion.
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()
    del lines[start_line-1:end_line]
    with open(file_path, 'w') as file:
        file.writelines(lines)
    return lines
