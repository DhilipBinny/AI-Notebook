"""
File Utils Tools - Allows LLM to interact with the file system.

These tools provide file operations within a safe working directory.
Operations are restricted to the /workspace directory for security.
"""

import os
import re
import fnmatch
import shutil
from pathlib import Path
from typing import Optional, List
from backend.utils.util_func import log

# Safe working directory for file operations
WORKSPACE_DIR = Path("/workspace")

# Limits
MAX_READ_LINES = 2000
MAX_READ_BYTES = 30 * 1024  # 30KB
MAX_CTX_BYTES = 100 * 1024  # 100KB for workspace context
MAX_GREP_MATCHES = 100
MAX_GLOB_RESULTS = 1000


def _ensure_workspace():
    """Ensure workspace directory exists"""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_path(file_path: str) -> Optional[Path]:
    """
    Validate and resolve a file path to ensure it's within the workspace.

    Args:
        file_path: Relative or absolute path

    Returns:
        Safe Path object within workspace, or None if path escapes workspace
    """
    _ensure_workspace()

    # Convert to Path
    path = Path(file_path)

    # If absolute path, check if it's already under workspace
    if path.is_absolute():
        resolved = path.resolve()
    else:
        # Relative path - resolve from workspace
        resolved = (WORKSPACE_DIR / path).resolve()

    # Security check: ensure path is within workspace
    try:
        resolved.relative_to(WORKSPACE_DIR.resolve())
        return resolved
    except ValueError:
        return None


def read_file(file_path: str, max_lines: Optional[int] = None) -> dict:
    """
    Read the contents of a file.

    Use this tool when you need to:
    - Read configuration files
    - Inspect data files (CSV, JSON, etc.)
    - Check file contents before processing
    - Read Python scripts or modules

    Args:
        file_path: Path to the file (relative to /workspace or absolute within /workspace)
        max_lines: Optional maximum number of lines to read (useful for large files)

    Returns:
        Dictionary with:
        - success: Whether the read succeeded
        - content: File contents (or first N lines if max_lines specified)
        - file_path: The resolved file path
        - size_bytes: File size in bytes
        - lines_count: Total number of lines
        - truncated: Whether content was truncated
        - error: Error message if read failed

    Example:
        To read a config file: read_file("config.json")
        To read first 50 lines of a large file: read_file("data.csv", max_lines=50)
    """
    log(f"==> read_file({file_path}) called from LLM")

    safe_path = _safe_path(file_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{file_path}' is outside the allowed workspace directory"
        }

    if not safe_path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }

    if not safe_path.is_file():
        return {
            "success": False,
            "error": f"Path is not a file: {file_path}"
        }

    try:
        # Get file info
        stat = safe_path.stat()
        size_bytes = stat.st_size

        # Read content
        with open(safe_path, 'r', encoding='utf-8', errors='replace') as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                content = ''.join(lines)
                truncated = True
            else:
                content = f.read()
                truncated = False

        lines_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)

        return {
            "success": True,
            "content": content,
            "file_path": str(safe_path),
            "size_bytes": size_bytes,
            "lines_count": lines_count,
            "truncated": truncated
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}"
        }


def write_file(file_path: str, content: str, create_dirs: bool = True) -> dict:
    """
    Write content to a file (creates or overwrites).

    Use this tool when you need to:
    - Save data to a file
    - Create configuration files
    - Write generated code or scripts
    - Save analysis results

    Args:
        file_path: Path to the file (relative to /workspace or absolute within /workspace)
        content: The content to write to the file
        create_dirs: Whether to create parent directories if they don't exist (default: True)

    Returns:
        Dictionary with:
        - success: Whether the write succeeded
        - file_path: The resolved file path
        - size_bytes: Number of bytes written
        - created: Whether the file was newly created (vs overwritten)
        - error: Error message if write failed

    Example:
        To save results: write_file("output/results.json", json_content)
        To create a script: write_file("scripts/process.py", python_code)
    """
    log(f"==> write_file({file_path}) called from LLM")

    safe_path = _safe_path(file_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{file_path}' is outside the allowed workspace directory"
        }

    try:
        # Check if file exists before writing
        file_existed = safe_path.exists()

        # Create parent directories if needed
        if create_dirs:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
        elif not safe_path.parent.exists():
            return {
                "success": False,
                "error": f"Parent directory does not exist: {safe_path.parent}"
            }

        # Write content
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)

        size_bytes = safe_path.stat().st_size

        return {
            "success": True,
            "file_path": str(safe_path),
            "size_bytes": size_bytes,
            "created": not file_existed
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write file: {str(e)}"
        }


def append_file(file_path: str, content: str) -> dict:
    """
    Append content to an existing file.

    Use this tool when you need to:
    - Add data to a log file
    - Append records to a data file
    - Add new entries without overwriting existing content

    Args:
        file_path: Path to the file (relative to /workspace or absolute within /workspace)
        content: The content to append to the file

    Returns:
        Dictionary with:
        - success: Whether the append succeeded
        - file_path: The resolved file path
        - bytes_appended: Number of bytes appended
        - new_size_bytes: Total file size after append
        - error: Error message if append failed

    Example:
        To append to a log: append_file("logs/process.log", "New log entry\\n")
    """
    log(f"==> append_file({file_path}) called from LLM")

    safe_path = _safe_path(file_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{file_path}' is outside the allowed workspace directory"
        }

    try:
        # Create file and parent dirs if they don't exist
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        bytes_appended = len(content.encode('utf-8'))

        with open(safe_path, 'a', encoding='utf-8') as f:
            f.write(content)

        new_size = safe_path.stat().st_size

        return {
            "success": True,
            "file_path": str(safe_path),
            "bytes_appended": bytes_appended,
            "new_size_bytes": new_size
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to append to file: {str(e)}"
        }


def delete_file(file_path: str) -> dict:
    """
    Delete a file.

    Use this tool when you need to:
    - Remove temporary files
    - Clean up intermediate files
    - Delete outdated data

    Args:
        file_path: Path to the file to delete (relative to /workspace or absolute within /workspace)

    Returns:
        Dictionary with:
        - success: Whether the deletion succeeded
        - file_path: The deleted file path
        - error: Error message if deletion failed

    Example:
        To delete a temp file: delete_file("temp/processing.tmp")
    """
    log(f"==> delete_file({file_path}) called from LLM")

    safe_path = _safe_path(file_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{file_path}' is outside the allowed workspace directory"
        }

    if not safe_path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }

    if not safe_path.is_file():
        return {
            "success": False,
            "error": f"Path is not a file: {file_path}. Use delete_directory for directories."
        }

    try:
        safe_path.unlink()
        return {
            "success": True,
            "file_path": str(safe_path)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to delete file: {str(e)}"
        }


def rename_file(old_path: str, new_path: str) -> dict:
    """
    Rename or move a file.

    Use this tool when you need to:
    - Rename a file
    - Move a file to a different location
    - Organize files into directories

    Args:
        old_path: Current path of the file
        new_path: New path for the file

    Returns:
        Dictionary with:
        - success: Whether the rename succeeded
        - old_path: Original file path
        - new_path: New file path
        - error: Error message if rename failed

    Example:
        To rename: rename_file("data.csv", "data_processed.csv")
        To move: rename_file("data.csv", "processed/data.csv")
    """
    log(f"==> rename_file({old_path}, {new_path}) called from LLM")

    safe_old = _safe_path(old_path)
    safe_new = _safe_path(new_path)

    if safe_old is None:
        return {
            "success": False,
            "error": f"Source path '{old_path}' is outside the allowed workspace directory"
        }

    if safe_new is None:
        return {
            "success": False,
            "error": f"Destination path '{new_path}' is outside the allowed workspace directory"
        }

    if not safe_old.exists():
        return {
            "success": False,
            "error": f"Source file not found: {old_path}"
        }

    if not safe_old.is_file():
        return {
            "success": False,
            "error": f"Source path is not a file: {old_path}"
        }

    try:
        # Create parent directory for destination if needed
        safe_new.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(safe_old), str(safe_new))

        return {
            "success": True,
            "old_path": str(safe_old),
            "new_path": str(safe_new)
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to rename file: {str(e)}"
        }


def copy_file(source_path: str, dest_path: str) -> dict:
    """
    Copy a file to a new location.

    Use this tool when you need to:
    - Create a backup of a file
    - Duplicate a file for processing
    - Copy templates

    Args:
        source_path: Path to the source file
        dest_path: Path for the destination file

    Returns:
        Dictionary with:
        - success: Whether the copy succeeded
        - source_path: Source file path
        - dest_path: Destination file path
        - size_bytes: Size of the copied file
        - error: Error message if copy failed

    Example:
        To backup: copy_file("config.json", "config.json.backup")
        To copy to new location: copy_file("template.py", "scripts/new_script.py")
    """
    log(f"==> copy_file({source_path}, {dest_path}) called from LLM")

    safe_source = _safe_path(source_path)
    safe_dest = _safe_path(dest_path)

    if safe_source is None:
        return {
            "success": False,
            "error": f"Source path '{source_path}' is outside the allowed workspace directory"
        }

    if safe_dest is None:
        return {
            "success": False,
            "error": f"Destination path '{dest_path}' is outside the allowed workspace directory"
        }

    if not safe_source.exists():
        return {
            "success": False,
            "error": f"Source file not found: {source_path}"
        }

    if not safe_source.is_file():
        return {
            "success": False,
            "error": f"Source path is not a file: {source_path}"
        }

    try:
        # Create parent directory for destination if needed
        safe_dest.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(safe_source), str(safe_dest))

        size_bytes = safe_dest.stat().st_size

        return {
            "success": True,
            "source_path": str(safe_source),
            "dest_path": str(safe_dest),
            "size_bytes": size_bytes
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to copy file: {str(e)}"
        }


def list_directory(dir_path: str = ".", include_hidden: bool = False) -> dict:
    """
    List contents of a directory.

    Use this tool when you need to:
    - See what files are in a directory
    - Explore the workspace structure
    - Find files before reading them
    - Check if files exist

    Args:
        dir_path: Path to the directory (default: current workspace root)
        include_hidden: Whether to include hidden files starting with . (default: False)

    Returns:
        Dictionary with:
        - success: Whether the listing succeeded
        - path: The listed directory path
        - entries: List of entries with name, type (file/dir), and size
        - total_files: Number of files
        - total_dirs: Number of directories
        - error: Error message if listing failed

    Example:
        To list workspace root: list_directory()
        To list a subdirectory: list_directory("data")
        To include hidden files: list_directory(".", include_hidden=True)
    """
    log(f"==> list_directory({dir_path}) called from LLM")

    safe_path = _safe_path(dir_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{dir_path}' is outside the allowed workspace directory"
        }

    if not safe_path.exists():
        return {
            "success": False,
            "error": f"Directory not found: {dir_path}"
        }

    if not safe_path.is_dir():
        return {
            "success": False,
            "error": f"Path is not a directory: {dir_path}"
        }

    try:
        entries = []
        total_files = 0
        total_dirs = 0

        for item in sorted(safe_path.iterdir()):
            # Skip hidden files if not requested
            if not include_hidden and item.name.startswith('.'):
                continue

            entry = {
                "name": item.name,
                "type": "dir" if item.is_dir() else "file"
            }

            if item.is_file():
                entry["size_bytes"] = item.stat().st_size
                total_files += 1
            else:
                total_dirs += 1

            entries.append(entry)

        return {
            "success": True,
            "path": str(safe_path),
            "entries": entries,
            "total_files": total_files,
            "total_dirs": total_dirs
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list directory: {str(e)}"
        }


def create_directory(dir_path: str) -> dict:
    """
    Create a directory (including parent directories).

    Use this tool when you need to:
    - Create directories for organizing files
    - Set up output directories
    - Create project structure

    Args:
        dir_path: Path to the directory to create

    Returns:
        Dictionary with:
        - success: Whether the creation succeeded
        - path: The created directory path
        - created: Whether directory was newly created (False if it already existed)
        - error: Error message if creation failed

    Example:
        To create output dir: create_directory("output/results")
    """
    log(f"==> create_directory({dir_path}) called from LLM")

    safe_path = _safe_path(dir_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{dir_path}' is outside the allowed workspace directory"
        }

    try:
        existed = safe_path.exists()
        safe_path.mkdir(parents=True, exist_ok=True)

        return {
            "success": True,
            "path": str(safe_path),
            "created": not existed
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create directory: {str(e)}"
        }


def delete_directory(dir_path: str, recursive: bool = False) -> dict:
    """
    Delete a directory.

    Use this tool when you need to:
    - Remove empty directories
    - Clean up directory structures
    - Delete directories with all contents (with recursive=True)

    Args:
        dir_path: Path to the directory to delete
        recursive: If True, delete directory and all contents. If False, only delete if empty.

    Returns:
        Dictionary with:
        - success: Whether the deletion succeeded
        - path: The deleted directory path
        - error: Error message if deletion failed

    Example:
        To delete empty dir: delete_directory("temp")
        To delete with contents: delete_directory("temp", recursive=True)
    """
    log(f"==> delete_directory({dir_path}, recursive={recursive}) called from LLM")

    safe_path = _safe_path(dir_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{dir_path}' is outside the allowed workspace directory"
        }

    if not safe_path.exists():
        return {
            "success": False,
            "error": f"Directory not found: {dir_path}"
        }

    if not safe_path.is_dir():
        return {
            "success": False,
            "error": f"Path is not a directory: {dir_path}. Use delete_file for files."
        }

    # Prevent deleting the workspace root
    if safe_path.resolve() == WORKSPACE_DIR.resolve():
        return {
            "success": False,
            "error": "Cannot delete the workspace root directory"
        }

    try:
        if recursive:
            shutil.rmtree(str(safe_path))
        else:
            safe_path.rmdir()  # Will fail if not empty

        return {
            "success": True,
            "path": str(safe_path)
        }
    except OSError as e:
        if "not empty" in str(e).lower() or "directory not empty" in str(e).lower():
            return {
                "success": False,
                "error": "Directory is not empty. Use recursive=True to delete with contents."
            }
        return {
            "success": False,
            "error": f"Failed to delete directory: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to delete directory: {str(e)}"
        }


def file_exists(file_path: str) -> dict:
    """
    Check if a file or directory exists.

    Use this tool when you need to:
    - Check if a file exists before reading
    - Verify output file was created
    - Check for existing data before processing

    Args:
        file_path: Path to check

    Returns:
        Dictionary with:
        - success: True (always succeeds)
        - exists: Whether the path exists
        - is_file: Whether it's a file
        - is_dir: Whether it's a directory
        - path: The resolved path

    Example:
        To check if data exists: file_exists("data/input.csv")
    """
    log(f"==> file_exists({file_path}) called from LLM")

    safe_path = _safe_path(file_path)
    if safe_path is None:
        return {
            "success": True,
            "exists": False,
            "is_file": False,
            "is_dir": False,
            "path": file_path,
            "note": "Path is outside workspace directory"
        }

    return {
        "success": True,
        "exists": safe_path.exists(),
        "is_file": safe_path.is_file() if safe_path.exists() else False,
        "is_dir": safe_path.is_dir() if safe_path.exists() else False,
        "path": str(safe_path)
    }


# ---------------------------------------------------------------------------
# edit_file  (OpenClaw: edit)
# ---------------------------------------------------------------------------

def edit_file(file_path: str, old_text: str, new_text: str) -> dict:
    """
    Edit a file by finding and replacing exact text. The old_text must match
    exactly (including whitespace and newlines). This is for precise, surgical
    edits without rewriting the whole file.

    Use this tool when you need to:
    - Fix a bug in a specific line or block
    - Update a function, variable name, or config value
    - Add imports, parameters, or small code sections
    - Make targeted changes without touching other content

    IMPORTANT: old_text must be unique in the file. If there are multiple
    occurrences, provide more surrounding context to make it unique.

    Args:
        file_path: Path to the file to edit (relative to /workspace or absolute within /workspace)
        old_text: Exact text to find in the file (must match exactly, must be unique)
        new_text: New text to replace the old text with

    Returns:
        Dictionary with:
        - success: Whether the edit succeeded
        - file_path: The resolved file path
        - replacements: Number of replacements made (should be 1)
        - error: Error message if edit failed

    Example:
        To fix a typo: edit_file("script.py", "pritn('hello')", "print('hello')")
        To update a value: edit_file("config.json", '"port": 3000', '"port": 8080')
    """
    log(f"==> edit_file({file_path}) called from LLM")

    safe_path = _safe_path(file_path)
    if safe_path is None:
        return {
            "success": False,
            "error": f"Path '{file_path}' is outside the allowed workspace directory"
        }

    if not safe_path.exists():
        return {
            "success": False,
            "error": f"File not found: {file_path}"
        }

    if not safe_path.is_file():
        return {
            "success": False,
            "error": f"Path is not a file: {file_path}"
        }

    try:
        with open(safe_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Normalize line endings for matching
        normalized_content = content.replace('\r\n', '\n')
        normalized_old = old_text.replace('\r\n', '\n')
        normalized_new = new_text.replace('\r\n', '\n')

        occurrences = normalized_content.count(normalized_old)

        if occurrences == 0:
            return {
                "success": False,
                "error": f"Could not find the exact text in {file_path}. The old_text must match exactly including all whitespace and newlines."
            }

        if occurrences > 1:
            return {
                "success": False,
                "error": f"Found {occurrences} occurrences of the text in {file_path}. The text must be unique. Please provide more surrounding context to make it unique."
            }

        new_content = normalized_content.replace(normalized_old, normalized_new, 1)

        if new_content == normalized_content:
            return {
                "success": False,
                "error": f"No changes made to {file_path}. old_text and new_text produce identical content."
            }

        # Restore original line endings if file used CRLF
        if '\r\n' in content and '\r\n' not in new_content:
            new_content = new_content.replace('\n', '\r\n')

        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return {
            "success": True,
            "file_path": str(safe_path),
            "replacements": 1,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to edit file: {str(e)}"
        }


# ---------------------------------------------------------------------------
# list_files  (OpenClaw: find)
# ---------------------------------------------------------------------------

def list_files(pattern: str = "*", directory: str = ".") -> dict:
    """
    Search for files by glob pattern. Returns matching file paths relative to
    the search directory. Similar to the 'find' command.

    Use this tool when you need to:
    - Find files by name or extension (e.g., all .csv files)
    - Discover project structure
    - Locate specific files before reading them
    - Search with glob patterns like "**/*.py" for recursive matches

    Args:
        pattern: Glob pattern to match files (e.g., "*.py", "**/*.json", "data_*.csv").
                 Use "**/" prefix for recursive search.
        directory: Directory to search in, relative to workspace (default: workspace root ".")

    Returns:
        Dictionary with:
        - success: Whether the search succeeded
        - files: List of matching file paths (relative to search directory)
        - total: Number of matches found
        - truncated: Whether results were truncated (limit: 1000)
        - error: Error message if search failed

    Example:
        To find all Python files: list_files("**/*.py")
        To find CSVs in data dir: list_files("*.csv", "data")
        To list everything: list_files("**/*")
    """
    log(f"==> list_files({pattern}, {directory}) called from LLM")

    safe_dir = _safe_path(directory)
    if safe_dir is None:
        return {
            "success": False,
            "error": f"Path '{directory}' is outside the allowed workspace directory"
        }

    if not safe_dir.exists():
        return {
            "success": False,
            "error": f"Directory not found: {directory}"
        }

    if not safe_dir.is_dir():
        return {
            "success": False,
            "error": f"Path is not a directory: {directory}"
        }

    try:
        matches = []
        truncated = False

        for match in sorted(safe_dir.glob(pattern)):
            if len(matches) >= MAX_GLOB_RESULTS:
                truncated = True
                break
            parts = match.relative_to(safe_dir).parts
            if any(p.startswith('.') or p == '__pycache__' for p in parts):
                continue
            try:
                rel_path = str(match.relative_to(safe_dir))
                if match.is_dir():
                    rel_path += "/"
                matches.append(rel_path)
            except ValueError:
                continue

        return {
            "success": True,
            "files": matches,
            "total": len(matches),
            "truncated": truncated,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list files: {str(e)}"
        }


# ---------------------------------------------------------------------------
# search_files  (OpenClaw: grep)
# ---------------------------------------------------------------------------

def search_files(pattern: str, directory: str = ".", file_glob: str = "*", ignore_case: bool = False) -> dict:
    """
    Search file contents for a pattern (regex or literal). Returns matching
    lines with file paths and line numbers. Similar to grep/ripgrep.

    Use this tool when you need to:
    - Find where a function, variable, or string is used
    - Search for error messages or log patterns
    - Find TODOs, FIXMEs, or specific comments
    - Locate configuration values across files

    Args:
        pattern: Search pattern (Python regex syntax, e.g., "import pandas", "def .*process", "TODO")
        directory: Directory to search in, relative to workspace (default: workspace root ".")
        file_glob: Filter files by glob pattern (e.g., "*.py", "*.json"). Default: all files.
        ignore_case: Case-insensitive search (default: False)

    Returns:
        Dictionary with:
        - success: Whether the search succeeded
        - matches: List of matches, each with file, line_number, and content
        - total: Number of matches found
        - truncated: Whether results were truncated (limit: 100)
        - error: Error message if search failed

    Example:
        To find imports: search_files("import pandas", file_glob="*.py")
        To find TODOs: search_files("TODO|FIXME", file_glob="*.py", ignore_case=True)
        To search in a specific dir: search_files("error", "logs", "*.log")
    """
    log(f"==> search_files({pattern}, {directory}, {file_glob}) called from LLM")

    safe_dir = _safe_path(directory)
    if safe_dir is None:
        return {
            "success": False,
            "error": f"Path '{directory}' is outside the allowed workspace directory"
        }

    if not safe_dir.exists():
        return {
            "success": False,
            "error": f"Directory not found: {directory}"
        }

    try:
        regex_flags = re.IGNORECASE if ignore_case else 0
        compiled = re.compile(pattern, regex_flags)
    except re.error as e:
        return {
            "success": False,
            "error": f"Invalid regex pattern: {str(e)}"
        }

    try:
        matches = []
        truncated = False

        for root, dirs, files in os.walk(str(safe_dir)):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != 'node_modules']

            for filename in files:
                if not fnmatch.fnmatch(filename, file_glob):
                    continue

                filepath = Path(root) / filename

                try:
                    filepath.resolve().relative_to(WORKSPACE_DIR.resolve())
                except ValueError:
                    continue

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            if compiled.search(line):
                                rel_path = str(filepath.relative_to(safe_dir))
                                matches.append({
                                    "file": rel_path,
                                    "line_number": line_num,
                                    "content": line.rstrip('\n\r')[:500]
                                })
                                if len(matches) >= MAX_GREP_MATCHES:
                                    truncated = True
                                    break
                except (OSError, UnicodeDecodeError):
                    continue

                if truncated:
                    break
            if truncated:
                break

        return {
            "success": True,
            "matches": matches,
            "total": len(matches),
            "truncated": truncated,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to search files: {str(e)}"
        }


# ---------------------------------------------------------------------------
# get_workspace_context  (inspired by toolslm's folder2ctx)
# ---------------------------------------------------------------------------

_TEXT_EXTENSIONS = {
    '.py', '.txt', '.md', '.csv', '.json', '.yaml', '.yml', '.toml',
    '.ini', '.cfg', '.conf', '.sh', '.bash', '.sql', '.html', '.css',
    '.js', '.ts', '.jsx', '.tsx', '.xml', '.env', '.gitignore',
    '.dockerfile', '.r', '.rmd', '.jl', '.lua', '.rb', '.pl',
    '.log', '.rst', '.tex', '.bib',
}

_SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.ipynb_checkpoints', '.venv', 'venv'}


def get_workspace_context(directory: str = ".", file_types: Optional[str] = None, max_file_size: int = 10000, include_content: bool = True) -> dict:
    """
    Get a structured overview of the workspace — file tree plus file contents
    packaged into a single context string. This gives you a comprehensive
    understanding of the project in one call.

    Produces an XML-structured context document that is easy to parse and reference.

    Use this tool when you need to:
    - Understand the overall project structure before making changes
    - Get a birds-eye view of all files and their contents
    - Analyze a codebase or data project holistically
    - Find where specific logic lives across multiple files

    Args:
        directory: Directory to scan, relative to workspace (default: workspace root ".")
        file_types: Comma-separated file extensions to include (e.g., "py,json,csv").
                    If not provided, includes all common text file types.
        max_file_size: Maximum size in bytes for including file contents (default: 10000).
                       Files larger than this show only metadata, not content.
        include_content: Whether to include file contents (default: True).
                         Set to False for just the file tree.

    Returns:
        Dictionary with:
        - success: Whether the scan succeeded
        - context: The structured context string (XML-formatted)
        - file_count: Number of files included
        - total_size: Combined size of all included file contents
        - truncated: Whether the context was truncated (limit: 100KB)
        - error: Error message if scan failed

    Example:
        Full project context: get_workspace_context()
        Python files only: get_workspace_context(file_types="py")
        Just the tree: get_workspace_context(include_content=False)
        Specific folder: get_workspace_context("src", file_types="py,json")
    """
    log(f"==> get_workspace_context({directory}, {file_types}) called from LLM")

    safe_dir = _safe_path(directory)
    if safe_dir is None:
        return {
            "success": False,
            "error": f"Path '{directory}' is outside the allowed workspace directory"
        }

    if not safe_dir.exists():
        return {
            "success": False,
            "error": f"Directory not found: {directory}"
        }

    if not safe_dir.is_dir():
        return {
            "success": False,
            "error": f"Path is not a directory: {directory}"
        }

    allowed_exts = None
    if file_types:
        allowed_exts = set()
        for ext in file_types.split(','):
            ext = ext.strip().lstrip('.')
            if ext:
                allowed_exts.add(f'.{ext}')

    try:
        files_data: List[dict] = []
        total_content_size = 0

        for root, dirs, files in os.walk(str(safe_dir)):
            dirs[:] = sorted([d for d in dirs if d not in _SKIP_DIRS and not d.startswith('.')])

            for filename in sorted(files):
                filepath = Path(root) / filename
                ext = filepath.suffix.lower()

                if allowed_exts:
                    if ext not in allowed_exts:
                        continue
                elif ext not in _TEXT_EXTENSIONS and ext != '':
                    if '.' in filename:
                        continue

                try:
                    filepath.resolve().relative_to(WORKSPACE_DIR.resolve())
                except ValueError:
                    continue

                rel_path = str(filepath.relative_to(safe_dir))

                try:
                    stat = filepath.stat()
                    file_size = stat.st_size
                except OSError:
                    continue

                file_info_entry = {
                    "path": rel_path,
                    "size": file_size,
                    "content": None
                }

                if include_content and file_size <= max_file_size:
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                        file_info_entry["content"] = content
                        total_content_size += len(content)
                    except (OSError, UnicodeDecodeError):
                        pass

                files_data.append(file_info_entry)

                if total_content_size > MAX_CTX_BYTES:
                    break

            if total_content_size > MAX_CTX_BYTES:
                break

        parts = []
        parts.append(f'<workspace path="{safe_dir}">')

        parts.append('  <file_tree>')
        for f in files_data:
            size_str = _format_size(f["size"])
            parts.append(f'    <file path="{f["path"]}" size="{size_str}" />')
        parts.append('  </file_tree>')

        if include_content:
            parts.append('  <files>')
            for f in files_data:
                if f["content"] is not None:
                    parts.append(f'  <file path="{f["path"]}">')
                    parts.append(f'{f["content"]}')
                    parts.append('  </file>')
            parts.append('  </files>')

        parts.append('</workspace>')

        context = '\n'.join(parts)

        truncated = False
        if len(context.encode('utf-8')) > MAX_CTX_BYTES:
            context = context[:MAX_CTX_BYTES]
            context += "\n\n[Context truncated at 100KB. Use file_types filter or include_content=False to reduce size.]"
            truncated = True

        return {
            "success": True,
            "context": context,
            "file_count": len(files_data),
            "total_size": total_content_size,
            "truncated": truncated,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to build workspace context: {str(e)}"
        }


def _format_size(size_bytes: int) -> str:
    """Format byte size to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
