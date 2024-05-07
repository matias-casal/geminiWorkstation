This is how the program modifies the file content based on a series of defined actions.

You can not give solutions that can not be achiavable, with this actions.

Each action requires different fields and makes specific changes to the file content.
You have to do deep thinking and anticipate how your changes impact, what result will bring each action. Be careful with the consequences of each modification, pay attention to the structure and relationships of each line of content. For example: your modifications could break the structure of the file, or the relationships between the lines of content, if the uphead line is related with the line that you are modifying pay attention.

List of actions:

1. 'replace_lines' Action
   Description: This action replaces the content in a file between the specified lines.
   Warning: This action remove entire lines, be careful with the consequences.
   Required Fields:
   start_line: The initial line from which the content will be replaced.
   end_line: The final line up to which the content will be replaced.
   content: New content that will replace the existing one between the specified lines.
   Example:
   Original file:

   ```
   Line 1
   Line 2
   Line 3
   Line 4
   Line 5
   ```

   Modification:

   ```
   action = 'replace_lines'
   modification = {'start_line': 2, 'end_line': 4, 'content': 'New content'}
   ```

   Modified file:

   ```
   Line 1
   New content
   Line 5
   ```

2. 'insert_lines' Action
   Description: Inserts a new line at the specified position.
   Warning: This action put a new line, be careful with the position and how affect the structure and relationships of each line of content.
   Required Fields:
   start_line: The line at which the new content will be inserted.
   content: Content that will be added as a new line.
   Example:
   Original file:

   ```
   Line 1
   Line 2
   Line 3
   ```

   Modification:

   ```
   action = 'insert_lines'
   modification = {'start_line': 2, 'content': 'Inserted line'}
   ```

   Modified file:

   ```
   Line 1
   Inserted line
   Line 2
   Line 3
   ```

3. 'delete_lines' Action
   Description: Deletes lines between the specified ones.
   Warning: This action remove entire lines, be careful with the consequences.
   Required Fields:
   start_line: The initial line from which deletion will start.
   end_line: The final line up to which lines will be deleted.
   Example:
   Original file:

   ```
   Line 1
   Line 2
   Line 3
   Line 4
   Line 5
   ```

   Modification:

   ```
   action = 'delete_lines'
   modification = {'start_line': 2, 'end_line': 4}
   ```

   Modified file:

   ```
   Line 1
   Line 5
   ```

4. 'replace_content_with_regex' Action
   Description: Replaces text that matches a regular expression between the specified lines.
   Required Fields:
   start_line: The initial line from where the regular expression is applied.
   end_line: The final line up to where the regular expression is applied.
   replace_content_with_regex: Regular expression identifying the text to replace.
   content: Content that will replace the text matching the regular expression.
   Example:
   Original file:
   ```
   Line 1
   Line 2: Some text
   Line 3
   ```
   Modification:
   ```
   action = 'replace_content_with_regex'
   modification = {'start_line': 2, 'end_line': 3, 'replace_content_with_regex': 'text', 'content': 'content'}
   ```
   Modified file:
   ```
   Line 1
   Line 2: Some content
   Line 3
   ```

THE MODIFICATIONS ARE PLANNED WISELY

Rules:

- If you need to add something to replace it with new content try to do it with replace_content_with_regex
- If the line is to complex, try to not delete it, just change the content with replace_content_with_regex if its posible
