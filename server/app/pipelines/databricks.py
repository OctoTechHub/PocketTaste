"""Databricks batch tier — optional, and deliberately outside the request path.

The three agents run fine in-process at hackathon scale. They stop being fine when
the catalog is large: embedding refresh, full-catalog clustering and O(n*k)
similarity are batch jobs, not API calls.

This module emits a Databricks Jobs 2.1 job specification for that tier. It is a
deployable artifact, not a live integration — nothing here requires credentials,
and `configured` reports honestly whether a workspace is actually wired up.

Division of labour:
  online  (FastAPI + Mongo)  — event ingest, ranking, similarity gate, discovery
  batch   (Databricks)       — embedding refresh, clustering, evaluation, aggregates
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings

_TASKS: list[dict[str, Any]] = [
    {
        "task_key": "refresh_embeddings",
        "description": "Re-embed catalog items whose transcript changed since the last run.",
        "entrypoint": "jobs/refresh_embeddings.py",
        "depends_on": [],
    },
    {
        "task_key": "rebuild_clusters",
        "description": "Full-catalog agglomerative clustering on narrative-arc embeddings.",
        "entrypoint": "jobs/rebuild_clusters.py",
        "depends_on": ["refresh_embeddings"],
    },
    {
        "task_key": "similarity_sweep",
        "description": "All-pairs duplicate sweep over the catalog; writes duplicate families.",
        "entrypoint": "jobs/similarity_sweep.py",
        "depends_on": ["rebuild_clusters"],
    },
    {
        "task_key": "aggregate_features",
        "description": "Recompute retention curves and chapter interest over the full event log.",
        "entrypoint": "jobs/aggregate_features.py",
        "depends_on": [],
    },
    {
        "task_key": "evaluate_ranker",
        "description": "Leave-one-out offline evaluation; writes Recall@K/NDCG@K vs baselines.",
        "entrypoint": "jobs/evaluate_ranker.py",
        "depends_on": ["aggregate_features", "rebuild_clusters"],
    },
]


#: Python packages the batch cluster needs. Deliberately smaller than the API's
#: requirements — no uvicorn, no fastapi, no auth stack. The tasks import the service
#: layer, not the web layer.
#:
#: Lower bounds, not exact pins, and two deliberate omissions.
#:
#: **numpy** is absent because serverless compute ships its own (1.26) as a core
#: package. Installing another over it kills the Python kernel outright:
#:
#:     ERROR_CORE_PACKAGE_VERSION_CHANGE ... (numpy: 1.26.4 -> 2.2.1)
#:
#: Nothing here needs numpy 2.x — the vector maths is `asarray`, `linalg.norm`,
#: `argsort`, `clip`, `interp` — so the runtime's copy is left alone.
#:
#: **haystack-ai** is absent because it declares an unpinned `numpy` dependency, so
#: pip resolves it to 2.x and triggers exactly that failure. Pinning haystack below
#: 2.8 would avoid it but cost the API real retrieval features. The batch tasks do
#: not retrieve anything — an in-memory index built by a job that then exits is
#: pointless, and `similarity_sweep` compares all pairs rather than a shortlist — so
#: `DiscoveryService` degrades to a no-op here and Haystack stays at 2.31 in the API.
BATCH_LIBRARIES: list[str] = [
    "pymongo>=4.13",
    "pydantic>=2.9",
    "pydantic-settings>=2.7",
    "openai>=1.99",
    "python-dotenv>=1.0",
]


def _task_parameters(settings: Settings) -> list[str]:
    return [
        f"--catalog={settings.databricks_catalog}",
        f"--database={settings.mongo_db_name}",
        "--mongo-secret={{secrets/pockettaste/mongo_uri}}",
        "--openai-secret={{secrets/pockettaste/openai_key}}",
    ]


def build_serverless_job_spec(
    settings: Settings, *, workspace_base: str | None = None
) -> dict[str, Any]:
    """Serverless variant of the job.

    Some workspaces (Free Edition and serverless-only accounts) reject `new_cluster`
    outright with *"Only serverless compute is supported in the workspace"*. On
    serverless there is no cluster to size, and Python dependencies move from
    per-task `libraries` into a shared `environments` block.

    This suits the workload anyway: the tasks are IO- and API-bound against Mongo and
    OpenAI, so there was never anything for Spark workers to do.
    """
    root = workspace_base or "/Workspace/Users/<you>/pockettaste"
    return {
        "name": settings.databricks_job_name,
        "schedule": {
            "quartz_cron_expression": settings.databricks_cron,
            "timezone_id": settings.databricks_timezone,
            "pause_status": "UNPAUSED",
        },
        "max_concurrent_runs": 1,
        "environments": [
            {
                "environment_key": "intelligence",
                "spec": {"client": "3", "dependencies": BATCH_LIBRARIES},
            }
        ],
        "tasks": [
            {
                "task_key": task["task_key"],
                "description": task["description"],
                "spark_python_task": {
                    "python_file": f"{root}/databricks/{task['entrypoint']}",
                    "source": "WORKSPACE",
                    "parameters": _task_parameters(settings),
                },
                "environment_key": "intelligence",
                "depends_on": [{"task_key": key} for key in task["depends_on"]],
                "timeout_seconds": 3600,
                "max_retries": 1,
            }
            for task in _TASKS
        ],
        "tags": {"project": "pockettaste", "tier": "batch", "compute": "serverless"},
    }


def build_job_spec(settings: Settings, *, workspace_base: str | None = None) -> dict[str, Any]:
    """Databricks Jobs API 2.1 payload for the nightly batch tier (classic compute).

    `workspace_base` is the deployed source root, e.g.
    `/Workspace/Users/you@example.com/pockettaste`. Without it the spec still renders
    with a placeholder so `GET /pipeline/databricks` is useful before any deploy.
    """
    catalog = settings.databricks_catalog
    root = workspace_base or "/Workspace/Users/<you>/pockettaste"
    return {
        "name": settings.databricks_job_name,
        "schedule": {
            "quartz_cron_expression": settings.databricks_cron,
            "timezone_id": settings.databricks_timezone,
            "pause_status": "UNPAUSED",
        },
        "max_concurrent_runs": 1,
        "job_clusters": [
            {
                "job_cluster_key": "intelligence",
                "new_cluster": {
                    "spark_version": settings.databricks_spark_version,
                    "node_type_id": settings.databricks_node_type,
                    # Single node: these tasks are IO- and API-bound against Mongo and
                    # OpenAI, not Spark-parallel. Workers would idle and cost money.
                    "num_workers": 0,
                    "spark_conf": {
                        "spark.databricks.cluster.profile": "singleNode",
                        "spark.master": "local[*]",
                    },
                    "custom_tags": {"ResourceClass": "SingleNode"},
                },
            }
        ],
        "tasks": [
            {
                "task_key": task["task_key"],
                "description": task["description"],
                "job_cluster_key": "intelligence",
                "spark_python_task": {
                    "python_file": f"{root}/databricks/{task['entrypoint']}",
                    "source": "WORKSPACE",
                    "parameters": [
                        f"--catalog={catalog}",
                        f"--database={settings.mongo_db_name}",
                        "--mongo-secret={{secrets/pockettaste/mongo_uri}}",
                        "--openai-secret={{secrets/pockettaste/openai_key}}",
                    ],
                },
                "libraries": [{"pypi": {"package": package}} for package in BATCH_LIBRARIES],
                "depends_on": [{"task_key": key} for key in task["depends_on"]],
                "timeout_seconds": 3600,
                "max_retries": 1,
            }
            for task in _TASKS
        ],
        "tags": {"project": "pockettaste", "tier": "batch", "owner": "content-intelligence"},
    }


def build_unity_catalog_plan(settings: Settings) -> dict[str, Any]:
    """Delta tables the batch tier reads/writes, mirrored from the Mongo collections."""
    catalog = settings.databricks_catalog
    return {
        "catalog": catalog,
        "schema": "intelligence",
        "tables": [
            {"name": "content_items", "mode": "mirrored_from_mongo", "partition_by": ["language"]},
            {"name": "activity_events", "mode": "append", "partition_by": ["event_date"]},
            {"name": "content_profiles", "mode": "overwrite_on_refresh", "notes": "holds embeddings"},
            {"name": "content_features", "mode": "overwrite_on_refresh"},
            {"name": "demand_segments", "mode": "append", "notes": "one snapshot per run"},
            {"name": "evaluation_runs", "mode": "append", "notes": "Recall@K / NDCG@K history"},
        ],
        "note": (
            "Delta is the analytics store; MongoDB stays the operational store for the API. "
            "Nothing in the online request path depends on Databricks being reachable."
        ),
    }


def describe(settings: Settings) -> dict[str, Any]:
    return {
        "configured": settings.databricks_enabled,
        "host": settings.databricks_host or None,
        "role": "optional batch tier — not on the online request path",
        "tasks": [task["task_key"] for task in _TASKS],
        "job_spec": build_job_spec(settings, workspace_base=settings.databricks_workspace_base or None),
        "unity_catalog": build_unity_catalog_plan(settings),
        "deployed_source": settings.databricks_workspace_base or None,
        "batch_libraries": BATCH_LIBRARIES,
        "deploy_command": "python -m scripts.deploy_databricks --apply",
        "status_note": (
            "No workspace credentials are configured, so this is a deployable specification "
            "rather than a live integration."
            if not settings.databricks_enabled
            else (
                "Workspace credentials detected. Run scripts/deploy_databricks.py to upload "
                "the task sources and create the job."
            )
        ),
    }
