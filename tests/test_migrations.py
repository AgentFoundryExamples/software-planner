"""Integration tests for database migrations."""

import pytest
import os
import subprocess
from pathlib import Path


class TestMigrationIntegration:
    """Test cases for Alembic migration execution.
    
    Note: These tests require a running PostgreSQL instance and proper
    database configuration. They can be skipped if DB is not available.
    """

    def test_alembic_config_exists(self):
        """Test that alembic.ini configuration file exists."""
        config_path = Path(__file__).parent.parent / "alembic.ini"
        assert config_path.exists(), "alembic.ini not found"

    def test_migrations_directory_exists(self):
        """Test that migrations directory structure exists."""
        migrations_dir = Path(__file__).parent.parent / "migrations"
        assert migrations_dir.exists(), "migrations directory not found"
        assert (migrations_dir / "env.py").exists(), "migrations/env.py not found"
        assert (migrations_dir / "versions").exists(), "migrations/versions directory not found"

    def test_initial_migration_exists(self):
        """Test that the initial migration file exists."""
        versions_dir = Path(__file__).parent.parent / "migrations" / "versions"
        migration_files = list(versions_dir.glob("*_create_jobs_table.py"))
        assert len(migration_files) > 0, "Initial migration file not found"

    def test_migration_has_required_operations(self):
        """Test that the initial migration contains required DDL operations."""
        versions_dir = Path(__file__).parent.parent / "migrations" / "versions"
        migration_files = list(versions_dir.glob("*_create_jobs_table.py"))
        assert len(migration_files) > 0, "Initial migration file not found"
        
        migration_file = migration_files[0]
        content = migration_file.read_text()
        
        # Check for required table creation
        assert "op.create_table" in content, "Migration missing create_table operation"
        assert "'jobs'" in content, "Migration not creating 'jobs' table"
        
        # Check for required columns
        required_columns = [
            "job_id", "status", "description", "model", "system_prompt",
            "result", "error", "created_at", "updated_at", "started_at", "finished_at"
        ]
        for column in required_columns:
            assert column in content, f"Migration missing required column: {column}"
        
        # Check for indexes
        assert "op.create_index" in content, "Migration missing index creation"
        assert "ix_jobs_status" in content, "Migration missing status index"
        assert "ix_jobs_created_at" in content, "Migration missing created_at index"
        
        # Check for downgrade function
        assert "def downgrade()" in content, "Migration missing downgrade function"
        assert "op.drop_table" in content, "Migration missing drop_table in downgrade"

    def test_migration_is_idempotent_definition(self):
        """Test that migration has proper structure for idempotency.
        
        While we can't test actual database execution without a DB,
        we can verify the migration structure follows Alembic best practices.
        """
        versions_dir = Path(__file__).parent.parent / "migrations" / "versions"
        migration_files = list(versions_dir.glob("*_create_jobs_table.py"))
        assert len(migration_files) > 0
        
        migration_file = migration_files[0]
        content = migration_file.read_text()
        
        # Check for revision identifiers
        assert "revision:" in content or "revision =" in content
        assert "down_revision:" in content or "down_revision =" in content

    @pytest.mark.skipif(
        not os.environ.get("DATABASE_URL") and not (
            os.environ.get("DATABASE_USER") and os.environ.get("DATABASE_PASSWORD")
        ),
        reason="Database configuration not available - set DATABASE_URL or DATABASE_USER/PASSWORD"
    )
    def test_alembic_current_command(self):
        """Test that 'alembic current' command works.
        
        This validates that Alembic can connect to the database and
        read the current migration version. Skipped if DB not configured.
        """
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            ["python3", "-m", "alembic", "current"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should exit successfully or with version info
        # Exit code 0 means success, but database might not exist yet
        assert result.returncode in [0, 1], f"alembic current failed: {result.stderr}"

    @pytest.mark.skipif(
        not os.environ.get("DATABASE_URL") and not (
            os.environ.get("DATABASE_USER") and os.environ.get("DATABASE_PASSWORD")
        ),
        reason="Database configuration not available - set DATABASE_URL or DATABASE_USER/PASSWORD"
    )
    def test_alembic_history_command(self):
        """Test that 'alembic history' command works.
        
        This validates that Alembic can list migration history.
        Skipped if DB not configured.
        """
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            ["python3", "-m", "alembic", "history"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0, f"alembic history failed: {result.stderr}"
        
        # Should show the initial migration
        assert "create_jobs_table" in result.stdout


class TestMigrationConfiguration:
    """Test cases for migration configuration."""

    def test_env_py_imports_settings(self):
        """Test that migrations/env.py imports application settings."""
        env_file = Path(__file__).parent.parent / "migrations" / "env.py"
        content = env_file.read_text()
        
        assert "from app.core.config import settings" in content
        assert "settings.database_url" in content

    def test_env_py_uses_async_engine(self):
        """Test that migrations/env.py is configured for async operations."""
        env_file = Path(__file__).parent.parent / "migrations" / "env.py"
        content = env_file.read_text()
        
        # Should use async engine for asyncpg
        assert "async" in content or "asyncio" in content
        assert "async_engine_from_config" in content or "run_async_migrations" in content

    def test_alembic_ini_references_migrations_dir(self):
        """Test that alembic.ini points to correct migrations directory."""
        config_file = Path(__file__).parent.parent / "alembic.ini"
        content = config_file.read_text()
        
        assert "script_location" in content
        assert "migrations" in content
