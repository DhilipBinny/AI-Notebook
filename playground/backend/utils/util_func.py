"""
Utility functions for logging and debugging.

Short function names for easy use:
- log()          - debug message
- log_err()      - error message
- log_warn()     - warning message
- log_request()  - LLM request details
- log_chat()     - chat header
- log_ai_cell()  - AI cell header
- log_user()     - user message
- log_resp()     - LLM response preview
- log_resp_box() - full LLM response
- log_cache()    - cache info
- log_tool()     - tool call
- log_tool_res() - tool result
"""

# ANSI Color codes
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


# =============================================================================
# Core Debug Logging
# =============================================================================

def log(message: str) -> None:
    """Simple single-line debug message."""
    print(f"{INFO_COLOR}{message}{RESET}")


def log_err(message: str) -> None:
    """Log error message."""
    print(f"{RED}{BOLD}ERROR:{RESET} {RED}{message}{RESET}")


def log_warn(message: str) -> None:
    """Log warning message."""
    print(f"{YELLOW}{BOLD}WARNING:{RESET} {YELLOW}{message}{RESET}")


# =============================================================================
# LLM Request/Response Logging
# =============================================================================

def log_request(
    source: str,
    provider: str,
    context_format: str,
    notebook_context: str,
    user_prompt: str,
    context_cells: int = 0,
    tool_mode: str = None,
    position_info: str = None,
) -> None:
    """
    Log LLM request details in a structured format.

    Args:
        source: "CHAT" or "AI_CELL"
        provider: LLM provider name (anthropic, gemini, etc.)
        context_format: Format used (xml, json, plain)
        notebook_context: The formatted notebook context
        user_prompt: The user's question/prompt
        context_cells: Number of context cells
        tool_mode: Tool execution mode (for chat)
        position_info: Cell position info (for AI cell)
    """
    print(f"\n{'='*80}")
    print(f"{CYAN}{BOLD}📋 {source} REQUEST TO LLM [{provider.upper()}]{RESET}")
    print(f"{'='*80}")
    print(f"Format: {context_format}")
    print(f"Context cells: {context_cells}")
    if tool_mode:
        print(f"Tool mode: {tool_mode}")
    if position_info:
        print(f"Position: {position_info}")
    print(f"{'─'*80}")

    # Context logging - always show full content
    ctx_len = len(notebook_context) if notebook_context else 0
    print(f"NOTEBOOK CONTEXT ({ctx_len} chars):")
    if notebook_context:
        print(f"{MUTED_COLOR}{notebook_context}{RESET}")
    else:
        print(f"{MUTED_COLOR}(empty){RESET}")

    print(f"{'─'*80}")

    # User prompt logging - always show full content
    prompt_len = len(user_prompt) if user_prompt else 0
    print(f"USER PROMPT ({prompt_len} chars):")
    if user_prompt:
        print(f"{CYAN}{user_prompt}{RESET}")
    else:
        print(f"{MUTED_COLOR}(empty){RESET}")

    print(f"{'='*80}")
    print(f"Stats: context={ctx_len} chars, user_prompt={prompt_len} chars")
    print(f"{'='*80}\n")


def log_chat(model: str, mode: str, context_cells: int) -> None:
    """Log chat request header."""
    print(f"")
    print(f"{YELLOW}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{YELLOW}║{RESET} {WHITE}{BOLD}💬 CHAT REQUEST{RESET}                                                       {YELLOW}║{RESET}")
    print(f"{YELLOW}╠══════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{YELLOW}║{RESET} 🧠 Model: {CYAN}{model:12}{RESET} │ ⚙️  Mode: {CYAN}{mode:8}{RESET} │ 📝 Context: {CYAN}{context_cells:3}{RESET} cells {YELLOW}║{RESET}")
    print(f"{YELLOW}╚══════════════════════════════════════════════════════════════════════╝{RESET}")


def log_ai_cell(provider: str, cell_position: int, total_cells: int) -> None:
    """Log AI cell request header."""
    print(f"")
    print(f"{BLUE}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BLUE}║{RESET} {WHITE}{BOLD}🤖 AI CELL REQUEST{RESET}                                                    {BLUE}║{RESET}")
    print(f"{BLUE}╠══════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{BLUE}║{RESET} 🧠 Provider: {CYAN}{provider:10}{RESET} │ 📍 Position: Cell {CYAN}#{cell_position}{RESET} of {CYAN}{total_cells}{RESET}        {BLUE}║{RESET}")
    print(f"{BLUE}╚══════════════════════════════════════════════════════════════════════╝{RESET}")


def log_user(message: str) -> None:
    """Log user message with cyan color."""
    preview = message[:100].replace('\n', ' ')
    print(f"{CYAN}{BOLD}👤 USER:{RESET} {CYAN}{preview}{'...' if len(message) > 100 else ''}{RESET}")


def log_resp(response: str) -> None:
    """Log LLM response preview."""
    preview = response[:150].replace('\n', ' ') if response else "(empty)"
    print(f"{GREEN}{BOLD}🤖 LLM:{RESET} {GREEN}{preview}{'...' if len(response) > 150 else ''}{RESET}")


def log_resp_box(response: str) -> None:
    """Log full LLM response with header."""
    print(f"")
    print(f"{GREEN}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{GREEN}║ 🤖 LLM RESPONSE ({len(response)} chars)                                          {GREEN}║{RESET}")
    print(f"{GREEN}╚══════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{GREEN}{response if response else '(empty)'}{RESET}")
    print(f"{GREEN}{'─' * 72}{RESET}")
    print(f"")


# =============================================================================
# Cache Logging
# =============================================================================

def log_cache(
    layer: int,
    description: str,
    chars: int,
    cached: bool = True
) -> None:
    """Log cache layer information."""
    status = "cached" if cached else "not cached"
    icon = "💾" if cached else "📝"
    print(f"{INFO_COLOR}{icon} Layer {layer}: {description}={chars} chars ({status}){RESET}")


# =============================================================================
# Tool Logging
# =============================================================================

def log_tool(tool_name: str, arguments: dict = None) -> None:
    """Log tool call."""
    args_str = str(arguments)[:100] if arguments else ""
    print(f"{YELLOW}🔧 Tool call: {tool_name}{RESET}")
    if args_str:
        print(f"{MUTED_COLOR}   Args: {args_str}{'...' if len(str(arguments)) > 100 else ''}{RESET}")


def log_tool_res(tool_name: str, result: str, is_error: bool = False) -> None:
    """Log tool result."""
    color = RED if is_error else GREEN
    icon = "❌" if is_error else "✅"
    preview = result[:200] if result else "(empty)"
    print(f"{color}{icon} Tool result ({tool_name}): {preview}{'...' if len(result) > 200 else ''}{RESET}")


# =============================================================================
# Legacy Functions (for backward compatibility)
# =============================================================================

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


def log_prompt(prompt: str) -> None:
    """Log prompt with border."""
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{PROMPT_COLOR}{prompt}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")


def log_response(response: str) -> None:
    """Log response with border."""
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
    print(f"{RESPONSE_COLOR}{response}{RESET}")
    print(f"{MUTED_COLOR}{'*' * 50}{RESET}")
