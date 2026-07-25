"""Deploy the batch tier to Databricks.

    python -m scripts.deploy_databricks              # dry run: show the plan
    python -m scripts.deploy_databricks --apply      # upload sources, create the job
    python -m scripts.deploy_databricks --run-now    # ...and trigger a run immediately
    python -m scripts.deploy_databricks --status     # show the deployed job and last runs
    python -m scripts.deploy_databricks --delete     # remove the job

What it does:

1. Uploads `app/` and `databricks/jobs/` into the workspace as files, so the batch
   tasks import the *same* service code the API runs. Two implementations of a
   retention curve would drift, and then the nightly numbers and the live numbers
   would disagree with nobody able to say which is right.
2. Puts the Mongo URI and OpenAI key into a Databricks secret scope. They are
   referenced as `{{secrets/pockettaste/...}}` in the job, never inlined as
   plaintext job parameters.
3. Creates (or resets) the job from the same spec `GET /pipeline/databricks` serves.

This workspace has DBFS disabled and the Files API rejects `/Workspace` paths, so
uploads go through `workspace/import` with `format=AUTO`, which creates real `.py`
workspace files that `spark_python_task` can execute with `source: WORKSPACE`.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.pipelines.databricks import build_job_spec, build_serverless_job_spec  # noqa: E402

logger = get_logger("deploy")

SECRET_SCOPE = "pockettaste"
#: Only what the batch tasks import. The web layer is not uploaded.
SOURCE_DIRS = ["app", "databricks/jobs"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", "tests"}


def clean_host(raw: str) -> str:
    """Workspace URLs are often pasted with the `?o=` org suffix; strip it."""
    return raw.split("/?")[0].split("?")[0].rstrip("/")


class Databricks:
    def __init__(self, host: str, token: str) -> None:
        self.host = clean_host(host)
        self._client = httpx.Client(
            base_url=self.host, headers={"Authorization": f"Bearer {token}"}, timeout=90
        )

    def call(self, method: str, path: str, **kwargs) -> httpx.Response:
        return self._client.request(method, path, **kwargs)

    def me(self) -> str:
        response = self.call("GET", "/api/2.0/preview/scim/v2/Me")
        response.raise_for_status()
        return response.json()["userName"]

    def mkdirs(self, path: str) -> None:
        self.call("POST", "/api/2.0/workspace/mkdirs", json={"path": path}).raise_for_status()

    def upload(self, workspace_path: str, content: bytes) -> None:
        response = self.call(
            "POST",
            "/api/2.0/workspace/import",
            json={
                "path": workspace_path,
                "content": base64.b64encode(content).decode(),
                "format": "AUTO",
                "overwrite": True,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"upload {workspace_path} -> {response.status_code} {response.text[:200]}")

    def ensure_secret(self, scope: str, key: str, value: str) -> None:
        self.call("POST", "/api/2.0/secrets/scopes/create",
                  json={"scope": scope, "initial_manage_principal": "users"})
        response = self.call(
            "POST", "/api/2.0/secrets/put", json={"scope": scope, "key": key, "string_value": value}
        )
        if response.status_code != 200:
            raise RuntimeError(f"secret {key} -> {response.status_code} {response.text[:200]}")

    def find_job(self, name: str) -> int | None:
        response = self.call("GET", "/api/2.1/jobs/list", params={"name": name, "limit": 25})
        response.raise_for_status()
        for job in response.json().get("jobs", []):
            if job.get("settings", {}).get("name") == name:
                return job["job_id"]
        return None

    def create_or_reset(self, spec: dict, fallback: dict | None = None) -> tuple[int, str, dict]:
        """Create or update the job, falling back to serverless when required.

        Serverless-only workspaces reject `new_cluster` with a specific error rather
        than a capability flag we could check up front, so the cleanest detection is
        to try and read the refusal.
        """
        existing = self.find_job(spec["name"])
        for candidate, label in ((spec, "classic"), (fallback, "serverless")):
            if candidate is None:
                continue
            if existing:
                response = self.call(
                    "POST", "/api/2.1/jobs/reset", json={"job_id": existing, "new_settings": candidate}
                )
                if response.status_code == 200:
                    return existing, f"updated ({label} compute)", candidate
            else:
                response = self.call("POST", "/api/2.1/jobs/create", json=candidate)
                if response.status_code == 200:
                    return response.json()["job_id"], f"created ({label} compute)", candidate

            if "serverless compute is supported" in response.text and fallback is not None:
                print("  workspace is serverless-only; retrying with a serverless job spec")
                continue
            raise RuntimeError(f"jobs -> {response.status_code} {response.text[:400]}")
        raise RuntimeError("Could not create the job with either compute type.")


APP_NAME = "pockettaste-api"


def deploy_app(client: "Databricks", root: Path, user: str, settings) -> int:
    """Host the FastAPI service itself on Databricks Apps.

    Apps runs the container and puts workspace SSO in front of it, so the API is
    reachable by anyone in the workspace and by nobody else. A personal access token
    will not open it — Apps expects an OAuth session, which is the point.

    Two differences from a local run, both in `app.yaml`:
      * secrets arrive as environment variables from the same `pockettaste` scope the
        batch jobs use, so there is one place to rotate them;
      * the background loop is disabled, because a scheduled job should have exactly
        one owner and that owner is the Databricks job, not an API replica.
    """
    import secrets as _secrets

    base = f"/Users/{user}/pockettaste-app"
    logger.info("Deploying the API to Databricks Apps at %s", base)

    client.ensure_secret(SECRET_SCOPE, "mongo_uri", settings.mongo_uri)
    client.ensure_secret(SECRET_SCOPE, "openai_key", settings.openai_secret or "")
    client.ensure_secret(
        SECRET_SCOPE, "jwt_secret", settings.jwt_secret or _secrets.token_urlsafe(48)
    )
    client.ensure_secret(SECRET_SCOPE, "sarvam_api_key", settings.sarvam_api_key or "")
    client.ensure_secret(SECRET_SCOPE, "databricks_token", settings.databricks_token)

    existing = client.call("GET", f"/api/2.0/apps/{APP_NAME}")
    if existing.status_code == 404:
        created = client.call(
            "POST", "/api/2.0/apps",
            json={"name": APP_NAME, "description": "PocketTaste creator-intelligence API"},
        )
        if created.status_code != 200:
            logger.error("apps/create -> %s %s", created.status_code, created.text[:300])
            return 1
        logger.info("App created. Waiting for compute...")
        for _ in range(40):
            state = client.call("GET", f"/api/2.0/apps/{APP_NAME}").json()
            if state.get("compute_status", {}).get("state") == "ACTIVE":
                break
            time.sleep(15)

    # `valueFrom` in app.yaml names an app **resource**, not a scope key. Without the
    # resources declared here every variable silently resolves to nothing and the
    # container boots unconfigured — which presents as "the env vars are missing".
    resources = [
        {"name": key, "secret": {"scope": SECRET_SCOPE, "key": key, "permission": "READ"}}
        for key in ("mongo_uri", "openai_key", "jwt_secret", "sarvam_api_key", "databricks_token")
    ]
    patched = client.call(
        "PATCH", f"/api/2.0/apps/{APP_NAME}",
        json={"name": APP_NAME, "description": "PocketTaste creator-intelligence API",
              "resources": resources},
    )
    logger.info(
        "Declared %d secret resources on the app (%s)",
        len(resources), "ok" if patched.status_code == 200 else patched.text[:120],
    )

    # The app runs as its own service principal, which is not a member of `users`.
    # Without an explicit READ grant every `valueFrom` in app.yaml resolves to
    # nothing and the container starts with no configuration at all — which looks
    # exactly like "the env vars are missing".
    app = client.call("GET", f"/api/2.0/apps/{APP_NAME}").json()
    principal = app.get("service_principal_client_id")
    if principal:
        acl = client.call(
            "POST", "/api/2.0/secrets/acls/put",
            json={"scope": SECRET_SCOPE, "principal": principal, "permission": "READ"},
        )
        logger.info(
            "Granted READ on scope '%s' to the app service principal (%s)",
            SECRET_SCOPE, "ok" if acl.status_code == 200 else acl.text[:120],
        )
    else:
        logger.warning("Could not resolve the app service principal; secrets may not resolve.")

    files = [
        (path, path.relative_to(root).as_posix())
        for path in sorted((root / "app").rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    files += [(root / "app.yaml", "app.yaml"), (root / "requirements-app.txt", "requirements.txt")]

    made: set[str] = set()
    for path, relative in files:
        target = f"{base}/{relative}"
        parent = target.rsplit("/", 1)[0]
        if parent not in made:
            client.mkdirs(parent)
            made.add(parent)
        client.upload(target, path.read_bytes())
    logger.info("Uploaded %d files.", len(files))

    response = client.call(
        "POST", f"/api/2.0/apps/{APP_NAME}/deployments",
        json={"source_code_path": f"/Workspace{base}"},
    )
    if response.status_code != 200:
        logger.error("deployment -> %s %s", response.status_code, response.text[:300])
        return 1

    deployment_id = response.json()["deployment_id"]
    for _ in range(60):
        status = client.call(
            "GET", f"/api/2.0/apps/{APP_NAME}/deployments/{deployment_id}"
        ).json().get("status", {})
        if status.get("state") in ("SUCCEEDED", "FAILED", "STOPPED"):
            logger.info("Deployment %s: %s", status.get("state"), status.get("message"))
            break
        time.sleep(15)

    app = client.call("GET", f"/api/2.0/apps/{APP_NAME}").json()
    logger.info("")
    logger.info("App   : %s", app.get("app_status", {}).get("state"))
    logger.info("URL   : %s", app.get("url"))
    logger.info("Access: workspace SSO. Open the URL in a browser; a PAT will not work.")
    return 0


def collect_sources(root: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for directory in SOURCE_DIRS:
        base = root / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_PARTS & set(path.parts):
                continue
            files.append((path, path.relative_to(root).as_posix()))
    return files


def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()

    if not settings.databricks_enabled:
        logger.error("DATABRICKS_HOST and DATABRICKS_TOKEN must be set in server/.env.")
        return 1

    client = Databricks(settings.databricks_host, settings.databricks_token)
    root = Path(__file__).resolve().parents[1]

    try:
        user = client.me()
    except Exception as exc:  # noqa: BLE001 - a bad token should read clearly
        logger.error("Cannot reach the workspace: %s", exc)
        return 1

    base = settings.databricks_workspace_base or f"/Workspace/Users/{user}/pockettaste"
    import_root = base.replace("/Workspace", "", 1) if base.startswith("/Workspace") else base
    spec = build_job_spec(settings, workspace_base=base)
    serverless_spec = build_serverless_job_spec(settings, workspace_base=base)
    sources = collect_sources(root)

    logger.info("workspace : %s", client.host)
    logger.info("user      : %s", user)
    logger.info("source    : %s", base)
    logger.info("job       : %s", spec["name"])
    logger.info("schedule  : %s %s", spec["schedule"]["quartz_cron_expression"],
                spec["schedule"]["timezone_id"])
    logger.info("cluster   : %s / %s (single node)",
                spec["job_clusters"][0]["new_cluster"]["node_type_id"],
                spec["job_clusters"][0]["new_cluster"]["spark_version"])
    logger.info("tasks     : %s", [task["task_key"] for task in spec["tasks"]])
    logger.info("sources   : %d python files to upload", len(sources))

    if args.app:
        return deploy_app(client, root, user, settings)
    if args.status:
        return _status(client, spec["name"])
    if args.delete:
        job_id = client.find_job(spec["name"])
        if not job_id:
            logger.info("No job named %s exists.", spec["name"])
            return 0
        client.call("POST", "/api/2.1/jobs/delete", json={"job_id": job_id})
        logger.info("Deleted job %s.", job_id)
        return 0

    if not args.apply:
        logger.info("")
        logger.info("Dry run. Re-run with --apply to upload and create the job.")
        return 0

    # --- 1. secrets -------------------------------------------------------
    logger.info("")
    logger.info("Storing secrets in scope '%s'...", SECRET_SCOPE)
    client.ensure_secret(SECRET_SCOPE, "mongo_uri", settings.mongo_uri)
    if settings.openai_secret:
        client.ensure_secret(SECRET_SCOPE, "openai_key", settings.openai_secret)
    else:
        client.ensure_secret(SECRET_SCOPE, "openai_key", "")
        logger.warning("No OPENAI_KEY set; refresh_embeddings will use the hash fallback.")

    # --- 2. sources -------------------------------------------------------
    logger.info("Uploading %d source files...", len(sources))
    made: set[str] = set()
    for path, relative in sources:
        target = f"{import_root}/{relative}"
        parent = target.rsplit("/", 1)[0]
        if parent not in made:
            client.mkdirs(parent)
            made.add(parent)
        client.upload(target, path.read_bytes())
    logger.info("Uploaded into %d directories.", len(made))

    # --- 3. job -----------------------------------------------------------
    job_id, action, applied = client.create_or_reset(spec, serverless_spec)
    logger.info("")
    logger.info("Job %s: %s (id=%s)", action, applied["name"], job_id)
    logger.info("  %s/jobs/%s", client.host, job_id)

    if args.run_now:
        response = client.call("POST", "/api/2.1/jobs/run-now", json={"job_id": job_id})
        if response.status_code == 200:
            run_id = response.json()["run_id"]
            logger.info("Triggered run %s -> %s/jobs/%s/runs/%s", run_id, client.host, job_id, run_id)
        else:
            logger.error("run-now failed: %s %s", response.status_code, response.text[:300])

    logger.info("")
    logger.info("Add this to server/.env so the API reports the deployed source:")
    logger.info("    DATABRICKS_WORKSPACE_BASE=%s", base)
    return 0


def _status(client: Databricks, name: str) -> int:
    job_id = client.find_job(name)
    if not job_id:
        logger.info("No job named %s is deployed.", name)
        return 0
    logger.info("job_id: %s  ->  %s/jobs/%s", job_id, client.host, job_id)
    runs = client.call("GET", "/api/2.1/jobs/runs/list", params={"job_id": job_id, "limit": 5})
    for run in runs.json().get("runs", []):
        state = run.get("state", {})
        logger.info(
            "  run %-12s %-12s %-10s %s",
            run.get("run_id"),
            state.get("life_cycle_state"),
            state.get("result_state") or "",
            (state.get("state_message") or "")[:60],
        )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy the PocketTaste batch tier to Databricks.")
    parser.add_argument("--apply", action="store_true", help="Upload sources and create the job.")
    parser.add_argument("--run-now", action="store_true", help="Trigger a run after deploying.")
    parser.add_argument("--status", action="store_true", help="Show the deployed job and recent runs.")
    parser.add_argument("--delete", action="store_true", help="Delete the deployed job.")
    parser.add_argument(
        "--app", action="store_true",
        help="Host the FastAPI service on Databricks Apps instead of deploying the batch job.",
    )
    raise SystemExit(main(parser.parse_args()))
