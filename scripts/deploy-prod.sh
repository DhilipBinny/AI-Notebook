#!/bin/bash
# AI Notebook - Production Deployment Script
#
# This script builds Docker images and deploys to the production VM
#
# Usage:
#   ./scripts/deploy-prod.sh [VM_HOST] [VM_USER]
#
# Example:
#   ./scripts/deploy-prod.sh 10.0.2.21 binny

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Change to project root
cd "${PROJECT_ROOT}"
echo "Working directory: ${PROJECT_ROOT}"

# Configuration
VM_HOST="${1:-10.0.2.21}"
VM_USER="${2:-sysadmin}"
REMOTE_DIR="/home/${VM_USER}/ai-jupyter"

REGISTRY_PREFIX="ainotebook"

echo "=============================================="
echo "  AI Notebook - Production Deployment"
echo "=============================================="
echo "Target VM: ${VM_USER}@${VM_HOST}"
echo "Remote Dir: ${REMOTE_DIR}"
echo ""

# Step 1: Build production images locally
echo "[1/5] Building production Docker images..."

echo "  Building web (Next.js production)..."
docker build -t ${REGISTRY_PREFIX}-web:latest -f web/Dockerfile.prod ./web

echo "  Building master-api (FastAPI production)..."
docker build -t ${REGISTRY_PREFIX}-master-api:latest -f master/Dockerfile.prod ./master

echo "  Building playground..."
docker build -t ${REGISTRY_PREFIX}-playground:latest ./playground

echo ""
echo "[2/5] Saving Docker images to tar files..."
mkdir -p ./dist

docker save ${REGISTRY_PREFIX}-web:latest | gzip > ./dist/ainotebook-web.tar.gz
docker save ${REGISTRY_PREFIX}-master-api:latest | gzip > ./dist/ainotebook-master-api.tar.gz
docker save ${REGISTRY_PREFIX}-playground:latest | gzip > ./dist/ainotebook-playground.tar.gz

echo "  Images saved to ./dist/"
ls -lh ./dist/*.tar.gz

echo ""
echo "[3/5] Copying files to VM..."

# Create remote directory structure
ssh ${VM_USER}@${VM_HOST} "mkdir -p ${REMOTE_DIR}/{nginx,dist}"

# Copy image tarballs
scp ./dist/*.tar.gz ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/dist/

# Copy configuration files
scp docker-compose.prod.yml ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/
scp nginx/nginx.prod.conf ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/nginx/

# Copy env template if not exists
scp -n .env.prod.example ${VM_USER}@${VM_HOST}:${REMOTE_DIR}/.env 2>/dev/null || true

echo ""
echo "[4/5] Loading Docker images on VM..."

ssh ${VM_USER}@${VM_HOST} << REMOTE_SCRIPT
cd ${REMOTE_DIR}

echo "  Loading ainotebook-web..."
gunzip -c dist/ainotebook-web.tar.gz | docker load

echo "  Loading ainotebook-master-api..."
gunzip -c dist/ainotebook-master-api.tar.gz | docker load

echo "  Loading ainotebook-playground..."
gunzip -c dist/ainotebook-playground.tar.gz | docker load

echo ""
echo "  Loaded images:"
docker images | grep ainotebook
REMOTE_SCRIPT

echo ""
echo "[5/5] Deployment ready!"
echo ""
echo "=============================================="
echo "  Next Steps on VM (${VM_HOST}):"
echo "=============================================="
echo ""
echo "  1. SSH to VM:"
echo "     ssh ${VM_USER}@${VM_HOST}"
echo ""
echo "  2. Configure environment:"
echo "     cd ${REMOTE_DIR}"
echo "     cp .env.example .env"
echo "     nano .env  # Edit with your production values"
echo ""
echo "  3. Create LLM env file:"
echo "     nano llm.env  # Add GEMINI_API_KEY, OPENAI_API_KEY, etc."
echo ""
echo "  4. Ensure network exists:"
echo "     docker network create ainotebook-network 2>/dev/null || true"
echo ""
echo "  5. Start services:"
echo "     docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "  6. Check status:"
echo "     docker compose -f docker-compose.prod.yml ps"
echo "     docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "=============================================="
