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
"""

import re
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
from backend.utils.util_func import log_debug_message


class ContextFormat(str, Enum):
    """Supported context formats for LLM"""
    PLAIN = "plain"  # Simple text format
    XML = "xml"      # XML tags (recommended)


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
            format: Output format - PLAIN (legacy) or XML (recommended for Claude)

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
        else:
            context_str = self._format_compact_context(structured)

        log_debug_message(f"📋 Context [{format.value}]: {len(context_str)} chars, {structured.total_cells} cells, {len(structured.imports)} imports, {len(structured.recent_errors)} errors")

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
            first_line = self._get_first_line(content)
            has_output = bool(output and output.strip())
            has_error = self._is_error_output(output) if output else False
            output_type = self._detect_output_type(output) if has_output else None

            structured.cells.append({
                "cell_id": cell_id,
                "type": cell_type,
                "preview": first_line,
                "has_output": has_output,
                "has_error": has_error,
                "output_type": output_type
            })

        # Add kernel variables if provided
        if kernel_variables:
            structured.variables.update(kernel_variables)

        # Deduplicate imports
        structured.imports = list(set(structured.imports))

        return structured

    def _format_compact_context(self, structured: StructuredContext) -> str:
        """Format structured context into compact LLM-friendly string"""
        parts = []

        parts.append("=== NOTEBOOK OVERVIEW ===")
        parts.append(f"Total cells: {structured.total_cells}")

        # Environment section
        if structured.imports:
            imports_str = ', '.join(sorted(structured.imports)[:12])
            if len(structured.imports) > 12:
                imports_str += f" (+{len(structured.imports) - 12} more)"
            parts.append(f"Imports: {imports_str}")

        if structured.variables:
            vars_list = [f"{k}:{v}" for k, v in list(structured.variables.items())[:8]]
            vars_str = ', '.join(vars_list)
            if len(structured.variables) > 8:
                vars_str += f" (+{len(structured.variables) - 8} more)"
            parts.append(f"Variables: {vars_str}")

        # Errors section (important!)
        if structured.recent_errors:
            parts.append("\n[ERRORS]")
            for err in structured.recent_errors[-3:]:
                parts.append(f"  {err['cell_id']}: {err['error']}")

        # Cells overview - compact table format
        parts.append("\n[CELLS]")
        parts.append("ID | Type | Preview | Output")
        parts.append("-" * 60)

        for cell in structured.cells:
            cell_id = cell["cell_id"]
            cell_type = "md" if cell["type"] == "markdown" else "py"
            preview = cell["preview"][:45]

            # Output indicator
            if cell["has_error"]:
                output_ind = "[ERROR]"
            elif cell["has_output"]:
                output_ind = f"[{cell['output_type']}]" if cell["output_type"] else "[out]"
            else:
                output_ind = ""

            parts.append(f"{cell_id} | {cell_type} | {preview} | {output_ind}")

        parts.append("\n=== END OVERVIEW ===")
        parts.append("\nUse get_cell_content(cell_id) to read full cell content/output.")

        return '\n'.join(parts)

    def _format_xml_context(self, structured: StructuredContext) -> str:
        """
        Format structured context into XML for LLM.

        XML format is recommended for Claude (specifically trained on XML tags)
        and works well with other LLMs like GPT-4 and Gemini.
        Research shows XML can improve accuracy by up to 40% for complex tasks.
        """
        parts = []

        parts.append('<notebook_context>')
        parts.append(f'  <overview total_cells="{structured.total_cells}"/>')

        # Imports section
        if structured.imports:
            parts.append('  <imports>')
            for imp in sorted(structured.imports)[:12]:
                parts.append(f'    <import>{self._escape_xml(imp)}</import>')
            if len(structured.imports) > 12:
                parts.append(f'    <!-- +{len(structured.imports) - 12} more imports -->')
            parts.append('  </imports>')

        # Variables section
        if structured.variables:
            parts.append('  <variables>')
            for name, var_type in list(structured.variables.items())[:10]:
                parts.append(f'    <var name="{self._escape_xml(name)}" type="{self._escape_xml(var_type)}"/>')
            if len(structured.variables) > 10:
                parts.append(f'    <!-- +{len(structured.variables) - 10} more variables -->')
            parts.append('  </variables>')

        # Errors section (high priority - always show)
        if structured.recent_errors:
            parts.append('  <errors>')
            for err in structured.recent_errors[-3:]:
                parts.append(f'    <error cell_id="{self._escape_xml(err["cell_id"])}">')
                parts.append(f'      {self._escape_xml(err["error"])}')
                parts.append('    </error>')
            parts.append('  </errors>')

        # Cells section
        parts.append('  <cells>')
        for cell in structured.cells:
            cell_type = "markdown" if cell["type"] == "markdown" else "code"
            has_output = "true" if cell["has_output"] else "false"
            has_error = "true" if cell["has_error"] else "false"
            output_type = cell["output_type"] or ""

            parts.append(f'    <cell id="{self._escape_xml(cell["cell_id"])}" type="{cell_type}" has_output="{has_output}" has_error="{has_error}" output_type="{output_type}">')
            parts.append(f'      <preview>{self._escape_xml(cell["preview"][:50])}</preview>')
            parts.append('    </cell>')
        parts.append('  </cells>')

        parts.append('</notebook_context>')
        parts.append('')
        parts.append('<tool_hint>Use get_cell_content(cell_id) to read full cell content and output.</tool_hint>')

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

    # =========================================================================
    # POSITIONAL CONTEXT (for AI Cell)
    # =========================================================================

    def process_positional_context(
        self,
        cells: List[Dict[str, Any]],
        ai_cell_index: int,
        format: ContextFormat = ContextFormat.PLAIN,
        max_output_chars: int = 500
    ) -> str:
        """
        Process notebook cells into positional context for AI Cell.

        This creates a context with cells organized as "above" and "below"
        the AI cell's position, with immediate neighbors marked.

        Args:
            cells: List of cell dicts with id, type, content, output, cellNumber
            ai_cell_index: The 0-based index of the AI cell in the notebook
            format: Output format - PLAIN or XML
            max_output_chars: Max characters for cell output (default: 500)

        Returns:
            Positional context string for AI Cell
        """
        if not cells:
            if format == ContextFormat.XML:
                return "<notebook_context><empty>No other cells in notebook</empty></notebook_context>"
            return "(No other cells in notebook)"

        cells_above = []
        cells_below = []

        for i, cell in enumerate(cells):
            cell_position = cell.get("cellNumber", i + 1) - 1 if cell.get("cellNumber") else i
            output = cell.get("output", "") or ""

            cell_data = {
                "id": cell.get("id", f"cell-{i}"),
                "type": cell.get("type", "code"),
                "content": cell.get("content", "") or "",
                "output": output[:max_output_chars] if output else "",
                "position": cell_position,
                "is_immediate": False
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
        else:
            context_str = self._format_positional_plain(cells_above, cells_below, ai_cell_index)

        log_debug_message(f"📋 Positional Context [{format.value}]: {len(context_str)} chars, {len(cells_above)} above, {len(cells_below)} below")

        return context_str

    def _format_positional_plain(self, cells_above: List[Dict], cells_below: List[Dict], ai_cell_index: int) -> str:
        """Format positional context in plain text"""
        parts = []

        if cells_above:
            parts.append("=== CELLS ABOVE YOU ===")
            for cell in cells_above:
                cell_type = "Code" if cell["type"] == "code" else cell["type"].capitalize()
                prefix = "[IMMEDIATELY ABOVE] " if cell["is_immediate"] else ""
                cell_info = f"{prefix}[@{cell['id']}] ({cell_type}):\n{cell['content']}"
                if cell["output"]:
                    cell_info += f"\n[Output]: {cell['output']}"
                parts.append(cell_info)

        parts.append(f"\n=== YOUR POSITION (AI Cell #{ai_cell_index + 1}) ===")

        if cells_below:
            parts.append("\n=== CELLS BELOW YOU ===")
            for cell in cells_below:
                cell_type = "Code" if cell["type"] == "code" else cell["type"].capitalize()
                prefix = "[IMMEDIATELY BELOW] " if cell["is_immediate"] else ""
                cell_info = f"{prefix}[@{cell['id']}] ({cell_type}):\n{cell['content']}"
                if cell["output"]:
                    cell_info += f"\n[Output]: {cell['output']}"
                parts.append(cell_info)

        return "\n".join(parts)

    def _format_positional_xml(self, cells_above: List[Dict], cells_below: List[Dict], ai_cell_index: int) -> str:
        """Format positional context in XML"""
        parts = []
        parts.append('<notebook_context>')
        parts.append(f'  <your_position cell_number="{ai_cell_index + 1}"/>')

        if cells_above:
            parts.append('  <cells_above>')
            for cell in cells_above:
                immediate = ' immediate="true"' if cell["is_immediate"] else ''
                parts.append(f'    <cell id="{self._escape_xml(cell["id"])}" type="{cell["type"]}"{immediate}>')
                parts.append(f'      <content>{self._escape_xml(cell["content"])}</content>')
                if cell["output"]:
                    parts.append(f'      <output>{self._escape_xml(cell["output"])}</output>')
                parts.append('    </cell>')
            parts.append('  </cells_above>')

        if cells_below:
            parts.append('  <cells_below>')
            for cell in cells_below:
                immediate = ' immediate="true"' if cell["is_immediate"] else ''
                parts.append(f'    <cell id="{self._escape_xml(cell["id"])}" type="{cell["type"]}"{immediate}>')
                parts.append(f'      <content>{self._escape_xml(cell["content"])}</content>')
                if cell["output"]:
                    parts.append(f'      <output>{self._escape_xml(cell["output"])}</output>')
                parts.append('    </cell>')
            parts.append('  </cells_below>')

        parts.append('</notebook_context>')
        return '\n'.join(parts)

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
                var_type = self._infer_type(value)
                if var_type:
                    variables[var_name] = var_type

        return variables

    def _infer_type(self, value: str) -> Optional[str]:
        """Infer variable type from assignment value"""
        value = value.strip()

        if value.startswith(('pd.read_', 'pd.DataFrame')):
            return 'DataFrame'
        elif value.startswith(('np.array', 'np.zeros', 'np.ones', 'np.arange')):
            return 'ndarray'
        elif value.startswith('['):
            return 'list'
        elif value.startswith('{'):
            return 'dict'
        elif value.startswith(('"', "'")):
            return 'str'
        elif value.replace('.', '').replace('-', '').isdigit():
            return 'float' if '.' in value else 'int'
        elif value in ('True', 'False'):
            return 'bool'
        elif value == 'None':
            return 'None'
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
