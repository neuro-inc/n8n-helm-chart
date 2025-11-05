import pytest
from apolo_app_types_fixtures.constants import (
    APP_ID,
    APP_SECRETS_NAME,
    DEFAULT_NAMESPACE,
)
from apolo_apps_n8n.app_types import (
    DataBaseConfig,
    DBTypes,
    MainApplicationConfig,
    N8nAppInputs,
    PostgresDatabase,
    SQLiteDatabase,
    WebhookConfig,
    WorkerConfig,
)
from apolo_apps_n8n.inputs_processor import N8nAppChartValueProcessor

from apolo_app_types.protocols.common import Preset
from apolo_app_types.protocols.common.ingress import BasicNetworkingConfig
from apolo_app_types.protocols.postgres import CrunchyPostgresUserCredentials


@pytest.fixture
def basic_n8n_inputs():
    """Create basic N8nAppInputs for testing with SQLite database."""
    return N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=SQLiteDatabase(database_type=DBTypes.SQLITE)
        ),
    )


@pytest.fixture
def postgres_n8n_inputs():
    """Create N8nAppInputs for testing with PostgreSQL database."""
    return N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password="testpass",
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    pgbouncer_uri="postgresql://testuser:testpass@pgbouncer.example.com:6432/testdb",
                ),
            )
        ),
    )


async def test_n8n_values_generation_with_sqlite(
    setup_clients, mock_get_preset_cpu, basic_n8n_inputs
):
    """Test N8n values generation with SQLite database configuration."""
    apolo_client = setup_clients
    input_processor = N8nAppChartValueProcessor(client=apolo_client)
    helm_params = await input_processor.gen_extra_values(
        input_=basic_n8n_inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify top-level structure
    assert "apolo_app_id" in helm_params
    assert "ingress" in helm_params
    assert "main" in helm_params
    assert "worker" in helm_params
    assert "webhook" in helm_params
    assert "labels" in helm_params

    # Verify labels
    assert helm_params["labels"] == {"application": "n8n"}

    # Verify main application configuration
    main_config = helm_params["main"]
    assert "resources" in main_config
    assert "tolerations" in main_config
    assert "affinity" in main_config
    assert "podLabels" in main_config
    assert "config" in main_config
    assert "service" in main_config

    # Verify service labels
    assert main_config["service"] == {"labels": {"service": "main"}}

    # Verify SQLite database configuration
    db_config = main_config["config"]["db"]
    assert db_config["type"] == "sqlite"
    assert "sqlite" in db_config
    assert db_config["sqlite"]["pool_size"] == 1
    assert db_config["sqlite"]["vacuum_on_startup"] is True

    # Verify worker configuration
    worker_config = helm_params["worker"]
    assert "service" in worker_config
    assert worker_config["service"]["labels"] == {"service": "worker"}
    assert "resources" in worker_config
    assert "tolerations" in worker_config
    assert "affinity" in worker_config

    # Verify webhook configuration
    webhook_config = helm_params["webhook"]
    assert "service" in webhook_config
    assert webhook_config["service"]["labels"] == {"service": "webhook"}
    assert "resources" in webhook_config
    assert "tolerations" in webhook_config
    assert "affinity" in webhook_config


async def test_n8n_values_generation_with_postgres(
    setup_clients, mock_get_preset_cpu, postgres_n8n_inputs
):
    """Test N8n values generation with PostgreSQL database configuration."""
    apolo_client = setup_clients
    input_processor = N8nAppChartValueProcessor(client=apolo_client)
    helm_params = await input_processor.gen_extra_values(
        input_=postgres_n8n_inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify PostgreSQL database configuration
    db_config = helm_params["main"]["config"]["db"]
    assert db_config["type"] == "postgresdb"
    assert "postgresdb" in db_config

    # Verify parsed PostgreSQL connection details
    pg_config = db_config["postgresdb"]
    assert pg_config["user"] == "testuser"
    assert pg_config["password"] == "testpass"
    assert pg_config["host"] == "pgbouncer.example.com"
    assert pg_config["port"] == 6432
    assert pg_config["database"] == "testdb"


async def test_database_config_without_pgbouncer_uri(
    setup_clients, mock_get_preset_cpu
):
    """Test that error is raised when pgbouncer_uri is None."""
    apolo_client = setup_clients
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Create inputs with missing pgbouncer_uri
    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password="testpass",
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    pgbouncer_uri=None,  # Explicitly set to None
                ),
            )
        ),
    )

    # This should raise a ValueError because pgbouncer_uri is required
    with pytest.raises(
        ValueError,
        match="PostgreSQL database configuration requires a valid pgbouncer_uri",
    ):
        await input_processor.gen_extra_values(
            input_=inputs,
            app_name="n8n-app",
            namespace=DEFAULT_NAMESPACE,
            app_secrets_name=APP_SECRETS_NAME,
            app_id=APP_ID,
        )


async def test_database_config_with_empty_pgbouncer_uri(
    setup_clients, mock_get_preset_cpu
):
    """Test that error is raised when pgbouncer_uri is an empty string."""
    apolo_client = setup_clients
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Create inputs with empty pgbouncer_uri
    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password="testpass",
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    pgbouncer_uri="",  # Empty string
                ),
            )
        ),
    )

    # This should raise a ValueError because pgbouncer_uri cannot be empty
    with pytest.raises(
        ValueError,
        match="PostgreSQL database configuration requires a valid pgbouncer_uri",
    ):
        await input_processor.gen_extra_values(
            input_=inputs,
            app_name="n8n-app",
            namespace=DEFAULT_NAMESPACE,
            app_secrets_name=APP_SECRETS_NAME,
            app_id=APP_ID,
        )
