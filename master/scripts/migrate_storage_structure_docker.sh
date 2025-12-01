#!/bin/bash
# Migration script to run inside Docker containers
#
# This script:
# 1. Adds storage_month column to projects table
# 2. Updates existing projects with storage_month derived from created_at
# 3. Moves existing MinIO files to the new folder structure
#
# Usage:
#   chmod +x scripts/migrate_storage_structure_docker.sh
#   ./scripts/migrate_storage_structure_docker.sh

set -e

echo "============================================================"
echo "Storage Structure Migration"
echo "============================================================"

# MySQL settings
MYSQL_HOST="ainotebook-mysql"
MYSQL_USER="root"
MYSQL_PASS="ainotebook_dev_password"
MYSQL_DB="ainotebook"

# MinIO settings
MINIO_ALIAS="local"

echo ""
echo "=== Step 1: Database Migration ==="

# Check if storage_month column exists
COLUMN_EXISTS=$(docker exec ainotebook-mysql mysql -u${MYSQL_USER} -p${MYSQL_PASS} -N -e \
  "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='${MYSQL_DB}' AND table_name='projects' AND column_name='storage_month';" 2>/dev/null)

if [ "$COLUMN_EXISTS" -eq "0" ]; then
    echo "  Adding 'storage_month' column to projects table..."
    docker exec ainotebook-mysql mysql -u${MYSQL_USER} -p${MYSQL_PASS} -e \
      "ALTER TABLE ${MYSQL_DB}.projects ADD COLUMN storage_month VARCHAR(7) NULL;" 2>/dev/null
    echo "  Column added."
else
    echo "  Column 'storage_month' already exists."
fi

# Update existing projects with storage_month
echo "  Updating existing projects with storage_month..."
docker exec ainotebook-mysql mysql -u${MYSQL_USER} -p${MYSQL_PASS} -e \
  "UPDATE ${MYSQL_DB}.projects SET storage_month = DATE_FORMAT(created_at, '%m-%Y') WHERE storage_month IS NULL;" 2>/dev/null

# Make column NOT NULL (might fail if there are still NULLs)
echo "  Making storage_month NOT NULL..."
docker exec ainotebook-mysql mysql -u${MYSQL_USER} -p${MYSQL_PASS} -e \
  "ALTER TABLE ${MYSQL_DB}.projects MODIFY COLUMN storage_month VARCHAR(7) NOT NULL;" 2>/dev/null || echo "  Warning: Could not make NOT NULL (may have NULL values)"

# Get project data for MinIO migration
echo "  Getting project data..."
PROJECTS=$(docker exec ainotebook-mysql mysql -u${MYSQL_USER} -p${MYSQL_PASS} -N -e \
  "SELECT CONCAT(id, '|', user_id, '|', storage_month) FROM ${MYSQL_DB}.projects;" 2>/dev/null)

echo "  Found $(echo "$PROJECTS" | wc -l) projects."

echo ""
echo "=== Step 2: MinIO Migration ==="

# Setup MinIO client alias inside container
docker exec ainotebook-minio mc alias set ${MINIO_ALIAS} http://localhost:9000 minioadmin minioadmin123 2>/dev/null

MIGRATED_NOTEBOOKS=0
MIGRATED_CHATS=0

while IFS='|' read -r PROJECT_ID USER_ID STORAGE_MONTH; do
    [ -z "$PROJECT_ID" ] && continue

    echo ""
    echo "  Project: $PROJECT_ID"
    echo "    User: $USER_ID"
    echo "    Storage month: $STORAGE_MONTH"

    # === Migrate notebook files ===
    OLD_PREFIX="projects/${PROJECT_ID}/"
    NEW_PREFIX="${STORAGE_MONTH}/${PROJECT_ID}/"

    # Check if old location has files
    OLD_FILES=$(docker exec ainotebook-minio mc ls ${MINIO_ALIAS}/notebooks/${OLD_PREFIX} 2>/dev/null | wc -l)

    if [ "$OLD_FILES" -gt "0" ]; then
        echo "    Moving $OLD_FILES notebook files..."

        # Copy all files to new location
        docker exec ainotebook-minio mc cp --recursive \
          ${MINIO_ALIAS}/notebooks/${OLD_PREFIX} \
          ${MINIO_ALIAS}/notebooks/${NEW_PREFIX} 2>/dev/null || true

        # Remove old files
        docker exec ainotebook-minio mc rm --recursive --force \
          ${MINIO_ALIAS}/notebooks/${OLD_PREFIX} 2>/dev/null || true

        MIGRATED_NOTEBOOKS=$((MIGRATED_NOTEBOOKS + OLD_FILES))
    else
        echo "    No notebook files at old location."
    fi

    # === Migrate chat history ===
    OLD_CHAT="${USER_ID}/${PROJECT_ID}/chat_history.json"
    NEW_CHAT="${STORAGE_MONTH}/${PROJECT_ID}/chats/default.json"

    # Check if old chat file exists
    if docker exec ainotebook-minio mc stat ${MINIO_ALIAS}/notebooks/${OLD_CHAT} 2>/dev/null >/dev/null; then
        echo "    Moving chat history..."

        # Download old chat
        OLD_CHAT_DATA=$(docker exec ainotebook-minio mc cat ${MINIO_ALIAS}/notebooks/${OLD_CHAT} 2>/dev/null)

        # Extract messages and create new format
        MESSAGES=$(echo "$OLD_CHAT_DATA" | python3 -c "
import sys, json
data = json.load(sys.stdin)
messages = data.get('messages', [])
new_data = {
    'chat_id': 'default',
    'name': 'Main Chat',
    'project_id': '${PROJECT_ID}',
    'created': data.get('created', ''),
    'updated': data.get('updated', ''),
    'messages': messages
}
print(json.dumps(new_data, indent=2))
" 2>/dev/null) || MESSAGES=""

        if [ -n "$MESSAGES" ]; then
            # Save new chat file
            echo "$MESSAGES" | docker exec -i ainotebook-minio mc pipe ${MINIO_ALIAS}/notebooks/${NEW_CHAT} 2>/dev/null

            # Create index file
            INDEX_DATA="{\"chats\": [{\"id\": \"default\", \"name\": \"Main Chat\", \"created\": \"\", \"updated\": \"\"}]}"
            echo "$INDEX_DATA" | docker exec -i ainotebook-minio mc pipe ${MINIO_ALIAS}/notebooks/${STORAGE_MONTH}/${PROJECT_ID}/chats/index.json 2>/dev/null

            # Remove old chat file
            docker exec ainotebook-minio mc rm ${MINIO_ALIAS}/notebooks/${OLD_CHAT} 2>/dev/null || true

            MIGRATED_CHATS=$((MIGRATED_CHATS + 1))
            echo "    Chat migrated."
        else
            echo "    Warning: Could not parse chat data."
        fi
    else
        echo "    No chat history at old location."
    fi

done <<< "$PROJECTS"

echo ""
echo "=== Step 3: Cleanup ==="

# Check remaining files in old locations
REMAINING=$(docker exec ainotebook-minio mc ls ${MINIO_ALIAS}/notebooks/projects/ 2>/dev/null | wc -l || echo "0")
echo "  Remaining files in 'projects/' folder: $REMAINING"

echo ""
echo "============================================================"
echo "Migration Complete!"
echo "============================================================"
echo ""
echo "Summary:"
echo "  - Migrated notebook files: $MIGRATED_NOTEBOOKS"
echo "  - Migrated chat histories: $MIGRATED_CHATS"
echo ""
echo "Next steps:"
echo "  1. Rebuild the master-api container: docker-compose -f docker-compose.apps.yml up -d --build master-api"
echo "  2. Test notebook and chat functionality"
