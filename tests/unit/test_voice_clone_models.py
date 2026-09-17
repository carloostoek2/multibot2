"""Ensure Replicate FreeVC model ref is version-pinned (unpinned slugs 404)."""
from bot.voice_clone import FREEVC_MODEL, FREEVC_MODEL_TYPE


def _assert_pinned(ref: str, owner_name: str) -> None:
    assert ref.startswith(owner_name + ":"), ref
    version = ref.split(":", 1)[1]
    assert len(version) >= 32
    assert all(c in "0123456789abcdef" for c in version), version


def test_freevc_model_is_version_pinned():
    _assert_pinned(FREEVC_MODEL, "jagilley/free-vc")


def test_freevc_model_type_is_24khz_enum():
    # Exact OpenAPI enum from jagilley/free-vc (not "FreeVC (24k)").
    assert FREEVC_MODEL_TYPE == "FreeVC (24kHz)"
