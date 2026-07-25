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


def build_job_spec(settings: Settings) -> dict[str, Any]:
    """Databricks Jobs API 2.1 payload for the nightly batch tier."""
    catalog = settings.databricks_catalog
    return {
        "name": "pockettaste-nightly-intelligence",
        "schedule": {
            "quartz_cron_expression": "0 0 3 * * ?",
            "timezone_id": "Asia/Kolkata",
            "pause_status": "UNPAUSED",
        },
        "max_concurrent_runs": 1,
        "job_clusters": [
            {
                "job_cluster_key": "intelligence",
                "new_cluster": {
                    "spark_version": "15.4.x-scala2.12",
                    "node_type_id": "Standard_DS3_v2",
                    "num_workers": 2,
                    "data_security_mode": "SINGLE_USER",
                    "spark_conf": {"spark.databricks.delta.preview.enabled": "true"},
                },
            }
        ],
        "tasks": [
            {
                "task_key": task["task_key"],
                "description": task["description"],
                "job_cluster_key": "intelligence",
                "spark_python_task": {
                    "python_file": f"dbfs:/pockettaste/{task['entrypoint']}",
                    "parameters": [
                        f"--catalog={catalog}",
                        "--mongo-secret={{secrets/pockettaste/mongo_uri}}",
                        "--openai-secret={{secrets/pockettaste/openai_key}}",
                    ],
                },
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
        "job_spec": build_job_spec(settings),
        "unity_catalog": build_unity_catalog_plan(settings),
        "status_note": (
            "No workspace credentials are configured, so this is a deployable specification "
            "rather than a live integration."
            if not settings.databricks_enabled
            else "Workspace credentials detected; submit the job spec with the Jobs 2.1 API."
        ),
    }
