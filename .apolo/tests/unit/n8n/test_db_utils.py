"""Tests for database utility functions."""

from apolo_apps_n8n.db_utils import parse_postgres_connection_string

from apolo_app_types.protocols.common.secrets_ import ApoloSecret
from apolo_app_types.protocols.postgres import CrunchyPostgresUserCredentials


class TestParsePostgresConnectionString:
    """Test the parse_postgres_connection_string function."""

    def test_basic_connection_string(self):
        """Test parsing a basic PostgreSQL connection string."""
        credentials = CrunchyPostgresUserCredentials(
            user="myuser",
            password=ApoloSecret(key="password-secret"),
            host="localhost",
            port=5432,
            pgbouncer_host="localhost",
            pgbouncer_port=5432,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result == {
            "user": "myuser",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
        }

    def test_connection_string_with_special_chars_in_password(self):
        """Test parsing connection string with URL-encoded special
        characters in password."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="host.example.com",
            port=5432,
            pgbouncer_host="host.example.com",
            pgbouncer_port=5432,
            dbname="dbname",
        )
        result = parse_postgres_connection_string(credentials)

        assert result == {
            "user": "user",
            "host": "host.example.com",
            "port": 5432,
            "database": "dbname",
        }

    def test_connection_string_without_port(self):
        """Test parsing connection string without explicit port
        (should default to 5432)."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="localhost",
            port=5432,
            pgbouncer_host="localhost",
            pgbouncer_port=5432,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result == {
            "user": "user",
            "host": "localhost",
            "port": 5432,  # Default port
            "database": "mydb",
        }

    def test_connection_string_with_custom_port(self):
        """Test parsing connection string with custom port."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="localhost",
            port=9876,
            pgbouncer_host="localhost",
            pgbouncer_port=9876,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result["port"] == 9876

    def test_connection_string_with_ip_address(self):
        """Test parsing connection string with IP address as host."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="192.168.1.100",
            port=5432,
            pgbouncer_host="192.168.1.100",
            pgbouncer_port=5432,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result["host"] == "192.168.1.100"

    def test_connection_string_with_domain(self):
        """Test parsing connection string with domain name."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="db.example.com",
            port=5432,
            pgbouncer_host="db.example.com",
            pgbouncer_port=5432,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result["host"] == "db.example.com"

    def test_connection_string_with_empty_database(self):
        """Test parsing connection string with empty database name."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="localhost",
            port=5432,
            pgbouncer_host="localhost",
            pgbouncer_port=5432,
            dbname=None,
        )
        result = parse_postgres_connection_string(credentials)

        assert result["database"] == ""

    def test_connection_string_complex_password(self):
        """Test parsing connection string with complex encoded password."""
        credentials = CrunchyPostgresUserCredentials(
            user="admin",
            password=ApoloSecret(key="password-secret"),
            host="prod-db.example.com",
            port=5432,
            pgbouncer_host="prod-db.example.com",
            pgbouncer_port=5432,
            dbname="production",
        )
        result = parse_postgres_connection_string(credentials)

        assert result == {
            "user": "admin",
            "host": "prod-db.example.com",
            "port": 5432,
            "database": "production",
        }

    def test_connection_string_with_postgres_scheme(self):
        """Test parsing connection string with 'postgres' scheme (alternative)."""
        credentials = CrunchyPostgresUserCredentials(
            user="user",
            password=ApoloSecret(key="password-secret"),
            host="localhost",
            port=5432,
            pgbouncer_host="localhost",
            pgbouncer_port=5432,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result == {
            "user": "user",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
        }

    def test_connection_string_minimal(self):
        """Test parsing minimal connection string with defaults."""
        credentials = CrunchyPostgresUserCredentials(
            user="",
            password=ApoloSecret(key="password-secret"),
            host="localhost",
            port=5432,
            pgbouncer_host="localhost",
            pgbouncer_port=5432,
            dbname="mydb",
        )
        result = parse_postgres_connection_string(credentials)

        assert result["user"] == ""
        assert result["host"] == "localhost"
        assert result["port"] == 5432
        assert result["database"] == "mydb"
