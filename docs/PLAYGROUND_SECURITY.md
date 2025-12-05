# Playground Container Security

This document describes the security model for the playground container, specifically the "stealth build" that protects source code while allowing user file access.

## Overview

The playground container runs an AI-powered Jupyter kernel service. In production, the Python source code is compiled to a binary using PyInstaller to protect intellectual property. The security model ensures:

1. **Binary Protection**: Users cannot read or reverse-engineer the server binary
2. **Workspace Access**: Users can read/write files in `/workspace` via terminal
3. **Service Functionality**: The playground service can access both the binary and workspace

## Build Modes

### Development Build (`Dockerfile`)
- Source code visible as Python files
- Suitable for local development and debugging

### Production/Stealth Build (`Dockerfile.stealth`)
- Python compiled to single binary via PyInstaller
- No readable source code in container
- Binary protected with restricted permissions

## User & Group Model

```
Users:
├── playground (uid=1000)  → Runs the server binary
└── nobody (uid=65534)     → Runs terminal sessions

Groups:
├── playground (gid=1000)  → Primary group for playground user
├── nogroup (gid=65534)    → Primary group for nobody user
└── workspace (gid=999)    → Shared group for file access
                             Members: playground, nobody
```

## Directory Permissions

| Path | Owner | Mode | Purpose |
|------|-------|------|---------|
| `/usr/local/bin/playground_server` | playground:playground | `500` (r-x------) | Compiled binary |
| `/app/entrypoint.sh` | playground:playground | `500` (r-x------) | Startup script |
| `/workspace` | playground:workspace | `2775` (rwxrwsr-x) | User file storage |
| `/notebooks` | playground:playground | `755` | Internal notebook storage |

### Permission Breakdown

**Binary (`500` = r-x------)**
- Owner (playground): read + execute
- Group: none
- Others: none
- Result: Only `playground` user can access

**Workspace (`2775` = rwxrwsr-x)**
- Owner (playground): read + write + execute
- Group (workspace): read + write + execute + setgid
- Others: read + execute
- Setgid bit: New files inherit `workspace` group

## Access Matrix

| User | Binary | /workspace | Purpose |
|------|--------|------------|---------|
| playground | r-x | rwx | Run server, manage files |
| nobody | --- | rwx | Terminal access, user files |
| root | rwx | rwx | System administration |

## Terminal Security

The terminal WebSocket endpoint (`/projects/{id}/playground/terminal`) creates an interactive shell session:

```python
exec_instance = docker_client.client.api.exec_create(
    container_id,
    cmd=["/bin/bash"],
    user="nobody",           # Restricted user
    workdir="/workspace",    # Start in workspace
    environment={
        "TERM": "xterm-256color",
        "HOME": "/workspace"
    },
)
```

**Security measures:**
- Runs as `nobody` user (cannot access binary)
- Starts in `/workspace` directory
- HOME set to `/workspace` for shell config files

## File Upload Flow

When files are uploaded to the container:

1. **Upload API** (runs as `playground` user)
   - Writes file to `/workspace`
   - File created with group `workspace`

2. **Terminal Access** (runs as `nobody` user)
   - Can read/write file via `workspace` group membership
   - New files created also get `workspace` group (setgid)

3. **Service Access** (runs as `playground` user)
   - Can read files created by terminal user
   - Group membership ensures bidirectional access

## Verification Tests

Run these commands to verify security model:

```bash
# Start test container
docker run -d --name test-stealth ainotebook-playground:stealth

# Test 1: nobody cannot read binary
docker exec --user nobody test-stealth cat /usr/local/bin/playground_server
# Expected: Permission denied

# Test 2: nobody cannot execute binary
docker exec --user nobody test-stealth /usr/local/bin/playground_server
# Expected: Error (cannot read PKG archive)

# Test 3: nobody can write to workspace
docker exec --user nobody test-stealth touch /workspace/test.txt
docker exec test-stealth ls -la /workspace/
# Expected: File created with workspace group

# Test 4: playground can read nobody's file
docker exec --user playground test-stealth cat /workspace/test.txt
# Expected: Success

# Test 5: Verify group membership
docker exec test-stealth id playground
# Expected: groups=...,999(workspace)

docker exec test-stealth id nobody
# Expected: groups=...,999(workspace)

# Cleanup
docker stop test-stealth && docker rm test-stealth
```

## Implementation Files

- `playground/Dockerfile.stealth` - Production build with security model
- `playground/main_entry.py` - PyInstaller entry point
- `master/app/playgrounds/routes.py` - Terminal WebSocket (line ~436)
- `master/app/playgrounds/docker_client.py` - Container creation

## Security Considerations

### What's Protected
- Python source code (compiled to binary)
- Server implementation details
- LLM integration logic

### What's Not Protected
- Container environment variables (API keys passed at runtime)
- Files in `/workspace` (user-accessible by design)
- Network traffic (use TLS in production)

### Limitations
- Root user can still access everything
- Binary can be copied out (but not easily decompiled)
- PyInstaller binaries can be reverse-engineered with effort (not trivial)

## Deployment

Build the stealth image:
```bash
./scripts/deploy-prod.sh --playground
```

Or manually:
```bash
docker build -f playground/Dockerfile.stealth -t ainotebook-playground:stealth ./playground
```
