from rich.prompt import Prompt
from rich.console import Console

console = Console()


def ask_the_user(feedback_question: str) -> str:
    """Ask the user a question and return their feedback."""
    feedback = Prompt.ask(f"[bold yellow]{feedback_question}")
    return f"[question]{feedback_question}[/question][answer]{feedback}[/answer]"


def chose_options(question: str, options: list) -> str:
    choice = Prompt.ask(f"[bold yellow]{question}", choices=options)
    return f"[question]{question}[/question][options]{options}[/options][choice]{choice}[/choice]"


functions_declaration = [{
    "name": "ask_the_user",
    "description": "Ask the user a question and return their feedback.",
    "parameters": [{
        "feedback_question": {"type": "string", "description": "The question to be asked to the user."}
    }]
}, {
    "name": "chose_options",
    "description": "Make the user choose one of the options in the list of options that you provide. In the question, provide the posible choices with their number, and in the options, provide the list numbers. Like this: question: '1. Option 1\n2. Option 2\n3. Option 3', choices: [1, 2, 3]",
    "parameters": [{
        "question": {"type": "string", "description": "List all the options with their number, like this: question: '1. Option 1\n2. Option 2\n3. Option 3'. If you are going to show the question in your text resonse, then leave the question empty."},
        "options": {"type": "array", "description": "The list of numbers relative to the options to be chosen from, like this: [1, 2, 3]", "items": {"type": "number", "description": "One option to be chosen from, example: 1"}}
    }]
}]
