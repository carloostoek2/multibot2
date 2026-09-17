"""Ensure Replicate model refs are version-pinned (unpinned slugs 404)."""
from bot.voice_clone import OPENVOICE_MODEL, WHISPER_MODEL


def _assert_pinned(ref: str, owner_name: str) -> None:
    assert ref.startswith(owner_name + ":"), ref
    version = ref.split(":", 1)[1]
    assert len(version) >= 32
    assert all(c in "0123456789abcdef" for c in version), version


def test_whisper_model_is_version_pinned():
    _assert_pinned(WHISPER_MODEL, "openai/whisper")


def test_openvoice_model_is_version_pinned():
    _assert_pinned(OPENVOICE_MODEL, "chenxwh/openvoice")
