import enum
from typing import Literal

from pydantic import ConfigDict, Field

from apolo_app_types.protocols.common import (
    AbstractAppFieldType,
    AppInputs,
    AppOutputs,
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


class WorkerConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Worker Configuration", description=""
        ).as_json_schema_extra(),
    )
    preset: Preset
    replicas: int = Field()


class WebhookConfig(AbstractAppFieldType):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra=SchemaExtraMetadata(
            title="Webhook Configuration", description=""
        ).as_json_schema_extra(),
    )
    preset: Preset
    replicas: int = Field()


class N8nAppInputs(AppInputs):
    main_app_config: MainApplicationConfig
    worker_config: WorkerConfig
    webhook_config: WebhookConfig
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
