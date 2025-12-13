"""
File Handling Tools - Allows LLM to work with files in the user's project.

These tools provide safe, sandboxed file access within the project directory:
- List files in project
- Read text files (txt, json, py, etc.)
- Preview data files (csv, excel) without full load
- Write/save files
- Check file existence and info

SECURITY: All paths are restricted to the project directory.
"""

import os
import json
from pathlib import Path
from typing import Optional
from backend.session_manager import get_current_session
from backend.utils.util_func import log
import backend.config as cfg


def _get_project_root() -> Optional[Path]:
    """Get the project root directory from session."""
    session = get_current_session()
    if not session:
        return None

    # Project files are stored in MinIO under projects/{project_id}/
    # For local access, we use the mounted path
    project_id = session.session_id

    # The project data path from config
    project_path = Path(cfg.MINIO_DATA_PATH) / "notebooks" / "projects" / project_id

    if project_path.exists():
        return project_path

    return None


def _safe_path(user_path: str) -> Optional[Path]:
    """
    Resolve and validate a user-provided path.
    Ensures the path is within the project directory (prevents path traversal).

    Args:
        user_path: User-provided path (relative or with ..)

    Returns:
        Safe absolute Path or None if invalid/outside project
    """
    project_root = _get_project_root()
    if not project_root:
        return None

    # Handle empty or root path
    if not user_path or user_path in [".", "/", ""]:
        return project_root

    # Remove leading slash for relative paths
    user_path = user_path.lstrip("/")

    # Resolve the full path with symlink protection
    try:
        # Build the path WITHOUT resolving symlinks first
        candidate_path = project_root / user_path

        # Check for symlinks in the path - reject if any component is a symlink
        # This prevents symlink attacks where a symlink points outside project root
        current = project_root
        for part in Path(user_path).parts:
            current = current / part
            if current.is_symlink():
                log(f"[Files] Symlink detected and blocked: {current}")
                return None

        # Now resolve to get the canonical path
        full_path = candidate_path.resolve()
        project_root_resolved = project_root.resolve()

        # Security check: ensure resolved path is within project root
        # Use os.path.commonpath for more robust check
        try:
            common = Path(os.path.commonpath([str(full_path), str(project_root_resolved)]))
            if common != project_root_resolved:
                log(f"[Files] Path traversal attempt blocked: {user_path}")
                return None
        except ValueError:
            # commonpath raises ValueError if paths are on different drives (Windows)
            log(f"[Files] Path traversal attempt blocked (different root): {user_path}")
            return None

        return full_path
    except Exception as e:
        log(f"[Files] Path resolution error: {e}")
        return None


def list_project_files(path: str = "/", pattern: str = "*", recursive: bool = False) -> dict:
    """
    List files in the user's project directory.

    WHEN TO USE THIS TOOL:
    - User asks "what files do I have?"
    - User asks "show me my data files"
    - Before reading a file, to find available files
    - To help user locate their uploaded files

    Args:
        path: Directory path relative to project root (default: "/" = project root)
        pattern: Glob pattern to filter files (default: "*" = all files)
                 Examples: "*.csv", "*.py", "data_*"
        recursive: If True, search subdirectories too (default: False)

    Returns:
        Dictionary with:
        - success: Whether listing succeeded
        - path: The directory path listed
        - files: List of file info dicts (name, type, size, modified)
        - directories: List of subdirectory names
        - total_files: Count of files
        - total_directories: Count of directories
        - error: Error message if failed

    Example:
        list_project_files()  → list all files in project root
        list_project_files("/data", "*.csv")  → list CSV files in data folder
        list_project_files("/", "*.py", recursive=True)  → find all Python files
    """
    log(f"==> list_project_files({path}, {pattern}, recursive={recursive}) called from LLM")

    safe_dir = _safe_path(path)
    if not safe_dir:
        return {
            "success": False,
            "error": "No active project or invalid path"
        }

    if not safe_dir.exists():
        return {
            "success": False,
            "path": path,
            "error": f"Directory '{path}' does not exist"
        }

    if not safe_dir.is_dir():
        return {
            "success": False,
            "path": path,
            "error": f"'{path}' is a file, not a directory"
        }

    files = []
    directories = []

    try:
        if recursive:
            # Use rglob for recursive search
            items = list(safe_dir.rglob(pattern))
        else:
            # Use glob for current directory only
            items = list(safe_dir.glob(pattern))

        project_root = _get_project_root()

        for item in items:
            # Get relative path from project root
            try:
                rel_path = item.relative_to(project_root)
            except ValueError:
                rel_path = item.name

            if item.is_file():
                # Get file info
                stat = item.stat()
                size_bytes = stat.st_size

                # Format size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

                files.append({
                    "name": item.name,
                    "path": str(rel_path),
                    "size": size_str,
                    "size_bytes": size_bytes,
                    "extension": item.suffix.lower(),
                    "modified": stat.st_mtime
                })
            elif item.is_dir() and not recursive:
                directories.append({
                    "name": item.name,
                    "path": str(rel_path)
                })

        # Also list directories if not using a specific pattern
        if pattern == "*" and not recursive:
            for item in safe_dir.iterdir():
                if item.is_dir():
                    try:
                        rel_path = item.relative_to(project_root)
                    except ValueError:
                        rel_path = item.name

                    # Avoid duplicates
                    if not any(d["name"] == item.name for d in directories):
                        directories.append({
                            "name": item.name,
                            "path": str(rel_path)
                        })

        # Sort files by name
        files.sort(key=lambda x: x["name"].lower())
        directories.sort(key=lambda x: x["name"].lower())

        return {
            "success": True,
            "path": path,
            "files": files,
            "directories": directories,
            "total_files": len(files),
            "total_directories": len(directories)
        }

    except Exception as e:
        log(f"[Files] List error: {e}")
        return {
            "success": False,
            "path": path,
            "error": f"Failed to list files: {str(e)}"
        }


def file_info(path: str) -> dict:
    """
    Get detailed information about a specific file.

    WHEN TO USE THIS TOOL:
    - Check if a file exists before reading
    - Get file size before loading (to warn about large files)
    - Determine file type

    Args:
        path: File path relative to project root

    Returns:
        Dictionary with:
        - success: Whether file was found
        - exists: Whether file exists
        - name: File name
        - path: Full relative path
        - size: Human-readable size
        - size_bytes: Size in bytes
        - extension: File extension
        - is_text: Whether file is likely text (based on extension)
        - is_data: Whether file is likely data (csv, json, excel)
        - modified: Last modified timestamp
        - error: Error message if failed

    Example:
        file_info("data.csv")  → check if data.csv exists and its size
    """
    log(f"==> file_info({path}) called from LLM")

    safe_file = _safe_path(path)
    if not safe_file:
        return {
            "success": False,
            "exists": False,
            "error": "No active project or invalid path"
        }

    if not safe_file.exists():
        return {
            "success": True,
            "exists": False,
            "path": path,
            "message": f"File '{path}' does not exist"
        }

    if safe_file.is_dir():
        return {
            "success": True,
            "exists": True,
            "path": path,
            "is_directory": True,
            "message": f"'{path}' is a directory, not a file"
        }

    try:
        stat = safe_file.stat()
        size_bytes = stat.st_size

        # Format size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

        extension = safe_file.suffix.lower()

        # Determine file type
        text_extensions = {'.txt', '.py', '.json', '.md', '.csv', '.yml', '.yaml',
                          '.html', '.css', '.js', '.xml', '.ini', '.cfg', '.log',
                          '.sh', '.bash', '.sql', '.r', '.jl'}
        data_extensions = {'.csv', '.json', '.xlsx', '.xls', '.parquet', '.feather',
                          '.pickle', '.pkl', '.hdf5', '.h5', '.sqlite', '.db'}

        return {
            "success": True,
            "exists": True,
            "name": safe_file.name,
            "path": path,
            "size": size_str,
            "size_bytes": size_bytes,
            "extension": extension,
            "is_text": extension in text_extensions,
            "is_data": extension in data_extensions,
            "modified": stat.st_mtime
        }

    except Exception as e:
        return {
            "success": False,
            "exists": True,
            "path": path,
            "error": f"Failed to get file info: {str(e)}"
        }


def read_text_file(path: str, max_lines: int = 200, encoding: str = "utf-8") -> dict:
    """
    Read a text file from the project directory.

    WHEN TO USE THIS TOOL:
    - User asks to read/show a file
    - Need to see contents of config files (json, yaml, txt)
    - Read Python scripts or other code files
    - Read markdown or documentation

    WHEN NOT TO USE THIS TOOL:
    - For CSV data files → use preview_data_file() for structured preview
    - For binary files (images, pickles) → these can't be read as text

    Args:
        path: File path relative to project root
        max_lines: Maximum lines to read (default: 200, max: 1000)
        encoding: File encoding (default: utf-8)

    Returns:
        Dictionary with:
        - success: Whether read succeeded
        - path: File path
        - content: File content (may be truncated)
        - lines: Number of lines read
        - total_lines: Total lines in file
        - truncated: Whether content was truncated
        - encoding: Encoding used
        - error: Error message if failed

    Example:
        read_text_file("config.json")  → read JSON config
        read_text_file("script.py", max_lines=50)  → read first 50 lines
    """
    log(f"==> read_text_file({path}, max_lines={max_lines}) called from LLM")

    safe_file = _safe_path(path)
    if not safe_file:
        return {
            "success": False,
            "error": "No active project or invalid path"
        }

    if not safe_file.exists():
        return {
            "success": False,
            "path": path,
            "error": f"File '{path}' does not exist"
        }

    if safe_file.is_dir():
        return {
            "success": False,
            "path": path,
            "error": f"'{path}' is a directory, not a file"
        }

    # Limit max_lines
    max_lines = min(max(max_lines, 1), 1000)

    # Check file size - warn if very large
    size_bytes = safe_file.stat().st_size
    if size_bytes > 10 * 1024 * 1024:  # 10MB
        return {
            "success": False,
            "path": path,
            "error": f"File is too large ({size_bytes / (1024*1024):.1f} MB). Use preview_data_file() for data files or read in chunks."
        }

    try:
        with open(safe_file, 'r', encoding=encoding) as f:
            lines = []
            total_lines = 0
            for line in f:
                total_lines += 1
                if len(lines) < max_lines:
                    lines.append(line)

            content = ''.join(lines)
            truncated = total_lines > max_lines

            return {
                "success": True,
                "path": path,
                "content": content,
                "lines": len(lines),
                "total_lines": total_lines,
                "truncated": truncated,
                "encoding": encoding,
                "note": f"Showing first {len(lines)} of {total_lines} lines" if truncated else None
            }

    except UnicodeDecodeError:
        return {
            "success": False,
            "path": path,
            "error": f"Cannot read file as text with {encoding} encoding. It may be a binary file."
        }
    except Exception as e:
        return {
            "success": False,
            "path": path,
            "error": f"Failed to read file: {str(e)}"
        }


def preview_data_file(path: str, rows: int = 10) -> dict:
    """
    Preview a data file (CSV, JSON, Excel) without loading the entire file.

    WHEN TO USE THIS TOOL:
    - User asks "what's in this CSV?"
    - Preview data before loading into pandas
    - Check column names and data types
    - Verify file format before analysis

    WHEN NOT TO USE THIS TOOL:
    - For text/code files → use read_text_file()
    - To actually load data → use execute_python_code with pandas

    Supports: CSV, JSON, Excel (.xlsx, .xls)

    Args:
        path: File path relative to project root
        rows: Number of rows to preview (default: 10, max: 100)

    Returns:
        Dictionary with:
        - success: Whether preview succeeded
        - path: File path
        - file_type: Detected file type
        - columns: List of column names (for tabular data)
        - row_count: Number of rows previewed
        - total_rows: Estimated total rows (for CSV)
        - preview: Preview data as string or list
        - dtypes: Inferred data types per column
        - error: Error message if failed

    Example:
        preview_data_file("data.csv")  → preview CSV with headers and first 10 rows
        preview_data_file("config.json")  → preview JSON structure
    """
    log(f"==> preview_data_file({path}, rows={rows}) called from LLM")

    safe_file = _safe_path(path)
    if not safe_file:
        return {
            "success": False,
            "error": "No active project or invalid path"
        }

    if not safe_file.exists():
        return {
            "success": False,
            "path": path,
            "error": f"File '{path}' does not exist"
        }

    # Limit rows
    rows = min(max(rows, 1), 100)

    extension = safe_file.suffix.lower()

    try:
        # CSV files
        if extension == '.csv':
            import csv

            with open(safe_file, 'r', encoding='utf-8', newline='') as f:
                # Count total lines (approximate)
                total_lines = sum(1 for _ in f)

            with open(safe_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)

                # Read header
                try:
                    header = next(reader)
                except StopIteration:
                    return {
                        "success": True,
                        "path": path,
                        "file_type": "csv",
                        "message": "Empty CSV file"
                    }

                # Read preview rows
                preview_rows = []
                for i, row in enumerate(reader):
                    if i >= rows:
                        break
                    preview_rows.append(row)

                # Format as table string
                table_lines = [",".join(header)]
                for row in preview_rows:
                    table_lines.append(",".join(str(cell) for cell in row))

                return {
                    "success": True,
                    "path": path,
                    "file_type": "csv",
                    "columns": header,
                    "column_count": len(header),
                    "row_count": len(preview_rows),
                    "total_rows": total_lines - 1,  # Exclude header
                    "preview": "\n".join(table_lines),
                    "preview_rows": preview_rows[:5]  # First 5 as list too
                }

        # JSON files
        elif extension == '.json':
            with open(safe_file, 'r', encoding='utf-8') as f:
                content = f.read(100000)  # Read first 100KB
                data = json.loads(content)

            # Determine structure
            if isinstance(data, list):
                preview = data[:rows]
                return {
                    "success": True,
                    "path": path,
                    "file_type": "json",
                    "structure": "array",
                    "total_items": len(data),
                    "preview_count": len(preview),
                    "preview": json.dumps(preview, indent=2)[:5000],
                    "columns": list(preview[0].keys()) if preview and isinstance(preview[0], dict) else None
                }
            elif isinstance(data, dict):
                keys = list(data.keys())
                return {
                    "success": True,
                    "path": path,
                    "file_type": "json",
                    "structure": "object",
                    "keys": keys[:50],
                    "total_keys": len(keys),
                    "preview": json.dumps(data, indent=2)[:5000]
                }
            else:
                return {
                    "success": True,
                    "path": path,
                    "file_type": "json",
                    "structure": type(data).__name__,
                    "preview": str(data)[:2000]
                }

        # Excel files
        elif extension in ['.xlsx', '.xls']:
            try:
                import pandas as pd

                # Read only first few rows
                df = pd.read_excel(safe_file, nrows=rows)

                return {
                    "success": True,
                    "path": path,
                    "file_type": "excel",
                    "columns": list(df.columns),
                    "column_count": len(df.columns),
                    "row_count": len(df),
                    "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
                    "preview": df.to_string()
                }
            except ImportError:
                return {
                    "success": False,
                    "path": path,
                    "error": "pandas or openpyxl not installed. Cannot preview Excel files."
                }

        else:
            return {
                "success": False,
                "path": path,
                "error": f"Unsupported file type '{extension}'. Use read_text_file() for text files."
            }

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "path": path,
            "error": f"Invalid JSON: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "path": path,
            "error": f"Failed to preview file: {str(e)}"
        }


def write_text_file(path: str, content: str, overwrite: bool = False) -> dict:
    """
    Write content to a text file in the project directory.

    WHEN TO USE THIS TOOL:
    - User asks to save/create a file
    - Export results to a file
    - Create config or script files
    - Save processed text data

    WHEN NOT TO USE THIS TOOL:
    - To save DataFrames → use df.to_csv() in execute_python_code
    - To save plots → use plt.savefig() in execute_python_code

    SECURITY: Can only write within project directory.

    Args:
        path: File path relative to project root
        content: Text content to write
        overwrite: If False (default), fails if file exists

    Returns:
        Dictionary with:
        - success: Whether write succeeded
        - path: File path
        - bytes_written: Number of bytes written
        - created: Whether a new file was created
        - overwritten: Whether existing file was overwritten
        - error: Error message if failed

    Example:
        write_text_file("output.txt", "Hello world")  → create new file
        write_text_file("config.json", json_str, overwrite=True)  → update existing
    """
    log(f"==> write_text_file({path}, overwrite={overwrite}) called from LLM")

    safe_file = _safe_path(path)
    if not safe_file:
        return {
            "success": False,
            "error": "No active project or invalid path"
        }

    # Check if file exists
    file_exists = safe_file.exists()
    if file_exists and not overwrite:
        return {
            "success": False,
            "path": path,
            "error": f"File '{path}' already exists. Set overwrite=True to replace it."
        }

    # Create parent directories if needed
    try:
        safe_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {
            "success": False,
            "path": path,
            "error": f"Failed to create directory: {str(e)}"
        }

    # Write the file
    try:
        with open(safe_file, 'w', encoding='utf-8') as f:
            bytes_written = f.write(content)

        return {
            "success": True,
            "path": path,
            "bytes_written": bytes_written,
            "created": not file_exists,
            "overwritten": file_exists and overwrite,
            "message": f"File '{path}' {'overwritten' if file_exists else 'created'} successfully"
        }

    except Exception as e:
        return {
            "success": False,
            "path": path,
            "error": f"Failed to write file: {str(e)}"
        }


def delete_file(path: str, confirm: bool = False) -> dict:
    """
    Delete a file from the project directory.

    WHEN TO USE THIS TOOL:
    - User explicitly asks to delete a file
    - Clean up temporary files

    SECURITY:
    - Can only delete within project directory
    - Requires confirm=True to actually delete
    - Cannot delete directories (only files)

    Args:
        path: File path relative to project root
        confirm: Must be True to actually delete (safety check)

    Returns:
        Dictionary with:
        - success: Whether deletion succeeded
        - path: File path
        - deleted: Whether file was actually deleted
        - error: Error message if failed

    Example:
        delete_file("temp.txt", confirm=True)  → delete the file
    """
    log(f"==> delete_file({path}, confirm={confirm}) called from LLM")

    safe_file = _safe_path(path)
    if not safe_file:
        return {
            "success": False,
            "error": "No active project or invalid path"
        }

    if not safe_file.exists():
        return {
            "success": False,
            "path": path,
            "error": f"File '{path}' does not exist"
        }

    if safe_file.is_dir():
        return {
            "success": False,
            "path": path,
            "error": f"'{path}' is a directory. Cannot delete directories."
        }

    if not confirm:
        return {
            "success": False,
            "path": path,
            "deleted": False,
            "error": "Deletion not confirmed. Set confirm=True to delete the file."
        }

    try:
        safe_file.unlink()
        return {
            "success": True,
            "path": path,
            "deleted": True,
            "message": f"File '{path}' deleted successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "path": path,
            "error": f"Failed to delete file: {str(e)}"
        }
