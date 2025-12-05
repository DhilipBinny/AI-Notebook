
from pathlib import Path

from fastapi.routing import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any

# Create API Router
router = APIRouter(prefix="", tags=["notebook"])


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Default notebooks directory
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
NOTEBOOKS_DIR.mkdir(exist_ok=True)

# Chat history directory
CHAT_HISTORY_DIR = NOTEBOOKS_DIR / "chat_history"
CHAT_HISTORY_DIR.mkdir(exist_ok=True)


class NotebookSaveRequest(BaseModel):
    filepath: str  # Relative or absolute path
    content: Dict[str, Any]  # The notebook JSON content


class NotebookLoadRequest(BaseModel):
    filepath: str

# === Chat History Management ===

def get_chat_history_path(notebook_name: str) -> Path:
    """Get the path to chat history file for a notebook"""
    # Sanitize filename
    safe_name = notebook_name.replace("/", "_").replace("\\", "_")
    if safe_name.endswith(".ipynb"):
        safe_name = safe_name[:-6]  # Remove .ipynb extension

    return CHAT_HISTORY_DIR / f"{safe_name}_chat.json"


def load_chat_history(notebook_name: str) -> List[Dict[str, Any]]:
    """Load chat history from file"""
    history_path = get_chat_history_path(notebook_name)

    if not history_path.exists():
        return []

    try:
        import json
        with open(history_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('messages', [])
    except Exception as e:
        print(f"Error loading chat history: {e}")
        return []


def save_chat_history(notebook_name: str, messages: List[Dict[str, Any]]) -> bool:
    """Save chat history to file"""
    history_path = get_chat_history_path(notebook_name)

    try:
        import json
        from datetime import datetime

        # Load existing data to preserve metadata
        existing_data = {}
        if history_path.exists():
            with open(history_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)

        # Update data
        data = {
            "notebook": notebook_name,
            "created": existing_data.get("created", datetime.now().isoformat()),
            "updated": datetime.now().isoformat(),
            "messages": messages
        }

        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"Error saving chat history: {e}")
        return False

@router.post("/notebook/save")
async def save_notebook(request: NotebookSaveRequest):
    """Save notebook to server filesystem"""
    try:
        # Resolve filepath - if relative, use NOTEBOOKS_DIR
        filepath = Path(request.filepath)
        if not filepath.is_absolute():
            filepath = NOTEBOOKS_DIR / filepath

        # Ensure .ipynb extension
        if not str(filepath).endswith('.ipynb'):
            filepath = Path(str(filepath) + '.ipynb')

        # Create parent directories if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Write the notebook
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(request.content, f, indent=2)

        return {
            "success": True,
            "filepath": str(filepath),
            "message": f"Saved to {filepath.name}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notebook/load")
async def load_notebook(request: NotebookLoadRequest):
    """Load notebook from server filesystem"""
    try:
        filepath = Path(request.filepath)
        if not filepath.is_absolute():
            filepath = NOTEBOOKS_DIR / filepath

        if not filepath.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            content = json.load(f)

        return {
            "success": True,
            "filepath": str(filepath),
            "filename": filepath.name,
            "content": content
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notebook/list")
async def list_notebooks(directory: str = None):
    """List available notebooks in a directory"""
    try:
        if directory:
            search_dir = Path(directory)
            if not search_dir.is_absolute():
                search_dir = NOTEBOOKS_DIR / directory
        else:
            search_dir = NOTEBOOKS_DIR

        if not search_dir.exists():
            return {"success": True, "notebooks": [], "directory": str(search_dir)}

        notebooks = []
        for f in search_dir.glob("*.ipynb"):
            notebooks.append({
                "name": f.name,
                "path": str(f),
                "modified": f.stat().st_mtime
            })

        # Sort by modification time (newest first)
        notebooks.sort(key=lambda x: x["modified"], reverse=True)

        return {
            "success": True,
            "notebooks": notebooks,
            "directory": str(search_dir)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notebook/{filepath:path}")
async def serve_notebook_frontend(filepath: str):
    """Serve the frontend HTML for notebook URLs (URL-based routing)"""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    else:
        raise HTTPException(status_code=404, detail="Frontend not found")