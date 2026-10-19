"""Concurrency tests: IG download gate + per-user ordered update processor."""
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import bot.downloaders.platforms.instagram as ig
from bot.handlers import IG_QUEUED_MESSAGE, _run_download_with_instagram_gate
from bot.telegram_client import PerUserOrderedUpdateProcessor, _per_user_lane_key

IG_URL = "https://www.instagram.com/reel/ABC123/"
DELAY = 0.3


@pytest.fixture(autouse=True)
def _reset_ig_state():
    ig._last_instagram_download_end = 0.0
    # Fresh locks per test: pytest-asyncio gives each test its own event loop and
    # asyncio.Lock binds to the first loop that contends on it.
    with patch.object(ig, "_get_instagram_delay_config", return_value=(DELAY, DELAY)), \
         patch.object(ig, "_IG_CANCEL_POLL_SECONDS", 0.05), \
         patch.object(ig, "_instagram_download_gate", asyncio.Lock()), \
         patch.object(ig, "_instagram_delay_lock", asyncio.Lock()):
        yield
    ig._last_instagram_download_end = 0.0


def _ctx():
    return SimpleNamespace(user_data={})


class _Edits:
    def __init__(self):
        self.texts = []

    async def __call__(self, text):
        self.texts.append(text)


@pytest.mark.asyncio
async def test_two_instagram_downloads_are_serialized_and_spaced():
    spans = []

    def make_download(name):
        async def _dl():
            start = time.monotonic()
            await asyncio.sleep(0.1)
            spans.append((name, start, time.monotonic()))
            return name
        return _dl

    edits_b = _Edits()
    a = asyncio.create_task(_run_download_with_instagram_gate(
        url=IG_URL, correlation_id="a", context=_ctx(), edit=_Edits(),
        restore_text="Descargando...", do_download=make_download("a")))
    await asyncio.sleep(0.01)  # let A take the gate first
    b = asyncio.create_task(_run_download_with_instagram_gate(
        url=IG_URL, correlation_id="b", context=_ctx(), edit=edits_b,
        restore_text="Descargando...", do_download=make_download("b")))

    assert await asyncio.wait_for(asyncio.gather(a, b), timeout=5) == ["a", "b"]
    (_, a_start, a_end), (_, b_start, b_end) = sorted(spans, key=lambda s: s[1])
    assert b_start >= a_end, "downloads overlapped"
    assert b_start - a_end >= DELAY * 0.9, "inter-download delay not applied"
    # B told the user it was queued, then about the delay, then restored the text.
    assert edits_b.texts[0] == IG_QUEUED_MESSAGE
    assert any("Aplicando delay" in t for t in edits_b.texts)
    assert edits_b.texts[-1] == "Descargando..."
    assert not ig.instagram_gate_busy()


@pytest.mark.asyncio
async def test_cancel_while_queued_skips_download_and_frees_nothing_else():
    ctx_b = _ctx()
    ran = []
    release_a = asyncio.Event()

    async def dl_a():
        await release_a.wait()
        return "a"

    async def dl_b():
        ran.append("b")
        return "b"

    a = asyncio.create_task(_run_download_with_instagram_gate(
        url=IG_URL, correlation_id="a", context=_ctx(), edit=_Edits(),
        restore_text="x", do_download=dl_a))
    await asyncio.sleep(0.01)
    b = asyncio.create_task(_run_download_with_instagram_gate(
        url=IG_URL, correlation_id="b", context=ctx_b, edit=_Edits(),
        restore_text="x", do_download=dl_b))
    await asyncio.sleep(0.1)
    ctx_b.user_data["download_status_b"] = "cancelled"
    assert await asyncio.wait_for(b, timeout=2) is None
    assert ran == []
    assert ig.instagram_gate_busy()  # A still holds it
    release_a.set()
    assert await asyncio.wait_for(a, timeout=2) == "a"
    assert not ig.instagram_gate_busy()


@pytest.mark.asyncio
async def test_cancel_during_delay_returns_quickly():
    ig._last_instagram_download_end = time.monotonic()  # force a full delay
    ctx = _ctx()
    ran = []

    async def dl():
        ran.append(1)

    task = asyncio.create_task(_run_download_with_instagram_gate(
        url=IG_URL, correlation_id="c", context=ctx, edit=_Edits(),
        restore_text="x", do_download=dl))
    await asyncio.sleep(0.05)
    ctx.user_data["download_status_c"] = "cancelled"
    assert await asyncio.wait_for(task, timeout=DELAY) is None
    assert ran == []
    assert not ig.instagram_gate_busy()


@pytest.mark.asyncio
async def test_non_instagram_urls_bypass_the_gate():
    await ig._instagram_download_gate.acquire()
    try:
        async def dl():
            return "yt"
        result = await asyncio.wait_for(_run_download_with_instagram_gate(
            url="https://youtube.com/watch?v=x", correlation_id="y", context=_ctx(),
            edit=_Edits(), restore_text="x", do_download=dl), timeout=1)
        assert result == "yt"
    finally:
        ig._instagram_download_gate.release()


def _cb_update(user_id=1):
    return SimpleNamespace(message=None, edited_message=None,
                           callback_query=SimpleNamespace(data="screenshot:abc"),
                           effective_chat=SimpleNamespace(id=user_id),
                           effective_user=SimpleNamespace(id=user_id))


def _msg_update(text=None, user_id=1):
    return SimpleNamespace(message=SimpleNamespace(text=text), edited_message=None,
                           callback_query=None,
                           effective_chat=SimpleNamespace(id=user_id),
                           effective_user=SimpleNamespace(id=user_id))


@pytest.mark.asyncio
async def test_screenshot_callback_not_blocked_by_sleeping_instagram_download():
    """A download handler sleeping in the IG delay must not block a screenshot tap."""
    processor = PerUserOrderedUpdateProcessor(32)
    ig._last_instagram_download_end = time.monotonic()  # IG download will sleep DELAY
    screenshot_done = asyncio.Event()
    order = []

    async def ig_download_handler():
        async def dl():
            order.append("download")
        await _run_download_with_instagram_gate(
            url=IG_URL, correlation_id="d", context=_ctx(), edit=_Edits(),
            restore_text="x", do_download=dl)

    async def screenshot_handler():
        order.append("screenshot")
        screenshot_done.set()

    # Download arrives as a URL text message (the reel-link flow), then a button tap.
    dl_task = asyncio.create_task(processor.process_update(_msg_update(IG_URL), ig_download_handler()))
    await asyncio.sleep(0.02)
    sc_task = asyncio.create_task(processor.process_update(_cb_update(), screenshot_handler()))
    await asyncio.wait_for(screenshot_done.wait(), timeout=DELAY / 2)
    assert order == ["screenshot"]  # served while the download is still waiting
    await asyncio.wait_for(asyncio.gather(dl_task, sc_task), timeout=3)
    assert order == ["screenshot", "download"]


@pytest.mark.asyncio
async def test_messages_of_one_user_keep_arrival_order():
    processor = PerUserOrderedUpdateProcessor(32)
    order = []

    async def handler(name, delay):
        await asyncio.sleep(delay)
        order.append(name)

    tasks = [
        asyncio.create_task(processor.process_update(_msg_update(None), handler("video1", 0.1))),
        asyncio.create_task(processor.process_update(_msg_update(None), handler("video2", 0.0))),
        asyncio.create_task(processor.process_update(_msg_update("/done"), handler("done", 0.0))),
    ]
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)
    assert order == ["video1", "video2", "done"]
    assert processor._lanes == {}


def test_lane_key_rules():
    assert _per_user_lane_key(_cb_update()) is None
    assert _per_user_lane_key(_msg_update(IG_URL)) is None
    assert _per_user_lane_key(_msg_update("/download https://x.y")) is None
    assert _per_user_lane_key(_msg_update("/download@mybot")) is None
    assert _per_user_lane_key(_msg_update("1:30, 2:45")) == (1, 1)
    assert _per_user_lane_key(_msg_update("/done")) == (1, 1)
    assert _per_user_lane_key(_msg_update(None)) == (1, 1)  # media upload
