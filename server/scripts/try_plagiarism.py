"""Submit a copy of a real story through the creator-studio upload path and see what happens.

This calls the same HTTP endpoint the creator studio calls -- no test harness, no
mocks, no shortcut past the gate. Whatever verdict prints here is the verdict a real
creator would get.

    # start the server first:  uvicorn app.main:app --port 8000
    python scripts/try_plagiarism.py                       # copies a random story
    python scripts/try_plagiarism.py --story cnt_abc123    # copies the one you name
    python scripts/try_plagiarism.py --rewrite             # reword it instead of copying
    python scripts/try_plagiarism.py --keep                # leave the upload in the catalog

Anything the gate lets through is deleted again on exit unless you pass --keep, so
running this repeatedly does not pollute the catalog.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_EMAIL = "krish@gmail.com"
DEFAULT_PASSWORD = "Test@1234"

#: Swapped into the description word by word to produce a "rewritten" draft. The story
#: is unchanged -- only the wording moves. This is the case a title check cannot catch.
_REWRITES = {
    "raat": "night", "ghar": "makaan", "aadhi": "half", "mehmaan": "guest",
    "ek": "koi", "aur": "tatha", "hai": "hota hai", "jo": "jisne",
    "woman": "lady", "man": "fellow", "house": "home", "night": "darkness",
    "young": "youthful", "family": "household", "village": "hamlet",
    "returns": "comes back", "finds": "discovers", "begins": "starts",
    "secret": "hidden truth", "story": "tale", "love": "romance",
}


def _call(base: str, method: str, path: str, body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, payload, headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=600)
        return response.status, json.load(response)
    except urllib.error.HTTPError as error:          # 409 is a result, not a failure
        try:
            return error.code, json.load(error)
        except Exception:
            return error.code, {}
    except urllib.error.URLError as error:
        sys.exit(f"Cannot reach {base} -- is the server running?  ({error.reason})")


def _warn_if_server_is_stale(report: dict) -> None:
    """Compare the thresholds the server reports against the ones in this checkout.

    On Windows a second `uvicorn` cannot bind a port that is already held; it logs
    `[Errno 10048]` and exits, leaving an older build serving. The verdicts still look
    plausible, so the staleness is invisible. Every report carries the thresholds it
    was scored with, which makes the mismatch cheap to detect.
    """
    from app.services import similarity

    served = report.get("thresholds") or {}
    local = {
        "near_duplicate_arc": similarity._NEAR_ARC_THRESHOLD,
        "arc_alone_review": similarity._ARC_ALONE_REVIEW,
        "near_duplicate_semantic": similarity._NEAR_SEMANTIC_THRESHOLD,
    }
    drift = {k: (served[k], v) for k, v in local.items() if k in served and served[k] != v}
    if drift:
        print("\n  WARNING: the server is running older code than this checkout.")
        for name, (there, here) in drift.items():
            print(f"      {name}: server={there}  checkout={here}")
        print("      Restart it -- a second uvicorn on a taken port exits silently.\n")


def _reword(text: str) -> str:
    return " ".join(_REWRITES.get(word.lower().strip(".,!?"), word) for word in text.split())


def _rule(char: str = "-") -> None:
    print(char * 78)


def _show_matches(matches, *, label: str) -> None:
    for match in (matches or [])[:3]:
        print(f"\n  {label:<11} {match['title']}  [{match['content_id']}]")
        for name, value in (match.get("signals") or {}).items():
            if isinstance(value, (int, float)) and value:
                print(f"      {name:<20} {value:.3f}")
        if match.get("rationale"):
            print(f"      -> {match['rationale']}")


async def _delete(content_id: str) -> None:
    from pymongo import AsyncMongoClient

    from app.core.config import get_settings

    settings = get_settings()
    client = AsyncMongoClient(settings.mongo_uri)
    try:
        await client[settings.mongo_db_name].content_items.delete_one({"content_id": content_id})
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE, help="Server URL.")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--story", help="content_id to copy. Default: a random one.")
    parser.add_argument("--title", help="Title to publish the copy under.")
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Reword the story instead of copying it verbatim.",
    )
    parser.add_argument("--keep", action="store_true", help="Do not delete an accepted upload.")
    args = parser.parse_args()

    status, auth = _call(args.base, "POST", "/auth/login",
                         {"email": args.email, "password": args.password})
    if status != 200:
        sys.exit(f"Login failed ({status}): {auth}")
    token = auth["access_token"]

    if args.story:
        status, detail = _call(args.base, "GET", f"/catalog/{args.story}")
        if status != 200:
            sys.exit(f"No story {args.story} ({status}).")
        source = detail["content"]
    else:
        status, catalog = _call(args.base, "GET", "/catalog?limit=200")
        usable = [item for item in catalog if len(item.get("description") or "") > 60]
        if not usable:
            sys.exit("No story in the catalog has enough text to copy.")
        source = random.choice(usable)

    description = source.get("description") or ""
    body = _reword(description) if args.rewrite else description
    title = args.title or (f"{source['title'].split()[0]} Ka Raaz"
                           if args.rewrite else "Ek Anjaani Kahani")

    _rule("=")
    print("COPYING FROM")
    print(f"  {source['title']}   [{source['content_id']}]")
    print(f"  {description[:150]}{'...' if len(description) > 150 else ''}")
    print()
    print(f"SUBMITTING AS  ({'reworded' if args.rewrite else 'verbatim'})")
    print(f"  {title}")
    print(f"  {body[:150]}{'...' if len(body) > 150 else ''}")
    _rule("=")

    status, result = _call(
        args.base, "POST", "/catalog",
        {
            "title": title,
            "description": body,
            "transcript": body * 3,
            "language": source.get("language", "hinglish"),
            "genres": source.get("genres") or ["drama"],
            "duration_seconds": source.get("duration_seconds") or 20000,
        },
        token,
    )

    if status == 409:
        details = result["error"]["details"]
        print("\n  HTTP 409 -- BLOCKED. Nothing was written to the catalog.\n")
        print(f"  verdict     {details['risk']}")
        print(f"  reason      {details['duplicate_kind']}")
        print(f"  score       {details['top_score']}")
        _show_matches(details.get("matches"), label="matched")
        print(f"\n  {details.get('explanation', '')}")
        _rule()
        return

    if status != 201:
        sys.exit(f"Unexpected response {status}: {json.dumps(result)[:400]}")

    content_id = result["content_id"]
    gate = result.get("similarity_gate") or {}
    _warn_if_server_is_stale(gate)
    print(f"\n  HTTP 201 -- accepted as {content_id}\n")
    print(f"  verdict     {gate.get('risk', 'n/a')}")
    print(f"  reason      {gate.get('duplicate_kind', 'n/a')}")
    print(f"  score       {gate.get('top_score', 'n/a')}")
    _show_matches(gate.get("matches"), label="closest")
    if gate.get("risk") == "review":
        print("\n  Flagged for a human, not auto-rejected: a reworded story shares only its")
        print("  skeleton, and skeletons are genre tropes. Blocking on that alone would")
        print("  reject honest creators.")
    print()

    if args.keep:
        print(f"  Kept in the catalog. Remove it with:  --story {content_id}")
    else:
        asyncio.run(_delete(content_id))
        print(f"  Removed {content_id} from the catalog.")
    _rule()


if __name__ == "__main__":
    main()
