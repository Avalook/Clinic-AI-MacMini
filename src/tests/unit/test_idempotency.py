"""Unit tests for endpoint/actor-scoped atomic idempotency."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.idempotency import IdempotencyGuard, tra_khoa_neu_bi_tu_choi
from clinicai.core.exceptions import ClinicAIBaseException


def _pool() -> MagicMock:
    pool = MagicMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock(return_value="UPDATE 1")
    return pool


@pytest.mark.asyncio
async def test_acquire_reserves_key_atomically_for_endpoint_and_actor() -> None:
    pool = _pool()
    pool.fetchrow.return_value = {"key": "request-1"}
    guard = IdempotencyGuard(key="request-1", endpoint="POST /api/v1/payments")

    guard = await guard.acquire(pool, actor_id="staff-a")

    sql, key, endpoint, actor_id = pool.fetchrow.await_args.args
    assert "INSERT INTO idempotency_key" in sql
    assert "ON CONFLICT (key, endpoint, actor_id) DO NOTHING" in sql
    assert (key, endpoint, actor_id) == (
        "request-1",
        "POST /api/v1/payments",
        "staff-a",
    )
    assert not guard.is_replay


@pytest.mark.asyncio
async def test_acquire_replays_only_matching_endpoint_and_actor() -> None:
    pool = _pool()
    pool.fetchrow.side_effect = [
        None,  # INSERT lost to the existing composite key
        None,  # stale reservation was not reclaimable
        {
            "response": json.dumps({"ok": True}),
            "status_code": 201,
            "state": "COMPLETED",
        },
    ]
    guard = IdempotencyGuard(key="same-client-key", endpoint="POST /appointments")

    guard = await guard.acquire(pool, actor_id="staff-b")

    assert guard.is_replay
    assert guard.cached_response is not None
    assert guard.cached_response.status_code == 201
    assert guard.actor_id == "staff-b"
    lookup = pool.fetchrow.await_args_list[2].args
    assert lookup[1:] == ("same-client-key", "POST /appointments", "staff-b")


@pytest.mark.asyncio
async def test_concurrent_in_progress_request_returns_conflict() -> None:
    pool = _pool()
    pool.fetchrow.side_effect = [
        None,
        None,
        {"response": None, "status_code": 200, "state": "PROCESSING"},
    ]
    guard = IdempotencyGuard(key="request-2", endpoint="POST /appointments")

    with pytest.raises(ConflictError, match="đang được xử lý"):
        await guard.acquire(pool)


@pytest.mark.asyncio
async def test_save_completes_the_exact_reservation() -> None:
    pool = _pool()
    pool.fetchrow.return_value = {"key": "request-3"}
    guard = IdempotencyGuard(key="request-3", endpoint="POST /payments")
    guard = await guard.acquire(pool, actor_id="staff-c")

    await guard.save(pool, {"ok": True}, status_code=201)

    sql, response, status_code, key, endpoint, actor_id = pool.execute.await_args.args
    assert "state = 'COMPLETED'" in sql
    assert json.loads(response) == {"ok": True}
    assert (status_code, key, endpoint, actor_id) == (
        201,
        "request-3",
        "POST /payments",
        "staff-c",
    )


@pytest.mark.asyncio
async def test_missing_key_never_touches_database() -> None:
    pool = _pool()
    guard = IdempotencyGuard(key=None, endpoint="POST /appointments")

    guard = await guard.acquire(pool)
    await guard.save(pool, {"ok": True})

    pool.fetchrow.assert_not_awaited()
    pool.execute.assert_not_awaited()


# ── Trả khoá khi thao tác bị TỪ CHỐI ────────────────────────────────────────
#
# Tìm ra khi Tuyền nghiệm thu staging 13/08/2026. Chuỗi thật trong log, theo
# mốc thời gian:
#
#     08:08:23  422  "Chưa có tệp kết quả nào được xác nhận đã gửi cho khách…"
#     08:08:30  422  cùng lý do
#     08:08:35  409  "Idempotency-Key này đang được xử lý; vui lòng thử lại"
#     08:08:41  409  cùng câu
#
# Khoá bị chiếm TRƯỚC khi handler chạy, còn handler thì từ chối — nên chỗ giữ
# chỗ nằm lại 5 phút và nuốt mất câu giải thích thật. Lúc đo có 8 khoá kẹt ở
# đúng đường này, cái lâu nhất 1 ngày 5 giờ.


@pytest.mark.asyncio
async def test_release_xoa_cho_giu_khi_bi_tu_choi() -> None:
    pool = _pool()
    pool.fetchrow.return_value = {"key": "lan-bam-1"}
    guard = IdempotencyGuard(key="lan-bam-1", endpoint="POST /cskh/tuong-tac")
    guard = await guard.acquire(pool, actor_id="staff-a")

    await guard.release(pool)

    sql, key, endpoint, actor_id = pool.execute.await_args.args
    assert "DELETE FROM idempotency_key" in sql
    assert "state = 'PROCESSING'" in sql, (
        "chỉ xoá chỗ giữ còn dở — một khoá ĐÃ COMPLETED là kết quả thật, "
        "xoá nó đi là mở đường cho bản ghi thứ hai"
    )
    assert (key, endpoint, actor_id) == (
        "lan-bam-1",
        "POST /cskh/tuong-tac",
        "staff-a",
    )


@pytest.mark.asyncio
async def test_loi_4xx_thi_tra_khoa_lai() -> None:
    """Máy chủ TỪ CHỐI ⇒ chắc chắn chưa ghi gì ⇒ lần bấm sau phải đi qua được."""
    pool = _pool()
    pool.fetchrow.return_value = {"key": "lan-bam-1"}
    guard = IdempotencyGuard(key="lan-bam-1", endpoint="POST /cskh/tuong-tac")
    guard = await guard.acquire(pool, actor_id="staff-a")

    with pytest.raises(ValidationError):
        async with tra_khoa_neu_bi_tu_choi(guard, pool):
            raise ValidationError("Chưa có tệp kết quả nào được xác nhận đã gửi.")

    assert "DELETE FROM idempotency_key" in pool.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_loi_5xx_thi_giu_khoa() -> None:
    """Máy chủ HỎNG ⇒ không ai biết đã ghi tới đâu ⇒ giữ khoá.

    Đây là ranh giới của cả cơ chế: gửi lại sau một lỗi 5xx có thể tạo bản ghi
    thứ hai, mà đó đúng là thứ khoá này sinh ra để chặn.
    """
    pool = _pool()
    pool.fetchrow.return_value = {"key": "lan-bam-1"}
    guard = IdempotencyGuard(key="lan-bam-1", endpoint="POST /cskh/tuong-tac")
    guard = await guard.acquire(pool, actor_id="staff-a")

    class LoiMayChu(ClinicAIBaseException):
        status_code = 500

    with pytest.raises(LoiMayChu):
        async with tra_khoa_neu_bi_tu_choi(guard, pool):
            raise LoiMayChu("Database sập giữa chừng")

    pool.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_chay_xuoi_thi_khong_dong_toi_khoa() -> None:
    pool = _pool()
    pool.fetchrow.return_value = {"key": "lan-bam-1"}
    guard = IdempotencyGuard(key="lan-bam-1", endpoint="POST /cskh/tuong-tac")
    guard = await guard.acquire(pool, actor_id="staff-a")

    async with tra_khoa_neu_bi_tu_choi(guard, pool):
        pass

    pool.execute.assert_not_awaited()


def test_moi_endpoint_dung_khoa_deu_phai_tra_khoa_khi_bi_tu_choi() -> None:
    """Endpoint nào cầm Idempotency-Key thì phải thả nó khi từ chối 4xx.

    KHÔNG PHẢI MỘT BÀI KIỂM PHÒNG XA. Bản vá này đã merge vào main ngày
    13/08/2026 (PR #80) rồi BIẾN MẤT trong lần hoà nhánh hôm sau (PR #81) —
    không ai thấy, vì không có gì canh nó. Lỗi quay lại nguyên vẹn: người dùng
    bấm một bước, nhận 422 thật, rồi mọi lần bấm sau đó nhận "Yêu cầu với
    Idempotency-Key này đang được xử lý" suốt 5 phút, và câu giải thích thật
    biến mất sau nó.

    Bài kiểm này canh QUAN HỆ giữa hai thứ, chứ không canh một tệp: hễ có
    `idempotency_guard` thì phải có `tra_khoa_neu_bi_tu_choi`. Endpoint thứ năm
    thêm vào mai sau cũng bị bắt.
    """
    import pathlib

    goc = (
        pathlib.Path(__file__).resolve().parents[2]
        / "clinicai"
        / "api"
        / "v1"
        / "routers"
    )
    thieu = [
        p.name
        for p in sorted(goc.glob("*.py"))
        if "idempotency_guard" in p.read_text()
        and "tra_khoa_neu_bi_tu_choi" not in p.read_text()
    ]
    assert thieu == [], (
        f"{thieu} cầm Idempotency-Key mà không thả khi bị từ chối — "
        "người dùng sẽ kẹt 5 phút với câu 'đang được xử lý'"
    )
