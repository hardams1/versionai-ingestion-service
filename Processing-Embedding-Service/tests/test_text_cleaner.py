from __future__ import annotations

from app.services.text_cleaner import TextCleaner


class TestTextCleaner:
    def setup_method(self):
        self.cleaner = TextCleaner()

    def test_empty_input(self):
        assert self.cleaner.clean("") == ""
        assert self.cleaner.clean("   ") == ""

    def test_unicode_normalization(self, sample_dirty_text: str):
        result = self.cleaner.clean(sample_dirty_text)
        assert "\u00c2\u00a0" not in result
        assert "\ufffd" not in result

    def test_whitespace_normalization(self):
        text = "hello   world\t\ttabs   here"
        result = self.cleaner.clean(text)
        assert "\t" not in result
        assert "  " not in result  # no double spaces (except indent replacement)

    def test_newline_collapse(self):
        text = "paragraph 1\n\n\n\n\n\n\nparagraph 2"
        result = self.cleaner.clean(text)
        assert "\n\n\n\n" not in result
        assert "paragraph 1" in result
        assert "paragraph 2" in result

    def test_crlf_normalization(self):
        text = "line1\r\nline2\rline3\nline4"
        result = self.cleaner.clean(text)
        assert "\r" not in result
        assert "line1" in result and "line4" in result

    def test_truncation(self):
        text = "x" * 100
        result = self.cleaner.clean(text, max_length=50)
        assert len(result) == 50

    def test_preserves_valid_content(self, sample_text: str):
        result = self.cleaner.clean(sample_text)
        assert "Artificial intelligence" in result
        assert "AI applications" in result
        assert len(result) > 100
