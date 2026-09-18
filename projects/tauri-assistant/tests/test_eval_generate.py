from __future__ import annotations

from tauri_assistant.eval.generate import has_leakage


class TestHasLeakage:
    def test_verbatim_phrase_is_leakage(self):
        chunk_text = "Call the getVersion function from the app module to retrieve the version"
        question = "What does calling the getVersion function from the app module actually return?"
        assert has_leakage(question, chunk_text)

    def test_paraphrased_question_is_not_leakage(self):
        chunk_text = "Call the getVersion function from the app module to retrieve the version"
        question = "How can a frontend script find out which release of my app is running?"
        assert not has_leakage(question, chunk_text)

    def test_short_question_never_flagged(self):
        # Fewer than n=5 words -- no 5-gram exists, so nothing to compare.
        assert not has_leakage("What is Tauri?", "Tauri is a framework for building apps.")

    def test_case_and_punctuation_insensitive(self):
        chunk_text = "The allow-read-file permission enables reading a single file from disk"
        question = "Which permission enables READING a single file from disk?"
        assert has_leakage(question, chunk_text)

    def test_empty_chunk_text_never_leaks(self):
        assert not has_leakage("How do I get the app version from JavaScript?", "")
