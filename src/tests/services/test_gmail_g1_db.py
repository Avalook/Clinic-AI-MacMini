"""Gmail G1 — lược đồ kết quả đối tác qua Gmail, chạy thật trên DB.

Ca biên (kế hoạch docs/KE-HOACH-KET-QUA-QUA-GMAIL.md mục 3 G1, 4): email người gửi chữ
thường và duy nhất trong phòng khám; mã bên đối tác duy nhất trong một đối tác (dòng còn
dùng); dòng Drive cũ không đổi; dòng Gmail luôn có thư + byte đã lưu; lý do mới; sự việc
không sửa được nhưng cột đẩy tệp luôn sửa được (kể cả sau khi từ chối) và không làm
đường lách; thư Lưu trữ không vào hàng ghép tay; nhịp tách theo nguồn mà màn cũ không
nhân đôi đối tác.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import pytest

from clinicai.services.xet_nghiem import doi_tac, drive, ghep_tay
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

CAM = asyncpg.exceptions.CheckViolationError
TRUNG = asyncpg.exceptions.UniqueViolationError
KHOA = asyncpg.exceptions.InsufficientPrivilegeError
VN = timezone(timedelta(hours=7))


async def _dt(pool: asyncpg.Pool, email: str | None = None) -> str:  # noqa: F811
    ma = "G" + uuid.uuid4().hex[:6].upper()
    return str(
        await pool.fetchval(
            "INSERT INTO doi_tac (clinic_id, ten, ma_ngan, email_gui_ket_qua)"
            " VALUES ($1::uuid, $2, $3, $4) RETURNING id::text",
            CLINIC,
            f"Đối tác {ma}",
            ma,
            email,
        )
    )


async def _nv(pool: asyncpg.Pool) -> Any:  # noqa: F811
    """Một nhân viên thử (staff không có clinic_id — gắn qua cơ sở chính)."""
    return await pool.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id)"
        " SELECT 'Thử Gmail G1', 'MANAGEMENT', id FROM clinic_location"
        " WHERE clinic_id = $1::uuid ORDER BY created_at LIMIT 1 RETURNING id",
        CLINIC,
    )


def _thu(dt_id: str, **them: Any) -> dict[str, Any]:
    """Một dòng drive_tep nguồn GMAIL hợp lệ (byte đã lưu ở ổ VPS)."""
    mid = uuid.uuid4().hex[:16]
    noi = f"%PDF giả {mid}".encode()
    return {
        "clinic_id": CLINIC,
        "doi_tac_id": dt_id,
        "nguon": "GMAIL",
        "file_id": f"gmail:{mid}:1",
        "md5": hashlib.md5(noi, usedforsecurity=False).hexdigest(),
        "ten": "VU_THI_A_081126-501726_HPV_TMD.pdf",
        "mime": "application/pdf",
        "so_byte": len(noi),
        "email_message_id": mid,
        "email_tieu_de": "Kết quả xét nghiệm: VŨ THỊ A - Ngày xét nghiệm: 08/11/2026",
        "email_than": "Họ tên: VŨ THỊ A, NS: 1981, Giới: Nữ",
        "email_nhan_luc": datetime(2026, 11, 9, 8, 0, tzinfo=VN),
        "ma_ben_doi_tac_tep": "081126-501726",
        "khoa": f"{CLINIC}/gmail/{mid}.pdf",
        "sha256": hashlib.sha256(noi).hexdigest(),
        "vi_tri": "vps",
        "tai_len_luc": datetime(2026, 11, 9, 8, 0, 5, tzinfo=VN),
        "ly_do_cho": "LUU_TRU",
        **them,
    }


async def _ghi(pool: asyncpg.Pool, dong: dict[str, Any]) -> str:  # noqa: F811
    cot = [k for k in dong if dong[k] is not None]
    gia = [dong[k] for k in cot]
    o = []
    for i, k in enumerate(cot, 1):
        kieu = {
            "clinic_id": "::uuid",
            "doi_tac_id": "::uuid",
            "email_nhan_luc": "::timestamptz",
            "tai_len_luc": "::timestamptz",
        }.get(k, "")
        o.append(f"${i}{kieu}")
    return str(
        await pool.fetchval(
            f"INSERT INTO drive_tep ({', '.join(cot)}) VALUES ({', '.join(o)})"  # noqa: S608
            " RETURNING id::text",
            *gia,
        )
    )


# ── 1–2. doi_tac.email_gui_ket_qua ───────────────────────────────────────────
async def test_email_chu_thuong_duy_nhat_trong_phong_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    em = f"kq_{uuid.uuid4().hex[:8]}@lab-thu.vn"
    await _dt(pool, em)
    with pytest.raises(TRUNG):
        await _dt(pool, em)  # hai đối tác cùng địa chỉ ⇒ không biết thư của ai
    with pytest.raises(CAM):
        await _dt(pool, f"KQ_{uuid.uuid4().hex[:8]}@Lab.vn")  # phải chữ thường
    for rac in ("khong-co-a-cong", "a@b", " x@lab.vn", "@lab.vn"):
        with pytest.raises(CAM):
            await _dt(pool, rac)
    # NULL nhiều đối tác được.
    await _dt(pool, None)
    await _dt(pool, None)


# ── 3. doi_tac_dich_vu.ma_ben_doi_tac ───────────────────────────────────────
async def test_ma_ben_doi_tac_duy_nhat_trong_doi_tac_con_dung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    dt_id = await _dt(pool)
    sp = [
        r["id"]
        for r in await pool.fetch(
            "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
            " AND \"group\" = 'dich_vu' ORDER BY id LIMIT 3",
            CLINIC,
        )
    ]
    assert len(sp) == 3

    async def gan(sp_id: str, ma: str | None) -> str:
        return str(
            await pool.fetchval(
                "INSERT INTO doi_tac_dich_vu (clinic_id, doi_tac_id, service_price_id,"
                " mac_dinh, ma_ben_doi_tac) VALUES ($1::uuid, $2::uuid, $3::uuid,"
                " false, $4) RETURNING id::text",
                CLINIC,
                dt_id,
                sp_id,
                ma,
            )
        )

    dong = await gan(sp[0], "HPV")
    with pytest.raises(TRUNG):
        await gan(sp[1], "HPV")  # cùng đối tác, cùng mã, cả hai còn dùng
    with pytest.raises(CAM):
        await gan(sp[1], "hpv")  # phải chữ hoa
    with pytest.raises(CAM):
        await gan(sp[1], "HPV GENO")  # không khoảng trắng
    # Dòng cũ ngưng ⇒ không chặn mã ở dòng mới.
    await pool.execute(
        "UPDATE doi_tac_dich_vu SET ngung_luc = now(), ngung_boi = $2"
        " WHERE id = $1::uuid",
        dong,
        await _nv(pool),
    )
    await gan(sp[1], "HPV")
    # Đối tác khác dùng cùng mã được.
    dt2 = await _dt(pool)
    await pool.execute(
        "INSERT INTO doi_tac_dich_vu (clinic_id, doi_tac_id, service_price_id,"
        " mac_dinh,"
        " ma_ben_doi_tac) VALUES ($1::uuid, $2::uuid, $3::uuid, false, 'HPV')",
        CLINIC,
        dt2,
        sp[2],
    )


# ── 4. xet_nghiem_cai_dat.gmail_tu_ngay ─────────────────────────────────────
async def test_moc_tu_ghep_mac_dinh_trong(pool: asyncpg.Pool) -> None:  # noqa: F811
    await pool.execute(
        "INSERT INTO xet_nghiem_cai_dat (clinic_id) VALUES ($1::uuid)"
        " ON CONFLICT (clinic_id) DO NOTHING",
        CLINIC,
    )
    # Cột mới mặc định NULL = chưa tự ghép thư nào (không đổi dòng cài đặt đang có).
    await pool.execute(
        "UPDATE xet_nghiem_cai_dat SET gmail_tu_ngay = NULL WHERE clinic_id = $1::uuid",
        CLINIC,
    )
    await pool.execute(
        "UPDATE xet_nghiem_cai_dat SET gmail_tu_ngay = '2026-11-09'"
        " WHERE clinic_id = $1::uuid",
        CLINIC,
    )
    assert (
        str(
            await pool.fetchval(
                "SELECT gmail_tu_ngay FROM xet_nghiem_cai_dat"
                " WHERE clinic_id = $1::uuid",
                CLINIC,
            )
        )
        == "2026-11-09"
    )
    await pool.execute(
        "UPDATE xet_nghiem_cai_dat SET gmail_tu_ngay = NULL WHERE clinic_id = $1::uuid",
        CLINIC,
    )


# ── 5–7, 9. drive_tep nguồn GMAIL ───────────────────────────────────────────
async def test_dong_drive_cu_mac_dinh_nguon_drive(pool: asyncpg.Pool) -> None:  # noqa: F811
    dt_id = await _dt(pool)
    tid = await pool.fetchval(
        "INSERT INTO drive_tep (clinic_id, doi_tac_id, file_id, md5, ten)"
        " VALUES ($1::uuid, $2::uuid, $3, $4, 'kq.pdf') RETURNING id",
        CLINIC,
        dt_id,
        "driveFile" + uuid.uuid4().hex[:8],
        uuid.uuid4().hex,
    )
    r = await pool.fetchrow(
        "SELECT nguon, vi_tri, khoa FROM drive_tep WHERE id = $1", tid
    )
    assert (r["nguon"], r["vi_tri"], r["khoa"]) == ("DRIVE", None, None)
    # Dòng Drive không được mang cột thư / byte lưu / mốc đẩy / lý do Lưu trữ (thư
    # LUU_TRU chỉ hiện ở Kho email — dòng Drive mang nó sẽ biến mất khỏi mọi màn).
    for cot, gia in (
        ("email_message_id", "abc123"),
        ("tai_len_luc", datetime(2026, 11, 9, tzinfo=VN)),
        ("da_day_luc", datetime(2026, 11, 9, tzinfo=VN)),
        ("ly_do_cho", "LUU_TRU"),
    ):
        with pytest.raises(CAM):
            await pool.execute(
                "INSERT INTO drive_tep"  # noqa: S608 — tên cột từ bộ cố định ở trên
                f" (clinic_id, doi_tac_id, file_id, md5, ten, {cot})"
                " VALUES ($1::uuid, $2::uuid, $3, $4, 'kq.pdf', $5)",
                CLINIC,
                dt_id,
                "driveFile" + uuid.uuid4().hex[:8],
                uuid.uuid4().hex,
                gia,
            )


async def test_dong_gmail_luon_co_thu_va_byte(pool: asyncpg.Pool) -> None:  # noqa: F811
    dt_id = await _dt(pool)
    await _ghi(pool, _thu(dt_id))  # hợp lệ (file_id có dấu ':')
    for hong in (
        {"email_message_id": None},
        {"email_message_id": "thuKhacHanCuaTep"},  # file_id trỏ thư khác
        {"email_nhan_luc": None},
        {"khoa": None},
        {"sha256": None},
        {"sha256": "khong-phai-sha"},
        {"vi_tri": None},
        {"email_than": "x" * 2001},
        {"file_id": "gmail:abc"},  # thiếu partId
        {"nguon": "IMAP"},
        {"ly_do_cho": "LY_DO_RAC"},
    ):
        with pytest.raises(CAM):
            await _ghi(pool, _thu(dt_id, **hong))
    # Drive không nhận file_id dạng gmail.
    with pytest.raises(CAM):
        await pool.execute(
            "INSERT INTO drive_tep (clinic_id, doi_tac_id, file_id, md5, ten)"
            " VALUES ($1::uuid, $2::uuid, 'gmail:abcdef:1', $3, 'kq.pdf')",
            CLINIC,
            dt_id,
            uuid.uuid4().hex,
        )
    for ly_do in ("LUU_TRU", "CHUA_LAY_MAU", "CO_BAN_MOI", None):
        await _ghi(pool, _thu(dt_id, ly_do_cho=ly_do))


async def test_quet_lai_cung_thu_khong_tao_ban_hai(pool: asyncpg.Pool) -> None:  # noqa: F811
    dt_id = await _dt(pool)
    dong = _thu(dt_id)
    await _ghi(pool, dong)
    with pytest.raises(TRUNG):
        await _ghi(pool, {**dong, "khoa": dong["khoa"] + ".2"})


# ── 8. trigger sự việc không sửa / cột đẩy luôn sửa được ────────────────────
async def test_su_viec_khong_sua_cot_day_luon_sua(pool: asyncpg.Pool) -> None:  # noqa: F811
    dt_id = await _dt(pool)
    tid = await _ghi(pool, _thu(dt_id))
    for cot, gia in (
        ("email_tieu_de", "sửa tiêu đề"),
        ("email_than", "sửa thân"),
        ("email_message_id", "khacMessage1"),
        ("nguon", "DRIVE"),
        ("khoa", f"{CLINIC}/gmail/khac.pdf"),
        ("ma_ben_doi_tac_tep", "000000-000000"),
        ("md5", uuid.uuid4().hex),
        ("ten", "doi-ten.pdf"),
        ("mime", "image/png"),
        ("so_byte", 999),
        ("sha256", "0" * 64),
        ("tai_len_luc", datetime(2026, 11, 10, tzinfo=VN)),
    ):
        with pytest.raises((KHOA, CAM)):
            await pool.execute(
                f"UPDATE drive_tep SET {cot} = $2 WHERE id = $1::uuid",  # noqa: S608
                tid,
                gia,
            )
    # Đi kèm cột đẩy KHÔNG phải đường lách: một câu đổi cả hai ⇒ vẫn bị chặn.
    with pytest.raises(KHOA):
        await pool.execute(
            "UPDATE drive_tep SET vi_tri = 'cfs', da_day_luc = now(),"
            " email_than = 'x' WHERE id = $1::uuid",
            tid,
        )
    # Gợi ý + lý do đi tiếp được (G3 xét lại thư Lưu trữ một lần).
    await pool.execute(
        "UPDATE drive_tep SET ly_do_cho = 'KHONG_KHOP_KHACH' WHERE id = $1::uuid", tid
    )
    # Từ chối ⇒ mọi cột sự việc / gợi ý khoá, NHƯNG day_tep vẫn đẩy được tệp lên CFS.
    staff = await _nv(pool)
    await pool.execute(
        "UPDATE drive_tep SET tu_choi_luc = now(), tu_choi_boi = $2,"
        " ly_do_tu_choi = 'thư quảng cáo' WHERE id = $1::uuid",
        tid,
        staff,
    )
    with pytest.raises(KHOA):
        await pool.execute(
            "UPDATE drive_tep SET ly_do_cho = 'LUU_TRU' WHERE id = $1::uuid", tid
        )
    await pool.execute(
        "UPDATE drive_tep SET vi_tri = 'cfs', da_day_luc = now() WHERE id = $1::uuid",
        tid,
    )
    await pool.execute(
        "UPDATE drive_tep SET da_xoa_ban_vps_luc = now() WHERE id = $1::uuid", tid
    )
    with pytest.raises(KHOA):
        await pool.execute("DELETE FROM drive_tep WHERE id = $1::uuid", tid)


# ── Hàng ghép tay không có thư Lưu trữ ──────────────────────────────────────
async def test_hang_ghep_tay_khong_co_thu_luu_tru(pool: asyncpg.Pool) -> None:  # noqa: F811
    dt_id = await _dt(pool)
    luu = await _ghi(pool, _thu(dt_id, ly_do_cho="LUU_TRU"))
    cho = await _ghi(pool, _thu(dt_id, ly_do_cho="KHONG_KHOP_KHACH"))
    async with pool.acquire() as conn:
        ids = {r["id"] for r in await ghep_tay.ds_cho(conn, CLINIC)}
    assert cho in ids
    assert luu not in ids


# ── 10. drive_nhip theo nguồn ───────────────────────────────────────────────
async def test_nhip_theo_nguon_khong_nhan_doi_doi_tac(pool: asyncpg.Pool) -> None:  # noqa: F811
    dt_id = await _dt(pool)
    await drive._nhip(pool, CLINIC, dt_id, None, 2)
    await drive._nhip(pool, CLINIC, dt_id, "lỗi thử", 0)  # upsert đúng dòng DRIVE
    await pool.execute(
        "INSERT INTO drive_nhip (clinic_id, doi_tac_id, nguon, lan_quet_cuoi, ok_cuoi,"
        " con_tro_lich_su, so_lich_su_con) VALUES ($1::uuid, $2::uuid, 'GMAIL', now(),"
        " now(), 'trang-ke-tiep', 1200)",
        CLINIC,
        dt_id,
    )
    hai = await pool.fetch(
        "SELECT nguon, loi_cuoi FROM drive_nhip WHERE doi_tac_id = $1::uuid ORDER BY 1",
        dt_id,
    )
    assert [(r["nguon"], r["loi_cuoi"]) for r in hai] == [
        ("DRIVE", "lỗi thử"),
        ("GMAIL", None),
    ]
    # Con trỏ lịch sử chỉ dành cho Gmail.
    dt2 = await _dt(pool)
    with pytest.raises(CAM):
        await pool.execute(
            "INSERT INTO drive_nhip (clinic_id, doi_tac_id, nguon, lan_quet_cuoi,"
            " con_tro_lich_su) VALUES ($1::uuid, $2::uuid, 'DRIVE', now(), 'x')",
            CLINIC,
            dt2,
        )
    async with pool.acquire() as conn:
        ds = await doi_tac.danh_sach(conn, CLINIC)
        nhip = await ghep_tay.ds_nhip(conn, CLINIC)
    # Màn Cài đặt → Đối tác: mỗi đối tác MỘT dòng (không nhân đôi vì có dòng GMAIL).
    assert [d["id"] for d in ds["doi_tac"]].count(dt_id) == 1
    assert [n["doi_tac_id"] for n in nhip].count(dt_id) == 1


# ── tep_ket_qua.nguon nhận GMAIL ────────────────────────────────────────────
async def test_tep_ket_qua_nhan_nguon_gmail(pool: asyncpg.Pool) -> None:  # noqa: F811
    dinh_nghia = await pool.fetchval(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
        " WHERE conname = 'tep_ket_qua_nguon_hop_le'"
    )
    assert "GMAIL" in dinh_nghia
