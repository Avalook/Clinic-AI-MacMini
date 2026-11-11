"""Gmail G2b — Kho email kết quả (tạm), chạy thật trên DB.

Ca biên kế hoạch mục 4: người không có quyền Kho gọi thẳng API Kho / mở PDF ⇒ 404 (kể
cả Quản lý — khối cấp riêng); mở PDF ⇒ có vết `lab.archive_viewed`; thư Gmail không lọt
qua cửa hàng chờ Drive (xem trước theo id — đường lách quyền Kho); lọc ngày / trạng
thái / tên bỏ dấu / SĐT; tham số rác không 500.
"""

from __future__ import annotations

import pathlib
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.services.permission_service import PermissionService
from clinicai.services.tep_ket_qua_service import doc_dan
from clinicai.services.xet_nghiem import ghep_khach, ghep_tay, kho_email
from tests.services.test_gmail_g1_db import _dt, _ghi, _thu
from tests.services.test_permission_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
    quan_ly,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _co_kho(pool: asyncpg.Pool, ql: StaffIdentity) -> StaffIdentity:  # noqa: F811
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "RECEPTION")
    await PermissionService(pool).cap_khoi(
        staff_id=x.staff_id, khoi="kho_email", identity=ql
    )
    return x


async def _thu_kho(
    pool: asyncpg.Pool,  # noqa: F811
    tmp_path: pathlib.Path,
    **them: Any,
) -> str:
    """Một thư Gmail trong Kho + tệp PDF thật trên ổ VPS (tmp)."""
    dong = _thu(await _dt(pool), **them)
    noi = f"%PDF-1.4 kho {uuid.uuid4().hex}".encode()
    import hashlib

    dong.update(
        so_byte=len(noi),
        sha256=hashlib.sha256(noi).hexdigest(),
        md5=hashlib.md5(noi, usedforsecurity=False).hexdigest(),
    )
    p = tmp_path / dong["khoa"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(noi)
    return await _ghi(pool, dong)


@pytest.fixture
def o_vps(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    import clinicai.services.media_service as media

    monkeypatch.setattr(media, "MEDIA_LOCAL_ROOT", tmp_path)
    return tmp_path


async def test_khong_quyen_kho_thi_404_ke_ca_quan_ly(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
    o_vps: pathlib.Path,
) -> None:
    tid = await _thu_kho(pool, o_vps)
    async with pool.acquire() as conn:
        le_tan = await _nguoi(conn, "RECEPTION")
    for ai in (quan_ly, le_tan):  # Quản lý có mọi khối TRỪ khối cấp riêng
        async with pool.acquire() as conn:
            with pytest.raises(NotFoundError):
                await kho_email.danh_sach(conn, ai, {})
            with pytest.raises(NotFoundError):
                await kho_email.chi_tiet(conn, ai, tid)
        with pytest.raises(NotFoundError):
            await kho_email.mo_pdf(pool, ai, tid)


async def test_co_quyen_thi_thay_thu_va_mo_pdf_co_vet(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
    o_vps: pathlib.Path,
) -> None:
    x = await _co_kho(pool, quan_ly)
    tid = await _thu_kho(pool, o_vps)
    async with pool.acquire() as conn:
        ds = await kho_email.danh_sach(conn, x, {"co": "500"})
        ct = await kho_email.chi_tiet(conn, x, tid)
    dong = {t["id"]: t for t in ds["thu"]}[tid]
    assert (dong["trang_thai"], dong["nhan_trang_thai"]) == ("LUU_TRU", "Lưu trữ")
    # G5: dòng Lưu trữ cũ (không mã lý do) vẫn có câu, mã thô không lộ ra màn.
    assert dong["vi_sao"] == ct["vi_sao"] == "Lưu trữ (không tự ghép)"
    assert "ly_do_cho" not in dong and "luu_tru_vi_sao" not in ct
    assert ds["co"] == kho_email.CO_TOI_DA and ds["tong"] >= 1
    assert ds["thanh_tren"]["nhan"].startswith("Đã nạp")
    assert ct["than"] and "khoa" not in ct  # đường ổ không lộ ra màn
    tep = await kho_email.mo_pdf(pool, x, tid)
    noi = b"".join([m async for m in doc_dan(tep, 0, tep.so_byte - 1)])
    assert noi.startswith(b"%PDF") and tep.mime == "application/pdf"
    vet = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type = 'lab.archive_viewed'"
        " AND aggregate_id = $1::uuid",
        tid,
    )
    assert vet == 1
    # Id rác / dòng Drive ⇒ 404, không 500.
    async with pool.acquire() as conn:
        for rac in ("khong-phai-uuid", str(uuid.uuid4())):
            with pytest.raises(NotFoundError):
                await kho_email.chi_tiet(conn, x, rac)


async def test_loc_ngay_trang_thai_ten_bo_dau_sdt(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
    o_vps: pathlib.Path,
) -> None:
    x = await _co_kho(pool, quan_ly)
    ten = "Đỗ Thị Lọc" + uuid.uuid4().hex[:4].upper()
    sdt = "09" + str(uuid.uuid4().int)[:8]
    nhan = datetime(2026, 3, 15, 2, tzinfo=UTC)  # 09:00 giờ VN ngày 15/03
    tid = await _thu_kho(
        pool,
        o_vps,
        email_tieu_de=f"Kết quả xét nghiệm: {ten}",
        email_than=f"Họ tên: {ten}, SĐT: {sdt}",
        email_nhan_luc=nhan,
    )

    async def ids(**loc: str) -> set[str]:
        async with pool.acquire() as conn:
            ds = await kho_email.danh_sach(conn, x, {"co": "100", **loc})
        return {t["id"] for t in ds["thu"]}

    bo_dau = ghep_khach.chuan(ten)
    assert tid in await ids(q=bo_dau)  # gõ không dấu
    assert tid in await ids(q=ten.upper())  # gõ có dấu, chữ hoa
    assert tid in await ids(q=sdt)
    assert tid in await ids(q=bo_dau[:-3])  # gõ dở từ cuối — khớp tiền tố
    assert tid in await ids(q=f"+84 {sdt[1:4]}.{sdt[4:7]}.{sdt[7:]}")
    assert tid not in await ids(q="khong ai ten nay ca")
    assert tid in await ids(tu_ngay="2026-03-15", den_ngay="2026-03-15")
    assert tid not in await ids(tu_ngay="2026-03-16")
    assert tid in await ids(trang_thai="LUU_TRU", q=sdt)
    assert tid not in await ids(trang_thai="DA_GHEP", q=sdt)
    # Rác ⇒ bỏ lọc đó, không 500.
    assert tid in await ids(
        tu_ngay="31/02", den_ngay="xx", trang_thai="BAY", trang="-3", co="abc", q=sdt
    )


async def test_thanh_tren_do_khi_co_doi_tac_chua_quet(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Một đối tác đã đặt email mà chưa có lượt quét nào ⇒ đèn đỏ (min() một mình bỏ
    qua NULL và báo "Email ổn" sai)."""
    a = await _dt(pool, f"a_{uuid.uuid4().hex[:8]}@lab-thu.vn")
    await _dt(pool, f"b_{uuid.uuid4().hex[:8]}@lab-thu.vn")  # chưa quét lần nào
    await pool.execute(
        "INSERT INTO drive_nhip (clinic_id, doi_tac_id, nguon, lan_quet_cuoi, ok_cuoi)"
        " VALUES ($1::uuid, $2::uuid, 'GMAIL', now(), now())",
        CLINIC,
        a,
    )
    async with pool.acquire() as conn:
        den = await kho_email.thanh_tren(conn, CLINIC)
    assert den["mau"] == "danger"


async def test_thu_gmail_khong_lot_qua_cua_hang_cho_drive(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
    o_vps: pathlib.Path,
) -> None:
    """Cửa xem trước / Gán / Từ chối của hàng chờ nhận id dòng bất kỳ — thư Gmail LƯU
    TRỮ phải 404 ở đó, chỉ mở qua Kho (có quyền). Thư Gmail sau mốc đã xét ghép (G3,
    lý do khác LUU_TRU) thì vào hàng chờ như tệp Drive, xem được bằng byte đã lưu."""
    luu = await _thu_kho(pool, o_vps, ly_do_cho="LUU_TRU")
    with pytest.raises(NotFoundError):
        await ghep_tay.noi_dung_cho(pool, quan_ly, luu)
    with pytest.raises(NotFoundError):
        await ghep_tay.tu_choi(
            pool, quan_ly, {"drive_tep_id": luu, "ly_do": "thử lách quyền"}
        )
    cho_ghep = await _thu_kho(pool, o_vps, ly_do_cho="KHONG_KHOP_KHACH")
    noi, mime = await ghep_tay.noi_dung_cho(pool, quan_ly, cho_ghep)
    assert noi.startswith(b"%PDF") and mime == "application/pdf"
    async with pool.acquire() as conn:
        cho = {t["id"]: t for t in await ghep_tay.ds_cho(conn, CLINIC)}
    assert luu not in cho
    assert cho[cho_ghep]["nguon"] == "GMAIL" and cho[cho_ghep]["email_tieu_de"]
