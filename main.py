from threading import Thread
import argparse
import sys
import os
import time
import json
import signal
import shutil
import requests
import threading
import traceback
import importlib.util
from datetime import datetime
from collections.abc import Iterable
from prompt_toolkit import PromptSession
from shutil import copy
from pathlib import Path
from git import Repo
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt as ConsolePrompt
from rich.markdown import Markdown
from rich.spinner import Spinner

import google.generativeai as genai
import google.api_core.exceptions
from google.generativeai import GenerationConfig
from google.generativeai.types import content_types

DEBUG = os.getenv('DEBUG', True)
MODEL_NAME = os.getenv('MODEL_NAME', 'gemini-1.5-pro-latest')
DATA_DIR = os.getenv('DATA_DIR', 'data')
CACHE_DIR = os.getenv('CACHE_DIR', 'cache')
SYSTEM_DIR = os.getenv('SYSTEM_DIR', 'system')
MAX_OUTPUT_TOKENS = os.getenv('MAX_OUTPUT_TOKENS', 4000)
SAVE_PROMPT_HISTORY = os.getenv('SAVE_PROMPT_HISTORY', True)
SAVE_OUTPUT_HISTORY = os.getenv('SAVE_OUTPUT_HISTORY', True)
WORKSTATION_DIR = os.getenv('WORKSTATION_DIR', 'workstation')
WORKSTATION_ORIGINAL_DIR = os.getenv(
    'WORKSTATION_ORIGINAL_DIR', WORKSTATION_DIR + '/original')
WORKSTATION_EDITED_DIR = os.getenv(
    'WORKSTATION_EDITED_DIR', WORKSTATION_DIR + '/edited')
FEEDBACK_TIMEOUT = int(os.getenv('FEEDBACK_TIMEOUT', 3))


console = Console(highlight=False)
session = PromptSession()


def feedback_timer(timeout=FEEDBACK_TIMEOUT):
    """
    Display a prompt with a countdown timer. Return True if the user presses Enter before the timer expires, otherwise return False.
    """
    console_update_time = 0.2
    input_received = [False]

    def get_input():
        nonlocal input_received
        input()  # Wait for Enter press
        input_received[0] = True

    input_thread = Thread(target=get_input)
    input_thread.daemon = True
    input_thread.start()

    with console.status(f"[bold yellow]Press Enter if you want to add feedback (Timeout in {timeout} seconds): ", spinner="dots") as status:
        remaining = timeout
        while remaining > 0:
            if input_received[0]:
                status.update("")
                return True
            status.update(
                f"[bold yellow]Press Enter if you want to add feedback (Timeout in {remaining:.1f} seconds): ")
            time.sleep(console_update_time)
            remaining -= console_update_time  # Decrement the remaining time by 0.3 seconds

    status.update("")
    return False


def load_functions_from_directory(directory=os.path.join(SYSTEM_DIR, 'functions')):
    console.print("Loading functions...", directory, style="yellow")
    loaded_functions = {}
    for filename in os.listdir(directory):
        if filename.endswith('.py'):
            module_name = filename[:-3]  # Remove the '.py' from filename
            module_path = os.path.join(directory, filename)
            spec = importlib.util.spec_from_file_location(
                module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Import only functions (not classes or other callable types) from the module
            for func_name, func in module.__dict__.items():
                if callable(func) and not isinstance(func, type):
                    loaded_functions[func_name] = func
    return loaded_functions


def show_available_modes(previous_results, user_inputs):
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)


def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            console.print(
                f"An unexpected error occurred: {e}", style="bold red")
            if DEBUG:
                console.print(traceback.format_exc(), style="bold red")
            console.print(
                "1. Retry\n2. Return to Main Menu\n3. Exit", style="bold yellow")
            choice = ConsolePrompt.ask(
                "Choose an option", choices=['1', '2', '3'])
            if choice == '1':
                return wrapper(*args, **kwargs)  # Reintentar la función
            elif choice == '2':
                display_menu()  # Volver al menú principal
            elif choice == '3':
                exit_program()  # Salir del programa
            return None
    return wrapper


def check_api_key():
    """Check if the GEMINI_API_KEY environment variable is set. If not, prompt the user to set it."""
    try:
        api_key = os.environ['GEMINI_API_KEY']
        console.print("API Key is set.", style="green")
    except KeyError:
        console.print(
            "API Key is not set. Please visit https://aistudio.google.com/app/apikey to obtain your API key.", style="bold red")
        api_key = session.prompt("Enter your GEMINI_API_KEY: ")
        genai.configure(api_key=api_key)


def tool_config_from_mode(mode: str, fns: Iterable[str] = ()):
    """Create a tool config with the specified function calling mode."""
    if mode == "ANY":
        return {
            "function_calling_config": {
                "mode": mode,
                "allowed_function_names": list(fns)
            }
        }
    else:
        return {
            "function_calling_config": {
                "mode": mode
            }
        }


def format_prompt(prompt_content, previous_results, user_inputs):
    with open(SYSTEM_DIR + '/base_prompt.md', 'r', encoding='utf-8') as file:
        base_prompt_content = file.read()
    with open(CACHE_DIR + '/data.txt', 'r', encoding='utf-8') as file:
        attached_content = file.read()

    # Construir el system_prompt con base_prompt y instructions section
    system_prompt = f"{base_prompt_content}\n\n-- INSTRUCTIONS:\n{prompt_content}"

    # Construir el prompt completo con todas las secciones
    prompt = f"\n\n-------------- USER INPUTS SECTION --------------\n{user_inputs}\n\n-------------- END USER INPUTS SECTION --------------\n"
    prompt += f"\n\n-------------- PREVIOUS RESULTS SECTION --------------\n{previous_results}\n\n-------------- END PREVIOUS RESULTS SECTION --------------\n"
    prompt += f"\n\n-------------- ATTACHED DATA SECTION --------------\n{attached_content}\n\n-------------- END ATTACHED DATA SECTION --------------\n"

    return system_prompt, prompt


@handle_errors
def call_gemini_api(system_prompt, prompt, output_format=None):
    try:
        with console.status("[bold yellow]Uploading data and waiting for Gemini...") as status:
            # Listar las funciones disponibles
            tools = list(load_functions_from_directory().values())

            # Crear la configuración de herramientas usando la función tool_config_from_mode
            tool_config = tool_config_from_mode(
                "auto", [func.__name__ for func in tools])
            console.print("Configuring model...",
                          MODEL_NAME, style="yellow")
            console.print("Tools:", tools, style="yellow")
            console.print("Tool config:", tool_config, style="yellow")
            # Configurar el modelo con las herramientas y la configuración de herramientas
            model = genai.GenerativeModel(
                MODEL_NAME,
                system_instruction=system_prompt,
                tools=tools,
                tool_config=tool_config
            )
            cache_path = Path('cache')

            if SAVE_PROMPT_HISTORY:
                # Guardar el prompt en la carpeta de historial
                prompt_history_path = cache_path / 'prompts_history'
                prompt_history_path.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                prompt_filename = prompt_history_path / f"{timestamp}.txt"

                with open(prompt_filename, 'w', encoding='utf-8') as file:
                    file.write(prompt)

            token_count = model.count_tokens(prompt).total_tokens
            if token_count > 1000000:
                console.print(
                    f"Error: The prompt is too big, it has more than 1 million tokens.", style="bold red")
                console.print(
                    f"The prompt has {token_count} tokens", style="red")
                return None
            elif token_count > 910000:
                console.print(
                    f"Warning: The prompt is using 91% of the token limit. {token_count} tokens", style="bold yellow")
            else:
                console.print(
                    f"The prompt has {token_count} tokens", style="green")

            # Configuración de la generación basada en el formato del prompt
            generation_config = GenerationConfig(
                max_output_tokens=MAX_OUTPUT_TOKENS)
            if output_format == "JSON":
                generation_config.response_mime_type = "application/json"

            response = model.generate_content(
                prompt,
                stream=True,
                request_options={"timeout": 1200},
                generation_config=generation_config
            )
            status.stop()
            full_response = handle_response_chunks(response)
            if output_format != "JSON":
                console.print(Markdown(full_response))
            else:
                console.print(full_response, style="italic")
            if SAVE_OUTPUT_HISTORY:
                # Guardar el prompt y la respuesta en la carpeta de outputs
                outputs_path = cache_path / 'outputs_history'
                outputs_path.mkdir(exist_ok=True)
                output_filename = outputs_path / f"{timestamp}.txt"
                with open(output_filename, 'w', encoding='utf-8') as file:
                    file.write(
                        f"Prompt:\n{prompt}\n\nResponse:\n{full_response}")
            for content in response:
                if content.parts[0].function_call:
                    console.print(
                        'function call', content.parts[0].function_call)
            return full_response
    except google.api_core.exceptions.DeadlineExceeded:
        console.print(
            "Error: The request timed out. Please try again later.", style="bold red")
        raise
    except google.api_core.exceptions.GoogleAPIError as e:
        console.print(f"API Error: {e.message}", style="bold red")
        raise


def clone_repo(url, directory="workstation"):
    """Clone a git repository from a given URL into a specified directory."""
    if not os.path.exists(directory) or not os.listdir(directory):
        os.makedirs(directory, exist_ok=True)
        Repo.clone_from(url, directory)
        console.print(f"\nRepository cloned into {directory}", style="green")
    else:
        console.print(
            f"\nDirectory {directory} already has files. Skipping cloning.", style="yellow")


def download_file(url, filename):
    """Download a file from a URL and save it locally."""
    response = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(response.content)
    console.print(f"File downloaded as {filename}", style="green")


def process_directory(directory, config, section_name):
    """Process files in a directory, excluding specified extensions, directories, and filenames."""
    exclude_extensions = config.get("exclude_extensions", [])
    exclude_directories = config.get("exclude_directories", [])
    exclude_filenames = config.get("exclude_filenames", [])
    cache_path = Path(CACHE_DIR)
    # Asegurarse de que la carpeta cache existe
    cache_path.mkdir(exist_ok=True)

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude_directories]
        files[:] = [f for f in files if f not in exclude_filenames and not any(
            f.endswith(ext) for ext in exclude_extensions)]
        for file_name in files:
            with open(os.path.join(root, file_name), 'r', encoding='utf-8', errors='ignore') as content_file:
                content = content_file.read()
                update_data_txt(Path(directory) / file_name, content)
    console.print(f"Directory processed: {directory}", style="green")


def process_input(path):
    """Process the input path or URL."""
    if isinstance(path, list):
        console.print(
            "Error: Expected a string for 'path', but got a list.", style="bold red")
        return
    # Verificar si la ruta es una URL de archivo local y convertirla a una ruta de sistema de archivos
    if path.startswith('file://'):
        path = path[7:]  # Eliminar el prefijo 'file://'

    if path.startswith(('http://', 'https://')):
        with console.status("[bold yellow]Cloning repository...") as status:
            clone_repo(path, directory=Path(WORKSTATION_ORIGINAL_DIR))
            status.update("Repository cloned successfully!")
    else:
        if not os.path.exists(path):
            console.print("The path does not exist.", style="red")
            # Solicitar al usuario que reintente ingresar la ruta
            console.print(
                "Please re-enter the directory path or repository URL:", style="yellow")
            new_path = input()
            if new_path:
                process_input(new_path)
            return
        if os.path.isdir(path):
            with console.status("[bold yellow]Processing directory...") as status:
                # Asegurarse de que la carpeta 'original' existe
                original_path = Path(WORKSTATION_ORIGINAL_DIR)
                original_path.mkdir(parents=True, exist_ok=True)

                # Copiar el contenido a la carpeta 'original'
                for item in os.listdir(path):
                    s = os.path.join(path, item)
                    d = os.path.join(original_path, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)

                status.update("Directory processed successfully!")
        elif os.path.isfile(path):
            original_path = Path(WORKSTATION_ORIGINAL_DIR)
            original_path.mkdir(parents=True, exist_ok=True)
            copy(path, original_path)
            console.print(
                f"File {path} copied to {original_path}.", style="green")


def load_config():
    """Load configuration from a JSON file."""
    with open(os.path.join(SYSTEM_DIR, 'rules.json'), 'r') as config_file:
        return json.load(config_file)


def execute_action(action, previous_results, user_inputs):
    output_format = action.get("output_format", "text")

    if "prompt" in action:
        prompt_path = Path('system/prompts') / f"{action['prompt']}.md"
        with open(prompt_path, 'r', encoding='utf-8') as file:
            prompt_content = file.read()
        system_prompt, prompt = format_prompt(
            prompt_content, previous_results, user_inputs)
        return call_gemini_api(system_prompt, prompt, output_format)
    elif "function" in action:
        function_name = action["function"]
        if function_name in globals():
            function_to_call = globals()[function_name]
            return function_to_call(previous_results, user_inputs)
        else:
            console.print(
                f"Function {function_name} is not defined", style="bold red")
            return None


def handle_actions(actions, previous_results, user_inputs):
    results = []
    for action in actions:
        console.print(Markdown(
            f"\n\n# Processing: {action.get('prompt', action.get('function', 'Action'))}"), style="bold bright_magenta")

        # Capture user feedback with a 2-second timeout only for 'prompt' actions
        if 'prompt' in action:
            feedback = feedback_timer()
            if feedback:
                user_inputs['user feedback'] = ConsolePrompt.ask(
                    "Please provide your feedback")
            else:
                console.print("No feedback received, continuing...",
                              style="yellow")
        # Execute action
        result = execute_action(action, previous_results, user_inputs)
        console.print(f"\n\nResult: {result}", style="bold green")
        if result is not None:
            previous_results.append(result)

    return results


def prepare_editing_environment():
    """Prepara el entorno de edición copiando archivos de 'original' a 'edited' solo si son necesarios."""
    original_dir = Path(WORKSTATION_DIR) / 'original'
    edited_dir = Path(WORKSTATION_DIR) / 'edited'
    edited_dir.mkdir(parents=True, exist_ok=True)

    with console.status("[bold green]Preparing editing environment...") as status:
        # Copiar archivos de 'original' a 'edited' solo si no existen o están desactualizados
        for item in os.listdir(original_dir):
            source_path = original_dir / item
            target_path = edited_dir / item
            # Verificar si el archivo o directorio necesita ser actualizado
            if not target_path.exists() or file_needs_update(source_path, target_path):
                if source_path.is_dir():
                    if target_path.exists():
                        shutil.rmtree(target_path)
                    shutil.copytree(source_path, target_path,
                                    dirs_exist_ok=True)
                else:
                    shutil.copy2(source_path, target_path)
                status.update(f"Copied {item} to editing environment.")
        status.update("Editing environment ready!")


def file_needs_update(source, target):
    """Determina si un archivo necesita ser actualizado basado en la fecha de modificación y tamaño."""
    if not target.exists():
        return True
    source_stat = source.stat()
    target_stat = target.stat()
    # Comprobar si la fecha de modificación o el tamaño del archivo son diferentes
    if source_stat.st_mtime > target_stat.st_mtime or source_stat.st_size != target_stat.st_size:
        return True
    return False


def handle_option(option):
    user_inputs = {}
    if "inputs" in option:
        for input_detail in option["inputs"]:
            user_input = session.prompt(
                f"Please enter: {input_detail['description']}\n")
            user_inputs[input_detail['name']] = user_input

    results = []  # Lista para almacenar los resultados de cada acción

    # Verificar si alguna acción requiere ejecución de edición
    execute_edition = any(action.get('execute_edition', False)
                          for action in option.get('actions', []))
    if execute_edition:
        prepare_editing_environment()

    # Handle actions
    if "actions" in option:
        results.extend(handle_actions(option["actions"], results, user_inputs))
    else:
        console.print(
            "Error: No actions defined for this option.", style="bold red")

    # Verificar si el último resultado es un JSON con achieved_goal en false
    if results and isinstance(results[-1], dict) and results[-1].get('achieved_goal') == False:
        console.print("Goal not achieved. Choose an option:",
                      style="bold yellow")
        choice = ConsolePrompt.ask("Choose an option", choices=[
                                   '1. Retry', '2. Retry with advice', '3. Exit'], default='1')
        if choice.startswith('1'):
            handle_actions(option["actions"], results,
                           user_inputs)  # Reintentar
        elif choice.startswith('2'):
            advice = session.prompt("Enter advice for retrying: ")
            user_inputs['advice'] = advice
            handle_actions(option["actions"], results, user_inputs)
        elif choice.startswith('3'):
            display_menu()


def display_other_functions(options):
    console.print(Markdown(f"\n\n# Other Functions"), style="bold magenta")
    for index, option in enumerate(options, start=1):
        console.print(f"{index}. {option['description']}", style="bold blue")

    console.print(f"{len(options) + 1}. Return to Main Menu",
                  style="bold blue")
    console.print(f"{len(options) + 2}. Exit Program", style="bold blue")

    choice = ConsolePrompt.ask("Choose an option", choices=[
        str(i) for i in range(1, len(options) + 3)])
    if int(choice) == len(options) + 1:
        display_menu()
        return
    elif int(choice) == len(options) + 2:
        exit_program()  # Sale del programa
    else:
        selected_option = options[int(choice) - 1]
        handle_option(selected_option)
        # Repite el menú después de ejecutar una acción
        display_other_functions(options)


def load_menu_options():
    with open('system/menu_options.json', 'r') as file:
        return json.load(file)


def display_menu():
    console.print(Markdown(f"\n\n# GEMINI WORKSTATION"), style="bold magenta")
    options = load_menu_options()
    main_menu_options = [opt for opt in options if opt.get('main_menu', False)]
    other_functions = [
        opt for opt in options if not opt.get('main_menu', False)]

    for index, option in enumerate(main_menu_options, start=1):
        console.print(f"{index}. {option['description']}", style="bold blue")

    console.print(
        f"{len(main_menu_options) + 1}. Other functions", style="bold blue")
    console.print(
        f"{len(main_menu_options) + 2}. Exit program", style="bold blue")

    choice = ConsolePrompt.ask("Choose an option", choices=[str(
        i) for i in range(1, len(main_menu_options) + 3)])
    if int(choice) == len(main_menu_options) + 1:
        display_other_functions(other_functions)
    elif int(choice) == len(main_menu_options) + 2:
        exit_program()
    else:
        selected_option = main_menu_options[int(choice) - 1]
        handle_option(selected_option)


def save_output(content, user_inputs, prompt):
    """Save the output content to a specified file, now includes user inputs, function name, and prompt name."""
    filename = None
    # Verificar si 'filename' está en user_inputs y usarlo si está presente
    if 'filename' in user_inputs:
        filename = f"{user_inputs['filename']}.txt"
    elif not filename:
        # Nombre de archivo por defecto si no se proporciona
        # Usar el nombre del prompt como nombre de archivo por defecto
        filename = f"output_{prompt}.txt"

    # Asegurarse de que el archivo se guarde en la carpeta 'data'
    filename = Path('data') / filename

    with open(filename, 'w', encoding='utf-8') as file:
        file.write(content)
    console.print(f"Output saved to {filename}", style="bold green")

    # Actualizar data.txt con el nuevo contenido
    update_data_txt(filename, content)


def delete_workspace(previous_results, user_inputs):
    """Delete the workspace after confirmation."""
    console.print(
        "This will delete all contents in the workspace including the insights data and cache.", style="bold red")
    confirmation = session.prompt(
        "Type 'delete' to confirm workspace deletion:\n")
    if confirmation.lower() == 'delete':
        with console.status("[bold green]Deleting workspace contents...") as status:
            # Eliminar contenido de las carpetas 'workstation', 'data' y 'cache'
            for subdir in [WORKSTATION_DIR, DATA_DIR, CACHE_DIR]:
                if os.path.exists(subdir):
                    for root, dirs, files in os.walk(subdir, topdown=False):
                        for name in files:
                            os.remove(os.path.join(root, name))
                            status.update(f"Deleting file: {name}")
                        for name in dirs:
                            os.rmdir(os.path.join(root, name))
                            status.update(f"Removing directory: {name}")
            console.print("Workspace contents deleted.", style="bold green")
    else:
        console.print("Workspace deletion cancelled.", style="bold yellow")
    exit_program()


def update_data_txt(filename, content):
    data_txt_path = Path(CACHE_DIR) / 'data.txt'
    filename = Path(filename).resolve()
    workstation_dir_path = Path(WORKSTATION_DIR).resolve()

    try:
        relative_path = filename.relative_to(workstation_dir_path)
        marker = f"```{relative_path}\n"
    except ValueError:
        relative_path = filename.relative_to(Path.cwd())
        marker = f"```{relative_path}\n"

    # Dividir el contenido en líneas y agregar el número de línea
    lines = content.splitlines()
    numbered_lines = [
        f"[LINE {i + 1}] {line}\n" for i, line in enumerate(lines)]
    new_entry = f"{marker}{''.join(numbered_lines)}```\n"

    if data_txt_path.exists():
        with open(data_txt_path, 'r+', encoding='utf-8') as file:
            existing_content = file.read()
            start_idx = existing_content.find(marker)
            if start_idx != -1:
                end_idx = existing_content.find(
                    "\n```", start_idx + len(marker))
                if end_idx == -1:
                    end_idx = len(existing_content)
                updated_content = existing_content[:start_idx] + \
                    new_entry + existing_content[end_idx:]
            else:
                updated_content = existing_content + new_entry
            file.seek(0)
            file.write(updated_content)
            file.truncate()
    else:
        with open(data_txt_path, 'w', encoding='utf-8') as file:
            file.write(new_entry)


def handle_response_chunks(model_response):
    full_response_text = ""
    live_text = Text()

    # Usar Live para mostrar el texto que va llegando
    with Live(live_text, console=console, auto_refresh=True, transient=True) as live:
        for chunk in model_response:
            text = getattr(chunk, 'text', str(chunk)
                           if isinstance(chunk, str) else None)
            if text is None:
                console.print(
                    f"Received non-text data: {chunk}", style="bold red")
                continue

            # Acumular texto en el texto completo
            full_response_text += text
            # Actualizar el texto en el Live display
            live_text.append(text)
            live.update(live_text)
        live.update(Text(""))
        live.stop()

    return full_response_text


def preprocess_json_response(data):
    """Preprocess the data to either parse a JSON string or convert a Python object to JSON string."""
    try:
        if isinstance(data, str):
            # Intenta cargar la cadena como JSON
            response_json = json.loads(data)
            return response_json  # Devolver el objeto JSON deserializado
        elif isinstance(data, (dict, list)):
            return data  # Devolver la cadena JSON
        else:
            raise TypeError("Unsupported data type for JSON conversion")
    except json.JSONDecodeError as e:
        console.print(f"Error decoding JSON: {e}", style="bold red")
        return None
    except TypeError as e:
        console.print(f"Error: {e}", style="bold red")
        return None


def recreate_data_file(previous_results, user_inputs):
    """Recreate the data.txt file from the workstation and data directories."""
    config = load_config()
    # Limpiar el archivo data.txt antes de escribir
    open(Path(CACHE_DIR) / 'data.txt', 'w').close()
    process_directory(WORKSTATION_DIR, config['dir'], "Workstation")
    process_directory(DATA_DIR, config['dir'], "Extra information")
    console.print("Data has been recreated.", style="bold green")


def exit_program():
    """Exit the program."""
    console.print("\n\nExiting program...", style="bold red")
    exit(0)


def handle_sigint(signum, frame):
    """Handle SIGINT signal (Ctrl+C)."""
    exit_program()


def main():
    """Main function to handle command line arguments and direct program flow."""
    try:
        parser = argparse.ArgumentParser(
            description="Manage local files and repositories.")
        parser.add_argument('path', nargs='?',
                            help='Path to a directory or a repository URL.')
        args = parser.parse_args()

        # Verificar si ya existe un workspace configurado o si hay datos procesados
        if os.path.exists(WORKSTATION_DIR) and os.listdir(WORKSTATION_DIR):
            console.print("Workspace already set up.", style="green")
            display_menu()  # Mostrar el menú directamente si ya hay un workspace
        elif args.path:
            process_input(args.path)
            display_menu()  # Mostrar el menú después de procesar la entrada
        else:
            console.print(
                "Welcome, please enter the directory path or repository URL:", style="yellow")
            path = input()
            if path:
                process_input(path)
                display_menu()  # Mostrar el menú después de procesar la entrada
            else:
                display_menu()  # Mostrar el menú si no se proporciona una entrada
    except KeyboardInterrupt:
        exit_program()  # Llamar a exit_program cuando se detecta una interrupción del teclado


if __name__ == "__main__":
    # Configurar el manejador de señales para SIGINT
    signal.signal(signal.SIGINT, handle_sigint)
    check_api_key()
    main()
