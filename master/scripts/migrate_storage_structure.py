#!/usr/bin/env python3
"""
Migration script to update storage structure.

This script:
1. Adds storage_month column to projects table
2. Updates existing projects with storage_month derived from created_at
3. Moves existing MinIO files to the new folder structure:
   - Old: projects/{project_id}/... and {user_id}/{project_id}/chat_history.json
   - New: {mm-yyyy}/{project_id}/... and {mm-yyyy}/{project_id}/chats/default.json

Usage:
    python scripts/migrate_storage_structure.py

Make sure to:
1. Stop the master-api service before running
2. Backup your database and MinIO data
3. Run this script
4. Start the master-api service
"""

import asyncio
import os
import sys
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+aiomysql://ainotebook:ainotebook123@localhost:3306/ainotebook")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin123")
S3_BUCKET = os.getenv("S3_BUCKET_NOTEBOOKS", "notebooks")


def get_s3_client():
    """Create S3/MinIO client."""
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )


def format_storage_month(dt: datetime) -> str:
    """Format datetime as mm-yyyy."""
    return dt.strftime("%m-%Y")


async def migrate_database():
    """Add storage_month column and update existing projects."""
    print("\n=== Database Migration ===")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if column exists
        try:
            result = await session.execute(text(
                "SELECT storage_month FROM projects LIMIT 1"
            ))
            print("  Column 'storage_month' already exists")
        except Exception:
            # Add the column
            print("  Adding 'storage_month' column to projects table...")
            await session.execute(text(
                "ALTER TABLE projects ADD COLUMN storage_month VARCHAR(7) NULL"
            ))
            await session.commit()
            print("  Column added successfully")

        # Update existing projects with storage_month
        print("  Updating existing projects with storage_month...")
        result = await session.execute(text(
            "SELECT id, created_at FROM projects WHERE storage_month IS NULL"
        ))
        projects = result.fetchall()

        updated_count = 0
        for project_id, created_at in projects:
            storage_month = format_storage_month(created_at)
            await session.execute(text(
                "UPDATE projects SET storage_month = :storage_month WHERE id = :project_id"
            ), {"storage_month": storage_month, "project_id": project_id})
            updated_count += 1

        await session.commit()
        print(f"  Updated {updated_count} projects with storage_month")

        # Make column NOT NULL
        try:
            await session.execute(text(
                "ALTER TABLE projects MODIFY COLUMN storage_month VARCHAR(7) NOT NULL"
            ))
            await session.commit()
            print("  Made storage_month column NOT NULL")
        except Exception as e:
            print(f"  Warning: Could not make column NOT NULL: {e}")

        # Get all projects for MinIO migration
        result = await session.execute(text(
            "SELECT id, user_id, storage_month FROM projects"
        ))
        projects_data = result.fetchall()

    await engine.dispose()
    return projects_data


def migrate_minio_files(projects_data):
    """Move MinIO files to new folder structure."""
    print("\n=== MinIO Migration ===")

    s3 = get_s3_client()

    # Ensure bucket exists
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except ClientError:
        print(f"  Error: Bucket '{S3_BUCKET}' does not exist")
        return

    migrated_notebooks = 0
    migrated_chats = 0
    errors = []

    for project_id, user_id, storage_month in projects_data:
        print(f"\n  Project: {project_id}")
        print(f"    User: {user_id}")
        print(f"    Storage month: {storage_month}")

        # === Migrate notebook files ===
        old_notebook_prefix = f"projects/{project_id}/"
        new_notebook_prefix = f"{storage_month}/{project_id}/"

        try:
            # List objects in old location
            response = s3.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=old_notebook_prefix,
            )

            for obj in response.get("Contents", []):
                old_key = obj["Key"]
                new_key = old_key.replace(old_notebook_prefix, new_notebook_prefix)

                # Skip if already in new location
                if old_key == new_key:
                    continue

                # Copy to new location
                print(f"    Moving: {old_key} -> {new_key}")
                try:
                    s3.copy_object(
                        Bucket=S3_BUCKET,
                        CopySource={"Bucket": S3_BUCKET, "Key": old_key},
                        Key=new_key,
                    )
                    # Delete old object
                    s3.delete_object(Bucket=S3_BUCKET, Key=old_key)
                    migrated_notebooks += 1
                except ClientError as e:
                    errors.append(f"Failed to migrate {old_key}: {e}")

        except ClientError as e:
            errors.append(f"Failed to list objects for project {project_id}: {e}")

        # === Migrate chat history ===
        old_chat_key = f"{user_id}/{project_id}/chat_history.json"
        new_chat_key = f"{storage_month}/{project_id}/chats/default.json"

        try:
            # Check if old chat file exists
            response = s3.get_object(Bucket=S3_BUCKET, Key=old_chat_key)
            old_chat_data = json.loads(response["Body"].read().decode("utf-8"))

            # Convert to new format
            messages = old_chat_data.get("messages", [])
            new_chat_data = {
                "chat_id": "default",
                "name": "Main Chat",
                "project_id": project_id,
                "created": old_chat_data.get("created", datetime.now().isoformat()),
                "updated": old_chat_data.get("updated", datetime.now().isoformat()),
                "messages": messages,
            }

            # Save in new location
            print(f"    Moving chat: {old_chat_key} -> {new_chat_key}")
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=new_chat_key,
                Body=json.dumps(new_chat_data, indent=2, ensure_ascii=False),
                ContentType="application/json",
            )

            # Create chat index
            index_key = f"{storage_month}/{project_id}/chats/index.json"
            index_data = {
                "chats": [
                    {
                        "id": "default",
                        "name": "Main Chat",
                        "created": new_chat_data["created"],
                        "updated": new_chat_data["updated"],
                    }
                ]
            }
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=index_key,
                Body=json.dumps(index_data, indent=2),
                ContentType="application/json",
            )

            # Delete old chat file
            s3.delete_object(Bucket=S3_BUCKET, Key=old_chat_key)
            migrated_chats += 1

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                print(f"    No chat history found at {old_chat_key}")
            else:
                errors.append(f"Failed to migrate chat for project {project_id}: {e}")

    print(f"\n  Migrated {migrated_notebooks} notebook files")
    print(f"  Migrated {migrated_chats} chat histories")

    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for error in errors:
            print(f"    - {error}")


def cleanup_empty_folders():
    """Remove empty 'projects/' folder structure."""
    print("\n=== Cleanup ===")

    s3 = get_s3_client()

    # List remaining objects in projects/ folder
    try:
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix="projects/",
        )

        remaining = response.get("Contents", [])
        if remaining:
            print(f"  Warning: {len(remaining)} objects still in 'projects/' folder:")
            for obj in remaining[:10]:  # Show first 10
                print(f"    - {obj['Key']}")
            if len(remaining) > 10:
                print(f"    ... and {len(remaining) - 10} more")
        else:
            print("  Old 'projects/' folder is empty (or doesn't exist)")

    except ClientError as e:
        print(f"  Error checking projects folder: {e}")

    # Check for user folders
    try:
        # This is a bit tricky since user IDs are UUIDs
        # We'll just report what's there
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Delimiter="/",
        )

        prefixes = [p.get("Prefix", "") for p in response.get("CommonPrefixes", [])]

        # Filter out month folders (mm-yyyy format)
        non_month_folders = [p for p in prefixes if not p.rstrip("/").count("-") == 1 or len(p.rstrip("/")) != 7]

        if non_month_folders:
            print(f"  Non-month folders found (may be old user folders):")
            for folder in non_month_folders[:10]:
                print(f"    - {folder}")

    except ClientError as e:
        print(f"  Error listing bucket contents: {e}")


async def main():
    print("=" * 60)
    print("Storage Structure Migration")
    print("=" * 60)
    print(f"\nDatabase: {DATABASE_URL}")
    print(f"MinIO: {S3_ENDPOINT}")
    print(f"Bucket: {S3_BUCKET}")

    # Confirm
    response = input("\nProceed with migration? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled.")
        return

    # Step 1: Database migration
    projects_data = await migrate_database()

    # Step 2: MinIO migration
    migrate_minio_files(projects_data)

    # Step 3: Cleanup
    cleanup_empty_folders()

    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify the data in MinIO console")
    print("2. Restart the master-api service")
    print("3. Test notebook and chat functionality")


if __name__ == "__main__":
    asyncio.run(main())
