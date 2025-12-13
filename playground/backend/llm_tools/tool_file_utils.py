"""
File Utils Tools - Allows LLM to interact with the file system.

These tools provide file operations within a safe working directory.
Operations are restricted to the /workspace directory for security.
"""

import shutil
from pathlib import Path
from typing import Optional
from backend.utils.util_func import log

# Safe working directory for file operations
WORKSPACE_DIR = Path("/workspace")


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
                "error": f"Directory is not empty. Use recursive=True to delete with contents."
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
