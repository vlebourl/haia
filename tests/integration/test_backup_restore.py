"""Integration tests for Neo4j backup and restore functionality.

Tests the backup.sh and restore.sh scripts to verify data persistence
and recovery capabilities.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest


class TestNeo4jBackupRestore:
    """Integration tests for backup and restore operations."""

    @pytest.fixture(scope="class")
    def neo4j_password(self):
        """Get Neo4j password from environment."""
        password = os.getenv("NEO4J_PASSWORD", "haia_neo4j_secure_2024")
        return password

    @pytest.fixture(scope="class")
    def project_root(self):
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_backup_script_exists(self, project_root):
        """Verify backup script exists and is executable (T064)."""
        backup_script = project_root / "database" / "backups" / "backup.sh"
        assert backup_script.exists(), "backup.sh not found"
        assert os.access(backup_script, os.X_OK), "backup.sh is not executable"

    def test_restore_script_exists(self, project_root):
        """Verify restore script exists and is executable (T064)."""
        restore_script = project_root / "database" / "backups" / "restore.sh"
        assert restore_script.exists(), "restore.sh not found"
        assert os.access(restore_script, os.X_OK), "restore.sh is not executable"

    def test_backup_creation(self, project_root, neo4j_password):
        """Test creating a backup with backup.sh (T064)."""
        backup_script = project_root / "database" / "backups" / "backup.sh"

        # Run backup script
        result = subprocess.run(
            [str(backup_script)],
            capture_output=True,
            text=True,
            env={**os.environ, "NEO4J_PASSWORD": neo4j_password},
        )

        # Check script succeeded
        assert result.returncode == 0, f"Backup script failed: {result.stderr}"
        assert "Backup Complete" in result.stdout, "Backup completion message not found"
        assert "✓" in result.stdout, "No success indicators in output"

    def test_backup_file_created(self, neo4j_password):
        """Verify backup file was created in container (T064)."""
        # List backup files in container
        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                "ls -1 /backups/haia_backup_*.dump 2>/dev/null | wc -l",
            ],
            capture_output=True,
            text=True,
        )

        backup_count = int(result.stdout.strip())
        assert backup_count > 0, "No backup files found in container"

    def test_backup_file_not_empty(self, neo4j_password):
        """Verify backup file has non-zero size (T064)."""
        # Get latest backup file
        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                "ls -t /backups/haia_backup_*.dump 2>/dev/null | head -1",
            ],
            capture_output=True,
            text=True,
        )

        latest_backup = result.stdout.strip()
        assert latest_backup, "No backup file found"

        # Check file size
        size_result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "stat",
                "-c",
                "%s",
                latest_backup,
            ],
            capture_output=True,
            text=True,
        )

        file_size = int(size_result.stdout.strip())
        assert file_size > 0, f"Backup file is empty: {latest_backup}"
        assert file_size > 1024, f"Backup file seems too small ({file_size} bytes)"

    def test_backup_rotation(self, project_root, neo4j_password):
        """Test backup rotation (old backups are cleaned up) (T064)."""
        # Create a fake old backup file
        old_backup_name = "haia_backup_neo4j_20200101_000000.dump"
        create_old = f"touch /backups/{old_backup_name}"

        subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                create_old,
            ],
            check=True,
        )

        # Make it appear old (8 days ago)
        make_old = f"touch -d '8 days ago' /backups/{old_backup_name}"
        subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                make_old,
            ],
            check=True,
        )

        # Run backup (should trigger rotation)
        backup_script = project_root / "database" / "backups" / "backup.sh"
        subprocess.run(
            [str(backup_script)],
            capture_output=True,
            text=True,
            env={**os.environ, "NEO4J_PASSWORD": neo4j_password},
        )

        # Check if old backup was deleted
        check_exists = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                f"[ -f /backups/{old_backup_name} ] && echo 'exists' || echo 'deleted'",
            ],
            capture_output=True,
            text=True,
        )

        assert "deleted" in check_exists.stdout, "Old backup was not rotated/deleted"

    def test_restore_with_data_preservation(self, project_root, neo4j_password):
        """Test full restore workflow with data verification (T065)."""
        # Step 1: Create test data
        test_id = "test_restore_person_001"
        create_query = f"""
        CREATE (p:Person {{
            user_id: '{test_id}',
            name: 'Restore Test Person',
            created_at: datetime()
        }})
        RETURN p.user_id AS id
        """

        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to create test data: {result.stderr}"

        # Step 2: Create backup
        backup_script = project_root / "database" / "backups" / "backup.sh"
        backup_result = subprocess.run(
            [str(backup_script)],
            capture_output=True,
            text=True,
            env={**os.environ, "NEO4J_PASSWORD": neo4j_password},
        )

        assert backup_result.returncode == 0, "Backup creation failed"

        # Get backup filename
        get_backup = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                "ls -t /backups/haia_backup_*.dump | head -1 | xargs basename",
            ],
            capture_output=True,
            text=True,
        )

        backup_file = get_backup.stdout.strip()
        assert backup_file, "Could not find backup file"

        # Step 3: Delete test data
        delete_query = f"MATCH (p:Person {{user_id: '{test_id}'}}) DELETE p"
        subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                delete_query,
            ],
            check=True,
        )

        # Verify deletion
        check_query = f"MATCH (p:Person {{user_id: '{test_id}'}}) RETURN count(p) AS count"
        check_result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                check_query,
            ],
            capture_output=True,
            text=True,
        )

        assert "0" in check_result.stdout, "Test data was not deleted"

        # Step 4: Restore from backup (non-interactive)
        restore_script = project_root / "database" / "backups" / "restore.sh"
        restore_result = subprocess.run(
            [str(restore_script), backup_file],
            input="yes\n",  # Auto-confirm
            capture_output=True,
            text=True,
            env={**os.environ, "NEO4J_PASSWORD": neo4j_password},
        )

        # The restore might fail due to interactive prompt issues,
        # so we'll verify by checking if data was restored
        time.sleep(5)  # Wait for Neo4j to stabilize

        # Step 5: Verify data was restored
        verify_query = f"MATCH (p:Person {{user_id: '{test_id}'}}) RETURN p.name AS name"
        verify_result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                verify_query,
            ],
            capture_output=True,
            text=True,
        )

        assert verify_result.returncode == 0, "Query after restore failed"
        assert "Restore Test Person" in verify_result.stdout, "Data was not restored from backup"

        # Cleanup
        subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                delete_query,
            ],
        )

    def test_multiple_backups_maintained(self, project_root, neo4j_password):
        """Test that multiple recent backups are maintained (T064)."""
        backup_script = project_root / "database" / "backups" / "backup.sh"

        # Create 3 backups with small delays
        for i in range(3):
            subprocess.run(
                [str(backup_script)],
                capture_output=True,
                env={**os.environ, "NEO4J_PASSWORD": neo4j_password},
            )
            time.sleep(2)  # Small delay to ensure different timestamps

        # Check how many backups exist
        count_result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "sh",
                "-c",
                "ls -1 /backups/haia_backup_*.dump 2>/dev/null | wc -l",
            ],
            capture_output=True,
            text=True,
        )

        backup_count = int(count_result.stdout.strip())
        assert backup_count >= 3, f"Expected at least 3 backups, found {backup_count}"

    def test_backup_README_exists(self, project_root):
        """Verify backup documentation exists (T062, T063)."""
        readme = project_root / "database" / "backups" / "README.md"
        assert readme.exists(), "Backup README.md not found"

        # Check for key documentation sections
        content = readme.read_text()
        assert "Backup Schedule" in content or "backup schedule" in content.lower()
        assert "Recovery" in content or "restore" in content.lower()
        assert "cron" in content.lower() or "automated" in content.lower()
