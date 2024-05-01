El programa geminiWorkstation es una herramienta de línea de comandos diseñada para facilitar la gestión y manipulación de bases de código utilizando la tecnología de inteligencia artificial de Google, Gemini. A continuación, se detalla cómo funciona el programa basándose en los fragmentos de código proporcionados:
Estructura General y Flujo del Programa

1. Inicio del Programa:
   El programa comienza en la función main() donde se manejan los argumentos de la línea de comandos y se dirige el flujo del programa.
   Si se proporciona un path, se procesa mediante process_input(); de lo contrario, se muestra un menú interactivo.
2. Manejo de Menús:
   display_menu() carga las opciones de menú desde un archivo JSON y muestra las opciones disponibles para el usuario. Las opciones pueden llevar a funciones específicas o submenús.
3. Procesamiento de Acciones:
   handle_option() procesa la opción seleccionada por el usuario, manejando entradas adicionales y ejecutando acciones definidas en las opciones del menú.
4. Interacción con API de Gemini:
   call_gemini_api() se utiliza para enviar datos a la API de Gemini y recibir contenido generado, que luego se maneja según el formato de salida especificado.
5. Modificaciones de Archivos:
   apply_modifications() lee las modificaciones especificadas en formato JSON y realiza acciones como reemplazar, insertar o eliminar contenido en archivos específicos.
   Funciones Clave y Utilidades
   process_input(): Procesa un path que puede ser una URL de un repositorio para clonar o un directorio local para procesar.
   handle_actions(): Ejecuta una serie de acciones definidas en las opciones del menú, como llamar a la API de Gemini o modificar archivos.
   save_output() y update_data_txt(): Guardan los resultados de las operaciones en archivos específicos y actualizan un archivo de registro centralizado.
   Manejadores de Errores: Decoradores y funciones como handle_errors() que ayudan a gestionar y recuperarse de errores durante la ejecución del programa.
   Integración y Configuración
   El programa utiliza un archivo de configuración JSON para manejar reglas específicas y un archivo JSON para las opciones del menú, lo que permite una configuración y expansión fácil del comportamiento del programa.
   Conclusión
   geminiWorkstation es una herramienta robusta y flexible diseñada para mejorar la eficiencia en la gestión de código utilizando capacidades avanzadas de AI, con una interfaz de usuario interactiva y un sistema de manejo de errores integrado para asegurar una operación estable.

El flujo de ejecución de una acción en geminiWorkstation se maneja principalmente a través de las funciones handle_option(), handle_actions(), y execute_action(). Aquí se detalla cómo estas funciones interactúan para procesar y ejecutar una acción seleccionada por el usuario:

6. Selección de Opción y Recolección de Entradas
   Cuando un usuario selecciona una opción del menú, handle_option() es invocada.
   Si la opción requiere entradas adicionales del usuario, se solicitan y se almacenan en user_inputs.
7. Ejecución de Acciones Asociadas
   Dentro de handle_option(), si la opción tiene acciones definidas ("actions"), se llama a handle_actions() pasando las acciones, los resultados previos y las entradas del usuario.
   handle_actions() itera sobre cada acción en la lista de acciones:
   Para cada acción, se llama a execute_action().
8. Procesamiento de una Acción Individual
   execute_action() determina el tipo de acción a realizar:
   Acción de Prompt: Si la acción es generar contenido usando un prompt (por ejemplo, interactuar con la API de Gemini), se carga el contenido del prompt desde un archivo, se formatea adecuadamente con format_prompt(), y luego se pasa a call_gemini_api() para ejecutar la solicitud y obtener la respuesta.
   Acción de Función: Si la acción implica llamar a una función específica (por ejemplo, modificar archivos o procesar datos), se verifica si la función está definida globalmente y luego se invoca con los resultados previos y las entradas del usuario como argumentos.
9. Manejo de Resultados
   Los resultados de execute_action() (ya sea contenido generado o el resultado de una función) se agregan a la lista de resultados.
   Estos resultados se pasan de vuelta a handle_option() donde pueden ser utilizados para acciones adicionales o para mostrar al usuario.
10. Opciones Post-Ejecución
    Después de ejecutar todas las acciones, handle_option() muestra opciones para regresar al menú principal o salir del programa, permitiendo al usuario decidir los siguientes pasos.
    Resumen del Flujo
    Este flujo permite una ejecución modular y flexible de diversas acciones, desde interactuar con APIs externas hasta realizar operaciones de archivo locales, todo mientras maneja dinámicamente las entradas del usuario y mantiene un control de flujo claro y manejable.
