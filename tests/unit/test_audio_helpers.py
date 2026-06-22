"""Unit tests for audio document helper functions."""
from types import SimpleNamespace

from bot.handlers import _get_message_audio_source, _is_audio_document


def _document(file_name: str, mime_type: str | None = None, file_id: str = "doc1"):
    return SimpleNamespace(
        file_name=file_name,
        mime_type=mime_type,
        file_id=file_id,
        file_size=1024,
        file_unique_id="uniq-doc",
    )


def _audio(file_id: str = "audio1"):
    return SimpleNamespace(
        file_id=file_id,
        file_size=2048,
        file_unique_id="uniq-audio",
    )


def _message(audio=None, document=None):
    return SimpleNamespace(audio=audio, document=document)


class TestIsAudioDocument:
    def test_accepts_audio_mime_type(self):
        doc = _document("track.bin", mime_type="audio/mpeg")
        assert _is_audio_document(doc) is True

    def test_accepts_octet_stream_with_mp3_extension(self):
        doc = _document("track.mp3", mime_type="application/octet-stream")
        assert _is_audio_document(doc) is True

    def test_accepts_known_extensions(self):
        for name in ("song.mp3", "track.WAV", "mix.flac"):
            assert _is_audio_document(_document(name)) is True

    def test_rejects_non_audio_document(self):
        doc = _document("readme.pdf", mime_type="application/pdf")
        assert _is_audio_document(doc) is False

    def test_rejects_none(self):
        assert _is_audio_document(None) is False


class TestGetMessageAudioSource:
    def test_prefers_native_audio(self):
        message = _message(audio=_audio("native-id"), document=_document("x.mp3"))
        file_id, file_size, unique_id = _get_message_audio_source(message)
        assert file_id == "native-id"
        assert file_size == 2048
        assert unique_id == "uniq-audio"

    def test_falls_back_to_audio_document(self):
        message = _message(document=_document("clip.mp3", mime_type="audio/mpeg", file_id="doc-id"))
        file_id, file_size, unique_id = _get_message_audio_source(message)
        assert file_id == "doc-id"
        assert file_size == 1024
        assert unique_id == "uniq-doc"

    def test_octet_stream_mp3_document_returns_document_file_id(self):
        message = _message(
            document=_document(
                "track.mp3",
                mime_type="application/octet-stream",
                file_id="doc-id",
            )
        )
        file_id, file_size, unique_id = _get_message_audio_source(message)
        assert file_id == "doc-id"
        assert file_size == 1024
        assert unique_id == "uniq-doc"

    def test_returns_none_for_unrelated_document(self):
        message = _message(document=_document("notes.txt", mime_type="text/plain"))
        assert _get_message_audio_source(message) == (None, None, None)