"""Unit tests for the Seed-VC HTTP backend and backend selection (HTTP mocked)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from bot import voice_clone as vc


@pytest.fixture
def seedvc_files(tmp_path, monkeypatch):
    url_file = tmp_path / "url.txt"
    key_file = tmp_path / "api_key"
    url_file.write_text("https://seedvc.example.test/\n")
    key_file.write_text("test-key\n")
    monkeypatch.setenv("SEEDVC_URL_FILE", str(url_file))
    monkeypatch.setenv("SEEDVC_API_KEY_FILE", str(key_file))
    monkeypatch.delenv("VOICE_CLONE_BACKEND", raising=False)
    src = tmp_path / "src.wav"; src.write_bytes(b"RIFFsrc")
    ref = tmp_path / "ref.wav"; ref.write_bytes(b"RIFFref")
    return {"url_file": url_file, "src": src, "ref": ref, "tmp": tmp_path}


def _mock(monkeypatch, handler, calls=None):
    def factory(timeout):
        if calls is not None:
            calls.append(timeout)
        return httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout)
    monkeypatch.setattr(vc, "_http_client", factory)


def test_run_seedvc_http_success(seedvc_files, monkeypatch):
    seen = {}
    def handler(req):
        seen["url"] = str(req.url); seen["key"] = req.headers.get("X-API-Key")
        seen["body"] = req.read()
        return httpx.Response(200, content=b"RIFFout", headers={"content-type": "audio/wav"})
    timeouts = []
    _mock(monkeypatch, handler, timeouts)
    out = vc.run_seedvc_http(seedvc_files["src"], seedvc_files["ref"], diffusion_steps=12, pitch_shift=-2)
    assert isinstance(out, str) and Path(out).read_bytes() == b"RIFFout"
    assert seen["url"] == "https://seedvc.example.test/convert"
    assert seen["key"] == "test-key"
    body = seen["body"]
    assert b'name="source"' in body and b'name="reference"' in body
    assert b'name="diffusion_steps"' in body and b"12" in body and b"-2" in body
    assert timeouts == [vc.SEEDVC_CONVERT_TIMEOUT]


def test_run_seedvc_http_401(seedvc_files, monkeypatch):
    _mock(monkeypatch, lambda r: httpx.Response(401, json={"error": "unauthorized"}))
    with pytest.raises(vc.VoiceCloneError, match="401"):
        vc.run_seedvc_http(seedvc_files["src"], seedvc_files["ref"])


def test_run_seedvc_http_500_json_error(seedvc_files, monkeypatch):
    _mock(monkeypatch, lambda r: httpx.Response(500, json={"error": "CUDA OOM"}))
    with pytest.raises(vc.VoiceCloneError, match="CUDA OOM"):
        vc.run_seedvc_http(seedvc_files["src"], seedvc_files["ref"])


def test_run_seedvc_http_no_url(seedvc_files, monkeypatch):
    seedvc_files["url_file"].write_text("")
    with pytest.raises(vc.VoiceCloneError):
        vc.run_seedvc_http(seedvc_files["src"], seedvc_files["ref"])


def test_url_read_fresh_each_call(seedvc_files, monkeypatch):
    assert vc.get_seedvc_url() == "https://seedvc.example.test"
    seedvc_files["url_file"].write_text("https://other.test")
    assert vc.get_seedvc_url() == "https://other.test"
    seedvc_files["url_file"].unlink()
    assert vc.get_seedvc_url() == ""


@pytest.mark.parametrize("status,payload,expected", [
    (200, {"ok": True, "model_loaded": True}, True),
    (200, {"ok": True, "model_loaded": False}, False),
    (503, {"error": "loading"}, False),
])
def test_health(seedvc_files, monkeypatch, status, payload, expected):
    _mock(monkeypatch, lambda r: httpx.Response(status, json=payload))
    assert vc.seedvc_health() is expected


def test_health_network_error(seedvc_files, monkeypatch):
    def handler(r):
        raise httpx.ConnectTimeout("boom")
    _mock(monkeypatch, handler)
    assert vc.seedvc_health() is False


def test_resolve_backend(seedvc_files, monkeypatch):
    monkeypatch.setattr(vc, "seedvc_health", lambda timeout=3.0: True)
    assert vc.resolve_backend() == "seedvc"
    monkeypatch.setattr(vc, "seedvc_health", lambda timeout=3.0: False)
    assert vc.resolve_backend() == "replicate"
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "seedvc")
    assert vc.resolve_backend() == "seedvc"
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "replicate")
    monkeypatch.setattr(vc, "seedvc_health", lambda timeout=3.0: True)
    assert vc.resolve_backend() == "replicate"
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "bogus")
    assert vc.resolve_backend() == "seedvc"


@pytest.fixture
def pipeline_stubs(monkeypatch):
    calls = {"seedvc": 0, "freevc": 0}
    monkeypatch.setattr(vc, "_convert_to_wav", lambda s, d: Path(d).write_bytes(b"RIFF"))
    monkeypatch.setattr(vc, "_convert_to_mp3", lambda s, d: Path(d).write_bytes(b"MP3"))
    def fake_dl(url, dest):
        Path(dest).write_bytes(b"RIFFrep"); return Path(dest)
    monkeypatch.setattr(vc, "download_url_to_file", fake_dl)
    def fake_freevc(*a, **k):
        calls["freevc"] += 1; return "https://replicate.delivery/x/out.wav"
    monkeypatch.setattr(vc, "run_freevc", fake_freevc)
    return calls


def _seed_ok(calls):
    def f(src, ref, *, output_path, **k):
        calls["seedvc"] += 1; Path(output_path).write_bytes(b"RIFFseed"); return str(output_path)
    return f


def _seed_fail(calls):
    def f(*a, **k):
        calls["seedvc"] += 1; raise vc.VoiceCloneError("Seed-VC falló (HTTP 500): x")
    return f


def test_pipeline_auto_uses_seedvc_without_replicate_token(seedvc_files, monkeypatch, pipeline_stubs):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    monkeypatch.setattr(vc, "run_seedvc_http", _seed_ok(pipeline_stubs))
    out = vc.clone_voice_pipeline(seedvc_files["src"], seedvc_files["ref"],
                                  seedvc_files["tmp"] / "o.mp3", api_token=None, backend="seedvc")
    assert out.read_bytes() == b"MP3"
    assert pipeline_stubs == {"seedvc": 1, "freevc": 0}


def test_pipeline_auto_falls_back_on_seedvc_failure(seedvc_files, monkeypatch, pipeline_stubs):
    monkeypatch.setattr(vc, "run_seedvc_http", _seed_fail(pipeline_stubs))
    vc.clone_voice_pipeline(seedvc_files["src"], seedvc_files["ref"],
                            seedvc_files["tmp"] / "o.mp3", api_token="r8_dummy", backend="seedvc")
    assert pipeline_stubs == {"seedvc": 1, "freevc": 1}


def test_pipeline_explicit_seedvc_no_fallback(seedvc_files, monkeypatch, pipeline_stubs):
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "seedvc")
    monkeypatch.setattr(vc, "run_seedvc_http", _seed_fail(pipeline_stubs))
    with pytest.raises(vc.VoiceCloneError):
        vc.clone_voice_pipeline(seedvc_files["src"], seedvc_files["ref"],
                                seedvc_files["tmp"] / "o.mp3", api_token="r8_dummy")
    assert pipeline_stubs["freevc"] == 0


def test_pipeline_replicate_requires_token(seedvc_files, monkeypatch, pipeline_stubs):
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "replicate")
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    with pytest.raises(vc.VoiceCloneError, match="REPLICATE_API_TOKEN"):
        vc.clone_voice_pipeline(seedvc_files["src"], seedvc_files["ref"], seedvc_files["tmp"] / "o.mp3")


def test_pipeline_auto_health_down_uses_replicate(seedvc_files, monkeypatch, pipeline_stubs):
    monkeypatch.setattr(vc, "seedvc_health", lambda timeout=3.0: False)
    vc.clone_voice_pipeline(seedvc_files["src"], seedvc_files["ref"],
                            seedvc_files["tmp"] / "o.mp3", api_token="r8_dummy")
    assert pipeline_stubs == {"seedvc": 0, "freevc": 1}
