from rich.table import Table


def generate_table(data: list, headers: list) -> Table:
    """
    Create a visually appealing table using the 'rich' library's Table class.

    This function takes a list of headers and a corresponding list of row data,
    constructs a table, and returns it. Each row of data should have elements
    corresponding to the headers provided.

    Args:
        headers (list of str): The column headers of the table.
        data (list of list): The rows of data, where each sublist corresponds to a row in the table.

    Returns:
        Table: A 'rich' table object populated with the provided headers and data.
    """
    table = Table()
    for header in headers:
        table.add_column(header)
    for row in data:
        table.add_row(*row)
    return table


functions_declaration = [{
    "name": "generate_table",
    "description": "Creates a table using the 'rich' library.this is the function that will be used to display the table:  ```   table = Table()     for header in headers:        table.add_column(header)    for row in data:        table.add_row(*row)    return table```",
    "parameters": [{
        "headers": {
            "type": "array",
            "description": "A list of strings representing the column headers of the table.",
            "items": {
                "type": "string",
                "description": "A single header for one of the table's columns."
            }
        },
        "data": {
            "type": "array",
            "description": "A list of lists, where each sublist represents a row of data corresponding to the headers.",
            "items": {
                "type": "array",
                "description": "A list representing a single row of data, with each element corresponding to a column defined by the headers."
            }
        }
    }]
}]
