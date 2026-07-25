"""Shared helpers for the Databricks batch tasks.

Each task is a plain Python entry point. They deliberately reuse the *same* service
code the API runs — `app.services.*` — rather than reimplementing the algorithms in
Spark. Two implementations of a retention curve would drift, and then the nightly
numbers and the live numbers would disagree with nobody able to say which is right.

What Databricks adds is the execution environment: scheduling, retries, a cluster
big enough for full-catalog passes, and Delta tables for history. The maths is the
same code.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# The job bundle ships the `app` package alongside these scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def run_async(coro):
    """Run a coroutine from a Databricks task entry point.

    `asyncio.run()` is not usable here: serverless Python executes inside an already
    running event loop, and calling it raises

        RuntimeError: asyncio.run() cannot be called from a running event loop

    When a loop is already running we cannot join it from synchronous code either, so
    the coroutine goes to a worker thread with a private loop and we block on that.
    Locally — where no loop is running — this is just `asyncio.run`.
    """
    import asyncio
    import threading

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    outcome: dict = {}

    def worker() -> None:
        try:
            outcome["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
            outcome["error"] = exc

    thread = threading.Thread(target=worker, name="pockettaste-task")
    thread.start()
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def _get_dbutils():
    """`dbutils` is injected into notebooks but must be imported in a Python task."""
    try:
        from databricks.sdk.runtime import dbutils  # type: ignore

        return dbutils
    except Exception:  # noqa: BLE001
        pass
    import builtins

    if hasattr(builtins, "dbutils"):
        return builtins.dbutils
    try:
        from pyspark.dbutils import DBUtils  # type: ignore
        from pyspark.sql import SparkSession

        return DBUtils(SparkSession.builder.getOrCreate())
    except Exception:  # noqa: BLE001 - not on Databricks at all
        return None


def resolve_secret(value: str) -> str:
    """Resolve a `{{secrets/scope/key}}` reference.

    Serverless `spark_python_task` does **not** interpolate these in `parameters` —
    the literal string arrives in argv. Job-level parameter interpolation is
    inconsistent across task types, so the task resolves the reference itself via
    `dbutils.secrets`, which works the same everywhere.
    """
    if not value or not value.startswith("{{secrets/"):
        return value
    try:
        _, scope, key = value.strip("{} ").split("/", 2)
    except ValueError:
        print(f"[secrets] malformed reference: {value[:60]}")
        return ""
    dbutils = _get_dbutils()
    if dbutils is None:
        print("[secrets] dbutils unavailable; cannot resolve secret references")
        return ""
    try:
        resolved = dbutils.secrets.get(scope=scope, key=key)
        print(f"[secrets] resolved {scope}/{key} ({len(resolved)} chars)")
        return resolved
    except Exception as exc:  # noqa: BLE001
        print(f"[secrets] failed to read {scope}/{key}: {type(exc).__name__}: {exc}")
        return ""


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--catalog", default="pockettaste", help="Unity Catalog name.")
    parser.add_argument("--mongo-secret", default="", help="Mongo URI, usually a secret ref.")
    parser.add_argument("--openai-secret", default="", help="OpenAI key, usually a secret ref.")
    parser.add_argument("--database", default="Click", help="Mongo database.")
    parser.add_argument("--dry-run", action="store_true")
    args, _unknown = parser.parse_known_args()

    args.mongo_secret = resolve_secret(args.mongo_secret)
    args.openai_secret = resolve_secret(args.openai_secret)

    # The service layer reads configuration from the environment, so bridge the job
    # parameters into it rather than threading a settings object through every call.
    if args.mongo_secret:
        os.environ["DB_URL"] = args.mongo_secret
    if args.openai_secret:
        os.environ["OPENAI_KEY"] = args.openai_secret
    os.environ["MONGO_DB_NAME"] = args.database
    # The bundled app ships no .env; make sure a stale one cannot shadow the secrets.
    os.environ.setdefault("JWT_SECRET", "batch-tier-unused")
    return args


def _describe_uri(uri: str) -> str:
    """Redacted description of the connection string, for diagnostics.

    Never print the URI itself — it carries the password.
    """
    if not uri:
        return "EMPTY (the secret did not resolve)"
    if uri.startswith("{{"):
        return f"UNRESOLVED secret reference ({uri[:40]}...)"
    scheme, _, rest = uri.partition("://")
    host = rest.split("@")[-1].split("/")[0] if "@" in rest else rest.split("/")[0]
    return f"{scheme}://***@{host} (len={len(uri)})"


async def build_context():
    """Connect to Mongo and construct the same container the API uses."""
    from app.container import build_container
    from app.core.config import get_settings
    from app.data.mongo import MongoGateway

    get_settings.cache_clear()
    settings = get_settings()
    print(f"[mongo] target: {_describe_uri(settings.mongo_uri)} db={settings.mongo_db_name}")

    if await MongoGateway(settings).connect():
        gateway = MongoGateway(settings)
        await gateway.connect()
        return settings, gateway, build_container(settings, gateway)

    # Re-raise the driver's own error rather than a generic message — the two real
    # causes look identical from the outside and need opposite fixes.
    from pymongo import AsyncMongoClient

    try:
        probe = AsyncMongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
        await probe.admin.command("ping")
    except Exception as exc:  # noqa: BLE001 - the whole point is to surface it
        reason = f"{type(exc).__name__}: {exc}"
        hint = (
            "MongoDB Atlas blocks unknown source IPs by default. Databricks serverless "
            "egresses from IPs that are almost certainly not in your Atlas Network Access "
            "allowlist. Add 0.0.0.0/0 for a test, or the workspace's stable egress range, "
            "then re-run."
            if "ServerSelectionTimeout" in reason or "timed out" in reason.lower()
            else "Check the mongo_uri secret in the 'pockettaste' scope."
        )
        raise SystemExit(f"Databricks task could not reach MongoDB.\n  cause: {reason[:400]}\n  hint: {hint}")
    raise SystemExit("Databricks task could not reach MongoDB (no error reported).")


def write_delta(spark, catalog: str, table: str, rows: list[dict], mode: str = "overwrite") -> int:
    """Persist a task result to Delta for history and BI.

    Best-effort: if Spark or the catalog is unavailable the task still completes,
    because the operational store is Mongo and Delta is the analytics mirror. A
    failure to mirror should not fail the computation.
    """
    if not rows:
        return 0
    try:
        import json

        frame = spark.createDataFrame([{"payload": json.dumps(row, default=str)} for row in rows])
        target = f"{catalog}.pockettaste.{table}"
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.pockettaste")
        frame.write.mode(mode).saveAsTable(target)
        print(f"[delta] wrote {len(rows)} rows -> {target}")
        return len(rows)
    except Exception as exc:  # noqa: BLE001 - mirroring is not the job's purpose
        print(f"[delta] skipped ({type(exc).__name__}: {exc})")
        return 0


def get_spark():
    try:
        from pyspark.sql import SparkSession

        return SparkSession.builder.getOrCreate()
    except Exception:  # noqa: BLE001 - lets the tasks run locally for testing
        return None
