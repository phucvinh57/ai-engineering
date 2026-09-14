from tauri_assistant.eval.metrics import hit_rate, mrr, precision_at_k
from tauri_assistant.rag.retriever import RetrievedChunk


def _chunk(heading_path: str = "", url: str = "", score: float = 1.0) -> RetrievedChunk:
    return RetrievedChunk(text="text", heading_path=heading_path, url=url, source="guide", score=score)


def test_hit_rate_and_mrr_are_zero_when_nothing_matches() -> None:
    chunks = [_chunk("unrelated > topic"), _chunk("also > unrelated")]
    assert hit_rate(chunks, ("plugin/updater",)) == 0.0
    assert mrr(chunks, ("plugin/updater",)) == 0.0


def test_hit_rate_and_mrr_when_relevant_chunk_is_first() -> None:
    chunks = [_chunk("plugin/updater > install"), _chunk("unrelated > topic")]
    assert hit_rate(chunks, ("plugin/updater",)) == 1.0
    assert mrr(chunks, ("plugin/updater",)) == 1.0


def test_match_is_case_insensitive_on_heading_or_url() -> None:
    heading_only = [_chunk(heading_path="Plugin/Updater > Install")]
    url_only = [_chunk(url="https://tauri.app/PLUGIN/UPDATER")]
    assert hit_rate(heading_only, ("plugin/updater",)) == 1.0
    assert hit_rate(url_only, ("plugin/updater",)) == 1.0


def test_mrr_reflects_rank_of_first_relevant_chunk() -> None:
    chunks = [_chunk("unrelated"), _chunk("also unrelated"), _chunk("plugin/updater > install")]
    assert mrr(chunks, ("plugin/updater",)) == 1.0 / 3


def test_precision_at_k_counts_all_relevant_chunks() -> None:
    chunks = [
        _chunk("plugin/updater > install"),
        _chunk("unrelated"),
        _chunk("plugin/updater > config"),
    ]
    assert precision_at_k(chunks, ("plugin/updater",)) == 2 / 3


def test_precision_at_k_is_zero_for_empty_results() -> None:
    assert precision_at_k([], ("plugin/updater",)) == 0.0
