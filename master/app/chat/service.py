"""
Chat service - handles LLM interactions and message persistence.

Uses S3/MinIO JSON storage for chat history (like the original backend).
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import httpx

from .s3_history import chat_history_client
from .schemas import CellContext, ChatResponse, LLMStep, PendingToolCall
from app.projects.models import Project
from app.playgrounds.models import Playground, PlaygroundStatus

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations and LLM interaction."""

    def __init__(self, user_id: str):
        """
        Initialize chat service.

        Args:
            user_id: Current user's ID (for S3 path)
        """
        self.user_id = user_id
        self.history_client = chat_history_client

    def get_history(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get chat history for a project.

        Args:
            project_id: Project ID

        Returns:
            List of message dicts with role, content, timestamp, steps
        """
        return self.history_client.load_history(self.user_id, project_id)

    def save_history(self, project_id: str, messages: List[Dict[str, Any]]) -> bool:
        """
        Save chat history for a project.

        Args:
            project_id: Project ID
            messages: List of message dicts

        Returns:
            True if successful
        """
        return self.history_client.save_history(self.user_id, project_id, messages)

    def add_message(
        self,
        project_id: str,
        role: str,
        content: str,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Add a message to chat history.

        Args:
            project_id: Project ID
            role: 'user' or 'assistant'
            content: Message content
            steps: Optional LLM steps (tool calls, results)

        Returns:
            True if successful
        """
        return self.history_client.add_message(
            self.user_id, project_id, role, content, steps
        )

    def clear_history(self, project_id: str) -> bool:
        """Clear chat history for a project."""
        return self.history_client.clear_history(self.user_id, project_id)

    async def send_message(
        self,
        project: Project,
        playground: Optional[Playground],
        message: str,
        context: List[CellContext],
        tool_mode: str = "manual",
    ) -> ChatResponse:
        """
        Send a message to the LLM via the playground container.

        The playground container handles:
        - LLM provider selection based on project settings
        - Tool execution (kernel, notebook cells, etc.)
        - Streaming responses

        Args:
            project: Project instance
            playground: Running playground (optional)
            message: User message
            context: Selected cells as context
            tool_mode: "auto", "manual", or "ai_decide"

        Returns:
            ChatResponse with LLM response
        """
        # Load existing history
        stored_messages = self.get_history(project.id)

        # Add user message to history
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        stored_messages.append(user_message)

        # Check if playground is running
        if not playground or playground.status != PlaygroundStatus.RUNNING:
            # Save user message even if playground not running
            self.save_history(project.id, stored_messages)
            return ChatResponse(
                success=False,
                response="",
                error="Playground is not running. Start the playground to enable AI assistance.",
            )

        try:
            # Convert context to playground format
            context_list = [
                {
                    "id": cell.id,
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
                # First, set the LLM provider based on project settings
                await client.post(
                    f"{playground.internal_url}/llm/provider",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    json={"provider": project.llm_provider.value},
                    timeout=10,
                )

                # Set tool execution mode
                await client.post(
                    f"{playground.internal_url}/llm/tool-mode",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    json={"mode": tool_mode},
                    timeout=10,
                )

                # Now send the chat message with history
                # Use project_id as session_id for tracking pending tools
                # Note: LLM tools fetch notebook data on-demand from playground's notebook state
                response = await client.post(
                    f"{playground.internal_url}/chat",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    json={
                        "message": message,
                        "context": context_list,
                        "history": history_list,
                        "session_id": project.id,
                    },
                    timeout=120,  # LLM can take a while
                )

                if response.status_code != 200:
                    # Save user message even on error
                    self.save_history(project.id, stored_messages)
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
                self.save_history(project.id, stored_messages)
            else:
                # Save just the user message for now
                self.save_history(project.id, stored_messages)

            return ChatResponse(
                success=True,
                response=response_text,
                pending_tool_calls=pending_tools,
                steps=steps,
                updates=updates,
            )

        except httpx.TimeoutException:
            self.save_history(project.id, stored_messages)
            return ChatResponse(
                success=False,
                response="",
                error="Request timed out. The LLM may be taking too long to respond.",
            )
        except Exception as e:
            logger.error(f"Chat error: {e}")
            self.save_history(project.id, stored_messages)
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
    ) -> ChatResponse:
        """
        Execute approved tool calls.

        Args:
            project: Project instance
            playground: Running playground
            approved_tools: Tools approved by user

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
                response = await client.post(
                    f"{playground.internal_url}/chat/execute-tools",
                    headers={"X-Internal-Secret": playground.internal_secret},
                    json={
                        "session_id": project.id,
                        "approved_tools": [t.model_dump() for t in approved_tools],
                    },
                    timeout=120,
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
                stored_messages = self.get_history(project.id)
                assistant_message = {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now().isoformat(),
                }
                if steps:
                    assistant_message["steps"] = [s.model_dump() for s in steps]
                stored_messages.append(assistant_message)
                self.save_history(project.id, stored_messages)

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
