"""Phiếu khám tự lưu không phát tin cho cả phòng khám — chỉ báo khi ngày hẹn đổi (S2).

Trigger cũ báo ở MỌI UPDATE nên mỗi lần phiếu tự lưu, mọi màn của mọi người lại
dựng lại trang (log prod 14–16/10: một lượt ghi → 7–10 lần dựng lại). Nay UPDATE chỉ
báo khi một ô `*_follow_date` đổi (khung lịch sử đơn thuốc đọc ô ấy).

CÁCH KIỂM — ba lớp, hai lớp đầu xác định:

1. Bảng chân lý của `phieu_kham_doi_ngay_hen` — chạy trong WHEN của câu UPDATE nên
   KHÔNG ĐƯỢC NÉM: ném là bác sĩ mất lần lưu. Có ca rác (NULL, mảng, số, chuỗi).
2. Cấu trúc: INSERT/DELETE vẫn báo mọi lần; UPDATE có WHEN trỏ đúng hàm.
3. Sống: đổi ô ngày hẹn thật sự phát tin. Chiều "không phát" KHÔNG kiểm bằng nghe
   kênh — DB test chia sẻ giữa các worker, test khác ghi phiếu cùng phòng khám sẽ làm
   bài chập chờn; chiều ấy đã được lớp 1 + 2 chứng minh.
"""

import asyncio
import json
from uuid import uuid4

import asyncpg
import pytest

from clinicai.core.change_broker import CHANNEL
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _doi(pool: asyncpg.Pool, cu: object, moi: object) -> bool:
    return bool(
        await pool.fetchval(
            "SELECT public.phieu_kham_doi_ngay_hen($1::jsonb, $2::jsonb)",
            None if cu is None else json.dumps(cu),
            None if moi is None else json.dumps(moi),
        )
    )


HEN_CU = {"pk_follow_date": {"nguon": "USER", "gia_tri": "2026-12-01"}}


@pytest.mark.parametrize(
    ("cu", "moi", "ky_vong"),
    [
        # Đổi / đặt / xoá ngày hẹn → báo.
        (HEN_CU, {"pk_follow_date": {"nguon": "USER", "gia_tri": "2026-12-09"}}, True),
        ({}, HEN_CU, True),
        (HEN_CU, {}, True),
        # Ô ngày hẹn của phiếu khác (mọi mã kết thúc `_follow_date`) cũng tính.
        ({}, {"sk_follow_date": {"gia_tri": "2026-12-01"}}, True),
        # Chữ bác sĩ đang gõ (tự lưu) → KHÔNG báo.
        ({"pk_dx": {"gia_tri": "Viêm"}}, {"pk_dx": {"gia_tri": "Viêm âm đạo"}}, False),
        (HEN_CU, {**HEN_CU, "pk_dx": {"gia_tri": "x"}}, False),
        # Ô tên gần giống nhưng không kết thúc bằng `_follow_date` → không tính.
        ({}, {"pk_follow_date_ghi_chu": {"gia_tri": "a"}}, False),
        ({}, {"follow_date_x": {"gia_tri": "a"}}, False),
        # Không đổi gì → không báo.
        (HEN_CU, HEN_CU, False),
        ({}, {}, False),
    ],
)
async def test_chi_bao_khi_o_ngay_hen_doi(
    pool: asyncpg.Pool, cu: object, moi: object, ky_vong: bool
) -> None:
    assert await _doi(pool, cu, moi) is ky_vong


@pytest.mark.parametrize(
    ("cu", "moi"),
    [
        (None, None),
        (None, {}),
        ([], []),
        ([1, 2], HEN_CU),
        (HEN_CU, [1, 2]),
        ("chuoi", HEN_CU),
        (42, 42),
        (None, HEN_CU),
    ],
)
async def test_du_lieu_rac_khong_bao_gio_nem(
    pool: asyncpg.Pool, cu: object, moi: object
) -> None:
    """`du_lieu` không phải object (NULL, mảng, chuỗi, số): trả bool, KHÔNG ném."""
    assert isinstance(await _doi(pool, cu, moi), bool)


async def test_trigger_dung_cau_truc(pool: asyncpg.Pool) -> None:
    dong = await pool.fetch(
        "SELECT t.tgname, pg_get_triggerdef(t.oid) AS def FROM pg_trigger t"
        " JOIN pg_class c ON c.oid = t.tgrelid WHERE c.relname = 'phieu_kham_luot'"
        " AND NOT t.tgisinternal AND t.tgname LIKE 'trg_notify_phieu_kham_luot%'"
    )
    theo_ten = {r["tgname"]: r["def"] for r in dong}
    assert set(theo_ten) == {
        "trg_notify_phieu_kham_luot",
        "trg_notify_phieu_kham_luot_hen",
    }
    chinh = theo_ten["trg_notify_phieu_kham_luot"]
    assert "INSERT OR DELETE" in chinh and "UPDATE" not in chinh
    assert "notify_row_change" in chinh
    hen = theo_ten["trg_notify_phieu_kham_luot_hen"]
    assert "AFTER UPDATE" in hen
    assert "WHEN" in hen and "phieu_kham_doi_ngay_hen" in hen
    assert "notify_row_change" in hen


async def test_doi_ngay_hen_that_su_phat_tin_con_chu_khac_thi_khong_chac(
    pool: asyncpg.Pool,
) -> None:
    """Chiều dương, nghe kênh thật: INSERT báo; đổi ô ngày hẹn báo (sau COMMIT)."""
    visit = str(uuid4())
    tin: list[str] = []

    def nghe(_c: object, _pid: int, _ch: str, payload: str) -> None:
        tin.append(payload)

    def so_tin_phieu() -> int:
        return sum(
            1 for t in tin if json.loads(t) == {"t": "phieu_kham_luot", "c": CLINIC}
        )

    async with pool.acquire() as listener:
        await listener.add_listener(CHANNEL, nghe)
        try:
            await pool.execute(
                "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version,"
                " du_lieu) VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
                CLINIC,
                visit,
                json.dumps({"pk_dx": {"gia_tri": "a"}}),
            )
            await asyncio.sleep(0.3)
            sau_insert = so_tin_phieu()
            assert sau_insert >= 1, "INSERT phiếu phải báo"

            await pool.execute(
                "UPDATE phieu_kham_luot SET du_lieu = $2::jsonb,"
                " revision = revision + 1 WHERE visit_id = $1::uuid",
                visit,
                json.dumps(HEN_CU),
            )
            await asyncio.sleep(0.3)
            assert so_tin_phieu() > sau_insert, "đổi ngày hẹn phải báo"
        finally:
            await listener.remove_listener(CHANNEL, nghe)
            await pool.execute(
                "DELETE FROM phieu_kham_luot WHERE visit_id = $1::uuid", visit
            )
