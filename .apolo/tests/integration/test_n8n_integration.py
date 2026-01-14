"""Integration tests for N8n app that generate helm values and validate with helm."""

import asyncio
import contextlib
import os
import tempfile
import typing as t
from pathlib import Path

import apolo_sdk
import pytest
import yaml
import yarl
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
from apolo_app_types.protocols.postgres import CrunchyPostgresUserCredentials


CHART_PATH = Path(__file__).parent.parent.parent.parent / "charts" / "n8n"


@pytest.fixture(scope="session", autouse=True)
def _build_helm_dependencies():
    """Build helm dependencies once per test session."""
    import subprocess

    # Check if helm is available
    if os.system("which helm > /dev/null 2>&1") != 0:
        pytest.skip("helm not installed")
        return

    # Build helm dependencies
    result = subprocess.run(
        ["helm", "dependency", "build", str(CHART_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        pytest.fail(
            f"Failed to build helm dependencies: {result.stderr}\n{result.stdout}"
        )


@pytest.fixture
def chart_path():
    """Get the path to the helm chart."""
    return CHART_PATH


@pytest.fixture
def basic_inputs_with_valkey_standalone():
    """Create N8nAppInputs with Valkey standalone architecture."""
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
            database=SQLiteDatabase(database_type=DBTypes.SQLITE)
        ),
    )


@pytest.fixture
def inputs_with_valkey_replication():
    """Create N8nAppInputs with Valkey replication architecture."""
    return N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"),
            replica_scaling=AutoscalingHPA(
                min_replicas=1,
                max_replicas=5,
                target_cpu_utilization_percentage=80,
                target_memory_utilization_percentage=80,
            ),
        ),
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


@pytest.fixture
def inputs_with_postgres():
    """Create N8nAppInputs with PostgreSQL database."""
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


@pytest.fixture
def apolo_client(setup_clients):
    apolo_sdk_client = setup_clients

    @contextlib.asynccontextmanager
    async def _open(uri: yarl.URL) -> t.AsyncIterator[bytes]:
        async def generator():
            if uri != yarl.URL("storage:.apps/n8n/n8n-app/config"):
                raise apolo_sdk.ResourceNotFound()
            payload = '{"encryptionKey": "some-encryption-key"}'
            for char in payload:
                yield char.encode()

        yield generator()

    apolo_sdk_client.storage.open = _open
    return apolo_sdk_client


@pytest.mark.skipif(
    os.system("which helm > /dev/null 2>&1") != 0,
    reason="helm not installed",
)
async def test_helm_template_with_generated_values_standalone(
    apolo_client, mock_get_preset_cpu, basic_inputs_with_valkey_standalone, chart_path
):
    """Test that helm template works with generated values (standalone Valkey)."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Generate helm values
    helm_values = await input_processor.gen_extra_values(
        input_=basic_inputs_with_valkey_standalone,
        app_name="n8n-test",
        namespace="test-namespace",
        app_secrets_name="test-secret",
        app_id="test-app-id",
    )

    # Write values to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as values_file:
        yaml.dump(helm_values, values_file)
        values_path = Path(values_file.name)

    try:
        # Run helm template
        process = await asyncio.create_subprocess_exec(
            "helm",
            "template",
            "test-release",
            str(chart_path),
            "-f",
            str(values_path),
            "--namespace",
            "test-namespace",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Check that helm template succeeded
        assert process.returncode == 0, f"helm template failed: {stderr.decode()}"

        # Verify the output contains valid YAML
        manifests = list(yaml.safe_load_all(stdout.decode()))
        assert len(manifests) > 0, "No manifests generated"

        # Verify we have expected resources
        resource_kinds = {m.get("kind") for m in manifests if m}
        assert "Deployment" in resource_kinds
        assert "StatefulSet" in resource_kinds
        assert "Service" in resource_kinds

        # Verify Valkey StatefulSet is present
        valkey_resources = [
            m for m in manifests if m and m.get("kind") == "StatefulSet"
        ]
        valkey_names = [r.get("metadata", {}).get("name", "") for r in valkey_resources]
        assert any(
            "valkey" in name or "redis" in name for name in valkey_names
        ), "No Valkey/Redis StatefulSet found"

    finally:
        values_path.unlink()
    assert helm_values == {
        "apolo_app_id": "test-app-id",
        "ingress": {
            "enabled": True,
            "className": "traefik",
            "hosts": [
                {"host": "n8n--test-app-id.apps.some.org.neu.ro", "paths": ["/"]}
            ],
            "annotations": {
                "traefik.ingress.kubernetes.io/router.middlewares": "platform-platform-control-plane-ingress-auth@kubernetescrd"  # noqa: E501
            },
            "grpc": {"enabled": False},
        },
        "main": {
            "resources": {
                "requests": {"cpu": "2000.0m", "memory": "0M"},
                "limits": {"cpu": "2000.0m", "memory": "0M"},
            },
            "tolerations": [
                {
                    "effect": "NoSchedule",
                    "key": "platform.neuromation.io/job",
                    "operator": "Exists",
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
            ],
            "affinity": {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {
                                "matchExpressions": [
                                    {
                                        "key": "platform.neuromation.io/nodepool",
                                        "operator": "In",
                                        "values": ["cpu_pool"],
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "podLabels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
                "platform.apolo.us/inject-storage": "true",
                "platform.apolo.us/org": "test-org",
                "platform.apolo.us/project": "test-project",
            },
            "config": {
                "db": {
                    "type": "sqlite",
                    "sqlite": {"pool_size": 1, "vacuum_on_startup": True},
                },
                "queue": {
                    "health": {"check": {"active": True}},
                    "bull": {
                        "redis": {
                            "host": "n8n-test-app-id-valkey-primary",
                            "port": 6379,
                            "tls": False,
                        }
                    },
                },
                "executions_mode": "queue",
                "webhook_url": "https://n8n--test-app-id.apps.some.org.neu.ro",
            },
            "secret": {"n8n": {"encryption_key": "some-encryption-key"}},
            "service": {"labels": {"service": "main"}},
            "replicaCount": 1,
            "podAnnotations": {
                "platform.apolo.us/inject-storage": '[{"storage_uri": "storage://cluster/test-org/test-project/.apps/n8n/n8n-app", "mount_path": "/home/node/.n8n", "mount_mode": "rw"}]'  # noqa: E501
            },
            "useApoloStorage": True,
            "extraEnv": {
                "WEBHOOK_URL": {
                    "value": "https://n8n--test-app-id.apps.some.org.neu.ro"
                },
                "EXECUTIONS_MODE": {"value": "queue"},
                "QUEUE_BULL_REDIS_HOST": {"value": "n8n-test-app-id-valkey-primary"},
                "QUEUE_BULL_REDIS_TLS": {"value": "false"},
            },
        },
        "worker": {
            "service": {"labels": {"service": "worker"}},
            "replicaCount": 2,
            "enabled": True,
            "labels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
            },
            "resources": {
                "requests": {"cpu": "2000.0m", "memory": "0M"},
                "limits": {"cpu": "2000.0m", "memory": "0M"},
            },
            "tolerations": [
                {
                    "effect": "NoSchedule",
                    "key": "platform.neuromation.io/job",
                    "operator": "Exists",
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
            ],
            "affinity": {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {
                                "matchExpressions": [
                                    {
                                        "key": "platform.neuromation.io/nodepool",
                                        "operator": "In",
                                        "values": ["cpu_pool"],
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "podLabels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
            },
            "deploymentLabels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
            },
            "extraEnv": {
                "WEBHOOK_URL": {
                    "value": "https://n8n--test-app-id.apps.some.org.neu.ro"
                },
                "EXECUTIONS_MODE": {"value": "queue"},
                "QUEUE_BULL_REDIS_HOST": {"value": "n8n-test-app-id-valkey-primary"},
                "QUEUE_BULL_REDIS_TLS": {"value": "false"},
            },
        },
        "webhook": {
            "service": {"labels": {"service": "webhook"}},
            "replicaCount": 1,
            "enabled": True,
            "labels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
            },
            "resources": {
                "requests": {"cpu": "2000.0m", "memory": "0M"},
                "limits": {"cpu": "2000.0m", "memory": "0M"},
            },
            "tolerations": [
                {
                    "effect": "NoSchedule",
                    "key": "platform.neuromation.io/job",
                    "operator": "Exists",
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/not-ready",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
                {
                    "effect": "NoExecute",
                    "key": "node.kubernetes.io/unreachable",
                    "operator": "Exists",
                    "tolerationSeconds": 300,
                },
            ],
            "affinity": {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [
                            {
                                "matchExpressions": [
                                    {
                                        "key": "platform.neuromation.io/nodepool",
                                        "operator": "In",
                                        "values": ["cpu_pool"],
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
            "podLabels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
            },
            "deploymentLabels": {
                "platform.apolo.us/component": "app",
                "platform.apolo.us/preset": "cpu-small",
            },
            "extraEnv": {
                "WEBHOOK_URL": {
                    "value": "https://n8n--test-app-id.apps.some.org.neu.ro"
                },
                "EXECUTIONS_MODE": {"value": "queue"},
                "QUEUE_BULL_REDIS_HOST": {"value": "n8n-test-app-id-valkey-primary"},
                "QUEUE_BULL_REDIS_TLS": {"value": "false"},
            },
        },
        "valkey": {
            "fullnameOverride": "n8n-test-app-id-valkey",
            "global": {"security": {"allowInsecureImages": True}},
            "image": {"repository": "bitnamilegacy/valkey"},
            "auth": {"enabled": False},
            "enabled": True,
            "architecture": "standalone",
            "primary": {
                "labels": {
                    "platform.apolo.us/component": "app",
                    "platform.apolo.us/preset": "cpu-small",
                },
                "resources": {
                    "requests": {"cpu": "2000.0m", "memory": "0M"},
                    "limits": {"cpu": "2000.0m", "memory": "0M"},
                },
                "tolerations": [
                    {
                        "effect": "NoSchedule",
                        "key": "platform.neuromation.io/job",
                        "operator": "Exists",
                    },
                    {
                        "effect": "NoExecute",
                        "key": "node.kubernetes.io/not-ready",
                        "operator": "Exists",
                        "tolerationSeconds": 300,
                    },
                    {
                        "effect": "NoExecute",
                        "key": "node.kubernetes.io/unreachable",
                        "operator": "Exists",
                        "tolerationSeconds": 300,
                    },
                ],
                "affinity": {
                    "nodeAffinity": {
                        "requiredDuringSchedulingIgnoredDuringExecution": {
                            "nodeSelectorTerms": [
                                {
                                    "matchExpressions": [
                                        {
                                            "key": "platform.neuromation.io/nodepool",
                                            "operator": "In",
                                            "values": ["cpu_pool"],
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                },
                "podLabels": {
                    "platform.apolo.us/component": "app",
                    "platform.apolo.us/preset": "cpu-small",
                },
                "deploymentLabels": {
                    "platform.apolo.us/component": "app",
                    "platform.apolo.us/preset": "cpu-small",
                },
            },
        },
        "labels": {"application": "n8n"},
    }


@pytest.mark.skipif(
    os.system("which helm > /dev/null 2>&1") != 0,
    reason="helm not installed",
)
async def test_helm_template_with_generated_values_replication(
    apolo_client, mock_get_preset_cpu, inputs_with_valkey_replication, chart_path
):
    """Test that helm template works with Valkey replication and autoscaling."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Generate helm values
    helm_values = await input_processor.gen_extra_values(
        input_=inputs_with_valkey_replication,
        app_name="n8n-test",
        namespace="test-namespace",
        app_secrets_name="test-secret",
        app_id="test-app-id",
    )

    # Write values to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as values_file:
        yaml.dump(helm_values, values_file)
        values_path = Path(values_file.name)

    try:
        # Run helm template
        process = await asyncio.create_subprocess_exec(
            "helm",
            "template",
            "test-release",
            str(chart_path),
            "-f",
            str(values_path),
            "--namespace",
            "test-namespace",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Check that helm template succeeded
        assert process.returncode == 0, f"helm template failed: {stderr.decode()}"

        # Verify the output contains valid YAML
        manifests = list(yaml.safe_load_all(stdout.decode()))
        assert len(manifests) > 0, "No manifests generated"

        # Verify HPA resources are present (for main app and valkey replicas)
        hpa_resources = [
            m for m in manifests if m and m.get("kind") == "HorizontalPodAutoscaler"
        ]
        assert len(hpa_resources) >= 2, "Expected HPA for main app and valkey replicas"

        # Verify Valkey primary and replica StatefulSets are present
        valkey_resources = [
            m for m in manifests if m and m.get("kind") == "StatefulSet"
        ]
        valkey_names = [r.get("metadata", {}).get("name", "") for r in valkey_resources]
        # In replication mode, we should have primary and replica
        valkey_count = sum(
            1 for name in valkey_names if "valkey" in name or "redis" in name
        )
        assert (
            valkey_count >= 1
        ), "Expected Valkey/Redis StatefulSets for replication mode"

    finally:
        values_path.unlink()


@pytest.mark.skipif(
    os.system("which helm > /dev/null 2>&1") != 0,
    reason="helm not installed",
)
async def test_helm_lint_with_generated_values(
    apolo_client, mock_get_preset_cpu, basic_inputs_with_valkey_standalone, chart_path
):
    """Test that helm lint passes with generated values."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Generate helm values
    helm_values = await input_processor.gen_extra_values(
        input_=basic_inputs_with_valkey_standalone,
        app_name="n8n-test",
        namespace="test-namespace",
        app_secrets_name="test-secret",
        app_id="test-app-id",
    )

    # Write values to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as values_file:
        yaml.dump(helm_values, values_file)
        values_path = Path(values_file.name)

    try:
        # Run helm lint
        process = await asyncio.create_subprocess_exec(
            "helm",
            "lint",
            str(chart_path),
            "-f",
            str(values_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Check that helm lint succeeded
        assert (
            process.returncode == 0
        ), f"helm lint failed: {stderr.decode()}\n{stdout.decode()}"

    finally:
        values_path.unlink()


@pytest.fixture
def inputs_with_persistence_none():
    """Create N8nAppInputs with persistence=None."""
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
def inputs_with_custom_persistence_path():
    """Create N8nAppInputs with custom persistence path."""
    return N8nAppInputs(
        main_app_config=MainApplicationConfig(
            preset=Preset(name="cpu-small"),
            persistence=N8nVolume(
                storage_mount=ApoloFilesPath(
                    path="storage://test-cluster/custom/n8n/data"
                )
            ),
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


@pytest.mark.skipif(
    os.system("which helm > /dev/null 2>&1") != 0,
    reason="helm not installed",
)
async def test_helm_template_with_persistence_none(
    apolo_client, mock_get_preset_cpu, inputs_with_persistence_none, chart_path
):
    """Test that helm template works with persistence=None."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Generate helm values
    helm_values = await input_processor.gen_extra_values(
        input_=inputs_with_persistence_none,
        app_name="n8n-test",
        namespace="test-namespace",
        app_secrets_name="test-secret",
        app_id="test-app-id",
    )

    # Write values to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as values_file:
        yaml.dump(helm_values, values_file)
        values_path = Path(values_file.name)

    try:
        # Run helm template
        process = await asyncio.create_subprocess_exec(
            "helm",
            "template",
            "test-release",
            str(chart_path),
            "-f",
            str(values_path),
            "--namespace",
            "test-namespace",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Check that helm template succeeded
        assert process.returncode == 0, f"helm template failed: {stderr.decode()}"

        # Verify the output contains valid YAML
        manifests = list(yaml.safe_load_all(stdout.decode()))
        assert len(manifests) > 0, "No manifests generated"

        # Verify we have expected resources
        resource_kinds = {m.get("kind") for m in manifests if m}
        assert "Deployment" in resource_kinds or "StatefulSet" in resource_kinds
        assert "Service" in resource_kinds

    finally:
        values_path.unlink()


@pytest.mark.skipif(
    os.system("which helm > /dev/null 2>&1") != 0,
    reason="helm not installed",
)
async def test_helm_template_with_custom_persistence_path(
    apolo_client,
    mock_get_preset_cpu,
    inputs_with_custom_persistence_path,
    chart_path,
):
    """Test that helm template works with custom persistence path."""
    input_processor = N8nAppChartValueProcessor(client=apolo_client)

    # Generate helm values
    helm_values = await input_processor.gen_extra_values(
        input_=inputs_with_custom_persistence_path,
        app_name="n8n-test",
        namespace="test-namespace",
        app_secrets_name="test-secret",
        app_id="test-app-id",
    )

    # Write values to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as values_file:
        yaml.dump(helm_values, values_file)
        values_path = Path(values_file.name)

    try:
        # Run helm template
        process = await asyncio.create_subprocess_exec(
            "helm",
            "template",
            "test-release",
            str(chart_path),
            "-f",
            str(values_path),
            "--namespace",
            "test-namespace",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Check that helm template succeeded
        assert process.returncode == 0, f"helm template failed: {stderr.decode()}"

        # Verify the output contains valid YAML
        manifests = list(yaml.safe_load_all(stdout.decode()))
        assert len(manifests) > 0, "No manifests generated"

        # Verify we have expected resources
        resource_kinds = {m.get("kind") for m in manifests if m}
        assert "Deployment" in resource_kinds or "StatefulSet" in resource_kinds
        assert "Service" in resource_kinds

    finally:
        values_path.unlink()
