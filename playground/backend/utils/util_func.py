RESET = "\033[0m"
PROMPT_COLOR = "\033[96m"  # light cyan
RESPONSE_COLOR = "\033[92m"  # light green
MUTED_COLOR = "\033[90m"  # gray
INFO_COLOR = "\033[95m"  # magenta
YELLOW = "\033[93m"  # yellow
BLUE = "\033[94m"  # blue
GREEN = "\033[92m"  # green
RED = "\033[91m"  # red
CYAN = "\033[96m"  # cyan
WHITE = "\033[97m"  # white
BOLD = "\033[1m"  # bold


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
    """Simple single-line debug message - no extra decorations"""
    print(f"{INFO_COLOR}{message}{RESET}")


def log_prompt(prompt):
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{PROMPT_COLOR}{prompt}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")


def log_response(response):
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{RESPONSE_COLOR}{response}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")


def log_user_message(message: str):
    """Log user message with cyan color and box"""
    preview = message[:100].replace('\n', ' ')
    print(f"{CYAN}{BOLD}👤 USER:{RESET} {CYAN}{preview}{'...' if len(message) > 100 else ''}{RESET}")


def log_llm_response(response: str):
    """Log LLM response with green color and box"""
    preview = response[:150].replace('\n', ' ') if response else "(empty)"
    print(f"{GREEN}{BOLD}🤖 LLM:{RESET} {GREEN}{preview}{'...' if len(response) > 150 else ''}{RESET}")


def log_chat_header(model: str, mode: str, context_cells: int):
    """Log chat request header"""
    print(f"")
    print(f"{YELLOW}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{YELLOW}║{RESET} {WHITE}{BOLD}💬 CHAT REQUEST{RESET}                                                       {YELLOW}║{RESET}")
    print(f"{YELLOW}╠══════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{YELLOW}║{RESET} 🧠 Model: {CYAN}{model:12}{RESET} │ ⚙️  Mode: {CYAN}{mode:8}{RESET} │ 📝 Context: {CYAN}{context_cells:3}{RESET} cells {YELLOW}║{RESET}")
    print(f"{YELLOW}╚══════════════════════════════════════════════════════════════════════╝{RESET}")


def log_llm_response_box(response: str):
    """Log full LLM response with header"""
    print(f"")
    print(f"{GREEN}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║ 🤖 LLM RESPONSE ({len(response)} chars)                                          {GREEN}║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{GREEN}{response if response else '(empty)'}{RESET}")
    print(f"{GREEN}{'─' * 72}{RESET}")
    print(f"")
