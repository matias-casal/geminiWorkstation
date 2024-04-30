El objetivo es cumplir con el requicito del usaurio, pero en este paso vamos a planea como impactar el cambio en el codigo.

- Tu respuesta va a ayudar a ejecutar la tarea indicada, sera leida por una inteligencia artificial, asi que no agregues ningun tipo de informacion o comentario innecesario.
- Todo el proceso es automatico, y una tarea se ejecuta despues de la otra sin intervencion humana.
- Para lograr tu objetivo solo puedes realizar estas acciones:

```
('replace'): Si la acción es 'replace', reemplaza un bloque de líneas entre 'start_line' y 'en d_line', es decir que el contenido dentro de esas lineas en el archivo original se reemplaza por el contenido nuevo especificado en 'content'.
('insert'): Si la acción es 'insert', inserta el contenido nuevo en una línea específica indicada por 'start_line'.
('delete'): Si la acción es 'delete', elimina un bloque de líneas entre 'start_line' y 'end_line'.

Si en cambio el archivo contiene grandes lineas de texto, se recomienta usar 'replace_content' o 'replace_regex'. Pero tambien los puedes utilizar para otros casos de uso donde te resulten utiles.
('replace_content'): Reemplaza un texto dentro de una linea. en este caso, el texto a reemplazar definelo en 'replace_content' y en 'content' ira el contenido a remplazar, la linea en la que se ejecutara se define en 'start_line'
('replace_regex'): Reemplaza texto que coincida con un regex. en este caso, el regex se define en 'replace_regex' y en 'content' ira el contenido a remplazar, el remplazo se ejecutara desde la linea 'start_line' hasta la linea 'end_line'
```

Ahora planifica cada cambio basado en esas acciones, ten en cuenta como esta compuesto el codigo y como lo afectaran tus modificaciones, osea como quedaria el resultado final.
