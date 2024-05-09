from rich.prompt import Prompt as ConsolePrompt


def ask_for_feedback(feedback_question: str) -> str:
    """Ask the user a question and return their feedback."""
    feedback = ConsolePrompt.ask(feedback_question)
    return feedback


function_details = {
    "ask_for_feedback": {
        "description": "Asks a question to the user and captures the feedback.",
        "parameters": {
            "feedback_question": "str: The question to be asked to the user."
        },
        "return": "str: The feedback provided by the user.",
        "usage_examples": [
            "ask_for_feedback('Can you expand on what you are looking for?') # User provides more details",
            "ask_for_feedback('Any suggestions for improvement?')  # User provides suggestions"
        ]
    }
}
