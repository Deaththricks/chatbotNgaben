"""
apply_review.py -- fold human decisions from review_queue.jsonl into a
persistent review_decisions.json that build_kb.py honours on its next run.

Workflow (from Graphing/kb/ unless noted):
  1. python build_kb.py                 -> writes output/review_queue.jsonl (blank decisions)
  2. edit output/review_queue.jsonl     -> set each record's "decision" to one of:
        accept                     keep the edge (bumped to MED/HIGH)
        reject                     drop the edge entirely
        fix: <subj> | <PRED> | <obj>   replace the triple, then keep it
  3. python curation/apply_review.py    -> merges those into tuning/review_decisions.json
  4. python build_kb.py                 -> rebuilds; decided edges are applied,
                                           output/review_queue.jsonl shrinks

tuning/review_decisions.json is the source of truth and is safe to hand-edit or commit.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUEUE = HERE.parent / "output" / "review_queue.jsonl"
STORE = HERE.parent / "tuning" / "review_decisions.json"

VALID_PREFIXES = ("accept", "reject", "fix:")


def read_jsonl(path):
    return [json.loads(b) for b in path.read_text(encoding="utf-8").split("\n\n")
            if b.strip()]


def main():
    if not QUEUE.exists():
        print("no review_queue.jsonl -- run build_kb.py first")
        return

    store = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    added, skipped, bad = 0, 0, 0

    for rec in read_jsonl(QUEUE):
        dec = (rec.get("decision") or "").strip()
        key = rec.get("key")
        if not dec:
            continue
        if not key:
            skipped += 1
            continue
        if not dec.startswith(VALID_PREFIXES):
            print(f"  ! unrecognised decision {dec!r} for {key}")
            bad += 1
            continue
        if dec.startswith("fix:") and len(dec[4:].split("|")) != 3:
            print(f"  ! fix must be 'fix: subj | PRED | obj' -- got {dec!r}")
            bad += 1
            continue
        if store.get(key) != dec:
            store[key] = dec
            added += 1

    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"decisions stored : {len(store)}  (+{added} this run, {bad} rejected, "
          f"{skipped} missing key)")
    print(f"wrote {STORE.name}  ->  now re-run:  python build_kb.py")


if __name__ == "__main__":
    main()
