from __future__ import annotations

from tauri_assistant.chat.retrieval import Passage
from tauri_assistant.eval.dataset import QuestionItem
from tauri_assistant.eval.metrics import context_tokens, hit_rate, is_relevant, mrr, precision_at_k


def make_passage(document_id: str, heading_path: str, score: float = 0.5) -> Passage:
    return Passage(
        text=f"text for {document_id}",
        metadata={"document_id": document_id, "heading_path": heading_path},
        score=score,
    )


def make_item(
    expected_document_ids: tuple[str, ...] = (), expected_heading_path: str = ""
) -> QuestionItem:
    return QuestionItem(
        id="q1",
        question="how do I foo?",
        source="js-api",
        kind="js-symbol",
        expected_document_ids=expected_document_ids,
        expected_heading_path=expected_heading_path,
    )


class TestIsRelevant:
    def test_matches_on_document_id(self):
        item = make_item(expected_document_ids=("js-api:app/getVersion",))
        passage = make_passage("js-api:app/getVersion", "app > something else")
        assert is_relevant(passage, item)

    def test_matches_on_heading_path_substring_case_insensitive(self):
        item = make_item(expected_heading_path="App > getVersion")
        passage = make_passage("other-id", "@tauri-apps/api > app > getVersion")
        assert is_relevant(passage, item)

    def test_no_match(self):
        item = make_item(expected_document_ids=("a",), expected_heading_path="zzz")
        passage = make_passage("b", "unrelated > heading")
        assert not is_relevant(passage, item)


class TestHitRate:
    def test_hit_when_any_passage_relevant(self):
        item = make_item(expected_heading_path="getVersion")
        passages = [make_passage("a", "unrelated"), make_passage("b", "app > getVersion")]
        assert hit_rate(passages, item) == 1.0

    def test_miss_when_none_relevant(self):
        item = make_item(expected_heading_path="getVersion")
        passages = [make_passage("a", "unrelated"), make_passage("b", "also unrelated")]
        assert hit_rate(passages, item) == 0.0

    def test_empty_passages_is_a_miss(self):
        item = make_item(expected_heading_path="getVersion")
        assert hit_rate([], item) == 0.0


class TestMRR:
    def test_reciprocal_rank_of_first_relevant(self):
        item = make_item(expected_heading_path="getVersion")
        passages = [
            make_passage("a", "unrelated"),
            make_passage("b", "unrelated too"),
            make_passage("c", "app > getVersion"),
        ]
        assert mrr(passages, item) == 1 / 3

    def test_first_result_relevant(self):
        item = make_item(expected_heading_path="getVersion")
        passages = [make_passage("a", "app > getVersion")]
        assert mrr(passages, item) == 1.0

    def test_no_relevant_result(self):
        item = make_item(expected_heading_path="getVersion")
        assert mrr([make_passage("a", "unrelated")], item) == 0.0


class TestPrecisionAtK:
    def test_fraction_of_relevant(self):
        item = make_item(expected_heading_path="getVersion")
        passages = [
            make_passage("a", "app > getVersion"),
            make_passage("b", "unrelated"),
            make_passage("c", "unrelated"),
            make_passage("d", "app > getVersion"),
        ]
        assert precision_at_k(passages, item) == 0.5

    def test_empty_passages(self):
        item = make_item(expected_heading_path="getVersion")
        assert precision_at_k([], item) == 0.0


class TestContextTokens:
    def test_counts_tokens(self):
        assert context_tokens("") == 0
        assert context_tokens("hello world") > 0

    def test_longer_text_has_more_tokens(self):
        short = context_tokens("hello")
        long = context_tokens("hello " * 50)
        assert long > short
