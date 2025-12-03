#!/usr/bin/env python3
"""
Database volume management helper for Task Assist.

This script helps manage the database volume for local Docker/Podman deployments.
"""

import subprocess
import sys
import os
from pathlib import Path


VOLUME_NAME = "task-manager-db"
CONTAINER_DATA_PATH = "/app/data"
DB_FILENAME = "task_manager.db"


def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        return None


def volume_exists():
    """Check if the volume exists."""
    result = run_command(f"docker volume ls -q -f name={VOLUME_NAME}")
    return result and VOLUME_NAME in result.stdout


def create_volume():
    """Create the persistent volume."""
    if volume_exists():
        print(f"✓ Volume '{VOLUME_NAME}' already exists")
        return True
    
    print(f"Creating volume '{VOLUME_NAME}'...")
    result = run_command(f"docker volume create {VOLUME_NAME}")
    if result and result.returncode == 0:
        print(f"✓ Volume '{VOLUME_NAME}' created successfully")
        return True
    else:
        print(f"✗ Failed to create volume")
        return False


def inspect_volume():
    """Show volume details."""
    if not volume_exists():
        print(f"✗ Volume '{VOLUME_NAME}' does not exist")
        return
    
    print(f"\nVolume details for '{VOLUME_NAME}':")
    run_command(f"docker volume inspect {VOLUME_NAME}", capture_output=False)


def backup_database(backup_path=None):
    """Backup database from volume to local file."""
    if not volume_exists():
        print(f"✗ Volume '{VOLUME_NAME}' does not exist")
        return False
    
    if backup_path is None:
        backup_path = f"./backup_{DB_FILENAME}"
    
    backup_path = Path(backup_path).resolve()
    
    print(f"Backing up database to {backup_path}...")
    
    cmd = (
        f"docker run --rm "
        f"-v {VOLUME_NAME}:{CONTAINER_DATA_PATH} "
        f"-v {backup_path.parent}:/backup "
        f"alpine cp {CONTAINER_DATA_PATH}/{DB_FILENAME} /backup/{backup_path.name}"
    )
    
    result = run_command(cmd)
    if result and result.returncode == 0:
        print(f"✓ Database backed up to {backup_path}")
        return True
    else:
        print(f"✗ Failed to backup database")
        return False


def restore_database(backup_path):
    """Restore database from local file to volume."""
    if not volume_exists():
        print(f"Creating volume '{VOLUME_NAME}'...")
        if not create_volume():
            return False
    
    backup_path = Path(backup_path).resolve()
    
    if not backup_path.exists():
        print(f"✗ Backup file not found: {backup_path}")
        return False
    
    print(f"Restoring database from {backup_path}...")
    
    cmd = (
        f"docker run --rm "
        f"-v {VOLUME_NAME}:{CONTAINER_DATA_PATH} "
        f"-v {backup_path.parent}:/backup "
        f"alpine cp /backup/{backup_path.name} {CONTAINER_DATA_PATH}/{DB_FILENAME}"
    )
    
    result = run_command(cmd)
    if result and result.returncode == 0:
        print(f"✓ Database restored from {backup_path}")
        return True
    else:
        print(f"✗ Failed to restore database")
        return False


def list_database_files():
    """List files in the database volume."""
    if not volume_exists():
        print(f"✗ Volume '{VOLUME_NAME}' does not exist")
        return
    
    print(f"\nFiles in volume '{VOLUME_NAME}':")
    cmd = (
        f"docker run --rm "
        f"-v {VOLUME_NAME}:{CONTAINER_DATA_PATH} "
        f"alpine ls -lh {CONTAINER_DATA_PATH}"
    )
    run_command(cmd, capture_output=False)


def delete_volume():
    """Delete the volume (WARNING: destroys all data)."""
    if not volume_exists():
        print(f"✗ Volume '{VOLUME_NAME}' does not exist")
        return
    
    print(f"\n⚠️  WARNING: This will delete all data in '{VOLUME_NAME}'")
    confirm = input("Type 'DELETE' to confirm: ")
    
    if confirm != "DELETE":
        print("Cancelled")
        return
    
    print(f"Deleting volume '{VOLUME_NAME}'...")
    result = run_command(f"docker volume rm {VOLUME_NAME}")
    if result and result.returncode == 0:
        print(f"✓ Volume '{VOLUME_NAME}' deleted")
    else:
        print(f"✗ Failed to delete volume")


def print_usage():
    """Print usage information."""
    print("""
Database Volume Manager for Task Assist

Usage:
    python scripts/manage_db_volume.py <command> [options]

Commands:
    create              Create the persistent volume
    inspect             Show volume details
    list                List files in the volume
    backup [path]       Backup database to local file (default: ./backup_task_manager.db)
    restore <path>      Restore database from local file
    delete              Delete the volume (WARNING: destroys data)

Examples:
    python scripts/manage_db_volume.py create
    python scripts/manage_db_volume.py backup ./my_backup.db
    python scripts/manage_db_volume.py restore ./my_backup.db
    python scripts/manage_db_volume.py list
    """)


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        create_volume()
    elif command == "inspect":
        inspect_volume()
    elif command == "list":
        list_database_files()
    elif command == "backup":
        backup_path = sys.argv[2] if len(sys.argv) > 2 else None
        backup_database(backup_path)
    elif command == "restore":
        if len(sys.argv) < 3:
            print("✗ Error: restore command requires a backup file path")
            print("Usage: python scripts/manage_db_volume.py restore <backup_file>")
            sys.exit(1)
        restore_database(sys.argv[2])
    elif command == "delete":
        delete_volume()
    else:
        print(f"✗ Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
