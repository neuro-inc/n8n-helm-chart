import enum
from typing import Literal

from pydantic import ConfigDict, Field

from apolo_app_types.helm.utils.storage import get_app_data_files_relative_path_url
from apolo_app_types.protocols.common import (
    AbstractAppFieldType,
    ApoloFilesPath,
    AppInputs,
    AppOutputs,
    AutoscalingHPA,
    Preset,
    SchemaExtraMetadata,
)
from apolo_app_types.protocols.common.ingress import BasicNetworkingConfig
from apolo_app_types.protocols.postgres import (
    CrunchyPostgresUserCredentials,
)


class DBTypes(enum.StrEnum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class SQLiteDatabase(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="SQLite Database",
            description="Use a local SQLite database for n8n.",
        ).as_json_schema_extra(),
    )
    # No additional fields needed for local SQLite database
    database_type: Literal[DBTypes.SQLITE] = Field(default=DBTypes.SQLITE)


class PostgresDatabase(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Postgres Database",
            description="Use a Postgres database for n8n.",
        ).as_json_schema_extra(),
    )
    # Use Crunchy Postgres credentials for the database
    database_type: Literal[DBTypes.POSTGRES] = Field(default=DBTypes.POSTGRES)
    credentials: CrunchyPostgresUserCredentials


class DataBaseConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Database Configuration",
            description="Configure the database for n8n.",
        ).as_json_schema_extra(),
    )
    database: SQLiteDatabase | PostgresDatabase = Field(
        default_factory=lambda: SQLiteDatabase(),
        json_schema_extra=SchemaExtraMetadata(
            title="Database Configuration",
            description="Configure the database for n8n. "
            "Choose between local SQLite or Postgres.",
        ).as_json_schema_extra(),
    )


class ReplicaCount(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Fixed Replica Count",
            description="This option create a fixed number of replicas "
            "with no autoscaling enabled.",
        ).as_json_schema_extra(),
    )
    replicas: int = Field(
        default=1,
        json_schema_extra=SchemaExtraMetadata(
            title="Replica Count",
            description="Number of replicas created for main application.",
        ).as_json_schema_extra(),
    )


class N8nVolume(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Persistent Storage",
            description=(
                "Configure persistent storage for the n8n data directory. "
                "With SQLite, this stores all data including workflows and "
                "credentials. With PostgreSQL, workflows and credentials are "
                "stored in the database, while this volume stores encryption "
                "keys, instance logs, and source control assets."
            ),
        ).as_json_schema_extra(),
    )
    storage_mount: ApoloFilesPath = Field(
        default=ApoloFilesPath(
            path=str(
                get_app_data_files_relative_path_url(
                    app_type_name="n8n", app_name="n8n-app"
                )
            )
        ),
        json_schema_extra=SchemaExtraMetadata(
            title="Storage Mount Path",
            description=(
                "Select a platform storage path to mount for the n8n data "
                "directory. This is required for both SQLite and PostgreSQL "
                "deployments to persist critical data."
            ),
        ).as_json_schema_extra(),
    )


class MainApplicationConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Main Application Configuration",
            description="Configure the primary n8n service that handles core "
            "workflow automation functionality, processes workflows, and "
            "manages the user interface.",
        ).as_json_schema_extra(),
    )
    preset: Preset
    replica_scaling: ReplicaCount | AutoscalingHPA = Field(
        default=ReplicaCount(replicas=1),
        json_schema_extra=SchemaExtraMetadata(
            title="Replicas",
            description="Choose a fixed number of replicas or " "enable autoscaling.",
        ).as_json_schema_extra(),
    )
    persistence: N8nVolume | None = Field(default=N8nVolume())


class WorkerConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Worker Configuration",
            description="Configure workers for distributed background job "
            "processing. Workers handle workflow execution tasks, enabling "
            "the main application to remain responsive by offloading "
            "computational work.",
        ).as_json_schema_extra(),
    )
    preset: Preset
    replicas: int = Field()


class WebhookConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Webhook Configuration",
            description="Configure dedicated webhook processing instances. "
            "Separating webhook handling allows dedicated resource allocation "
            "for webhook traffic without competing with core workflow execution.",
        ).as_json_schema_extra(),
    )
    preset: Preset
    replicas: int = Field()


class ValkeyArchitectureTypes(enum.StrEnum):
    STANDALONE = "standalone"
    REPLICATION = "replication"


class ValkeyArchitecture(AbstractAppFieldType):
    pass


class ValkeyStandaloneArchitecture(ValkeyArchitecture):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Standalone Mode",
            description="""This mode wiill deploy a standalone
                    Valkey StatefulSet. A single service will be exposed""",
        ).as_json_schema_extra(),
    )
    architecture_type: Literal[ValkeyArchitectureTypes.STANDALONE]


class ValkeyReplicationArchitecture(ValkeyArchitecture):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Replication Mode",
            description="""This mode will deploy a Valkey
                    primary StatefulSet and a Valkey replicas StatefulSet.
                    The replicas will be read-replicas of the primary and
                    two services will be exposed""",
        ).as_json_schema_extra(),
    )
    architecture_type: Literal[ValkeyArchitectureTypes.REPLICATION]
    replica_preset: Preset = Field(
        ...,
        json_schema_extra=SchemaExtraMetadata(
            title="Replica Preset", description=""
        ).as_json_schema_extra(),
    )
    autoscaling: AutoscalingHPA | None = Field(
        default=None,
        json_schema_extra=SchemaExtraMetadata(
            title="Autoscaling",
            description="Enable Autoscaling and configure it.",
            is_advanced_field=True,
        ).as_json_schema_extra(),
    )


ValkeyArchs = ValkeyStandaloneArchitecture | ValkeyReplicationArchitecture


class ValkeyConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Valkey/Redis Configuration", description=""
        ).as_json_schema_extra(),
    )
    preset: Preset
    architecture: ValkeyArchs


class N8nAppInputs(AppInputs):
    main_app_config: MainApplicationConfig
    worker_config: WorkerConfig
    webhook_config: WebhookConfig
    valkey_config: ValkeyConfig
    networking: BasicNetworkingConfig = Field(
        default_factory=BasicNetworkingConfig,
        json_schema_extra=SchemaExtraMetadata(
            title="Networking Settings",
            description="Configure network access, HTTP authentication,"
            " and related connectivity options.",
        ).as_json_schema_extra(),
    )
    database_config: DataBaseConfig


class N8nAppOutputs(AppOutputs):
    pass
