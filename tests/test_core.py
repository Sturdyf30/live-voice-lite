import asyncio

from app.conversation import ConversationStore
from app.main import _AUDIO_ID_RE
from app.text_utils import text_for_speech


def test_history_is_trimmed_by_turn() -> None:
    store = ConversationStore(history_turns=2)
    for index in range(3):
        store.append_turn("s", f"u{index}", f"a{index}")
    assert store.messages("s") == [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]


def test_reset_preserves_session_lock() -> None:
    store = ConversationStore(history_turns=2)
    original_lock = store.lock("s")
    store.append_turn("s", "hello", "hi")
    store.reset("s")
    assert store.messages("s") == []
    assert store.lock("s") is original_lock
    assert isinstance(original_lock, asyncio.Lock)


def test_audio_id_pattern_is_exact() -> None:
    assert _AUDIO_ID_RE.fullmatch("a" * 32 + ".mp3")
    assert not _AUDIO_ID_RE.fullmatch("../" + "a" * 32 + ".mp3")
    assert not _AUDIO_ID_RE.fullmatch("a.mp3")


def test_tts_cleanup_removes_markdown_and_code() -> None:
    text = "**Hello** [site](https://example.com) ```python\nprint('x')\n```"
    spoken = text_for_speech(text, 500)
    assert "https://" not in spoken
    assert "print" not in spoken
    assert "site" in spoken


def test_tts_cleanup_clips_long_text() -> None:
    spoken = text_for_speech("word " * 1000, 80)
    assert len(spoken) < 130
    assert spoken.endswith("The rest is in the transcript.")
