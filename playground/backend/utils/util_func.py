RESET = "\033[0m"
PROMPT_COLOR = "\033[96m"  # light cyan
RESPONSE_COLOR = "\033[92m"  # light green
MUTED_COLOR = "\033[90m"  # gray
INFO_COLOR = "\033[95m"  # magenta


def log_response_details(prompt: str, result) -> None:
    """Log the prompt, generated text, and response metadata."""
    response_text = getattr(result, "text", "") or "(empty)"
    usage_metadata = getattr(result, "usage_metadata", None)
    model_version = getattr(result, "model_version", "(unknown)")
    print(f"{MUTED_COLOR}{'- ' * 50}{RESET}")
    print(f"{PROMPT_COLOR}Prompt:{RESET}")
    print(f"{PROMPT_COLOR}{prompt or '(empty)'}{RESET}")
    print()
    print(f"{RESPONSE_COLOR}Response:{RESET}")
    print(f"{RESPONSE_COLOR}{response_text}{RESET}")
    print()
    if usage_metadata:
        usage_line = ' | '.join(line.strip() for line in str(usage_metadata).splitlines() if line.strip())
    else:
        usage_line = "(usage unavailable)"
    print(f"{INFO_COLOR}[{model_version}] {usage_line}{RESET}")
    print(f"{MUTED_COLOR}{'-' * 50}{RESET}\n")


def log_debug_message(message):
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{INFO_COLOR}{message}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")

def log_prompt(prompt):
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{PROMPT_COLOR}{prompt}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")

def log_response(response):
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{RESPONSE_COLOR}{response}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")