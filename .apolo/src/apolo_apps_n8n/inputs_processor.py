import typing as t

from apolo_sdk import Client

from apolo_app_types.app_types import AppType
from apolo_app_types.helm.apps.base import BaseChartValueProcessor
from apolo_app_types.helm.apps.common import (
    gen_extra_values,
    get_component_values,
    get_preset,
)
from apolo_app_types.protocols.common import AutoscalingHPA, Preset
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
            if not db.credentials.pgbouncer_uri:
                err = "PostgreSQL database configuration requires a valid pgbouncer_uri"
                raise ValueError(err)
            return {
                "type": "postgresdb",
                "postgresdb": parse_postgres_connection_string(
                    db.credentials.pgbouncer_uri
                ),
            }
        err = "Invalid database configuration"
        raise ValueError(err)

    async def preset_to_values(self, preset: Preset) -> dict[str, t.Any]:
        apolo_preset = get_preset(self.client, preset.name)
        values = await get_component_values(apolo_preset, preset.name)
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
            **(await self.preset_to_values(config.preset)),
        }

    async def get_webhook_values(self, input_: N8nAppInputs) -> dict[str, t.Any]:
        config = input_.webhook_config
        return {
            "service": {
                "labels": {"service": "webhook"},
            },
            "replicaCount": config.replicas,
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

    async def get_redis_values(self, input_: N8nAppInputs) -> dict[str, t.Any]:
        config = input_.valkey_config
        values = {
            "global": {"security": {"allowInsecureImages": True}},
            "image": {"repository": "bitnamilegacy/valkey"},
            "enabled": True,
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
                    "hpa": {
                        "enabled": True,
                        "minReplicas": autoscaling.min_replicas,
                        "maxReplicas": autoscaling.max_replicas,
                        # adding keys manually because they differ from main app
                        "targetCPU": (autoscaling.target_cpu_utilization_percentage),
                        "targetMemory": (
                            autoscaling.target_memory_utilization_percentage
                        ),
                    }
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
        for i, host in enumerate(ingress["hosts"]):
            paths = host["paths"]
            ingress["hosts"][i]["paths"] = [p["path"] for p in paths]
        return {
            "apolo_app_id": extra_values["apolo_app_id"],
            "ingress": ingress,
            "main": main_config,
            "worker": await self.get_worker_values(input_),
            "webhook": await self.get_webhook_values(input_),
            "valkey": await self.get_redis_values(input_),
            "labels": {"application": "n8n"},
        }
