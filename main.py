import argparse
import sys
import os
import time
import json
import signal
import shutil
import requests

import traceback
import importlib.util

from git import Repo
from shutil import copy
from pathlib import Path
from threading import Thread
from datetime import datetime
from rich.live import Live
from rich.text import Text
from rich.console import Console
from pytimedinput import timedKey
from rich.markdown import Markdown
from rich.prompt import Prompt as ConsolePrompt
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.shortcuts import CompleteStyle

import google.generativeai as genai
import google.api_core.exceptions
# TODO Implement this: Content, Part, FunctionResponse, FunctionCall
from google.protobuf.json_format import MessageToJson
from google.ai.generativelanguage import FunctionDeclaration, Tool, Schema, Type


DEBUG = os.getenv('DEBUG', False)
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
FEEDBACK_TIMEOUT = int(os.getenv('FEEDBACK_TIMEOUT', 4))


console = Console()
session = PromptSession(
    history=InMemoryHistory(),
    auto_suggest=AutoSuggestFromHistory(),
    complete_style=CompleteStyle.READLINE_LIKE
)


def option_timer(instruction, responseOnTimeout=True, responseOnEnter=True, responseOnESC=False, timeout=FEEDBACK_TIMEOUT):
    """
    Display a prompt with a countdown timer. Return True if the user presses Enter before the timer expires, otherwise return False.
    """
    user_input = [None]  # Use a list to hold the mutable reference
    time_start = time.time()

    def wait_for_input(timeout):
        nonlocal user_input
        user_input[0], timed_out = timedKey(timeout=timeout)
        return not timed_out

    try:
        with console.status(f"[bold yellow]Continues in {int(timeout)} secs[/bold yellow] - {instruction}", spinner="dots") as status:
            input_thread = Thread(target=wait_for_input, args=[timeout])
            input_thread.daemon = True
            input_thread.start()
            while input_thread.is_alive():
                input_thread.join(timeout=0.1)
                remaining = timeout - (time.time() - time_start)
                status.update(
                    f"[bold yellow]Continues in {int(remaining)} secs[/bold yellow] - {instruction}")
    except KeyboardInterrupt:
        exit_program()
    finally:
        if input_thread.is_alive():
            input_thread.join()

    if user_input[0] == "\n":  # ASCII code for the 'Enter' key
        return responseOnEnter
    elif user_input[0] == "\x1b":  # ASCII code for the 'Esc' key
        return responseOnESC
    else:
        return responseOnTimeout


def create_function_declaration(func):
    """
    Create a function declaration from a function object.
    """
    from inspect import signature, _empty
    sig = signature(func)
    properties = {}
    for param_name, param in sig.parameters.items():
        param_type = str(param.annotation).split(
            "'")[1] if param.annotation != _empty else 'string'
        properties[param_name] = {
            "type_": Type.STRING if param_type == 'string' else Type.OBJECT,
            "description": f"The {param_name} of the function."
        }

    return FunctionDeclaration(
        name=func.__name__,
        description=func.__doc__,
        parameters=Schema(type_=Type.OBJECT, properties=properties)
    )


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
                f"An unexpected error occurred, wanna try again?", style="red")
            if DEBUG:
                console.print(e, traceback.format_exc(), style="bold red")
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
    """Check if the GOOGLE_API_KEY environment variable is set. If not, prompt the user to set it."""
    try:
        api_key = os.environ['GOOGLE_API_KEY']
        console.print("API Key is set.", style="green")
    except KeyError:
        console.print(
            "API Key is not set. Please visit https://aistudio.google.com/app/apikey to obtain your API key.", style="bold red")
        api_key = session.prompt("Enter your GOOGLE_API_KEY: ")
        genai.configure(api_key=api_key)


def load_functions_from_directory(directory=os.path.join(SYSTEM_DIR, 'functions')):
    loaded_functions = []
    function_declarations = []
    for filename in os.listdir(directory):
        if filename.endswith('.py'):
            module_name = filename[:-3]  # Remove the '.py' from filename
            module_path = os.path.join(directory, filename)
            spec = importlib.util.spec_from_file_location(
                module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            # Create a custom namespace for the module to prevent imports from affecting globals
            module_namespace = {}
            # Load the module into the custom namespace
            # Temporarily add the module to sys.modules
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                # Copy only user-defined functions from the module to the namespace
                for func_name, func in module.__dict__.items():
                    if callable(func) and not isinstance(func, type) and not func_name.startswith("__"):
                        if any(d['name'] == func_name for d in getattr(module, 'functions_declaration', [])):
                            loaded_functions.append(func)
                            # Add function to custom namespace
                            module_namespace[func_name] = func
                            # Add function to global scope
                            globals()[func_name] = func
                            try:
                                func_decl = create_function_declaration(func)
                                function_declarations.append(func_decl)
                            except Exception as e:
                                console.print(
                                    f"Error creating function declaration for {func_name}: {str(e)}", style="bold red")
                        else:
                            console.print(
                                f"Warning: Function {func_name} in {filename} is not declared in functions_declaration.", style="bold yellow")
            finally:
                # Remove the module from sys.modules
                del sys.modules[module_name]
    return loaded_functions, function_declarations


def load_and_configure_model(system_prompt, output_format, use_tools):
    tools = []
    if use_tools:
        loaded_functions, function_declarations = load_functions_from_directory()
        # Crear herramientas a partir de las declaraciones de funciones
        tools = [Tool(function_declarations=function_declarations)]

    generation_config = genai.GenerationConfig(
        max_output_tokens=MAX_OUTPUT_TOKENS)

    if output_format == "JSON":
        generation_config.response_mime_type = "application/json"
    # Configurar el modelo con las herramientas y la configuración de herramientas
    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=system_prompt,
        generation_config=generation_config,
        tools=tools
    )

    return model


def format_prompt(prompt_name, previous_results, user_inputs):
    with open(SYSTEM_DIR + '/base_prompt.md', 'r', encoding='utf-8') as file:
        system_prompt = file.read()
    with open(SYSTEM_DIR + '/prompts/' + prompt_name + '.md', 'r', encoding='utf-8') as file:
        system_prompt += file.read()
    with open(CACHE_DIR + '/data.txt', 'r', encoding='utf-8') as file:
        attached_content = file.read()

    prompt = " "
    # Construir el prompt completo con todas las secciones
    if user_inputs and user_inputs != []:
        prompt += f"\n\n```USER INPUTS SECTION:\n{user_inputs}\n```"
    if previous_results:
        prompt += f"\n\n```PREVIOUS RESULTS SECTION:\n{previous_results}\n```"
    if attached_content:
        prompt += f"\n\n```ATTACHED DATA SECTION:\n{attached_content}\n```"
    if DEBUG:
        console.print('prompt', prompt, style="yellow")
    return system_prompt, prompt


def args_to_text(args):
    """
    Attempt to serialize arguments to a JSON-compatible format.
    Handles complex objects by converting them to a string representation if not directly serializable.
    """
    try:
        json_object = MessageToJson(args)
        return json.dumps(json_object)
    except TypeError as e:
        console.print(
            f"Failed to serialize arguments: {str(e)}", style="bold red")


def handle_function_call(response, output_format):
    full_actions_response = ""
    full_text_response = ""
    function_calls = []  # Array to store function calls

    if hasattr(response, 'candidates'):
        for candidate in response.candidates:
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text != "":
                        full_text_response += part.text
                    if hasattr(part, 'function_call') and hasattr(part.function_call, 'name'):
                        function_calls.append(part.function_call)

    if output_format != "JSON":
        console.print(Markdown(full_text_response, justify='left'))

    # Execute collected function calls
    for func_call in function_calls:
        func_name = func_call.name
        args = getattr(func_call, 'args', {})
        # Check if the function exists in the global scope before calling it
        if func_name in globals():
            try:
                if DEBUG:
                    console.print(
                        f"Calling function {func_name} with args {args}", style="blue italic")
                function_to_call = globals()[func_name]
                result = function_to_call(**args)
                if DEBUG:
                    console.print(
                        f"Function returned: {result}", style="green italic")
                full_actions_response += f"- function_name: {func_name} - function_response: {result}"
            except Exception as e:
                console.print(
                    f"Error executing function {func_name}: {str(e)}", style="bold red")
        else:
            if func_name:
                console.print(
                    f"Function {func_name} is not defined", style="bold red")

    return full_text_response, full_actions_response


@handle_errors
def call_gemini_api(system_prompt, prompt, output_format=None, use_tools=False):
    try:
        with console.status("[bold yellow]Uploading data and waiting for Gemini...") as status:
            if DEBUG:
                console.print("\n-- Model name:", MODEL_NAME, style="yellow")

            model = load_and_configure_model(
                system_prompt, output_format, use_tools)

            cache_path = Path('cache')

            if SAVE_PROMPT_HISTORY:
                prompt_history_path = cache_path / 'prompts_history'
                prompt_history_path.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                prompt_filename = prompt_history_path / f"{timestamp}.txt"

                with open(prompt_filename, 'w', encoding='utf-8') as file:
                    file.write('~~~~~~~~~~ Prompt\n'+prompt +
                               '\n\n~~~~~~~~~~ System Prompt\n'+system_prompt)

            token_count = model.count_tokens(system_prompt+prompt).total_tokens
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

            chat = model.start_chat(
                enable_automatic_function_calling=use_tools
            )
            response = chat.send_message(
                prompt
            )

            if DEBUG:
                console.print("\n-- Response:\n", response, style="yellow")

            status.stop()
            if use_tools:
                full_text_response, full_actions_response = handle_function_call(
                    response, output_format)
            else:
                full_text_response = handle_response_chunks(response)
                if output_format != "JSON":
                    console.print(Markdown(full_text_response, justify='left'))

            if SAVE_OUTPUT_HISTORY:
                outputs_path = cache_path / 'outputs_history'
                outputs_path.mkdir(exist_ok=True)
                output_filename = outputs_path / f"{timestamp}.txt"
                with open(output_filename, 'w', encoding='utf-8') as file:
                    file.write(
                        f'~~~~~~~~~~ Response text:\n{full_text_response}\n\n~~~~~~~~~~ Response actions:\n{full_actions_response}\n\n~~~~~~~~~~ Prompt\n{prompt}\n\n~~~~~~~~~~ System Prompt\n{system_prompt}\n')

            return full_text_response, full_actions_response
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


def process_path_workstation_input(path):
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
            new_path = session.prompt()
            if new_path:
                process_path_workstation_input(new_path)
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
    use_tools = action.get("tools", False)

    if "prompt" in action:
        system_prompt, prompt = format_prompt(
            action['prompt'], previous_results, user_inputs)
        return call_gemini_api(system_prompt, prompt, output_format, use_tools)
    elif "function" in action:
        function_name = action["function"]
        if function_name in globals():
            function_to_call = globals()[function_name]
            return None, function_to_call(previous_results, user_inputs)
        else:
            console.print(
                f"Function {function_name} is not defined", style="bold red")
            return None, None
    return None, None


def handle_action(action, previous_results, user_inputs):
    if 'prompt' in action:
        console.print(Markdown(
            f"\n\n# Processing prompt: {action['prompt']}"), style="bold bright_blue")
    elif 'function' in action:
        console.print(Markdown(
            f"\n\n# Executing action: {action['function']}"), style="bold bright_blue")
    else:
        console.print("Error: No action defined for this option.",
                      style="bold red")
        exit_program()

    # Capture user feedback with a 2-second timeout only for 'prompt' actions
    if 'prompt' in action and 'pre_feedback' in action:
        user_inputs = handle_feedback(user_inputs)
    # Execute action
    text, actions = execute_action(action, previous_results, user_inputs)

    return text, actions


def handle_feedback(user_inputs, directly=False):
    user_inputs['feedback'] = user_inputs.get('feedback', [])
    feedback = directly or option_timer(
        "[red]Press ESC to continues[/red] - [green]Press Enter to add feedback[/green]", responseOnTimeout=False)
    if feedback:
        user_feedback = session.prompt(
            HTML("<yellow><bold><italic>Provide feedback</italic></bold></yellow> "))
        if user_feedback:
            user_inputs['feedback'].append(user_feedback)
    return user_inputs


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
            console.print(f"{input_detail['description']}", style="yellow")
            user_input = session.prompt()
            user_inputs[input_detail['name']] = user_input

    results = []  # Lista para almacenar los resultados de cada acción

    # Verificar si alguna acción requiere ejecución de edición
    if "use_tools" in option:
        prepare_editing_environment()

    # Handle actions
    if "actions" in option:
        while True:
            for action in option["actions"]:
                text, actions = handle_action(action, results, user_inputs)
                if text is not None:
                    results.append(text)
                if actions is not None and type(actions) == str:
                    results.append(actions)
            not_continue = option_timer(
                "[red]Press Esc to abort[/red] - [green]Press Enter add feedback[/green]", responseOnTimeout=True, responseOnEnter='feedback')
            if not_continue == 'feedback':
                user_inputs = handle_feedback(user_inputs, directly=True)
            if not not_continue:
                break

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
    with open(f'{SYSTEM_DIR}/menu_options.json', 'r') as file:
        try:
            return json.load(file)
        except Exception as e:
            console.print(
                f"Error loading menu options:\n{e}", style="bold red")
            exit_program()


def display_menu():
    console.print(Markdown(f"\n\n# GEMINI WORKSTATION"), style="bold magenta")
    options = load_menu_options()
    main_menu_options = [opt for opt in options if opt.get('main_menu', False) and (
        not opt.get('debug_menu', False) or (opt.get('debug_menu', False) and DEBUG))]
    other_functions = [
        opt for opt in options if not opt.get('main_menu', False) and (not opt.get('debug_menu', False) or (opt.get('debug_menu', False) and DEBUG))]

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


def set_workspace(previous_results, user_inputs):
    """Set up the workspace by cloning the repository, if a URL is provided, or by copying the local directory, if a path is provided."""
    console.print(
        "Please enter the directory path or repository URL:", style="yellow")
    path = session.prompt()
    process_path_workstation_input(path)


def show_help(previous_results, user_inputs):
    """Show how to use this tool."""
    # Fetch the content of INFO.md from the root of the project and display it using Markdown
    with open('INFO.md', 'r', encoding='utf-8') as file:
        info_content = file.read()
    console.print(Markdown(info_content, justify='left'),
                  style="italic light_coral")


def recreate_data_file(previous_results, user_inputs):
    """Recreate the data.txt file from the workstation and data directories."""
    config = load_config()
    # Limpiar el archivo data.txt antes de escribir
    open(Path(CACHE_DIR) / 'data.txt', 'w').close()
    process_directory(WORKSTATION_DIR, config['workspace_dir'], "Workstation")
    process_directory(DATA_DIR, config['workspace_dir'], "Extra information")
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
        display_menu()  # Mostrar el menú si no se proporciona una entrada
    except KeyboardInterrupt:
        exit_program()  # Llamar a exit_program cuando se detecta una interrupción del teclado


if __name__ == "__main__":
    # Configurar el manejador de señales para SIGINT
    signal.signal(signal.SIGINT, handle_sigint)
    check_api_key()
    main()
