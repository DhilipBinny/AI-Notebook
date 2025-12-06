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
#
# Examples:
#   ./scripts/deploy-prod.sh                          # Build all, deploy to default VM
#   ./scripts/deploy-prod.sh --web --master           # Build web and master only
#   ./scripts/deploy-prod.sh --playground             # Build playground only
#   ./scripts/deploy-prod.sh --all 10.0.2.21 binny    # Build all, deploy to specific VM
#   ./scripts/deploy-prod.sh --web --skip-upload      # Build web only, no upload

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
[[ "$SKIP_UPLOAD" == "true" ]] && echo ""  && echo "  (skip upload enabled)"
echo ""

# Step 1: Build production images locally
echo "[1/5] Building production Docker images..."

if [[ "$BUILD_WEB" == "true" ]]; then
  echo "  Building web (Next.js production)..."
  docker build --no-cache -t ${REGISTRY_PREFIX}-web:prod -f web/Dockerfile.prod ./web
fi

if [[ "$BUILD_MASTER" == "true" ]]; then
  echo "  Building master-api (FastAPI production)..."
  docker build --no-cache -t ${REGISTRY_PREFIX}-master-api:prod -f master/Dockerfile.prod ./master
fi

if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  echo "  Building playground (stealth/compiled)..."
  docker build --no-cache -t ${REGISTRY_PREFIX}-playground:prod -f ./playground/Dockerfile.stealth ./playground
fi

echo ""
echo "[2/5] Saving Docker images to tar files..."
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
echo "[3/5] Copying files to VM..."

# Create remote directory structure
ssh ${VM_USER}@${VM_HOST} "mkdir -p ${REMOTE_DIR}/{dist}"

# Copy only the images that were built
if [[ "$BUILD_WEB" == "true" ]]; then
  scp ./dist/ainotebook-web.tar.gz ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/dist/
fi
if [[ "$BUILD_MASTER" == "true" ]]; then
  scp ./dist/ainotebook-master-api.tar.gz ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/dist/
fi
if [[ "$BUILD_PLAYGROUND" == "true" ]]; then
  scp ./dist/ainotebook-playground.tar.gz ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/dist/
fi

echo ""
echo "[4/5] Loading Docker images on VM..."

ssh ${VM_USER}@${VM_HOST} << REMOTE_SCRIPT
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
echo "  Loaded images:"
docker images | grep ainotebook
REMOTE_SCRIPT

echo ""
echo "[5/5] Deployment ready!"
echo ""
