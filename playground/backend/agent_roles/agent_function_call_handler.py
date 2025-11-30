"""
Tool Call Validator - Uses AI to decide if a tool call needs user approval

This module provides an AI-based validator that analyzes tool calls and determines
whether they are safe to execute automatically or require user confirmation.

Supports multiple LLM providers: Gemini, OpenAI, and Ollama (uses user-selected provider).
"""

import json
from typing import Dict, Any, List, Optional

import backend.config as cfg
from backend.utils.util_func import log_debug_message


VALIDATOR_PROMPT = """
You are a Tool Call Validator.
Your only job is to decide whether a requested tool call can be executed automatically or requires user confirmation.

Return only a JSON object with:
- "safe": true or false
- "reason": brief explanation (max 20 words)

Return safe=false if the request involves:
- Deleting or modifying system files
- Removing, dropping, or altering databases or tables
- Running shell commands (os.system, subprocess, etc.)
- Installing or uninstalling software
- Changing system or network configuration
- Accessing sensitive files (e.g., /etc, /root)
- Writing outside the working directory
- Any irreversible or destructive action
- Any action where the intent is unclear or uncertain
- Code that could have side effects on external systems

Return safe=true only when:
- The tool call is clearly safe
- The tool action is read-only, computational, or pure Python
- It does not change the environment or external systems
- It is fully reversible
- The user's intention is explicit and harmless
- Simple print statements, calculations, or data analysis

Examples:
- execute_python_code with "print('hello')" -> safe=true
- execute_python_code with "import os; os.remove('file')" -> safe=false
- get_notebook_overview -> safe=true (read-only)
- update_cell_content -> safe=true (reversible, user can undo)
- execute_python_code with "subprocess.run(...)" -> safe=false
"""


class ToolCallValidator:
    """Validates tool calls using AI to determine if they need user approval.

    Supports multiple providers: gemini, openai, ollama (based on cfg.LLM_PROVIDER)
    """

    def __init__(self, provider: Optional[str] = None):
        """
        Initialize the validator with the specified or current LLM provider.

        Args:
            provider: LLM provider to use ('gemini', 'openai', 'ollama').
        """
        self.provider = provider 
        # or cfg.LLM_PROVIDER # If None, uses cfg.LLM_PROVIDER.
        self.model = None
        self._init_provider()

    def _init_provider(self):
        """Initialize the appropriate LLM provider for validation"""
        log_debug_message(f"Initializing ToolCallValidator with provider: {self.provider}")

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "ollama":
            self._init_ollama()
        else:
            log_debug_message(f"Unknown provider: {self.provider}, defaulting to manual approval")
            self.model = None

    def _init_gemini(self):
        """Initialize Gemini provider"""
        if not cfg.GEMINI_API_KEY:
            log_debug_message("Warning: GEMINI_API_KEY not set, validator will default to requiring approval")
            self.model = None
            return

        try:
            import google.generativeai as genai
            genai.configure(api_key=cfg.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=cfg.GEMINI_MODEL,
                system_instruction=VALIDATOR_PROMPT
            )
            log_debug_message("ToolCallValidator initialized with gemini-2.0-flash")
        except Exception as e:
            log_debug_message(f"Failed to initialize Gemini validator: {e}")
            self.model = None

    def _init_openai(self):
        """Initialize OpenAI provider"""
        if not cfg.OPENAI_API_KEY:
            log_debug_message("Warning: OPENAI_API_KEY not set, validator will default to requiring approval")
            self.model = None
            return

        try:
            from openai import OpenAI
            self.model = OpenAI(api_key=cfg.OPENAI_API_KEY)
            log_debug_message("ToolCallValidator initialized with OpenAI gpt-4o-mini")
        except Exception as e:
            log_debug_message(f"Failed to initialize OpenAI validator: {e}")
            self.model = None

    def _init_ollama(self):
        """Initialize Ollama provider"""
        try:
            from openai import OpenAI
            self.model = OpenAI(
                base_url=cfg.OLLAMA_URL,
                api_key="ollama"  # Ollama doesn't need a real key
            )
            log_debug_message(f"ToolCallValidator initialized with Ollama ({cfg.OLLAMA_MODEL})")
        except Exception as e:
            log_debug_message(f"Failed to initialize Ollama validator: {e}")
            self.model = None

    def _call_gemini(self, tool_info: str) -> str:
        """Call Gemini API for validation"""
        response = self.model.generate_content(tool_info)
        return response.text.strip()

    def _call_openai(self, tool_info: str) -> str:
        """Call OpenAI API for validation"""
        response = self.model.chat.completions.create(
            model="gpt-4o-mini",  # Fast, cheap model for validation
            messages=[
                {"role": "system", "content": VALIDATOR_PROMPT},
                {"role": "user", "content": tool_info}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    def _call_ollama(self, tool_info: str) -> str:
        """Call Ollama API for validation"""
        response = self.model.chat.completions.create(
            model=cfg.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": VALIDATOR_PROMPT},
                {"role": "user", "content": tool_info}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()

    def _call_llm(self, tool_info: str) -> str:
        """Call the appropriate LLM based on provider"""
        if self.provider == "gemini":
            return self._call_gemini(tool_info)
        elif self.provider == "openai":
            return self._call_openai(tool_info)
        elif self.provider == "ollama":
            return self._call_ollama(tool_info)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single tool call to determine if it's safe to execute automatically.

        Args:
            tool_name: Name of the tool being called
            arguments: Arguments being passed to the tool

        Returns:
            Dict with:
                - safe: bool - True if safe to auto-execute, False if needs approval
                - reason: str - Explanation for the decision
        """
        if not self.model:
            return {"safe": False, "reason": "Validator not available, defaulting to manual approval"}

        try:
            # Build the prompt for validation
            tool_info = f"Tool: {tool_name}\nArguments: {json.dumps(arguments, indent=2)}"

            log_debug_message(f"Validating tool call: {tool_name} (provider: {self.provider})")

            response_text = self._call_llm(tool_info)

            log_debug_message(f"Validator response: {response_text}")

            # Parse the JSON response
            # Handle markdown code blocks if present
            if response_text.startswith("```"):
                # Extract JSON from code block
                lines = response_text.split("\n")
                json_lines = [l for l in lines if not l.startswith("```")]
                response_text = "\n".join(json_lines)

            result = json.loads(response_text)

            return {
                "safe": result.get("safe", False),
                "reason": result.get("reason", "No reason provided")
            }

        except json.JSONDecodeError as e:
            log_debug_message(f"Failed to parse validator response: {e}")
            return {"safe": False, "reason": "Could not parse validator response, defaulting to manual"}

        except Exception as e:
            log_debug_message(f"Validator error: {e}")
            return {"safe": False, "reason": f"Validation error: {str(e)[:50]}"}

    def validate_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate multiple tool calls and categorize them as safe or needing approval.

        Args:
            tool_calls: List of tool calls with 'name' and 'arguments' keys

        Returns:
            List of tool calls with added 'validation' field containing:
                - safe: bool
                - reason: str
        """
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            arguments = tool_call.get("arguments", {})

            validation = self.validate_tool_call(tool_name, arguments)

            results.append({
                **tool_call,
                "validation": validation
            })

        return results


def get_validator(provider: Optional[str] = None) -> ToolCallValidator:
    """
    Get a validator instance for the specified or current provider.

    Note: Unlike before, this creates a new instance each time to respect
    the current provider setting. For high-frequency validation, consider
    caching the validator if the provider hasn't changed.

    Args:
        provider: Optional provider override. If None, uses cfg.LLM_PROVIDER.
    """
    return ToolCallValidator(provider=provider)


def validate_tool_calls(tool_calls: List[Dict[str, Any]], provider: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Convenience function to validate tool calls and separate them into safe and unsafe.

    Args:
        tool_calls: List of tool calls to validate
        provider: Optional provider override. If None, uses cfg.LLM_PROVIDER.

    Returns:
        Dict with:
            - safe_tools: List of tools safe to auto-execute
            - unsafe_tools: List of tools needing user approval
    """
    validator = get_validator(provider=provider)
    validated = validator.validate_tool_calls(tool_calls)

    safe_tools = [t for t in validated if t.get("validation", {}).get("safe", False)]
    unsafe_tools = [t for t in validated if not t.get("validation", {}).get("safe", True)]

    log_debug_message(f"Validation result: {len(safe_tools)} safe, {len(unsafe_tools)} need approval")

    return {
        "safe_tools": safe_tools,
        "unsafe_tools": unsafe_tools
    }
