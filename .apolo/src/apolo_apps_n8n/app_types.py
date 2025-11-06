import enum
from typing import Literal

from pydantic import ConfigDict, Field

from apolo_app_types.protocols.common import (
    AbstractAppFieldType,
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
            description="Use a local SQLite database for OpenWebUI.",
        ).as_json_schema_extra(),
    )
    # No additional fields needed for local SQLite database
    database_type: Literal[DBTypes.SQLITE] = Field(default=DBTypes.SQLITE)


class PostgresDatabase(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Postgres Database",
            description="Use a Postgres database for OpenWebUI.",
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
            description="Configure the database for OpenWebUI.",
        ).as_json_schema_extra(),
    )
    database: SQLiteDatabase | PostgresDatabase = Field(
        default_factory=lambda: SQLiteDatabase(),
        json_schema_extra=SchemaExtraMetadata(
            title="Database Configuration",
            description="Configure the database for OpenWebUI. "
            "Choose between local SQLite or Postgres.",
        ).as_json_schema_extra(),
    )


class MainApplicationConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Main Application Configuration", description=""
        ).as_json_schema_extra(),
    )
    preset: Preset
    autoscaling: AutoscalingHPA | None = Field(
        default=None,
        json_schema_extra=SchemaExtraMetadata(
            title="Autoscaling",
            description="Enable Autoscaling and configure it.",
            is_advanced_field=True,
        ).as_json_schema_extra(),
    )


class WorkerConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Worker Configuration", description=""
        ).as_json_schema_extra(),
    )
    preset: Preset
    replicas: int = Field()
    autoscaling: AutoscalingHPA | None = Field(
        default=None,
        json_schema_extra=SchemaExtraMetadata(
            title="Autoscaling",
            description="Enable Autoscaling and configure it.",
            is_advanced_field=True,
        ).as_json_schema_extra(),
    )


class WebhookConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Webhook Configuration", description=""
        ).as_json_schema_extra(),
    )
    preset: Preset
    replicas: int = Field()
    autoscaling: AutoscalingHPA | None = Field(
        default=None,
        json_schema_extra=SchemaExtraMetadata(
            title="Autoscaling",
            description="Enable Autoscaling and configure it.",
            is_advanced_field=True,
        ).as_json_schema_extra(),
    )


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
        json_schema_extra=SchemaExtraMetadata(title="Replica Preset", description=""),
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
