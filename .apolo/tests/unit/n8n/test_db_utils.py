"""Tests for database utility functions."""

from apolo_apps_n8n.db_utils import parse_postgres_connection_string


class TestParsePostgresConnectionString:
    """Test the parse_postgres_connection_string function."""

    def test_basic_connection_string(self):
        """Test parsing a basic PostgreSQL connection string."""
        connection_string = "postgresql://myuser:mypass@localhost:5432/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result == {
            "user": "myuser",
            "password": "mypass",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
        }

    def test_connection_string_with_special_chars_in_password(self):
        """Test parsing connection string with URL-encoded special
        characters in password."""
        # Password with @ and % characters that need URL encoding
        connection_string = (
            "postgresql://user:p%40ssw%25rd@host.example.com:5432/dbname"
        )
        result = parse_postgres_connection_string(connection_string)

        assert result == {
            "user": "user",
            "password": "p@ssw%rd",  # Should be decoded
            "host": "host.example.com",
            "port": 5432,
            "database": "dbname",
        }

    def test_connection_string_without_port(self):
        """Test parsing connection string without explicit port
        (should default to 5432)."""
        connection_string = "postgresql://user:pass@localhost/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result == {
            "user": "user",
            "password": "pass",
            "host": "localhost",
            "port": 5432,  # Default port
            "database": "mydb",
        }

    def test_connection_string_with_custom_port(self):
        """Test parsing connection string with custom port."""
        connection_string = "postgresql://user:pass@localhost:9876/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result["port"] == 9876

    def test_connection_string_with_ip_address(self):
        """Test parsing connection string with IP address as host."""
        connection_string = "postgresql://user:pass@192.168.1.100:5432/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result["host"] == "192.168.1.100"

    def test_connection_string_with_domain(self):
        """Test parsing connection string with domain name."""
        connection_string = "postgresql://user:pass@db.example.com:5432/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result["host"] == "db.example.com"

    def test_connection_string_with_empty_database(self):
        """Test parsing connection string with empty database name."""
        connection_string = "postgresql://user:pass@localhost:5432"
        result = parse_postgres_connection_string(connection_string)

        assert result["database"] == ""

    def test_connection_string_complex_password(self):
        """Test parsing connection string with complex encoded password."""
        # Password: "p@ssw0rd!#$" encoded
        connection_string = (
            "postgresql://admin:p%40ssw0rd%21%23%24@prod-db.example.com:5432/production"
        )
        result = parse_postgres_connection_string(connection_string)

        assert result == {
            "user": "admin",
            "password": "p@ssw0rd!#$",
            "host": "prod-db.example.com",
            "port": 5432,
            "database": "production",
        }

    def test_connection_string_with_postgres_scheme(self):
        """Test parsing connection string with 'postgres' scheme (alternative)."""
        connection_string = "postgres://user:pass@localhost:5432/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result == {
            "user": "user",
            "password": "pass",
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
        }

    def test_connection_string_minimal(self):
        """Test parsing minimal connection string with defaults."""
        connection_string = "postgresql://localhost/mydb"
        result = parse_postgres_connection_string(connection_string)

        assert result["user"] == ""
        assert result["password"] == ""
        assert result["host"] == "localhost"
        assert result["port"] == 5432
        assert result["database"] == "mydb"
