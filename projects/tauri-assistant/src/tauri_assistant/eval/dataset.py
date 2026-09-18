"""The golden question set: `question -> (document_id, heading_path
substring)`, never a chunk id.

Chunk ids are content-addressed hashes of breadcrumb+text (`ingest/types.py`)
-- they change whenever chunking does, so grading against them would
silently invalidate the dataset the moment two chunkers were compared.
`document_id` is path/symbol-derived (`tauri-docs:develop/foo.mdx`,
`js-api:app/getVersion`) and stays stable across every variant in the
matrix.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "evalset" / "questions.jsonl"


@dataclass(frozen=True, slots=True)
class QuestionItem:
    id: str
    question: str
    source: str  # tauri-docs | rust-api | js-api | plugin-permissions
    kind: str  # guide | rust-fn | js-symbol | permission-set | ...
    expected_document_ids: tuple[str, ...]
    expected_heading_path: str  # substring match, case-insensitive
    origin_chunk_id: str = ""  # the chunk this was generated from, for auditing -- not graded against
    seed: bool = False  # hand-verified seed item (git history), never dropped by the verifier


def to_row(item: QuestionItem) -> dict:
    return asdict(item)


def from_row(row: dict) -> QuestionItem:
    return QuestionItem(
        id=row["id"],
        question=row["question"],
        source=row["source"],
        kind=row["kind"],
        expected_document_ids=tuple(row["expected_document_ids"]),
        expected_heading_path=row["expected_heading_path"],
        origin_chunk_id=row.get("origin_chunk_id", ""),
        seed=row.get("seed", False),
    )


def load(path: Path = DEFAULT_PATH) -> list[QuestionItem]:
    if not path.exists():
        return []
    items = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(from_row(json.loads(line)))
    return items


def save(items: Iterable[QuestionItem], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(to_row(item), sort_keys=True) + "\n")


def by_source(items: Iterable[QuestionItem]) -> dict[str, list[QuestionItem]]:
    grouped: dict[str, list[QuestionItem]] = {}
    for item in items:
        grouped.setdefault(item.source, []).append(item)
    return grouped


# ---- The ~15 hand-verified seed items, recovered from the prior
# implementation (git commit 08dcbda, eval/dataset.py). Each was checked
# against the live corpus via `tauri-assistant search` rather than guessed.
# `seed=True` so the verification pass in `eval/generate.py` never drops
# these regardless of leakage/answerability heuristics.
SEED_ITEMS: tuple[QuestionItem, ...] = (
    QuestionItem(
        id="seed-js-get-version",
        question="How do I get the app's version number from the frontend JavaScript API?",
        source="js-api",
        kind="js-symbol",
        expected_document_ids=("js-api:app/getVersion",),
        expected_heading_path="app > getVersion",
        seed=True,
    ),
    QuestionItem(
        id="seed-js-get-name",
        question="How do I get the name of a Tauri application from the frontend JS API?",
        source="js-api",
        kind="js-symbol",
        expected_document_ids=("js-api:app/getName",),
        expected_heading_path="app > getName",
        seed=True,
    ),
    QuestionItem(
        id="seed-perm-fs-read",
        question="How do I check whether the fs plugin is allowed to read a file?",
        source="plugin-permissions",
        kind="permission-permission",
        expected_document_ids=(),
        expected_heading_path="fs plugin > permissions > allow-read-file",
        seed=True,
    ),
    QuestionItem(
        id="seed-perm-autostart-disable",
        question=(
            "What is the permission identifier that allows disabling autostart, "
            "for the autostart plugin?"
        ),
        source="plugin-permissions",
        kind="permission-permission",
        expected_document_ids=(),
        expected_heading_path="autostart plugin > permissions > allow-disable",
        seed=True,
    ),
    QuestionItem(
        id="seed-guide-tray",
        question="How do I create a system tray icon in a Tauri app?",
        source="tauri-docs",
        kind="guide",
        expected_document_ids=(),
        expected_heading_path="learn/system-tray",
        seed=True,
    ),
)


def merge_seed(items: list[QuestionItem]) -> list[QuestionItem]:
    """Seed items first, then generated ones -- generated items never
    replace a seed with the same id."""
    seed_ids = {item.id for item in SEED_ITEMS}
    return list(SEED_ITEMS) + [item for item in items if item.id not in seed_ids]


def iter_ids(items: Iterable[QuestionItem]) -> Iterator[str]:
    yield from (item.id for item in items)


__all__ = [
    "DEFAULT_PATH",
    "SEED_ITEMS",
    "QuestionItem",
    "by_source",
    "from_row",
    "iter_ids",
    "load",
    "merge_seed",
    "save",
    "to_row",
]
