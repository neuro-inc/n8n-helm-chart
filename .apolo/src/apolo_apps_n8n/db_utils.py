"""Database utility functions."""

from apolo_app_types.protocols.postgres import CrunchyPostgresUserCredentials


def parse_postgres_connection_string(
    credentials: CrunchyPostgresUserCredentials,
) -> dict[str, str | int]:
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

    # Extract components

    return {
        "user": credentials.user,
        "host": credentials.pgbouncer_host,
        "port": credentials.pgbouncer_port or 5432,
        "database": credentials.dbname or "",
    }
