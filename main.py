import argparse
import os
import json
import requests
from git import Repo
from pathlib import Path
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt

console = Console()


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


def process_directory(directory, config):
    """Process files in a directory, excluding specified extensions and directories."""
    exclude_extensions = config.get("exclude_extensions", [])
    exclude_directories = config.get("exclude_directories", [])
    with open("repo.txt", "w") as file:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_directories]
            for file_name in files:
                if not any(file_name.endswith(ext) for ext in exclude_extensions):
                    file_path = os.path.join(root, file_name)
                    file.write(
                        f"filename: {file_name}, root: {root}, dir: {directory}\n")
                    with open(file_path, 'r') as content_file:
                        content = content_file.read()
                        file.write(content + "\n")
    console.print(f"Directory processed: {directory}", style="green")


def main():
    """Main function to handle command line arguments and direct program flow."""
    parser = argparse.ArgumentParser(
        description="Manage local files and repositories.")
    parser.add_argument('path', nargs='?',
                        help='Path to a directory or a repository URL.')
    args = parser.parse_args()

    if args.path:
        process_input(args.path)
    else:
        console.print(
            "Welcome, please enter the directory path or repository URL:", style="yellow")
        path = input()
        if path:
            process_input(path)


def process_input(path):
    """Process the input path or URL."""
    if path.startswith(('http://', 'https://')):
        with Progress() as progress:
            task = progress.add_task("[cyan]Cloning repository...", total=100)
            clone_repo(path)
            progress.update(task, advance=100)
    else:
        if not os.path.exists(path):
            console.print("The directory does not exist.", style="red")
            return
        with Progress() as progress:
            task = progress.add_task(
                "[cyan]Processing directory...", total=100)
            process_directory(path, load_config())
            progress.update(task, advance=100)


def load_config():
    """Load configuration from a JSON file."""
    with open('rules.json', 'r') as config_file:
        return json.load(config_file)


def display_menu():
    """Display a menu of options based on prompts.json."""
    with open('prompts.json', 'r') as file:
        prompts = json.load(file)
    for index, prompt in enumerate(prompts, start=1):
        console.print(f"{index}. {prompt['name']}", style="bold blue")
    choice = Prompt.ask("Choose an option", choices=[str(
        i) for i in range(1, len(prompts) + 1)], default="1")
    handle_choice(prompts[int(choice) - 1])


def handle_choice(prompt):
    """Handle user choice from the menu."""
    if 'inputs' in prompt:
        for input_prompt in prompt['inputs']:
            user_input = Prompt.ask(
                f"{input_prompt['description']}", style="bold magenta")
            # Process the input as needed
    console.print(prompt['prompt'], style="bold green")


if __name__ == "__main__":
    display_menu()
    main()
