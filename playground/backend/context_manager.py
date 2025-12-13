"""
Context Manager - Smart context preparation for LLM

Supports multiple context formats:
- PLAIN: Simple text format (legacy)
- XML: Structured XML tags (recommended for Claude, works well for all LLMs)

Research shows XML format can improve LLM accuracy by up to 40% for complex tasks.
Claude is specifically trained on XML tags.

Tiered Context Approach:
- TIER 1 (Always included): Imports, variables, errors, cell overview (minimal tokens)
- TIER 2 (On-demand): Full cell content fetched via LLM tools

This allows sending ALL cells as context while keeping token usage minimal.
LLM uses get_cell_content(cell_id) to dig deeper when needed.

Public Methods:
- build_ai_cell_context(): Complete AI Cell message with position info and context
- build_chat_context(): Complete Chat Panel message with tiered overview
- process_context(): Raw tiered context formatting (used by build_chat_context)
- process_positional_context(): Raw positional formatting (used by build_ai_cell_context)
"""

import re
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from backend.utils.util_func import log


class ContextFormat(str, Enum):
    """
    Supported context formats for LLM.

    Each format is optimized for different LLM providers:
    - XML: Best for Claude (specifically trained on XML tags)
    - JSON: Best for OpenAI, Gemini (structured data parsing)
    - PLAIN: Best for Ollama/local models (simple text)
    """
    PLAIN = "plain"  # Simple text with separators (legacy, Ollama)
    XML = "xml"      # XML tags (recommended for Claude)
    JSON = "json"    # JSON format (recommended for OpenAI, Gemini)


@dataclass
class FormattedContext:
    """
    Structured representation of formatted context for LLM.

    Keeps notebook_context and user_prompt separate to allow:
    - LLM clients to apply caching appropriately (e.g., Anthropic's cache_control)
    - Clean separation of cacheable vs dynamic content
    """
    notebook_context: str      # Formatted notebook context (cacheable - Layer 2)
    user_prompt: str           # User's question/prompt (never cached - Layer 3)
    format: ContextFormat      # Format used for notebook_context


@dataclass
class StructuredContext:
    """Structured representation of notebook context"""
    imports: List[str] = field(default_factory=list)
    variables: Dict[str, str] = field(default_factory=dict)  # name -> type/shape
    recent_errors: List[Dict[str, str]] = field(default_factory=list)  # cell_id, error
    cells: List[Dict[str, Any]] = field(default_factory=list)
    total_cells: int = 0


class ContextManager:
    """
    Manages context preparation for LLM requests.

    Creates a compressed overview of the entire notebook that fits in minimal tokens.
    LLM can use tools to fetch full content of specific cells when needed.
    """

    # Thresholds
    MAX_PREVIEW_CHARS = 60  # First line preview length
    MAX_TOTAL_CONTEXT_CHARS = 4000  # Keep context compact

    def __init__(self):
        """Initialize context manager."""
        pass

    # =========================================================================
    # PUBLIC HIGH-LEVEL METHODS
    # =========================================================================

    def build_ai_cell_context(
        self,
        cells: List[Any],  # List of CellContext Pydantic models or dicts
        ai_cell_index: int,
        user_prompt: str,
        format: ContextFormat = ContextFormat.XML
    ) -> FormattedContext:
        """
        Build AI Cell context with separate notebook_context and user_prompt.

        This is the main entry point for AI Cell context building.
        Handles conversion from Pydantic models, position calculation,
        and final message formatting.

        Returns FormattedContext with separate parts to allow:
        - LLM clients to apply caching appropriately (e.g., Anthropic's cache_control)
        - Clean separation of cacheable (notebook_context) vs dynamic (user_prompt) content

        Args:
            cells: List of CellContext objects (Pydantic) or dicts
            ai_cell_index: 0-based index of the AI cell in the notebook
            user_prompt: User's question/prompt
            format: Output format - XML (recommended) or PLAIN

        Returns:
            FormattedContext with notebook_context and user_prompt separated
        """
        # Convert cells to dicts if they are Pydantic models
        cells_data = self._convert_cells_to_dicts(cells)

        # Calculate total cells (+1 for AI cell itself which is not in the list)
        total_cells = len(cells_data) + 1

        # Build position info
        position_info = self._build_position_info(ai_cell_index, total_cells)

        # Build notebook context using positional formatting
        positional_context = self.process_positional_context(
            cells_data,
            ai_cell_index,
            format=format
        )

        # Build notebook_context with position info (this is the cacheable part)
        notebook_context = f"""POSITION: {position_info}

NOTEBOOK CONTEXT:
{positional_context}"""

        log(f"📋 AI Cell context built: context={len(notebook_context)} chars, user_prompt={len(user_prompt)} chars, position {ai_cell_index + 1}/{total_cells}")

        return FormattedContext(
            notebook_context=notebook_context,
            user_prompt=user_prompt,
            format=format
        )

    def build_chat_context(
        self,
        cells: List[Any],  # List of CellContext Pydantic models or dicts
        user_prompt: str,
        format: ContextFormat = ContextFormat.XML,
        kernel_variables: Optional[Dict[str, str]] = None
    ) -> FormattedContext:
        """
        Build Chat Panel context with separate notebook_context and user_prompt.

        This is the main entry point for Chat Panel context building.
        Uses tiered approach: compact overview + get_cell_content() tool for details.

        Returns FormattedContext with separate parts to allow:
        - LLM clients to apply caching appropriately (e.g., Anthropic's cache_control)
        - Clean separation of cacheable (notebook_context) vs dynamic (user_prompt) content

        Args:
            cells: List of CellContext objects (Pydantic) or dicts
            user_prompt: User's question/prompt
            format: Output format - XML (recommended) or PLAIN
            kernel_variables: Optional dict of variable names to types

        Returns:
            FormattedContext with notebook_context and user_prompt separated
        """
        # Convert cells to dicts if they are Pydantic models
        cells_data = self._convert_cells_to_dicts(cells)

        # Build compact context using tiered approach
        notebook_context = self.process_context(cells_data, kernel_variables, format)

        log(f"📋 Chat context built: context={len(notebook_context)} chars, user_prompt={len(user_prompt)} chars, {len(cells_data)} cells")

        return FormattedContext(
            notebook_context=notebook_context,
            user_prompt=user_prompt,
            format=format
        )

    def _convert_cells_to_dicts(self, cells: List[Any]) -> List[Dict[str, Any]]:
        """
        Convert cells to list of dicts.

        Handles both Pydantic BaseModel objects and plain dicts.
        """
        if not cells:
            return []

        cells_data = []
        for cell in cells:
            # Check if it's a Pydantic model (has model_dump or dict method)
            if hasattr(cell, 'model_dump'):
                # Pydantic v2
                cell_dict = cell.model_dump()
            elif hasattr(cell, 'dict'):
                # Pydantic v1
                cell_dict = cell.dict()
            elif isinstance(cell, dict):
                cell_dict = cell
            else:
                # Try to convert attributes manually
                cell_dict = {
                    "id": getattr(cell, 'id', ''),
                    "type": getattr(cell, 'type', 'code'),
                    "content": getattr(cell, 'content', ''),
                    "output": getattr(cell, 'output', None),
                    "cellNumber": getattr(cell, 'cellNumber', None),
                    "ai_prompt": getattr(cell, 'ai_prompt', None),
                    "ai_response": getattr(cell, 'ai_response', None),
                }
            cells_data.append(cell_dict)

        return cells_data

    def _build_position_info(self, ai_cell_index: int, total_cells: int) -> str:
        """
        Build position description string for AI Cell.

        Args:
            ai_cell_index: 0-based index of AI cell
            total_cells: Total number of cells in notebook

        Returns:
            Human-readable position description
        """
        if ai_cell_index < 0:
            return "Position unknown."

        position_info = f"You are in Cell #{ai_cell_index + 1} of {total_cells} total cells."
        if ai_cell_index > 0:
            position_info += f" There are {ai_cell_index} cell(s) ABOVE you."
        if ai_cell_index < total_cells - 1:
            position_info += f" There are {total_cells - ai_cell_index - 1} cell(s) BELOW you."

        return position_info

    # =========================================================================
    # CONTEXT FORMATTING METHODS
    # =========================================================================

    def process_context(
        self,
        cells: List[Dict[str, Any]],
        kernel_variables: Optional[Dict[str, str]] = None,
        format: ContextFormat = ContextFormat.PLAIN
    ) -> str:
        """
        Process ALL notebook cells into a compact overview.

        Args:
            cells: List of cell dicts with id, type, content, output, cellNumber
            kernel_variables: Optional dict of variable names to types from kernel
            format: Output format - PLAIN, XML, or JSON

        Returns:
            Compact context string for LLM
        """
        if not cells:
            return ""

        # Build structured context
        structured = self._extract_structured_context(cells, kernel_variables)

        # Format for LLM based on selected format
        if format == ContextFormat.XML:
            context_str = self._format_xml_context(structured)
        elif format == ContextFormat.JSON:
            context_str = self._format_json_context(structured)
        elif format == ContextFormat.PLAIN:
            context_str = self._format_plain_context(structured)
        else:
            log(f"Invalid context format: {format}")
            return ""

        log(f"📋 Context [{format.value}]: {len(context_str)} chars, {structured.total_cells} cells, {len(structured.imports)} imports, {len(structured.recent_errors)} errors")

        return context_str

    def _extract_structured_context(self, cells: List[Dict[str, Any]], kernel_variables: Optional[Dict[str, str]] = None) -> StructuredContext:
        """Extract structured information from all cells"""
        structured = StructuredContext()
        structured.total_cells = len(cells)

        for cell in cells:
            cell_type = cell.get("type", "code")
            content = cell.get("content", "") or ""
            output = cell.get("output", "") or ""
            cell_id = cell.get("id", "")

            # For AI cells, use ai_prompt as content if available
            ai_prompt = cell.get("ai_prompt", "")
            ai_response = cell.get("ai_response", "")
            if cell_type == "ai" and ai_prompt:
                content = ai_prompt

            # Extract imports from code cells
            if cell_type == "code":
                imports = self._extract_imports(content)
                structured.imports.extend(imports)

                # Extract variable assignments
                variables = self._extract_variables(content)
                structured.variables.update(variables)

            # Check for errors in output
            if output and self._is_error_output(output):
                error_summary = self._summarize_error(output)
                structured.recent_errors.append({
                    "cell_id": cell_id,
                    "error": error_summary
                })

            # Create cell overview (compact)
            # For AI cells, show the prompt as preview
            first_line = self._get_first_line(content)
            has_output = bool(output and output.strip())
            has_error = self._is_error_output(output) if output else False
            output_type = self._detect_output_type(output) if has_output else None

            cell_data = {
                "cell_id": cell_id,
                "type": cell_type,
                "preview": first_line,
                "has_output": has_output,
                "has_error": has_error,
                "output_type": output_type
            }
            # Include AI cell data if present
            if cell_type == "ai":
                cell_data["ai_prompt"] = ai_prompt
                cell_data["ai_response"] = ai_response[:100] + "..." if ai_response and len(ai_response) > 100 else ai_response
            structured.cells.append(cell_data)

        # Add kernel variables if provided
        if kernel_variables:
            structured.variables.update(kernel_variables)

        # Deduplicate imports
        structured.imports = list(set(structured.imports))

        return structured

    def _format_plain_context(self, structured: StructuredContext) -> str:
        """
        Format structured context into compact plain text.

        Uses bracketed format instead of tables to avoid issues with
        pipe characters in code. More robust and token-efficient.
        """
        parts = []

        parts.append("=== NOTEBOOK OVERVIEW ===")

        # Variables section - compact inline
        if structured.variables:
            vars_list = [f"{k}={v}" for k, v in list(structured.variables.items())[:8]]
            vars_str = ', '.join(vars_list)
            if len(structured.variables) > 8:
                vars_str += f" (+{len(structured.variables) - 8} more)"
            parts.append(f"Variables: {vars_str}")

        # Imports section - compact inline
        if structured.imports:
            imports_str = ', '.join(sorted(structured.imports)[:12])
            if len(structured.imports) > 12:
                imports_str += f" (+{len(structured.imports) - 12} more)"
            parts.append(f"Imports: {imports_str}")

        # Errors section (critical!)
        if structured.recent_errors:
            parts.append("")
            for err in structured.recent_errors[-3:]:
                parts.append(f"[ERROR {err['cell_id']}]: {err['error']}")

        # Cells - bracketed format with line numbers for position anchoring
        # Line numbers help LLMs understand cell positions without counting
        parts.append("")
        num_width = len(str(len(structured.cells)))  # Dynamic padding width
        for idx, cell in enumerate(structured.cells, 1):
            cell_id = cell["cell_id"]
            # Short type names
            cell_type = "md" if cell["type"] == "markdown" else cell["type"]
            preview = cell["preview"][:50]

            # Output indicator suffix
            if cell["has_error"]:
                suffix = " [ERR]"
            elif cell["has_output"] and cell["output_type"]:
                suffix = f" [{cell['output_type'][:4]}]"
            else:
                suffix = ""

            # Line number prefix (zero-padded)
            line_num = str(idx).zfill(num_width)

            # For AI cells, show the prompt
            if cell["type"] == "ai":
                ai_prompt = cell.get("ai_prompt", "")
                content = ai_prompt[:50] if ai_prompt else preview
                parts.append(f"{line_num}. [{cell_id}] ({cell_type}): {content}{suffix}")
            else:
                parts.append(f"{line_num}. [{cell_id}] ({cell_type}): {preview}{suffix}")

        parts.append("")
        parts.append("Tools: get_cell_content(id), get_notebook_overview()")

        return '\n'.join(parts)

    def _format_xml_context(self, structured: StructuredContext) -> str:
        """
        Format structured context into optimized XML for LLM.

        Uses short tag names and attributes for token efficiency:
        - <c> instead of <cell> (saves ~2 chars × N cells)
        - type="md" instead of type="markdown" (saves 6 chars)
        - Content directly inside tags (no nested <preview>)
        - Attributes for metadata instead of nested tags

        XML format is recommended for Claude (specifically trained on XML tags).
        """
        parts = []

        parts.append(f'<notebook cells="{structured.total_cells}">')

        # Variables section - compact format
        if structured.variables:
            vars_list = [f"{k}={v}" for k, v in list(structured.variables.items())[:10]]
            vars_str = ", ".join(vars_list)
            if len(structured.variables) > 10:
                vars_str += f" (+{len(structured.variables) - 10} more)"
            parts.append(f'<vars>{self._escape_xml(vars_str)}</vars>')

        # Imports section - compact inline
        if structured.imports:
            imports_str = ", ".join(sorted(structured.imports)[:12])
            if len(structured.imports) > 12:
                imports_str += f" (+{len(structured.imports) - 12} more)"
            parts.append(f'<imports>{self._escape_xml(imports_str)}</imports>')

        # Errors section (critical - always show)
        if structured.recent_errors:
            for err in structured.recent_errors[-3:]:
                parts.append(f'<err cell="{self._escape_xml(err["cell_id"])}">{self._escape_xml(err["error"])}</err>')

        # Cells section - optimized format
        for cell in structured.cells:
            # Short type names: code->code, markdown->md, ai->ai
            cell_type = "md" if cell["type"] == "markdown" else cell["type"]
            cell_id = cell["cell_id"]
            preview = self._escape_xml(cell["preview"][:50])

            # Build attributes string
            attrs = f'id="{self._escape_xml(cell_id)}" type="{cell_type}"'

            # Add output indicator as attribute if present
            if cell["has_error"]:
                attrs += ' err="1"'
            elif cell["has_output"] and cell["output_type"]:
                # Short output type
                out_type = cell["output_type"][:4]  # text->text, DataFrame->Data, etc.
                attrs += f' out="{out_type}"'

            # For AI cells, include prompt preview in content
            if cell["type"] == "ai":
                ai_prompt = cell.get("ai_prompt", "")
                content = self._escape_xml(ai_prompt[:60]) if ai_prompt else preview
                parts.append(f'<c {attrs}>{content}</c>')
            else:
                parts.append(f'<c {attrs}>{preview}</c>')

        parts.append('</notebook>')
        parts.append('<hint>Tools: get_cell_content(id), get_notebook_overview()</hint>')

        return '\n'.join(parts)

    def _escape_xml(self, text: str) -> str:
        """Escape special XML characters"""
        if not text:
            return ""
        text = str(text)
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&apos;')
        return text

    def _format_json_context(self, structured: StructuredContext) -> str:
        """
        Format structured context into ultra-compact JSON for LLM.

        Uses List of Lists instead of List of Objects to eliminate key repetition.
        Schema: [id, type, preview, output_indicator]
        - Saves ~50% on cell data compared to objects with keys

        Example: ["cell-1","code","import pandas",null] instead of {"id":"cell-1","t":"code","p":"import pandas"}
        """
        # Build cells as arrays: [id, type, preview, out/err]
        cells = []
        for cell in structured.cells:
            cell_type = "md" if cell["type"] == "markdown" else cell["type"]
            preview = cell["preview"][:50] if cell["preview"] else ""

            # Output indicator: "E" for error, short type, or null
            if cell["has_error"]:
                out_ind = "E"
            elif cell["has_output"] and cell["output_type"]:
                out_ind = cell["output_type"][:4]
            else:
                out_ind = None

            # For AI cells, use prompt as preview
            if cell["type"] == "ai":
                ai_prompt = cell.get("ai_prompt", "")
                preview = ai_prompt[:50] if ai_prompt else preview

            # Array format: [id, type, preview, out]
            cells.append([cell["cell_id"], cell_type, preview, out_ind])

        # Build compact context object
        context_obj = {
            "n": structured.total_cells,  # total cells count
        }

        # Add variables if present (compact format)
        if structured.variables:
            context_obj["vars"] = {k: v for k, v in list(structured.variables.items())[:10]}

        # Add imports if present
        if structured.imports:
            context_obj["imports"] = sorted(structured.imports)[:12]

        # Add errors if present (critical) - keep as objects for clarity
        if structured.recent_errors:
            context_obj["errs"] = [
                [err["cell_id"], err["error"]]
                for err in structured.recent_errors[-3:]
            ]

        # Cells object containing schema and list
        context_obj["cells"] = {
            "schema": ["id", "type", "preview", "out"],
            "list": cells
        }
        context_obj["hint"] = "tools: get_cell_content(id), get_notebook_overview()"

        # Minified JSON output
        return json.dumps(context_obj, separators=(',', ':'))

    # =========================================================================
    # POSITIONAL CONTEXT (for AI Cell)
    # =========================================================================

    def process_positional_context(
        self,
        cells: List[Dict[str, Any]],
        ai_cell_index: int,
        format: ContextFormat = ContextFormat.PLAIN
    ) -> str:
        """
        Process notebook cells into positional context for AI Cell.

        This creates a context with cells organized as "above" and "below"
        the AI cell's position, with immediate neighbors marked.

        Full Mode: No truncation on content, output, ai_prompt, or ai_response.
        LLM gets complete context to understand the notebook state.

        Args:
            cells: List of cell dicts with id, type, content, output, cellNumber
            ai_cell_index: The 0-based index of the AI cell in the notebook
            format: Output format - PLAIN, XML, or JSON

        Returns:
            Positional context string for AI Cell
        """
        if not cells:
            if format == ContextFormat.XML:
                return "<notebook><empty>No other cells in notebook</empty></notebook>"
            elif format == ContextFormat.JSON:
                return json.dumps({"empty": True, "msg": "No other cells"}, separators=(',', ':'))
            return "(No other cells in notebook)"

        cells_above = []
        cells_below = []

        for i, cell in enumerate(cells):
            cell_position = cell.get("cellNumber", i + 1) - 1 if cell.get("cellNumber") else i

            # Full Mode: Source code only, no outputs
            # LLM can use get_cell_content() tool if it needs output
            output = cell.get("output", "") or ""
            ai_response = cell.get("ai_response", "") or ""

            cell_data = {
                "id": cell.get("id", f"cell-{i}"),
                "type": cell.get("type", "code"),
                "content": cell.get("content", "") or "",  # Full source code
                "has_output": bool(output.strip()),  # Indicator only
                "position": cell_position,
                "is_immediate": False,
                # AI cell specific fields
                "ai_prompt": cell.get("ai_prompt", "") or "",  # Full prompt
                "has_response": bool(ai_response.strip()),  # Indicator only
            }

            if ai_cell_index >= 0 and cell_position < ai_cell_index:
                cell_data["is_immediate"] = (cell_position == ai_cell_index - 1)
                cells_above.append(cell_data)
            else:
                cell_data["is_immediate"] = (cell_position == ai_cell_index + 1)
                cells_below.append(cell_data)

        # Sort by position
        cells_above.sort(key=lambda x: x["position"])
        cells_below.sort(key=lambda x: x["position"])

        # Build context based on format
        if format == ContextFormat.XML:
            context_str = self._format_positional_xml(cells_above, cells_below, ai_cell_index)
        elif format == ContextFormat.JSON:
            context_str = self._format_positional_json(cells_above, cells_below, ai_cell_index)
        else:
            context_str = self._format_positional_plain(cells_above, cells_below, ai_cell_index)

        log(f"📋 Positional Context [{format.value}]: {len(context_str)} chars, {len(cells_above)} above, {len(cells_below)} below")

        return context_str

    def _format_positional_plain(self, cells_above: List[Dict], cells_below: List[Dict], ai_cell_index: int) -> str:
        """
        Format positional context in plain text with delimiter style.

        Uses clear separators between cells and their outputs.
        Includes line numbers for position anchoring.
        """
        total = len(cells_above) + len(cells_below) + 1
        num_width = len(str(total))  # Dynamic padding width
        parts = []

        def format_cell(cell: Dict, is_near: bool = False) -> str:
            """Format a single cell with delimiter style and line number"""
            cell_type = "md" if cell["type"] == "markdown" else cell["type"]
            near_marker = " [NEAR]" if is_near else ""
            # Line number from cell position (1-based)
            line_num = str(cell["position"] + 1).zfill(num_width)

            # Output indicator (no actual output - use get_cell_content for that)
            out_marker = " [OUT]" if cell.get("has_output") else ""

            # For AI cells, show question only (no response content)
            if cell["type"] == "ai":
                ai_prompt = cell.get("ai_prompt", "")
                resp_marker = " [RESP]" if cell.get("has_response") else ""
                cell_lines = [f"=== {line_num}. {cell['id']} ({cell_type}){near_marker}{resp_marker} ==="]
                if ai_prompt:
                    cell_lines.append(f"[Q]: {ai_prompt}")
                return "\n".join(cell_lines)
            else:
                cell_lines = [f"=== {line_num}. {cell['id']} ({cell_type}){near_marker}{out_marker} ==="]
                cell_lines.append(cell["content"])
                return "\n".join(cell_lines)

        parts.append(f"POSITION: {ai_cell_index + 1}/{total}")

        if cells_above:
            parts.append("\n[ABOVE]")
            for cell in cells_above:
                parts.append(format_cell(cell, cell["is_immediate"]))

        if cells_below:
            parts.append("\n[BELOW]")
            for cell in cells_below:
                parts.append(format_cell(cell, cell["is_immediate"]))

        return "\n".join(parts)

    def _format_positional_xml(self, cells_above: List[Dict], cells_below: List[Dict], ai_cell_index: int) -> str:
        """
        Format positional context in optimized XML.

        Uses short tag names for token efficiency:
        - <src> instead of <content>
        - out="1" attribute instead of <out> content
        - near="1" for immediate neighbors
        - type="md" for markdown
        """
        total = len(cells_above) + len(cells_below) + 1
        parts = []
        parts.append(f'<notebook pos="{ai_cell_index + 1}/{total}">')

        def format_cell_xml(cell: Dict) -> List[str]:
            """Format a single cell for XML output"""
            cell_parts = []
            cell_type = "md" if cell["type"] == "markdown" else cell["type"]
            near_attr = ' near="1"' if cell["is_immediate"] else ''
            out_attr = ' out="1"' if cell.get("has_output") else ''

            # For AI cells, show question only (no response content)
            if cell["type"] == "ai":
                ai_prompt = cell.get("ai_prompt", "")
                resp_attr = ' resp="1"' if cell.get("has_response") else ''
                cell_parts.append(f'<cell id="{self._escape_xml(cell["id"])}" type="{cell_type}"{near_attr}{resp_attr}>')
                if ai_prompt:
                    cell_parts.append(f'<q>{self._escape_xml(ai_prompt)}</q>')
            else:
                cell_parts.append(f'<cell id="{self._escape_xml(cell["id"])}" type="{cell_type}"{near_attr}{out_attr}>')
                cell_parts.append(f'<src>{self._escape_xml(cell["content"])}</src>')

            cell_parts.append('</cell>')
            return cell_parts

        if cells_above:
            parts.append('<above>')
            for cell in cells_above:
                parts.extend(format_cell_xml(cell))
            parts.append('</above>')

        if cells_below:
            parts.append('<below>')
            for cell in cells_below:
                parts.extend(format_cell_xml(cell))
            parts.append('</below>')

        parts.append('</notebook>')
        return '\n'.join(parts)

    def _format_positional_json(self, cells_above: List[Dict], cells_below: List[Dict], ai_cell_index: int) -> str:
        """
        Format positional context in ultra-compact JSON.

        Uses List of Lists to eliminate key repetition.
        Schema: [id, type, near, src, has_out]
        - near: 1 if immediate neighbor, 0 otherwise
        - src: content for code/md, prompt for ai
        - has_out: 1 if has output/response, 0 otherwise
        """
        total = len(cells_above) + len(cells_below) + 1

        def format_cell_array(cell: Dict) -> list:
            """Format a single cell as array: [id, type, near, src, has_out]"""
            cell_type = "md" if cell["type"] == "markdown" else cell["type"]
            near = 1 if cell["is_immediate"] else 0

            if cell["type"] == "ai":
                src = cell.get("ai_prompt", "") or None
                has_out = 1 if cell.get("has_response") else 0
            else:
                src = cell["content"] or None
                has_out = 1 if cell.get("has_output") else 0

            return [cell["id"], cell_type, near, src, has_out]

        context_obj = {
            "pos": f"{ai_cell_index + 1}/{total}",
            "cells": {
                "schema": ["id", "type", "near", "src", "has_out"],
            }
        }

        if cells_above:
            context_obj["cells"]["above"] = [format_cell_array(cell) for cell in cells_above]

        if cells_below:
            context_obj["cells"]["below"] = [format_cell_array(cell) for cell in cells_below]

        # Minified JSON output
        return json.dumps(context_obj, separators=(',', ':'))

    def _get_first_line(self, content: str) -> str:
        """Get first meaningful line of content as preview"""
        if not content:
            return "(empty)"

        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            # Skip empty lines and comments-only lines
            if line and not line.startswith('#'):
                # Truncate if too long
                if len(line) > self.MAX_PREVIEW_CHARS:
                    return line[:self.MAX_PREVIEW_CHARS] + "..."
                return line

        # If only comments, return first comment
        if lines:
            first = lines[0].strip()
            if len(first) > self.MAX_PREVIEW_CHARS:
                return first[:self.MAX_PREVIEW_CHARS] + "..."
            return first

        return "(empty)"

    def _detect_output_type(self, output: str) -> Optional[str]:
        """Detect the type of output for compact display"""
        if not output:
            return None

        output = output.strip()

        # Check for common output types
        if self._is_error_output(output):
            return "error"
        elif "image/png" in output or "[Image" in output:
            return "image"
        elif self._looks_like_dataframe(output):
            return "DataFrame"
        elif output.startswith('[') and output.endswith(']'):
            return "list"
        elif output.startswith('{') and output.endswith('}'):
            return "dict"
        elif '\n' in output and len(output) > 200:
            return "multiline"
        else:
            return "text"

    def _extract_imports(self, code: str) -> List[str]:
        """Extract import statements from code"""
        imports = []
        import_pattern = r'^(?:from\s+(\w+)|import\s+(\w+))'

        for line in code.split('\n'):
            line = line.strip()
            match = re.match(import_pattern, line)
            if match:
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module)

        return imports

    def _extract_variables(self, code: str) -> Dict[str, str]:
        """Extract variable assignments from code"""
        variables = {}
        assignment_pattern = r'^(\w+)\s*(?::\s*\w+)?\s*=\s*(.+)$'

        for line in code.split('\n'):
            line = line.strip()
            # Skip lines inside functions/classes
            if line.startswith(('def ', 'class ', 'if ', 'for ', 'while ', 'return ', '    ')):
                continue

            match = re.match(assignment_pattern, line)
            if match:
                var_name = match.group(1)
                value = match.group(2).strip()
                var_info = self._get_var_info(value)
                if var_info:
                    variables[var_name] = var_info

        return variables

    def _get_var_info(self, value: str) -> Optional[str]:
        """
        Get type AND value for primitives, just type for complex objects.

        For small primitives (int, float, bool, short strings), captures the actual
        value so LLM can answer "What is the value of X?" without calling tools.
        """
        value = value.strip()

        # Capture primitive literals with their values (max 30 chars for strings)
        # Numbers
        if value.replace('.', '', 1).replace('-', '', 1).isdigit():
            if '.' in value:
                return f"float={value}"
            else:
                return f"int={value}"

        # Booleans
        if value in ('True', 'False'):
            return f"bool={value}"

        # None
        if value == 'None':
            return 'None'

        # Strings - show value with truncation indicator if too long
        if value.startswith(('"', "'")):
            # Extract string content
            quote_char = value[0]
            if value.endswith(quote_char) and len(value) > 1:
                clean_val = value[1:-1]
                if len(clean_val) <= 30:
                    return f'str="{clean_val}"'
                else:
                    # Truncate with ... so LLM knows to fetch full value
                    return f'str="{clean_val[:30]}..."'
            return 'str'

        # Complex types - just return type name
        if value.startswith(('pd.read_', 'pd.DataFrame')):
            return 'DataFrame'
        elif value.startswith(('np.array', 'np.zeros', 'np.ones', 'np.arange')):
            return 'ndarray'
        elif value.startswith('['):
            return 'list'
        elif value.startswith('{'):
            return 'dict'
        elif '(' in value:
            func_match = re.match(r'(\w+(?:\.\w+)*)\s*\(', value)
            if func_match:
                func_name = func_match.group(1)
                # Common type constructors
                if func_name in ('list', 'dict', 'set', 'tuple', 'str', 'int', 'float'):
                    return func_name
                return f"{func_name}()"

        return None

    def _is_error_output(self, output: str) -> bool:
        """Check if output contains an error"""
        error_indicators = [
            'Traceback (most recent call last)',
            'Error:', 'Exception:', 'error:',
            'SyntaxError', 'NameError', 'TypeError', 'ValueError',
            'KeyError', 'IndexError', 'AttributeError',
            'ImportError', 'ModuleNotFoundError', 'FileNotFoundError'
        ]
        return any(indicator in output for indicator in error_indicators)

    def _summarize_error(self, output: str) -> str:
        """Extract key error information"""
        lines = output.strip().split('\n')

        # Get last line (usually the error message)
        error_line = lines[-1] if lines else output[:100]

        # Try to get error type
        for line in reversed(lines):
            if 'Error:' in line or 'Exception:' in line:
                error_line = line
                break

        return error_line[:80]

    def _looks_like_dataframe(self, output: str) -> bool:
        """Check if output looks like a DataFrame"""
        indicators = [
            'dtype:' in output,
            'Index:' in output,
            ('[' in output and 'rows' in output and 'columns' in output),
            (output.count('  ') > 3 and '\n' in output),  # Column alignment
        ]
        return any(indicators)


# Convenience functions
def prepare_context(
    cells: List[Dict[str, Any]],
    kernel_variables: Optional[Dict[str, str]] = None,
    format: ContextFormat = ContextFormat.PLAIN
) -> str:
    """
    Quick function to process cells into compact context string.

    Args:
        cells: List of cell dicts
        kernel_variables: Optional dict of variable names to types
        format: PLAIN (legacy) or XML (recommended for Claude)

    Returns:
        Formatted context string
    """
    manager = ContextManager()
    return manager.process_context(cells, kernel_variables, format)


def prepare_context_xml(cells: List[Dict[str, Any]], kernel_variables: Optional[Dict[str, str]] = None) -> str:
    """Quick function to process cells into XML context string (recommended for Claude)."""
    return prepare_context(cells, kernel_variables, ContextFormat.XML)


def prepare_context_plain(cells: List[Dict[str, Any]], kernel_variables: Optional[Dict[str, str]] = None) -> str:
    """Quick function to process cells into plain text context string (legacy)."""
    return prepare_context(cells, kernel_variables, ContextFormat.PLAIN)


def prepare_positional_context(
    cells: List[Dict[str, Any]],
    ai_cell_index: int,
    format: ContextFormat = ContextFormat.PLAIN
) -> str:
    """
    Quick function to process cells into positional context for AI Cell.

    Args:
        cells: List of cell dicts
        ai_cell_index: 0-based index of the AI cell
        format: PLAIN or XML

    Returns:
        Positional context string with above/below sections
    """
    manager = ContextManager()
    return manager.process_positional_context(cells, ai_cell_index, format)
