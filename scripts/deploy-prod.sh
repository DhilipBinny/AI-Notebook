#!/bin/bash
# AI Notebook - Production Deployment Script
#
# This script builds Docker images and deploys to the production VM
#
# Usage:
#   ./scripts/deploy-prod.sh [OPTIONS] [VM_HOST] [VM_USER]
#
# Options:
#   --all           Build all services (default if no option specified)
#   --web           Build web (Next.js) only
#   --master        Build master-api only
#   --playground    Build playground only
#   --skip-upload   Build only, don't upload to VM
#   --no-cache      Force rebuild without cache (slower but ensures fresh build)
#   --rollback      Rollback to previous version (restores :rollback tags to :prod)
#
# Examples:
#   ./scripts/deploy-prod.sh                          # Build all, deploy to default VM
#   ./scripts/deploy-prod.sh --web --master           # Build web and master only
#   ./scripts/deploy-prod.sh --playground             # Build playground only
#   ./scripts/deploy-prod.sh --all 10.0.2.21 binny    # Build all, deploy to specific VM
#   ./scripts/deploy-prod.sh --web --skip-upload      # Build web only, no upload
#   ./scripts/deploy-prod.sh --web --rollback         # Rollback web to previous version

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Change to project root
cd "${PROJECT_ROOT}"

# Default values
BUILD_WEB=false
BUILD_MASTER=false
BUILD_PLAYGROUND=false
SKIP_UPLOAD=false
NO_CACHE=false
ROLLBACK=false
VM_HOST="10.0.2.21"
VM_USER="sysadmin"

# Parse arguments
POSITIONAL_ARGS=()
while [[ $# -gt 0 ]]; do
  case $1 in
    --all)
      BUILD_WEB=true
      BUILD_MASTER=true
      BUILD_PLAYGROUND=true
      shift
      ;;
    --web)
      BUILD_WEB=true
      shift
      ;;
    --master)
      BUILD_MASTER=true
      shift
      ;;
    --playground)
      BUILD_PLAYGROUND=true
      shift
      ;;
    --skip-upload)
      SKIP_UPLOAD=true
      shift
      ;;
    --no-cache)
      NO_CACHE=true
      shift
      ;;
    --rollback)
      ROLLBACK=true
      shift
      ;;
    -*)
      echo "Unknown option: $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

# Handle positional args (VM_HOST, VM_USER)
if [[ ${#POSITIONAL_ARGS[@]} -ge 1 ]]; then
  VM_HOST="${POSITIONAL_ARGS[0]}"
fi
if [[ ${#POSITIONAL_ARGS[@]} -ge 2 ]]; then
  VM_USER="${POSITIONAL_ARGS[1]}"
fi

# If no service specified, build all
if [[ "$BUILD_WEB" == "false" && "$BUILD_MASTER" == "false" && "$BUILD_PLAYGROUND" == "false" ]]; then
  BUILD_WEB=true
  BUILD_MASTER=true
  BUILD_PLAYGROUND=true
fi

REMOTE_DIR="/home/${VM_USER}/ai-jupyter"
REGISTRY_PREFIX="ainotebook"

# =============================================
# ROLLBACK MODE — restore :rollback to :prod
# =============================================
if [[ "$ROLLBACK" == "true" ]]; then
  echo "=============================================="
  echo "  AI Notebook - ROLLBACK"
  echo "=============================================="
  echo "Target VM: ${VM_USER}@${VM_HOST}"
  echo ""
  echo "Services to rollback:"
  [[ "$BUILD_WEB" == "true" ]] && echo "  ← web"
  [[ "$BUILD_MASTER" == "true" ]] && echo "  ← master-api"
  [[ "$BUILD_PLAYGROUND" == "true" ]] && echo "  ← playground"
  echo ""

  # Setup SSH
  SSH_CONTROL_PATH="/tmp/ssh-deploy-$$"
  SSH_OPTS="-o ControlMaster=auto -o ControlPath=${SSH_CONTROL_PATH} -o ControlPersist=300"
  cleanup_ssh() { ssh -O exit -o ControlPath="${SSH_CONTROL_PATH}" ${VM_USER}@${VM_HOST} 2>/dev/null || true; }
  trap cleanup_ssh EXIT

  ssh ${SSH_OPTS} ${VM_USER}@${VM_HOST} << ROLLBACK_SCRIPT
    ERRORS=""

    if [[ "$BUILD_WEB" == "true" ]]; then
      if docker image inspect ${REGISTRY_PREFIX}-web:rollback >/dev/null 2>&1; then
        echo "  Restoring ${REGISTRY_PREFIX}-web:rollback → :prod"
        docker tag ${REGISTRY_PREFIX}-web:rollback ${REGISTRY_PREFIX}-web:prod
      else
        echo "  ✗ No rollback image found for web"
        ERRORS="web \$ERRORS"
      fi
    fi

    if [[ "$BUILD_MASTER" == "true" ]]; then
      if docker image inspect ${REGISTRY_PREFIX}-master-api:rollback >/dev/null 2>&1; then
        echo "  Restoring ${REGISTRY_PREFIX}-master-api:rollback → :prod"
        docker tag ${REGISTRY_PREFIX}-master-api:rollback ${REGISTRY_PREFIX}-master-api:prod
      else
        echo "  ✗ No rollback image found for master-api"
        ERRORS="master \$ERRORS"
      fi
    fi

    if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
      if docker image inspect ${REGISTRY_PREFIX}-playground:rollback >/dev/null 2>&1; then
        echo "  Restoring ${REGISTRY_PREFIX}-playground:rollback → :prod"
        docker tag ${REGISTRY_PREFIX}-playground:rollback ${REGISTRY_PREFIX}-playground:prod
      else
        echo "  ✗ No rollback image found for playground"
        ERRORS="playground \$ERRORS"
      fi
    fi

    if [[ -n "\$ERRORS" ]]; then
      echo ""
      echo "  ⚠ Missing rollback images for: \$ERRORS"
      echo "  (Only services with rollback images were restored)"
    fi

    echo ""
    echo "  Restarting services..."
    cd ${REMOTE_DIR}
    if [[ "$BUILD_WEB" == "true" || "$BUILD_MASTER" == "true" ]]; then
      docker compose -f docker-compose.prod.yml up -d
    fi

    echo ""
    echo "  Current images:"
    docker images | grep ${REGISTRY_PREFIX}
ROLLBACK_SCRIPT

  echo ""
  echo "Rollback complete!"
  exit 0
fi

echo "=============================================="
echo "  AI Notebook - Production Deployment"
echo "=============================================="
echo "Working directory: ${PROJECT_ROOT}"
echo "Target VM: ${VM_USER}@${VM_HOST}"
echo "Remote Dir: ${REMOTE_DIR}"
echo ""
echo "Services to build:"
[[ "$BUILD_WEB" == "true" ]] && echo "  ✓ web"
[[ "$BUILD_MASTER" == "true" ]] && echo "  ✓ master-api"
[[ "$BUILD_PLAYGROUND" == "true" ]] && echo "  ✓ playground"
[[ "$SKIP_UPLOAD" == "true" ]] && echo "" && echo "  (skip upload enabled)"
[[ "$NO_CACHE" == "true" ]] && echo "  (no-cache enabled - full rebuild)"
echo ""

# Set cache flag for docker build
CACHE_FLAG=""
if [[ "$NO_CACHE" == "true" ]]; then
  CACHE_FLAG="--no-cache"
fi

# Setup SSH ControlMaster for connection reuse (single password prompt)
SSH_CONTROL_PATH="/tmp/ssh-deploy-$$"
SSH_OPTS="-o ControlMaster=auto -o ControlPath=${SSH_CONTROL_PATH} -o ControlPersist=300"

cleanup_ssh() {
  # Close SSH control connection on exit
  ssh -O exit -o ControlPath="${SSH_CONTROL_PATH}" ${VM_USER}@${VM_HOST} 2>/dev/null || true
}
trap cleanup_ssh EXIT

# Step 1: Build production images locally
echo "[1/7] Building production Docker images..."

if [[ "$BUILD_WEB" == "true" ]]; then
  echo "  Building web (Next.js production)..."
  docker build ${CACHE_FLAG} -t ${REGISTRY_PREFIX}-web:prod -f web/Dockerfile.prod ./web
fi

if [[ "$BUILD_MASTER" == "true" ]]; then
  echo "  Building master-api (FastAPI production)..."
  docker build ${CACHE_FLAG} -t ${REGISTRY_PREFIX}-master-api:prod -f master/Dockerfile.prod ./master
fi

if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  echo "  Building playground (stealth/compiled)..."
  docker build ${CACHE_FLAG} -t ${REGISTRY_PREFIX}-playground:prod -f ./playground/Dockerfile.stealth ./playground
fi

echo ""
echo "[2/7] Saving Docker images to tar files..."
mkdir -p ./dist

if [[ "$BUILD_WEB" == "true" ]]; then
  echo "  Saving web..."
  docker save ${REGISTRY_PREFIX}-web:prod | gzip > ./dist/ainotebook-web.tar.gz
fi

if [[ "$BUILD_MASTER" == "true" ]]; then
  echo "  Saving master-api..."
  docker save ${REGISTRY_PREFIX}-master-api:prod | gzip > ./dist/ainotebook-master-api.tar.gz
fi

if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  echo "  Saving playground..."
  docker save ${REGISTRY_PREFIX}-playground:prod | gzip > ./dist/ainotebook-playground.tar.gz
fi

echo "  Images saved to ./dist/"
ls -lh ./dist/*.tar.gz 2>/dev/null || echo "  (no tar files found)"

# Skip upload if requested
if [[ "$SKIP_UPLOAD" == "true" ]]; then
  echo ""
  echo "[SKIP] Upload skipped. Images are in ./dist/"
  echo ""
  echo "To manually upload later:"
  echo "  scp ./dist/*.tar.gz ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/dist/"
  exit 0
fi

echo ""
echo "[3/7] Copying files to VM..."
echo "  (Establishing SSH connection - enter password once)"

# Create remote directory structure (this establishes the ControlMaster connection)
ssh ${SSH_OPTS} ${VM_USER}@${VM_HOST} "mkdir -p ${REMOTE_DIR}/dist"

# Build list of files to copy
FILES_TO_COPY=""
if [[ "$BUILD_WEB" == "true" ]]; then
  FILES_TO_COPY="${FILES_TO_COPY} ./dist/ainotebook-web.tar.gz"
fi
if [[ "$BUILD_MASTER" == "true" ]]; then
  FILES_TO_COPY="${FILES_TO_COPY} ./dist/ainotebook-master-api.tar.gz"
fi
if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  FILES_TO_COPY="${FILES_TO_COPY} ./dist/ainotebook-playground.tar.gz"
fi

# Copy all files in single scp command (reuses existing connection)
if [[ -n "${FILES_TO_COPY}" ]]; then
  echo "  Copying: ${FILES_TO_COPY}"
  scp ${SSH_OPTS} ${FILES_TO_COPY} ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/dist/
fi

echo ""
echo "[4/7] Backing up current images on VM (tagging :prod → :rollback)..."

ssh ${SSH_OPTS} ${VM_USER}@${VM_HOST} << BACKUP_SCRIPT
if [[ "$BUILD_WEB" == "true" ]]; then
  if docker image inspect ${REGISTRY_PREFIX}-web:prod >/dev/null 2>&1; then
    docker tag ${REGISTRY_PREFIX}-web:prod ${REGISTRY_PREFIX}-web:rollback
    echo "  ✓ web:prod → web:rollback"
  else
    echo "  - web:prod not found (first deploy?)"
  fi
fi

if [[ "$BUILD_MASTER" == "true" ]]; then
  if docker image inspect ${REGISTRY_PREFIX}-master-api:prod >/dev/null 2>&1; then
    docker tag ${REGISTRY_PREFIX}-master-api:prod ${REGISTRY_PREFIX}-master-api:rollback
    echo "  ✓ master-api:prod → master-api:rollback"
  else
    echo "  - master-api:prod not found (first deploy?)"
  fi
fi

if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  if docker image inspect ${REGISTRY_PREFIX}-playground:prod >/dev/null 2>&1; then
    docker tag ${REGISTRY_PREFIX}-playground:prod ${REGISTRY_PREFIX}-playground:rollback
    echo "  ✓ playground:prod → playground:rollback"
  else
    echo "  - playground:prod not found (first deploy?)"
  fi
fi
BACKUP_SCRIPT

echo ""
echo "[5/7] Loading new Docker images on VM..."

ssh ${SSH_OPTS} ${VM_USER}@${VM_HOST} << REMOTE_SCRIPT
cd ${REMOTE_DIR}

if [[ -f dist/ainotebook-web.tar.gz && "$BUILD_WEB" == "true" ]]; then
  echo "  Loading ainotebook-web..."
  gunzip -c dist/ainotebook-web.tar.gz | docker load
fi

if [[ -f dist/ainotebook-master-api.tar.gz && "$BUILD_MASTER" == "true" ]]; then
  echo "  Loading ainotebook-master-api..."
  gunzip -c dist/ainotebook-master-api.tar.gz | docker load
fi

if [[ -f dist/ainotebook-playground.tar.gz && "$BUILD_PLAYGROUND" == "true" ]]; then
  echo "  Loading ainotebook-playground..."
  gunzip -c dist/ainotebook-playground.tar.gz | docker load
fi

echo ""
echo "  Current images:"
docker images | grep ainotebook
REMOTE_SCRIPT

echo ""
echo "[6/7] Restarting updated services on VM..."

ssh ${SSH_OPTS} ${VM_USER}@${VM_HOST} << RESTART_SCRIPT
cd ${REMOTE_DIR}

COMPOSE_FILE="docker-compose.prod.yml"
RESTARTED=""

# Restart docker-compose services (web, master-api, nginx)
if [[ "$BUILD_WEB" == "true" || "$BUILD_MASTER" == "true" ]]; then
  echo "  Restarting compose services..."
  if [[ -f "\$COMPOSE_FILE" ]]; then
    docker compose -f "\$COMPOSE_FILE" up -d
    # Nginx caches upstream IPs at startup. When web/master gets a new container IP,
    # nginx must be restarted to resolve the new address.
    echo "  Restarting nginx to pick up new container IPs..."
    sleep 2
    docker restart ainotebook-nginx
    RESTARTED="compose"
  else
    echo "  ⚠️ \$COMPOSE_FILE not found, skipping compose restart"
  fi
fi

# Restart playground containers (spawned dynamically, not in compose)
if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  echo "  Finding running playground containers..."
  PLAYGROUND_CONTAINERS=\$(docker ps --filter "name=playground-" --format "{{.Names}}" 2>/dev/null)

  if [[ -n "\$PLAYGROUND_CONTAINERS" ]]; then
    echo "  Found running playgrounds: \$PLAYGROUND_CONTAINERS"
    for CONTAINER in \$PLAYGROUND_CONTAINERS; do
      echo "  Stopping \$CONTAINER..."
      docker stop "\$CONTAINER" 2>/dev/null || true
      docker rm "\$CONTAINER" 2>/dev/null || true
      echo "  ✓ Removed \$CONTAINER"
    done

    # Update DB to mark all playgrounds as stopped
    echo "  Updating playground status in DB..."
    docker exec ainotebook-mysql mysql -uroot -painotebook_dev_password ainotebook \
      -e "UPDATE playgrounds SET status='stopped', stopped_at=NOW() WHERE status IN ('running','starting');" 2>/dev/null
    echo "  ✓ DB updated — all playgrounds marked stopped"
    RESTARTED="\${RESTARTED} playgrounds"
  else
    echo "  No running playground containers found"
  fi
fi

if [[ -n "\$RESTARTED" ]]; then
  echo ""
  echo "  ✓ Restarted:\$RESTARTED"
else
  echo "  Nothing to restart"
fi
RESTART_SCRIPT

echo ""
echo "[7/7] Deployment complete!"
echo ""
echo "Summary:"
[[ "$BUILD_WEB" == "true" ]] && echo "  ✓ web — rebuilt & restarted"
[[ "$BUILD_MASTER" == "true" ]] && echo "  ✓ master-api — rebuilt & restarted"
[[ "$BUILD_PLAYGROUND" == "true" ]] && echo "  ✓ playground — rebuilt, old containers removed (new ones spawn on next use)"
echo ""
echo "To rollback if something breaks:"
ROLLBACK_FLAGS=""
[[ "$BUILD_WEB" == "true" ]] && ROLLBACK_FLAGS="${ROLLBACK_FLAGS} --web"
[[ "$BUILD_MASTER" == "true" ]] && ROLLBACK_FLAGS="${ROLLBACK_FLAGS} --master"
[[ "$BUILD_PLAYGROUND" == "true" ]] && ROLLBACK_FLAGS="${ROLLBACK_FLAGS} --playground"
echo "  ./scripts/deploy-prod.sh --rollback${ROLLBACK_FLAGS}"
echo ""
