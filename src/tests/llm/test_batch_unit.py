from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.llm.batch import AnthropicBatchClient, BatchItem
from clinicai.llm.models import MAIN_BRAIN_MODEL


def _patch(
    monkeypatch: pytest.MonkeyPatch, target: object, attr: str, mock: AsyncMock
) -> AsyncMock:
    """Swap out an SDK coroutine and hand the mock back for assertions.

    Assigning over the method directly would work at runtime but hides the mock
    from the type checker, so `.call_args` reads as an error on the real method.
    """
    monkeypatch.setattr(target, attr, mock)
    return mock


async def _aiter(items: list[Any]) -> AsyncIterator[Any]:
    for i in items:
        yield i


def _succeeded(custom_id: str, text: str) -> MagicMock:
    block = MagicMock(type="text", text=text)
    r = MagicMock(custom_id=custom_id)
    r.result = MagicMock(type="succeeded")
    r.result.message = MagicMock(content=[block])
    return r


def _errored(custom_id: str, err_type: str = "invalid_request") -> MagicMock:
    r = MagicMock(custom_id=custom_id)
    r.result = MagicMock(type="errored")
    r.result.error = MagicMock(type=err_type)
    return r


def _client(monkeypatch: pytest.MonkeyPatch) -> AnthropicBatchClient:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    return AnthropicBatchClient()


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicBatchClient()


@pytest.mark.asyncio
async def test_submit_builds_requests_with_cached_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch)
    create = _patch(
        monkeypatch,
        client._client.messages.batches,
        "create",
        AsyncMock(return_value=MagicMock(id="batch_123")),
    )

    batch_id = await client.submit(
        [
            BatchItem(
                custom_id="patient-1",
                messages=[{"role": "user", "content": "ctx 1"}],
                system="BRIEF SYSTEM PROMPT",
            )
        ]
    )

    assert batch_id == "batch_123"
    reqs = create.call_args.kwargs["requests"]
    assert reqs[0]["custom_id"] == "patient-1"
    params = reqs[0]["params"]
    assert params["model"] == MAIN_BRAIN_MODEL  # default tier=main_brain
    # system được bọc cache_control (prompt caching, cộng dồn với batch 50%)
    assert isinstance(params["system"], list)
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_submit_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    with pytest.raises(ValueError, match="rỗng"):
        await client.submit([])


@pytest.mark.asyncio
async def test_cache_system_false_keeps_string(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    create = _patch(
        monkeypatch,
        client._client.messages.batches,
        "create",
        AsyncMock(return_value=MagicMock(id="b")),
    )
    await client.submit(
        [
            BatchItem(
                custom_id="p",
                messages=[{"role": "user", "content": "x"}],
                system="PLAIN",
                cache_system=False,
            )
        ]
    )
    params = create.call_args.kwargs["requests"][0]["params"]
    assert params["system"] == "PLAIN"


@pytest.mark.asyncio
async def test_is_done_true_when_ended(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    _patch(
        monkeypatch,
        client._client.messages.batches,
        "retrieve",
        AsyncMock(return_value=MagicMock(processing_status="ended")),
    )
    assert await client.is_done("batch_1") is True


@pytest.mark.asyncio
async def test_is_done_false_when_in_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    _patch(
        monkeypatch,
        client._client.messages.batches,
        "retrieve",
        AsyncMock(return_value=MagicMock(processing_status="in_progress")),
    )
    assert await client.is_done("batch_1") is False


@pytest.mark.asyncio
async def test_results_maps_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(monkeypatch)
    _patch(
        monkeypatch,
        client._client.messages.batches,
        "results",
        AsyncMock(
            return_value=_aiter(
                [
                    _succeeded("patient-1", "BRIEF JSON 1"),
                    _errored("patient-2", "invalid_request"),
                ]
            )
        ),
    )

    results = await client.results("batch_123")

    by_id = {r.custom_id: r for r in results}
    assert by_id["patient-1"].succeeded is True
    assert by_id["patient-1"].text == "BRIEF JSON 1"
    assert by_id["patient-2"].succeeded is False
    assert by_id["patient-2"].error == "invalid_request"
