"""On-demand Seed-VC start: state file, start_request and polling (all mocked)."""
from __future__ import annotations

import asyncio

import pytest

from bot import voice_clone as vc


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    async def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name in ("url.txt", "state"):
        (tmp_path / name).write_text("")
    monkeypatch.setenv("SEEDVC_URL_FILE", str(tmp_path / "url.txt"))
    monkeypatch.setenv("SEEDVC_STATE_FILE", str(tmp_path / "state"))
    monkeypatch.setenv("SEEDVC_START_REQUEST_FILE", str(tmp_path / "start_request"))
    for v in ("VOICE_CLONE_BACKEND", "SEEDVC_START_WAIT", "SEEDVC_POLL_INTERVAL", "SEEDVC_DOWN_GRACE"):
        monkeypatch.delenv(v, raising=False)
    return tmp_path


def _run(ft, **kw):
    notes = []

    async def on_starting():
        notes.append(vc.SEEDVC_STARTING_MESSAGE)

    kw.setdefault("has_replicate_token", True)
    res = asyncio.run(vc.resolve_backend_ondemand(on_starting=on_starting, sleep=ft.sleep, clock=ft.clock, **kw))
    return res, notes


def test_ready_direct(env, monkeypatch):
    monkeypatch.setattr(vc, "seedvc_health", lambda: True)
    ft = FakeTime()
    assert _run(ft) == (vc.BACKEND_SEEDVC, [])
    assert not (env / "start_request").exists() and ft.sleeps == []


def test_start_ok_after_polling(env, monkeypatch):
    (env / "state").write_text("starting\n")
    ft = FakeTime()
    monkeypatch.setattr(vc, "seedvc_health", lambda: ft.now >= 60)
    res, notes = _run(ft)
    assert res == vc.BACKEND_SEEDVC
    assert notes == [vc.SEEDVC_STARTING_MESSAGE]
    assert (env / "start_request").exists()
    assert ft.now == 60 and set(ft.sleeps) == {5.0}


def test_timeout_falls_back_to_replicate(env, monkeypatch):
    (env / "state").write_text("starting")
    monkeypatch.setattr(vc, "seedvc_health", lambda: False)
    ft = FakeTime()
    res, notes = _run(ft)
    assert res == vc.BACKEND_REPLICATE and notes
    assert ft.now == 150


def test_cooldown_goes_to_replicate_immediately(env, monkeypatch):
    (env / "state").write_text("cooldown")
    monkeypatch.setattr(vc, "seedvc_health", lambda: False)
    ft = FakeTime()
    assert _run(ft) == (vc.BACKEND_REPLICATE, [])
    assert ft.sleeps == []


def test_down_gets_grace_then_replicate(env, monkeypatch):
    (env / "state").write_text("down")
    monkeypatch.setattr(vc, "seedvc_health", lambda: False)
    ft = FakeTime()
    res, _ = _run(ft)
    assert res == vc.BACKEND_REPLICATE and ft.now == 15


def test_explicit_seedvc_waits_and_never_falls_back(env, monkeypatch):
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "seedvc")
    monkeypatch.setenv("SEEDVC_START_WAIT", "30")
    (env / "state").write_text("down")
    monkeypatch.setattr(vc, "seedvc_health", lambda: False)
    ft = FakeTime()
    res, notes = _run(ft)
    assert res == vc.BACKEND_SEEDVC and notes and ft.now == 30


def test_explicit_seedvc_becomes_ready(env, monkeypatch):
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "seedvc")
    (env / "state").write_text("starting")
    ft = FakeTime()
    monkeypatch.setattr(vc, "seedvc_health", lambda: ft.now >= 10)
    assert _run(ft, has_replicate_token=False)[0] == vc.BACKEND_SEEDVC


def test_auto_without_token_keeps_waiting(env, monkeypatch):
    (env / "state").write_text("cooldown")
    monkeypatch.setattr(vc, "seedvc_health", lambda: False)
    ft = FakeTime()
    res, _ = _run(ft, has_replicate_token=False)
    assert res == vc.BACKEND_REPLICATE and ft.now == 150


def test_replicate_configured_skips_everything(env, monkeypatch):
    monkeypatch.setenv("VOICE_CLONE_BACKEND", "replicate")
    monkeypatch.setattr(vc, "seedvc_health", lambda: pytest.fail("no health"))
    assert _run(FakeTime())[0] == vc.BACKEND_REPLICATE
    assert not (env / "start_request").exists()
