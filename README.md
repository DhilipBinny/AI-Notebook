# AI Notebook

A modern, AI-powered Jupyter notebook platform that brings intelligent assistance directly into your data science workflow.

## Features

- **Multi-LLM Support** — Choose between Gemini, OpenAI, Anthropic, or Ollama
- **Real-time Code Execution** — Execute Python cells with live output streaming
- **Intelligent Cell Manipulation** — AI can read, write, insert, and execute cells
- **Automatic Package Management** — AI installs missing dependencies automatically
- **File Operations** — AI can read/write files in the workspace
- **Multiple Themes** — Dark, Light, and Monokai
- **Import/Export** — Import existing `.ipynb` files or export your work
- **Per-Project Playgrounds** — Isolated Docker containers for each project

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Nginx                                │
│                    (Reverse Proxy)                           │
└─────────────────┬───────────────────────┬───────────────────┘
                  │                       │
                  ▼                       ▼
        ┌─────────────────┐     ┌─────────────────┐
        │   Next.js Web   │     │   Master API    │
        │   (Frontend)    │     │   (FastAPI)     │
        └─────────────────┘     └────────┬────────┘
                                         │
                  ┌──────────────────────┼──────────────────────┐
                  │                      │                      │
                  ▼                      ▼                      ▼
        ┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
        │     MySQL       │     │     MinIO       │     │  Playground  │
        │   (Database)    │     │   (S3 Storage)  │     │  Containers  │
        └─────────────────┘     └─────────────────┘     └──────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, SQLAlchemy |
| Kernel | Jupyter Client, IPython |
| Infrastructure | Docker, MySQL, Redis, MinIO |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- API keys for LLM providers (optional, Ollama works locally)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-notebook.git
   cd ai-notebook
   ```

2. **Configure environment**
   ```bash
   cp infrastructure/.env.example infrastructure/.env
   # Edit .env with your API keys and settings
   ```

3. **Start the infrastructure**
   ```bash
   cd infrastructure
   docker-compose up -d
   ```

4. **Start the application**
   ```bash
   docker-compose -f docker-compose.apps.yml up -d
   ```

5. **Access the application**
   - Web UI: http://localhost
   - Create an account and start creating notebooks

## Project Structure

```
ai-notebook/
├── web/                 # Next.js frontend
├── master/              # FastAPI backend (auth, projects, storage)
├── playground/          # Isolated execution environment with LLM tools
├── infrastructure/      # Docker configs for MySQL, Redis, MinIO
├── nginx/               # Reverse proxy configuration
└── docs/                # Documentation
```

## LLM Providers

| Provider | Local | API Key Required |
|----------|-------|------------------|
| Ollama | Yes | No |
| Gemini | No | Yes |
| OpenAI | No | Yes |
| Anthropic | No | Yes |

## License

MIT
