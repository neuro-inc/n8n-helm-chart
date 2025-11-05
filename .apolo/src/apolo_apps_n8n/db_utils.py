"""Database utility functions."""

from urllib.parse import unquote, urlparse


def parse_postgres_connection_string(connection_string: str) -> dict[str, str | int]:
    """
    Parse a PostgreSQL connection string and extract its components.

    Args:
        connection_string: PostgreSQL connection string in URI format
                          (e.g., "postgresql://user:password@host:port/database")

    Returns:
        Dictionary containing:
            - user: Database username
            - password: Database password (URL-decoded)
            - host: Database host
            - port: Database port (int, defaults to 5432 if not specified)
            - database: Database name/database

    Example:
        >>> parse_postgres_connection_string(
        ...     "postgresql://myuser:mypass@localhost:5432/mydb"
        ... )
        {
            'user': 'myuser',
            'password': 'mypass',
            'host': 'localhost',
            'port': 5432,
            'database': 'mydb'
        }
    """
    parsed = urlparse(connection_string)

    # Extract components
    user = parsed.username or ""
    password = unquote(parsed.password) if parsed.password else ""
    host = parsed.hostname or ""
    port = parsed.port or 5432
    database = parsed.path.lstrip("/") if parsed.path else ""

    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database,
    }
