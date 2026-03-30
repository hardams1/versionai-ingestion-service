from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Set minimal env vars so Settings can be instantiated in tests."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "faiss")
    monkeypatch.setenv("SQS_QUEUE_URL", "")

    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("FAISS_INDEX_DIR", os.path.join(tmpdir, "faiss"))
        monkeypatch.setenv("STATE_DB_PATH", os.path.join(tmpdir, "test.db"))
        yield


@pytest.fixture
def sample_text() -> str:
    return (
        "Artificial intelligence (AI) is intelligence demonstrated by machines, "
        "as opposed to natural intelligence displayed by animals including humans. "
        "AI research has been defined as the field of study of intelligent agents, "
        "which refers to any system that perceives its environment and takes actions "
        "that maximize its chance of achieving its goals.\n\n"
        "The term 'artificial intelligence' had previously been used to describe "
        "machines that mimic and display 'human' cognitive skills that are associated "
        "with the human mind, such as 'learning' and 'problem-solving'. This definition "
        "has since been rejected by major AI researchers who now describe AI in terms "
        "of rationality and acting rationally, which does not limit how intelligence "
        "can be articulated.\n\n"
        "AI applications include advanced web search engines, recommendation systems, "
        "understanding human speech, self-driving cars, automated decision-making, "
        "and competing at the highest level in strategic game systems."
    )


@pytest.fixture
def sample_dirty_text() -> str:
    return (
        "  Hello\u00c2\u00a0World  \n\n\n\n\n"
        "This\tis\ta\ttest.\r\n"
        "Unicode: caf\u00e9 na\u00efve r\u00e9sum\u00e9\n"
        "\ufffdBad char\ufffd\n"
        "Normal paragraph here."
    )
