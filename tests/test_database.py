# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for database configuration and connection management."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pydantic import ValidationError

from app.core.config import Settings
from app.services.db.connection import get_db_engine, test_connection, close_db_engine


class TestDatabaseConfiguration:
    """Test cases for database settings validation."""

    def test_database_url_provided_directly(self):
        """Test that providing DATABASE_URL directly works."""
        settings = Settings(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb"
        )
        assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

    def test_database_url_constructed_from_individual_settings(self):
        """Test that DATABASE_URL is constructed from individual settings."""
        settings = Settings(
            database_user="testuser",
            database_password="testpass",
            database_host="dbhost",
            database_port=5433,
            database_name="mydb"
        )
        expected_url = "postgresql+asyncpg://testuser:testpass@dbhost:5433/mydb"
        assert settings.database_url == expected_url

    def test_database_url_validation_requires_postgresql_prefix(self):
        """Test that database_url must start with postgresql://."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(database_url="mysql://user:pass@localhost/db")
        
        assert "must start with 'postgresql://'" in str(exc_info.value)

    def test_database_user_required_when_constructing_url(self):
        """Test that database_user is required when DATABASE_URL not provided."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_password="pass",
                database_host="localhost"
            )
        
        assert "database_user is required" in str(exc_info.value)

    def test_database_password_required_when_constructing_url(self):
        """Test that database_password is required when DATABASE_URL not provided."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_user="user",
                database_host="localhost"
            )
        
        assert "database_password is required" in str(exc_info.value)

    def test_empty_database_user_rejected(self):
        """Test that empty or whitespace-only database_user is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_user="   ",
                database_password="pass"
            )
        
        assert "database_user is required" in str(exc_info.value)

    def test_empty_database_password_rejected(self):
        """Test that empty or whitespace-only database_password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_user="user",
                database_password="   "
            )
        
        assert "database_password is required" in str(exc_info.value)

    def test_database_port_validation_range(self):
        """Test that database_port must be in valid range."""
        # Valid port
        settings = Settings(
            database_user="user",
            database_password="pass",
            database_port=8080
        )
        assert settings.database_port == 8080

        # Port too low (0)
        with pytest.raises(ValidationError):
            Settings(
                database_user="user",
                database_password="pass",
                database_port=0
            )

        # Port too high
        with pytest.raises(ValidationError):
            Settings(
                database_user="user",
                database_password="pass",
                database_port=70000
            )

    def test_database_url_takes_precedence_over_individual_settings(self):
        """Test that DATABASE_URL overrides individual settings."""
        settings = Settings(
            database_url="postgresql+asyncpg://urluser:urlpass@urlhost:1234/urldb",
            database_user="ignored",
            database_password="ignored",
            database_host="ignored"
        )
        assert settings.database_url == "postgresql+asyncpg://urluser:urlpass@urlhost:1234/urldb"

    def test_default_database_settings(self):
        """Test default values for database settings."""
        settings = Settings(
            database_user="user",
            database_password="pass"
        )
        assert settings.database_host == "localhost"
        assert settings.database_port == 5432
        assert settings.database_name == "software_planner"


class TestDatabaseConnection:
    """Test cases for database connection management."""

    def test_get_db_engine_creates_engine(self):
        """Test that get_db_engine creates an engine."""
        # Reset global engine state
        import app.services.db.connection as conn_module
        conn_module._engine = None
        
        engine = get_db_engine(
            database_url="postgresql+asyncpg://test:test@localhost:5432/testdb"
        )
        
        assert engine is not None
        assert str(engine.url).startswith("postgresql+asyncpg://")

    def test_get_db_engine_returns_singleton(self):
        """Test that get_db_engine returns the same instance."""
        import app.services.db.connection as conn_module
        conn_module._engine = None
        
        engine1 = get_db_engine(
            database_url="postgresql+asyncpg://test:test@localhost:5432/testdb"
        )
        engine2 = get_db_engine()
        
        assert engine1 is engine2

    def test_get_db_engine_raises_without_url(self):
        """Test that get_db_engine raises error without URL."""
        import app.services.db.connection as conn_module
        conn_module._engine = None
        
        # Mock settings to have no database_url
        with patch('app.services.db.connection.settings') as mock_settings:
            mock_settings.database_url = None
            
            with pytest.raises(ValueError) as exc_info:
                get_db_engine()
            
            assert "Database URL is not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test that test_connection returns True on success."""
        import app.services.db.connection as conn_module
        conn_module._engine = None
        
        # Mock successful connection
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone = AsyncMock(return_value=(1,))
        mock_conn.execute = AsyncMock(return_value=mock_result)
        mock_engine.connect = MagicMock(return_value=mock_conn)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.services.db.connection.get_db_engine', return_value=mock_engine):
            result = await test_connection()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test that test_connection returns False on failure."""
        import app.services.db.connection as conn_module
        conn_module._engine = None
        
        # Mock failed connection
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(side_effect=Exception("Connection refused"))
        
        with patch('app.services.db.connection.get_db_engine', return_value=mock_engine):
            result = await test_connection()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_close_db_engine(self):
        """Test that close_db_engine disposes the engine."""
        import app.services.db.connection as conn_module
        
        # Create a mock engine
        mock_engine = AsyncMock()
        conn_module._engine = mock_engine
        
        await close_db_engine()
        
        mock_engine.dispose.assert_called_once()
        assert conn_module._engine is None
