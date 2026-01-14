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
    N8nVolume,
    PostgresDatabase,
    SQLiteDatabase,
    ValkeyArchitectureTypes,
    ValkeyConfig,
    ValkeyReplicationArchitecture,
    ValkeyStandaloneArchitecture,
    WebhookConfig,
    WorkerConfig,
)
from apolo_apps_n8n.inputs_processor import N8nAppChartValueProcessor

from apolo_app_types.protocols.common import ApoloFilesPath, AutoscalingHPA, Preset
from apolo_app_types.protocols.common.ingress import BasicNetworkingConfig
from apolo_app_types.protocols.common.secrets_ import ApoloSecret
from apolo_app_types.protocols.postgres import CrunchyPostgresUserCredentials


@pytest.fixture
def basic_n8n_inputs():
    """Create basic N8nAppInputs for testing with SQLite database."""
    return N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"), persistence=None
        ),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
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
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password=ApoloSecret(key="testpass"),
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    dbname="testdb",
                    pgbouncer_uri=ApoloSecret(
                        key="postgresql://testuser:testpass@pgbouncer.example.com:6432/testdb"
                    ),
                ),
            )
        ),
    )


async def test_n8n_values_generation_with_sqlite(
    apolo_client, mock_get_preset_cpu, basic_n8n_inputs
):
    """Test N8n values generation with SQLite database configuration."""
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
    assert "valkey" in helm_params
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

    # Verify valkey configuration (standalone mode)
    valkey_config = helm_params["valkey"]
    assert valkey_config["enabled"] is True
    assert valkey_config["architecture"] == "standalone"
    assert "primary" in valkey_config
    assert "resources" in valkey_config["primary"]
    assert "tolerations" in valkey_config["primary"]
    assert "affinity" in valkey_config["primary"]


async def test_n8n_values_generation_with_postgres(
    apolo_client, mock_get_preset_cpu, postgres_n8n_inputs
):
    """Test N8n values generation with PostgreSQL database configuration."""
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
    assert pg_config["host"] == "pgbouncer.example.com"
    assert pg_config["port"] == 6432
    assert pg_config["database"] == "testdb"


async def test_database_config_without_pgbouncer_uri(apolo_client, mock_get_preset_cpu):
    """Test that error is raised when pgbouncer_uri is None."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Create inputs with missing pgbouncer_uri
    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password=ApoloSecret(key="testpass"),
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
    apolo_client, mock_get_preset_cpu
):
    """Test that error is raised when pgbouncer_uri is an empty string."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Create inputs with empty pgbouncer_uri
    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password=ApoloSecret(key="testpass"),
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    pgbouncer_uri=ApoloSecret(key=""),  # Empty string
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


async def test_valkey_replication_without_autoscaling(
    apolo_client, mock_get_preset_cpu
):
    """Test Valkey replication mode without autoscaling."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyReplicationArchitecture(
                architecture_type=ValkeyArchitectureTypes.REPLICATION,
                replica_preset=Preset(name="cpu-small"),
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=SQLiteDatabase(database_type=DBTypes.SQLITE)
        ),
    )

    helm_params = await input_processor.gen_extra_values(
        input_=inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify valkey replication configuration
    valkey_config = helm_params["valkey"]
    assert valkey_config["enabled"] is True
    assert valkey_config["architecture"] == "replication"
    assert "primary" in valkey_config
    assert "replica" in valkey_config

    # Verify primary configuration
    assert "resources" in valkey_config["primary"]
    assert "tolerations" in valkey_config["primary"]
    assert "affinity" in valkey_config["primary"]

    # Verify replica configuration
    assert "resources" in valkey_config["replica"]
    assert "tolerations" in valkey_config["replica"]
    assert "affinity" in valkey_config["replica"]

    # Verify autoscaling is not present when not configured
    assert "autoscaling" not in valkey_config["replica"]


async def test_valkey_replication_with_autoscaling(apolo_client, mock_get_preset_cpu):
    """Test Valkey replication mode with autoscaling enabled."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(preset=Preset(name="cpu-small")),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyReplicationArchitecture(
                architecture_type=ValkeyArchitectureTypes.REPLICATION,
                replica_preset=Preset(name="cpu-small"),
                autoscaling=AutoscalingHPA(
                    min_replicas=2,
                    max_replicas=10,
                    target_cpu_utilization_percentage=70,
                    target_memory_utilization_percentage=80,
                ),
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=SQLiteDatabase(database_type=DBTypes.SQLITE)
        ),
    )

    helm_params = await input_processor.gen_extra_values(
        input_=inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify valkey replication configuration with autoscaling
    valkey_config = helm_params["valkey"]
    assert valkey_config["enabled"] is True
    assert valkey_config["architecture"] == "replication"

    # Verify autoscaling configuration
    assert "autoscaling" in valkey_config["replica"]
    hpa_config = valkey_config["replica"]["autoscaling"]["hpa"]
    assert hpa_config["enabled"] is True
    assert hpa_config["minReplicas"] == 2
    assert hpa_config["maxReplicas"] == 10
    assert hpa_config["targetCPU"] == 70
    assert hpa_config["targetMemory"] == 80


async def test_persistence_none_with_sqlite(apolo_client, mock_get_preset_cpu):
    """Test N8n values generation with persistence=None and SQLite database."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"), persistence=None
        ),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=SQLiteDatabase(database_type=DBTypes.SQLITE)
        ),
    )

    helm_params = await input_processor.gen_extra_values(
        input_=inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify basic structure exists
    assert "main" in helm_params
    assert "config" in helm_params["main"]


async def test_persistence_none_with_postgres(apolo_client, mock_get_preset_cpu):
    """Test N8n values generation with persistence=None and PostgreSQL database."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"), persistence=None
        ),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password=ApoloSecret(key="testpass"),
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    dbname="testdb",
                    pgbouncer_uri=ApoloSecret(
                        key="postgresql://testuser:testpass@pgbouncer.example.com:6432/testdb"
                    ),
                ),
            )
        ),
    )

    helm_params = await input_processor.gen_extra_values(
        input_=inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify PostgreSQL configuration
    db_config = helm_params["main"]["config"]["db"]
    assert db_config["type"] == "postgresdb"


async def test_custom_persistence_path_with_sqlite(apolo_client, mock_get_preset_cpu):
    """Test N8n values generation with custom persistence path and SQLite."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    custom_path = "storage://test-cluster/custom/n8n/data"
    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"),
            persistence=N8nVolume(storage_mount=ApoloFilesPath(path=custom_path)),
        ),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=SQLiteDatabase(database_type=DBTypes.SQLITE)
        ),
    )

    helm_params = await input_processor.gen_extra_values(
        input_=inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify basic structure exists
    assert "main" in helm_params
    assert "config" in helm_params["main"]
    assert "db" in helm_params["main"]["config"]
    assert helm_params["main"]["config"]["db"]["type"] == "sqlite"


async def test_custom_persistence_path_with_postgres(apolo_client, mock_get_preset_cpu):
    """Test N8n values generation with custom persistence path and PostgreSQL."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    custom_path = "storage://test-cluster/custom/n8n/data"
    inputs = N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"),
            persistence=N8nVolume(storage_mount=ApoloFilesPath(path=custom_path)),
        ),
        worker_config=WorkerConfig(preset=Preset(name="cpu-small"), replicas=2),
        webhook_config=WebhookConfig(preset=Preset(name="cpu-small"), replicas=1),
        valkey_config=ValkeyConfig(
            preset=Preset(name="cpu-small"),
            architecture=ValkeyStandaloneArchitecture(
                architecture_type=ValkeyArchitectureTypes.STANDALONE
            ),
        ),
        networking=BasicNetworkingConfig(),
        database_config=DataBaseConfig(
            database=PostgresDatabase(
                database_type=DBTypes.POSTGRES,
                credentials=CrunchyPostgresUserCredentials(
                    user="testuser",
                    password=ApoloSecret(key="testpass"),
                    host="postgres.example.com",
                    port=5432,
                    pgbouncer_host="pgbouncer.example.com",
                    pgbouncer_port=6432,
                    dbname="testdb",
                    pgbouncer_uri=ApoloSecret(
                        key="postgresql://testuser:testpass@pgbouncer.example.com:6432/testdb"
                    ),
                ),
            )
        ),
    )

    helm_params = await input_processor.gen_extra_values(
        input_=inputs,
        app_name="n8n-app",
        namespace=DEFAULT_NAMESPACE,
        app_secrets_name=APP_SECRETS_NAME,
        app_id=APP_ID,
    )

    # Verify PostgreSQL configuration
    db_config = helm_params["main"]["config"]["db"]
    assert db_config["type"] == "postgresdb"
    assert "postgresdb" in db_config
