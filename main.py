import argparse
import os
import re
import json
import signal
import requests
import traceback
import importlib.util
from datetime import datetime
from prompt_toolkit import PromptSession

from shutil import copy
from pathlib import Path
from git import Repo
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt as ConsolePrompt
from rich.markdown import Markdown
from rich.spinner import Spinner

import google.generativeai as genai
import google.api_core.exceptions
from google.generativeai import GenerationConfig

WORKSTATION_DIR = os.getenv('WORKSTATION_DIR', 'workstation')
DATA_DIR = os.getenv('DATA_DIR', 'data')
CACHE_DIR = os.getenv('CACHE_DIR', 'cache')
SYSTEM_DIR = os.getenv('SYSTEM_DIR', 'system')
MAX_OUTPUT_TOKENS = os.getenv('MAX_OUTPUT_TOKENS', 4000)
SAVE_PROMPT_HISTORY = os.getenv('SAVE_PROMPT_HISTORY', True)
SAVE_OUTPUT_HISTORY = os.getenv('SAVE_OUTPUT_HISTORY', True)
DEBUG = os.getenv('DEBUG', True)

console = Console(highlight=False)
session = PromptSession()


def load_functions_from_directory(directory=os.path.join(SYSTEM_DIR, 'functions')):
    for filename in os.listdir(directory):
        if filename.endswith('.py'):
            module_name = filename[:-3]  # Remove the '.py' from filename
            module_path = os.path.join(directory, filename)
            spec = importlib.util.spec_from_file_location(
                module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Import all functions from the module
            globals().update(
                {k: v for k, v in module.__dict__.items() if callable(v)})


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
    """Check if the GOOGLE_API_KEY environment variable is set. If not, prompt the user to set it."""
    try:
        api_key = os.environ['GOOGLE_API_KEY']
        console.print("API Key is set.", style="green")
    except KeyError:
        console.print(
            "API Key is not set. Please visit https://aistudio.google.com/app/apikey to obtain your API key.", style="bold red")
        api_key = session.prompt("Enter your GOOGLE_API_KEY: ")
        # Set the environment variable for the current session
        os.environ['GOOGLE_API_KEY'] = api_key
        genai.configure(api_key=api_key)


def format_prompt(prompt_content, previous_results, user_inputs):
    with open(SYSTEM_DIR + '/base_prompt.md', 'r', encoding='utf-8') as file:
        base_prompt_content = file.read()
    with open(CACHE_DIR + '/data.txt', 'r', encoding='utf-8') as file:
        attached_content = file.read()
    # Aquí puedes agregar lógica para incluir user_inputs y previous_results en el prompt
    return f"{base_prompt_content}\n\n{prompt_content}\n\nUser inputs: {user_inputs}\n\nPrevious Results: {previous_results}\n\nAttached data: {attached_content}"


@handle_errors
def call_gemini_api(prompt, output_format=None):
    try:
        with console.status("[bold yellow]Uploading data and waiting for Gemini...") as status:
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
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

            if SAVE_OUTPUT_HISTORY:
                # Guardar el prompt y la respuesta en la carpeta de outputs
                outputs_path = cache_path / 'outputs_history'
                outputs_path.mkdir(exist_ok=True)
                output_filename = outputs_path / f"{timestamp}.txt"
                with open(output_filename, 'w', encoding='utf-8') as file:
                    file.write(
                        f"Prompt:\n{prompt}\n\nResponse:\n{full_response}")

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
    console.print(path)
    """Process the input path or URL."""
    if isinstance(path, list):
        console.print(
            "Error: Expected a string for 'path', but got a list.", style="bold red")
        return
    if path.startswith(('http://', 'https://')):
        with Spinner("Cloning repository...") as spinner:
            clone_repo(path)
            spinner.update("Repository cloned successfully!")
    else:
        if not os.path.exists(path):
            console.print("The path does not exist.", style="red")
            return
        if os.path.isdir(path):
            with Spinner("Processing directory...") as spinner:
                process_directory(path, load_config())
                spinner.update("Directory processed successfully!")
        elif os.path.isfile(path):
            workstation_path = Path(WORKSTATION_DIR)
            workstation_path.mkdir(exist_ok=True)
            copy(path, workstation_path)
            console.print(
                f"File {path} copied to {workstation_path}.", style="green")


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
        formatted_prompt = format_prompt(
            prompt_content, previous_results, user_inputs)
        return call_gemini_api(formatted_prompt, output_format)
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
        console.print(action, style="bold blue")
        result = execute_action(action, previous_results, user_inputs)
        console.print(result, style="yellow")
        if result is not None:
            previous_results.append(result)
    return results


def handle_option(option):
    user_inputs = {}
    console.print(f"{option}", style="bold blue")
    if "inputs" in option:
        for input_detail in option["inputs"]:
            user_input = session.prompt(
                f"Please enter: {input_detail['description']}\n")
            user_inputs[input_detail['name']] = user_input

    results = []  # Lista para almacenar los resultados de cada acción
    # Handle actions
    if "actions" in option:
        results.extend(handle_actions(option["actions"], results, user_inputs))
    else:
        console.print(
            "Error: No actions defined for this option.", style="bold red")


def display_other_functions(options):
    console.print("## Other Functions ##", style="bold magenta")
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
    console.print("## GEMINI WORKSTATION ##", style="bold magenta")
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
        "Type 'delete' to confirm workspace deletion")
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

    with console.status("[bold green]Getting data from Gemini...") as status:
        for chunk in model_response:
            text = getattr(chunk, 'text', str(chunk)
                           if isinstance(chunk, str) else None)
            if text is None:
                console.print(
                    f"Received non-text data: {chunk}", style="bold red")
                continue

            # Acumular texto en el texto completo
            full_response_text += text
            # Imprimir el texto a medida que llega
            print(text, end='', flush=True)

    return full_response_text


def preprocess_json_response(data):
    """Preprocess the data to either parse a JSON string or convert a Python object to JSON string."""
    try:
        if isinstance(data, str):
            # Intenta cargar la cadena como JSON
            response_json = json.loads(data)
            console.print(response_json, style="bold green")
            return response_json  # Devolver el objeto JSON deserializado
        elif isinstance(data, (dict, list)):
            console.print(data, style="bold green")
            return data  # Devolver la cadena JSON
        else:
            raise TypeError("Unsupported data type for JSON conversion")
    except json.JSONDecodeError as e:
        console.print(f"Error decoding JSON: {e}", style="bold red")
        return None
    except TypeError as e:
        console.print(f"Error: {e}", style="bold red")
        return None


@handle_errors
def apply_modifications(previous_results, user_inputs=None):
    modifications = previous_results[-1]
    console.print('modifications:\n' + modifications, style="bold yellow")
    modifications = preprocess_json_response(modifications)
    console.print('modifications2:\n', style="bold yellow")
    console.print(modifications, style="bold yellow")

    modifications_made = []  # Lista para rastrear las modificaciones realizadas

    with console.status("[bold green]Applying modifications...") as status:
        total_modifications = len(modifications)
        for index, modification in enumerate(modifications, start=1):
            if not isinstance(modification, dict) or not {'file', 'action'}.issubset(modification.keys()):
                console.print(
                    f"Error: Modification is not a dictionary or missing required fields in modification for {modification}.", style="bold red")
                continue

            file_path = modification['file']
            if not file_path.startswith('/') and not file_path.startswith('./'):
                file_path = '/' + file_path
            file_path = f"{Path(WORKSTATION_DIR)}{file_path}"

            with open(file_path, 'r') as file:
                lines = file.readlines()

            action = modification['action']

            if action == 'replace':
                if 'start_line' in modification and 'end_line' in modification and 'content' in modification:
                    start_index = modification['start_line'] - 1
                    end_index = modification['end_line']
                    console.print(
                        f"Attempting to replace content from line {start_index+1} to line {end_index} in {file_path}", style="bold yellow")

                    original_content = ''.join(
                        lines[start_index:end_index]).strip()
                    lines[start_index:end_index] = [
                        modification['content'].strip() + '\n']

                    if original_content != ''.join(lines[start_index:end_index]).strip():
                        console.print(
                            f"Content replaced successfully.", style="bold green")
                        modifications_made.append(modification)
                    else:
                        console.print(
                            f"No content changes made.", style="bold yellow")

                    console.print(
                        f"File: {file_path} - Replace action completed.", style="bold green")
                else:
                    console.print(
                        f"Error: Missing fields for 'replace' action in {file_path}.", style="bold red")
                    continue

            elif action == 'insert':
                if 'start_line' in modification and 'content' in modification:
                    lines.insert(
                        modification['start_line'], modification['content'].strip() + '\n')
                    console.print(
                        f"File: {file_path} - Insert action completed.", style="bold green")
                    modifications_made.append(modification)
                else:
                    console.print(
                        f"Error: Missing fields for 'insert' action in {file_path}.", style="bold red")
                    continue

            elif action == 'delete':
                if 'start_line' in modification and 'end_line' in modification:
                    del lines[modification['start_line'] -
                              1:modification['end_line']]
                    console.print(
                        f"File: {file_path} - Delete action completed.", style="bold green")
                    modifications_made.append(modification)
                else:
                    console.print(
                        f"Error: Missing fields for 'delete' action in {file_path}.", style="bold red")
                    continue

            elif action == 'replace_regex':
                if 'start_line' in modification and 'end_line' in modification and 'replace_regex' in modification and 'content' in modification:
                    pattern = re.compile(modification['replace_regex'])
                    for i in range(modification['start_line'] - 1, modification['end_line']):
                        original_line = lines[i]
                        lines[i] = pattern.sub(
                            modification['content'], lines[i])
                        if lines[i] != original_line:
                            console.print(
                                f"Replaced content in line {i + 1} with regex.", style="bold green")
                            modifications_made.append(modification)
                    console.print(
                        f"File: {file_path} - Replace regex action completed.", style="bold green")
                else:
                    console.print(
                        f"Error: Missing fields for 'replace_regex' action in {file_path}.", style="bold red")
                    continue

            with open(file_path, 'w') as file:
                file.writelines(lines)

            status.update(
                f"Processing {index}/{total_modifications} modifications")

    return modifications_made  # Devolver la lista de modificaciones realizadas


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
    console.print("Exiting program...", style="bold red")
    exit(0)


def handle_sigint(signum, frame):
    """Handle SIGINT signal (Ctrl+C)."""
    exit_program()


# Configurar el manejador de señales para SIGINT
signal.signal(signal.SIGINT, handle_sigint)


def main():
    """Main function to handle command line arguments and direct program flow."""
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


if __name__ == "__main__":
    check_api_key()
    load_functions_from_directory()
    main()
