from app.conversation import ConversationStore
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
