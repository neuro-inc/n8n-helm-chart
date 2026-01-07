import secrets
import typing as t

from apolo_sdk import Client

from apolo_app_types import ApoloFilesMount
from apolo_app_types.app_types import AppType
from apolo_app_types.helm.apps.base import BaseChartValueProcessor
from apolo_app_types.helm.apps.common import (
    append_apolo_storage_integration_annotations,
    gen_apolo_storage_integration_labels,
    gen_extra_values,
    get_component_values,
    get_preset,
)
from apolo_app_types.protocols.common import (
    AutoscalingHPA,
    Preset,
)
from apolo_app_types.protocols.common.secrets_ import serialize_optional_secret
from apolo_app_types.protocols.common.storage import (
    ApoloMountMode,
    ApoloMountModes,
    MountPath,
)
from apolo_apps_n8n.app_types import DBTypes, N8nAppInputs, ValkeyArchitectureTypes
from apolo_apps_n8n.db_utils import parse_postgres_connection_string


class N8nAppChartValueProcessor(BaseChartValueProcessor[N8nAppInputs]):
    _port: int = 5678

    def __init__(self, client: Client, *args: t.Any, **kwargs: t.Any):
        super().__init__(client, *args, **kwargs)

    def get_database_values(self, input_: N8nAppInputs) -> dict[str, t.Any]:
        db = input_.database_config.database
        if db.database_type == DBTypes.SQLITE:
            return {
                "type": "sqlite",
                "sqlite": {"pool_size": 1, "vacuum_on_startup": True},
            }
        if db.database_type == DBTypes.POSTGRES:
            if not db.credentials.pgbouncer_uri or not db.credentials.pgbouncer_uri.key:
                err = "PostgreSQL database configuration requires a valid pgbouncer_uri"
                raise ValueError(err)
            return {
                "type": "postgresdb",
                "postgresdb": parse_postgres_connection_string(db.credentials),
            }
        err = "Invalid database configuration"
        raise ValueError(err)

    def get_extra_env(
        self,
        input_: N8nAppInputs,
        app_secrets_name: str,
        app_id: str,
        webhook_url: str | None = None,
    ) -> dict[str, t.Any]:
        db = input_.database_config.database
        envs = {}
        if db.database_type == DBTypes.POSTGRES:
            envs["DB_POSTGRESDB_PASSWORD"] = serialize_optional_secret(
                value=db.credentials.password, secret_name=app_secrets_name
            )
        if webhook_url:
            envs["WEBHOOK_URL"] = {"value": webhook_url}
            envs["EXECUTIONS_MODE"] = {"value": "queue"}
            # must be in sync with fullnameOverride in valkey
            envs["QUEUE_BULL_REDIS_HOST"] = {"value": f"n8n-{app_id}-valkey-primary"}
            envs["QUEUE_BULL_REDIS_TLS"] = {"value": "false"}
        return envs

    async def preset_to_values(self, preset: Preset) -> dict[str, t.Any]:
        apolo_preset = get_preset(self.client, preset.name)
        values = t.cast(
            dict[str, t.Any], await get_component_values(apolo_preset, preset.name)
        )
        values["podLabels"] = values["labels"]
        values["deploymentLabels"] = values["labels"]
        return values

    async def get_worker_values(self, input_: N8nAppInputs) -> dict[str, t.Any]:
        config = input_.worker_config
        return {
            "service": {
                "labels": {"service": "worker"},
            },
            "replicaCount": config.replicas,
            "enabled": config.replicas > 0,
            **(await self.preset_to_values(config.preset)),
        }

    async def get_webhook_values(self, input_: N8nAppInputs) -> dict[str, t.Any]:
        config = input_.webhook_config
        return {
            "service": {
                "labels": {"service": "webhook"},
            },
            "replicaCount": config.replicas,
            "enabled": config.replicas > 0,
            **(await self.preset_to_values(config.preset)),
        }

    def get_autoscaling_values(self, autoscaling: AutoscalingHPA) -> dict[str, t.Any]:
        return {
            "enabled": True,
            "minReplicas": autoscaling.min_replicas,
            "maxReplicas": autoscaling.max_replicas,
            "targetCPUUtilizationPercentage": (
                autoscaling.target_cpu_utilization_percentage
            ),
            "targetMemoryUtilizationPercentage": (
                autoscaling.target_memory_utilization_percentage
            ),
        }

    def is_webhook_enabled(self, input_: N8nAppInputs) -> bool:
        return input_.webhook_config.replicas > 0

    async def get_redis_values(
        self, input_: N8nAppInputs, app_id: str
    ) -> dict[str, t.Any]:
        config = input_.valkey_config
        values = {
            # due to https://github.com/kubernetes/kubernetes/issues/64023
            "fullnameOverride": f"n8n-{app_id}-valkey",
            "global": {"security": {"allowInsecureImages": True}},
            "image": {"repository": "bitnamilegacy/valkey"},
            "auth": {"enabled": False},
            "enabled": self.is_webhook_enabled(input_),
            "architecture": str(config.architecture.architecture_type.value),
            "primary": {
                **(await self.preset_to_values(config.preset)),
            },
        }

        if config.architecture.architecture_type == ValkeyArchitectureTypes.REPLICATION:
            replica_values = await self.preset_to_values(
                config.architecture.replica_preset
            )
            replica_config: dict[str, t.Any] = {**replica_values}

            if autoscaling := config.architecture.autoscaling:
                replica_config["autoscaling"] = {
                    "enabled": True,
                    "hpa": {
                        "enabled": True,
                        "minReplicas": autoscaling.min_replicas,
                        "maxReplicas": autoscaling.max_replicas,
                        # adding keys manually because they differ from main app
                        "targetCPU": (autoscaling.target_cpu_utilization_percentage),
                        "targetMemory": (
                            autoscaling.target_memory_utilization_percentage
                        ),
                    },
                }

            values["replica"] = replica_config
        return values

    async def gen_extra_values(
        self,
        input_: N8nAppInputs,
        app_name: str,
        namespace: str,
        app_id: str,
        app_secrets_name: str,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> dict[str, t.Any]:
        """
        Generate extra Helm values for Shell configuration.
        """

        # base_app_storage_path = get_app_data_files_path_url(
        #     client=self.client,
        #     app_type_name="n8n",
        #     app_name=app_name,
        # )
        # data_storage_path = base_app_storage_path
        # data_container_dir = URL("/home/node/.n8n")

        extra_values = await gen_extra_values(
            app_id=app_id,
            app_type=AppType.N8n,
            apolo_client=self.client,
            preset_type=input_.main_app_config.preset,
            namespace=namespace,
            ingress_http=input_.networking.ingress_http,
        )

        main_config = {
            "resources": extra_values["resources"],
            "tolerations": extra_values["tolerations"],
            "affinity": extra_values["affinity"],
            "podLabels": extra_values["podLabels"],
            "config": {
                "db": self.get_database_values(input_),
            },
            "secret": {"n8n": {"encryption_key": secrets.token_hex(32)}},
            "service": {"labels": {"service": "main"}},
        }
        if isinstance(input_.main_app_config.replica_scaling, AutoscalingHPA):
            main_config["autoscaling"] = self.get_autoscaling_values(
                input_.main_app_config.replica_scaling
            )
        else:
            main_config["replicaCount"] = (
                input_.main_app_config.replica_scaling.replicas
            )

        ingress = extra_values["ingress"]
        webhook_url = None
        for i, host in enumerate(ingress["hosts"]):
            paths = host["paths"]
            ingress["hosts"][i]["paths"] = [p["path"] for p in paths]
            if self.is_webhook_enabled(input_):
                webhook_url = "https://" + host["host"]

        if self.is_webhook_enabled(input_):
            main_config["config"]["queue"] = {
                "health": {"check": {"active": True}},
                "bull": {
                    "redis": {
                        "host": f"n8n-{app_id}-valkey-primary",
                        "port": 6379,
                        "tls": False,
                    }
                },
            }
            main_config["config"]["executions_mode"] = "queue"
            main_config["config"]["webhook_url"] = webhook_url

        # storage
        if input_.main_app_config.persistence:
            persistence = input_.main_app_config.persistence
            file_mount = ApoloFilesMount(
                storage_uri=persistence.storage_mount,
                mount_path=MountPath(path="/home/node/.n8n"),
                mode=ApoloMountMode(mode=ApoloMountModes.RW),
            )
            storage_annotations = append_apolo_storage_integration_annotations(
                main_config.get("podAnnotations", {}), [file_mount], client=self.client
            )

            if storage_annotations:
                main_config["podAnnotations"] = (
                    main_config.get("podAnnotations", {}) | storage_annotations
                )

            storage_labels = gen_apolo_storage_integration_labels(
                client=self.client, inject_storage=True
            )
            if storage_labels:
                main_config["podLabels"] = (
                    main_config.get("podLabels", {}) | storage_labels
                )
            main_config["useApoloStorage"] = True

        extra_env = self.get_extra_env(
            input_=input_,
            app_secrets_name=app_secrets_name,
            app_id=app_id,
            webhook_url=webhook_url,
        )
        main_config["extraEnv"] = extra_env

        worker_config = await self.get_worker_values(input_)
        worker_config["extraEnv"] = extra_env

        webhook_config = await self.get_webhook_values(input_)
        webhook_config["extraEnv"] = extra_env

        return {
            "apolo_app_id": extra_values["apolo_app_id"],
            "ingress": ingress,
            "main": main_config,
            "worker": worker_config,
            "webhook": webhook_config,
            "valkey": await self.get_redis_values(input_, app_id),
            "labels": {"application": "n8n"},
        }
