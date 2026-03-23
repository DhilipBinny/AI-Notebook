"""
Chat service - handles LLM interactions and message persistence.

Uses S3/MinIO JSON storage for chat history with the new folder structure:
    {mm-yyyy}/{project_id}/chats/default.json
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import httpx

from .s3_history import chat_history_client, DEFAULT_CHAT_ID
from .schemas import CellContext, ChatResponse, LLMStep, PendingToolCall
from app.projects.models import Project
from app.playgrounds.models import Playground, PlaygroundStatus

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations and LLM interaction."""

    def __init__(self, storage_month: str):
        """
        Initialize chat service.

        Args:
            storage_month: Project's storage month folder (mm-yyyy)
        """
        self.storage_month = storage_month
        self.history_client = chat_history_client

    def get_history(self, project_id: str, chat_id: str = DEFAULT_CHAT_ID) -> List[Dict[str, Any]]:
        """
        Get chat history for a project.

        Args:
            project_id: Project ID
            chat_id: Chat ID (default: "default")

        Returns:
            List of message dicts with role, content, timestamp, steps
        """
        return self.history_client.load_history(self.storage_month, project_id, chat_id)

    def save_history(self, project_id: str, messages: List[Dict[str, Any]], chat_id: str = DEFAULT_CHAT_ID) -> bool:
        """
        Save chat history for a project.

        Args:
            project_id: Project ID
            messages: List of message dicts
            chat_id: Chat ID (default: "default")

        Returns:
            True if successful
        """
        return self.history_client.save_history(self.storage_month, project_id, messages, chat_id)

    def add_message(
        self,
        project_id: str,
        role: str,
        content: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        chat_id: str = DEFAULT_CHAT_ID,
    ) -> bool:
        """
        Add a message to chat history.

        Args:
            project_id: Project ID
            role: 'user' or 'assistant'
            content: Message content
            steps: Optional LLM steps (tool calls, results)
            chat_id: Chat ID (default: "default")

        Returns:
            True if successful
        """
        return self.history_client.add_message(
            self.storage_month, project_id, role, content, steps, chat_id
        )

    def clear_history(self, project_id: str, chat_id: str = DEFAULT_CHAT_ID) -> bool:
        """Clear chat history for a project/chat."""
        return self.history_client.clear_history(self.storage_month, project_id, chat_id)

    def list_chats(self, project_id: str) -> List[Dict[str, Any]]:
        """List all chats for a project."""
        return self.history_client.list_chats(self.storage_month, project_id)

    def create_chat(self, project_id: str, name: Optional[str] = None) -> Optional[str]:
        """Create a new chat for a project. Returns chat_id or None."""
        return self.history_client.create_chat(self.storage_month, project_id, name)

    def rename_chat(self, project_id: str, chat_id: str, new_name: str) -> bool:
        """Rename a chat."""
        return self.history_client.rename_chat(self.storage_month, project_id, chat_id, new_name)

    def delete_chat(self, project_id: str, chat_id: str) -> bool:
        """Delete a chat (cannot delete default chat)."""
        return self.history_client.delete_chat(self.storage_month, project_id, chat_id)

    async def send_message(
        self,
        project: Project,
        playground: Optional[Playground],
        message: str,
        context: List[CellContext],
        tool_mode: str = "manual",
        llm_provider: str = "gemini",
        context_format: str = "xml",
        chat_id: str = DEFAULT_CHAT_ID,
        images: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResponse:
        """
        Send a message to the LLM via the playground container.

        The playground container handles:
        - LLM provider selection
        - Tool execution (kernel, notebook cells, etc.)
        - Streaming responses

        Args:
            project: Project instance
            playground: Running playground (optional)
            message: User message
            context: Selected cells as context
            tool_mode: "auto", "manual", or "ai_decide"
            llm_provider: LLM provider to use ("gemini", "openai", "anthropic", "openai_compatible")
            context_format: Context format for LLM ("xml" or "plain")
            chat_id: Chat ID (default: "default")

        Returns:
            ChatResponse with LLM response
        """
        # Load existing history
        stored_messages = self.get_history(project.id, chat_id)

        # Add user message to history
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        # Include images in user message if provided
        if images:
            user_message["images"] = images
        stored_messages.append(user_message)

        # Check if playground is running
        if not playground or playground.status != PlaygroundStatus.RUNNING:
            # Save user message even if playground not running
            self.save_history(project.id, stored_messages, chat_id)
            return ChatResponse(
                success=False,
                response="",
                error="Playground is not running. Start the playground to enable AI assistance.",
            )

        try:
            # Convert context to playground format (playground expects 'id' not 'cell_id')
            context_list = [
                {
                    "id": cell.cell_id,
                    "type": cell.type,
                    "content": cell.content,
                    "output": cell.output,
                    "cellNumber": cell.cell_number,
                }
                for cell in context
            ] if context else []

            # Build history for LLM (exclude the message we just added)
            history_list = [
                {"role": m["role"], "content": m["content"]}
                for m in stored_messages[:-1]
            ]

            # Call playground's chat endpoint
            async with httpx.AsyncClient() as client:
                # Send the chat message with all settings in request body (multi-user safe)
                # Use project_id as session_id for tracking pending tools
                # Note: LLM tools fetch notebook data on-demand from playground's notebook state
                request_body = {
                    "message": message,
                    "context": context_list,
                    "history": history_list,
                    "session_id": project.id,
                    "context_format": context_format,
                    "llm_provider": llm_provider,  # Pass provider per-request for multi-user safety
                    "tool_mode": tool_mode,  # Pass tool mode per-request for multi-user safety
                }
                if images:
                    request_body["images"] = images

                response = await client.post(
                    f"{playground.internal_url}/chat",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    json=request_body,
                    timeout=300,  # LLM with auto tool execution can take 5+ minutes
                )

                if response.status_code != 200:
                    # Save user message even on error
                    self.save_history(project.id, stored_messages, chat_id)
                    return ChatResponse(
                        success=False,
                        response="",
                        error=f"Playground returned error: {response.text}",
                    )

                data = response.json()

            # Parse response
            response_text = data.get("response", "")
            pending_tools = [
                PendingToolCall(**t) for t in data.get("pending_tool_calls", [])
            ]
            steps = [LLMStep(**s) for s in data.get("steps", [])]
            updates = data.get("updates", [])

            # Save assistant response if no pending tools
            if not pending_tools and response_text:
                assistant_message = {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now().isoformat(),
                }
                if steps:
                    assistant_message["steps"] = [s.model_dump() for s in steps]
                stored_messages.append(assistant_message)
                self.save_history(project.id, stored_messages, chat_id)
            else:
                # Save just the user message for now
                self.save_history(project.id, stored_messages, chat_id)

            return ChatResponse(
                success=True,
                response=response_text,
                pending_tool_calls=pending_tools,
                steps=steps,
                updates=updates,
            )

        except httpx.TimeoutException:
            self.save_history(project.id, stored_messages, chat_id)
            return ChatResponse(
                success=False,
                response="",
                error="Request timed out. The LLM may be taking too long to respond.",
            )
        except Exception as e:
            logger.error(f"Chat error: {e}")
            self.save_history(project.id, stored_messages, chat_id)
            return ChatResponse(
                success=False,
                response="",
                error=str(e),
            )

    async def execute_tools(
        self,
        project: Project,
        playground: Playground,
        approved_tools: List[PendingToolCall],
        tool_mode: str,
        llm_provider: str,
        context_format: str = "xml",
        chat_id: str = DEFAULT_CHAT_ID,
    ) -> ChatResponse:
        """
        Execute approved tool calls.

        Args:
            project: Project instance
            playground: Running playground
            approved_tools: Tools approved by user
            tool_mode: "auto", "manual", or "ai_decide"
            llm_provider: LLM provider to use ("gemini", "openai", "anthropic", "openai_compatible")
            context_format: Context format for LLM ("xml" or "plain")
            chat_id: Chat ID (default: "default")

        Returns:
            ChatResponse with results
        """
        if playground.status != PlaygroundStatus.RUNNING:
            return ChatResponse(
                success=False,
                response="",
                error="Playground is not running.",
            )

        try:
            async with httpx.AsyncClient() as client:
                # Execute the approved tools
                # Note: provider and tool_mode are already set in the session from the initial chat request
                response = await client.post(
                    f"{playground.internal_url}/chat/execute-tools",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    json={
                        "session_id": project.id,
                        "approved_tools": [t.model_dump() for t in approved_tools],
                    },
                    timeout=300,  # Tool execution with LLM can take time
                )

                if response.status_code != 200:
                    return ChatResponse(
                        success=False,
                        response="",
                        error=f"Tool execution failed: {response.text}",
                    )

                data = response.json()

            response_text = data.get("response", "")
            pending_tools = [
                PendingToolCall(**t) for t in data.get("pending_tool_calls", [])
            ]
            steps = [LLMStep(**s) for s in data.get("steps", [])]
            updates = data.get("updates", [])

            # Save assistant response if complete
            if not pending_tools and response_text:
                stored_messages = self.get_history(project.id, chat_id)
                assistant_message = {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now().isoformat(),
                }
                if steps:
                    assistant_message["steps"] = [s.model_dump() for s in steps]
                stored_messages.append(assistant_message)
                self.save_history(project.id, stored_messages, chat_id)

            return ChatResponse(
                success=True,
                response=response_text,
                pending_tool_calls=pending_tools,
                steps=steps,
                updates=updates,
            )

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return ChatResponse(
                success=False,
                response="",
                error=str(e),
            )


# =============================================================================
# Shared Utilities (used by chat and AI cell routes)
# =============================================================================


def extract_cell_context(
    notebook_data: Dict[str, Any],
    cell_ids: List[str],
    include_outputs: bool = False,
) -> List[Dict[str, Any]]:
    """
    Extract cell context from notebook data for LLM requests.

    Used by both send_message_stream and run_ai_cell endpoints.

    Args:
        notebook_data: Raw notebook JSON from S3
        cell_ids: List of cell IDs to include
        include_outputs: If True, extract cell outputs (for AI cells)

    Returns:
        List of cell context dicts
    """
    context_list = []
    if not notebook_data or "cells" not in notebook_data:
        return context_list

    cell_id_set = set(cell_ids)
    for idx, cell in enumerate(notebook_data["cells"]):
        cell_id = cell.get("metadata", {}).get("cell_id", "")
        if cell_id not in cell_id_set:
            continue

        # Extract output if requested
        output_text = None
        if include_outputs:
            outputs = cell.get("outputs", [])
            for output in outputs:
                if output.get("output_type") == "stream":
                    text = output.get("text", "")
                    if isinstance(text, list):
                        text = "".join(text)
                    output_text = text
                    break
                elif output.get("output_type") in ("execute_result", "display_data"):
                    data = output.get("data", {})
                    if "text/plain" in data:
                        output_text = data["text/plain"]
                        if isinstance(output_text, list):
                            output_text = "".join(output_text)
                        break
                elif output.get("output_type") == "error":
                    output_text = f"Error: {output.get('ename', '')}: {output.get('evalue', '')}"
                    break

        cell_type = cell.get("cell_type", "code")
        ai_data = cell.get("ai_data", {})

        if cell_type == "ai" and ai_data:
            content = ai_data.get("user_prompt", "") or cell.get("source", "")
            ai_prompt = ai_data.get("user_prompt", "")
            ai_response = ai_data.get("llm_response", "")
        else:
            content = cell.get("source", "")
            ai_prompt = None
            ai_response = None

        context_list.append({
            "id": cell_id,
            "type": cell_type,
            "content": content,
            "output": output_text,
            "cellNumber": idx + 1,
            "ai_prompt": ai_prompt,
            "ai_response": ai_response,
        })

    return context_list


def convert_images(images) -> Optional[List[Dict[str, Any]]]:
    """
    Convert image request objects to dict format for forwarding to playground.

    Args:
        images: List of image Pydantic models with data, mime_type, url, filename

    Returns:
        List of image dicts, or None if no valid images
    """
    if not images:
        return None
    images_data = [
        {"data": img.data, "mime_type": img.mime_type, "url": img.url, "filename": img.filename}
        for img in images
        if img.data or img.url
    ]
    return images_data if images_data else None
