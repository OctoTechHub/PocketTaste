"""Export PocketTaste behavior from MongoDB into RecBole atomic-file format.

Produces dataset/pockettaste/pockettaste.inter so the exact same benchmark can be
run on real PocketTaste signals instead of MovieLens — the bridge from our live
event log to the RecBole model R&D loop.

    python export_pockettaste.py
    python run_benchmark.py --dataset pockettaste
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# Reuse the server's .env so the connection string lives in one place.
load_dotenv(Path(__file__).resolve().parents[1] / "server" / ".env")

# Implicit-feedback weight per event type: higher = stronger positive signal.
EVENT_RATING = {
    "complete_series": 5,
    "coin_unlock": 5,
    "complete_episode": 4,
    "play": 3,
    "rate": 4,
    "skip_intro": 2,
    "drop": 1,
}

OUT_DIR = Path(__file__).resolve().parent / "dataset" / "pockettaste"


def main() -> None:
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise SystemExit("DB_URL not found (checked server/.env)")

    db = MongoClient(db_url, serverSelectionTimeoutMS=15_000).get_default_database()
    events = list(db["events"].find())
    if not events:
        raise SystemExit("No events found — run the server seed first.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    inter_path = OUT_DIR / "pockettaste.inter"

    with inter_path.open("w", encoding="utf-8") as f:
        # RecBole atomic-file header: field name + type.
        f.write("user_id:token\titem_id:token\trating:float\ttimestamp:float\n")
        written = 0
        for e in events:
            rating = EVENT_RATING.get(e.get("type", ""), 2)
            # Store timestamp in seconds for RecBole's TIME_FIELD.
            ts = float(e.get("ts", 0)) / 1000.0
            f.write(f"{e['user_id']}\t{e['series_id']}\t{rating}\t{ts}\n")
            written += 1

    print(f"[export] wrote {written} interactions -> {inter_path}")
    print("[export] now run: python run_benchmark.py --dataset pockettaste")


if __name__ == "__main__":
    main()
