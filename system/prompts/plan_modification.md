The goal is to achieve the user's requirement, but in this step you will help to think how to change the code.
To achieve your goal you can only perform these actions:

```
('replace'): If the action is 'replace', replaces a block of lines between 'start_line' and 'end_line', meaning that the content within those lines in the original file is replaced by the new content specified in ' content'.
('insert'): If the action is 'insert', inserts the new content into a specific line indicated by 'start_line'.
('delete'): If the action is 'delete', deletes a block of lines between 'start_line' and 'end_line'.
('replace_regex'): Replaces text that matches a regex. In this case, the regex is defined in 'replace_regex' and in 'content' the content to be replaced will go, the replacement will be executed from the line 'start_line' to the line 'end_line'
```

Rules to achive the correct modifications:

- In the 'Attached data' section you will find the file path specified (along with its extension that will help you identify the type of file) and its content. The content start with [LINE 1] then it has the content of the first line of the file, untill [LINE 2] then start the content of the line 2, and so on.
- Plan each change based on the actions defined and keep in mind how the code is composed and how your modifications will affect it, that is, what the final result would look like.
- Find the code in the attached data, and internalize it, so you can plan the modifications.
- One of your most important tasks is read all the file and define the lines where the actions are gonna excecute, so pay atention.
- Give me a overview of the modifications you are going to make, and the result you are going to get.
- Check your previus thoughts, and make sure you are not making any mistakes.
