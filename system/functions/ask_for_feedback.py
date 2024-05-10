from rich.prompt import Prompt as ConsolePrompt


def ask_for_feedback(feedback_question: str) -> str:
    """Ask the user a question and return their feedback."""
    feedback = ConsolePrompt.ask(
        f"[italic yellow]- Gemini asks: {feedback_question}[/italic yellow]")
    return f"[question]{feedback_question}[/question][feedback]{feedback}[/feedback]"


def chose_options(question: str, options: list) -> str:
    choice = ConsolePrompt.ask(
        f"[italic yellow]- Gemini asks: {question}[/italic yellow]", choices=options)
    return f"[question]{question}[/question][options]{options}[/options][choice]{choice}[/choice]"


functions_declaration = [{
    "name": "ask_for_feedback",
    "description": "Ask the user a question and return their feedback.",
    "parameters": [{
        "feedback_question": {"type": "string", "description": "The question to be asked to the user."}
    }]
}, {
    "name": "chose_options",
    "description": "Make the user choose one of the options in the list of options that you provide.",
    "parameters": [{
        "question": {"type": "string", "description": "Inform the user the decision that he must take."},
        "options": {"type": "array", "description": "The list of options to be chosen from.", "items": {"type": "string", "description": "One option to be chosen from."}}
    }]
}]
