#!/usr/bin/env python3
"""
Main entry point for PyInstaller compilation.
This file imports and runs the FastAPI server.
"""
import os
import uvicorn

# Import the FastAPI app
from backend.server import app

if __name__ == "__main__":
    port = int(os.environ.get("PLAYGROUND_PORT", 8888))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
