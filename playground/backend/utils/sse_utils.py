"""
SSE Utilities - Helper functions for Server-Sent Events formatting

Event Types:
- thinking: Status message (e.g., "Analyzing...")
- llm_thinking: LLM's internal reasoning (extended thinking)
- tool_call: Tool is being called with arguments
- tool_result: Tool execution result
- pending_tools: Tools awaiting user approval (chat only)
- done: Final response with all data
- error: Error occurred
"""

import json
from typing import Any, Dict, Optional


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """
    Format a Server-Sent Event.

    Args:
        event_type: The event type (e.g., "thinking", "tool_call", "done", "error")
        data: The event data dictionary

    Returns:
        Formatted SSE string ready to yield
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def format_progress_event(event_type: str, event_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Format a progress event from the LLM progress callback into an SSE event.

    Args:
        event_type: The progress event type from LLM client
        event_data: The event data dictionary (may be None)

    Returns:
        Formatted SSE string, or None if event should be skipped
    """
    event_data = event_data or {}

    if event_type == "thinking":
        thinking_content = event_data.get("content", "")
        thinking_iteration = event_data.get("iteration", 1)
        if thinking_content:
            return format_sse_event("llm_thinking", {
                "content": thinking_content,
                "iteration": thinking_iteration
            })
        return None

    elif event_type == "tool_call":
        return format_sse_event("tool_call", event_data)

    elif event_type == "tool_result":
        return format_sse_event("tool_result", event_data)

    elif event_type == "iteration_start":
        iteration_num = event_data.get("iteration", 1)
        return format_sse_event("thinking", {
            "message": f"Iteration {iteration_num}..."
        })

    elif event_type == "iteration_end":
        if event_data.get("final"):
            return format_sse_event("thinking", {
                "message": "Finalizing response..."
            })
        return None

    elif event_type == "pending_tools":
        # Chat-specific: tools awaiting user approval
        return format_sse_event("pending_tools", event_data)

    return None
