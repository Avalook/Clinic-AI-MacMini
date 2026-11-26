"""PR E (26/11/2026): cách dùng có cấu trúc — tính ở máy chủ, lưu bản chụp trên đơn.

Kế hoạch `docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md` mục 2, 4, 6, 10. Đi đúng đường màn
gọi: `PhieuKhamService.luu_don_thuoc` tự chạy `chuan_hoa_dong` (câu do máy sinh).
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.thuoc import cach_dung_db
from clinicai.services.thuoc.cach_dung import CachDung
from tests.services.test_phieu_kham_db import CLINIC, _luot, _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

HAI_LAN = {"kieu": "ngay", "moi_lan": 1, "so_lan": 2, "thoi_diem": "sau ăn"}
CHU_KY = {"kieu": "chu_ky", "moi_lan": 1, "so_lan": 1, "tu_ngay": 5, "den_ngay": 25}


async def _thuoc(conn: asyncpg.Connection, ten: str, goc: str, gia: int) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, unit_price,"
            " don_vi_ban) VALUES ($1::uuid, $2, $2, $3, $4) RETURNING id::text",
            CLINIC,
            f"{ten} {uuid.uuid4().hex[:6]}",
            gia,
            goc,
        )
    )


async def _ecanix(conn: asyncpg.Connection) -> str:
    """Gốc viên, hộp = 60 viên (như Ecanix sau khi sửa gốc)."""
    t = await _thuoc(conn, "Ecanix thử E", "viên", 9200)
    await conn.execute(
        "INSERT INTO thuoc_quy_doi (clinic_id, drug_catalog_id, don_vi, he_so, gia,"
        " dang_ban) VALUES ($1::uuid, $2::uuid, 'hộp', 60, 550000, true)",
        CLINIC,
        t,
    )
    return t


async def _ngay_luot(conn: asyncpg.Connection, visit: str, ngay: str) -> None:
    await conn.execute(
        "UPDATE visit SET checked_in_at = ($2::date + time '10:00')"
        " AT TIME ZONE 'Asia/Ho_Chi_Minh' WHERE visit_id = $1::uuid",
        visit,
        date.fromisoformat(ngay),
    )


async def _phieu(conn: asyncpg.Connection, visit: str, lmp: str, ck: str) -> None:
    await conn.execute(
        "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu)"
        " VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
        CLINIC,
        visit,
        json.dumps(
            {
                "pk_lmp": {"nguon": "USER", "gia_tri": lmp},
                "pk_cycle": {"nguon": "USER", "gia_tri": ck},
            }
        ),
    )


#: Màn bàn khám chỉ gửi CHỮ cách dùng (mặc định = chữ danh mục); máy chủ tự đọc.
CHU_HAI_LAN = "Ngày uống 2 lần, mỗi lần 1 viên. Sau ăn."
CHU_CHU_KY = "Từ ngày 5 đến ngày 25 của chu kỳ kinh, ngày uống 1 viên"


def _dong(thuoc: str | None, sl: str, dv: str, chu: str = "") -> Any:
    return {"drug_catalog_id": thuoc, "so_luong": sl, "don_vi": dv, "chu": chu}


async def test_ecanix_tinh_o_may_chu_va_luu_ban_chup(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        await _ngay_luot(conn, luot["visit"], "2026-11-26")
        t = await _ecanix(conn)
        t2 = await _thuoc(conn, "Kem bôi thử E", "tuýp", 50000)

    kq = await cach_dung_db.tinh_don(
        pool,
        identity=bs,
        visit_id=luot["visit"],
        dong=[
            _dong(t, "1", "hộp", CHU_HAI_LAN),
            _dong(t, "10", "viên", CHU_HAI_LAN),
            _dong(t, "", "hộp", CHU_HAI_LAN + " Trong 31 ngày."),
            _dong(None, "1", ""),
        ],
        kinh_lan_cuoi=None,
        chu_ky=None,
    )
    assert kq["ngay_ke"] == date(2026, 11, 26)
    hop, vien, goi_y, ngoai = kq["dong"]
    assert (hop["so_ngay"], hop["ngay_het"]) == (30, date(2026, 12, 25))
    assert hop["cau"] == CHU_HAI_LAN
    assert (vien["so_ngay"], vien["ngay_het"]) == (5, date(2026, 11, 30))
    assert goi_y["goi_y_so_luong"] == 2 and not goi_y["tinh_duoc"]
    assert "ngoài danh mục" in ngoai["ly_do"]

    # Lưu như router: chữ cách dùng do MÁY sinh, bản chụp nằm trên dòng.
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    gui = {
        "drug_catalog_id": t,
        "drug_name": "x",
        "quantity": "1 hộp",
        "dosage": "Uống — chữ màn gửi không được tin",
        "caution": "",
        "duong_dung": "Uống",
        "cach_dung_ct": HAI_LAN,
    }
    # Dòng không gửi cấu trúc (màn cũ / quầy): chữ đi nguyên, cột để NULL.
    cu = {"drug_catalog_id": t2, "drug_name": "y", "quantity": "1", "dosage": "bôi"}
    await svc.luu_don_thuoc(
        visit_id=luot["visit"],
        dong=[gui, cu],
        ly_do=None,
        identity=bs,
    )
    theo = {d["drug_catalog_id"]: d for d in await svc.doc_don_thuoc(
        visit_id=luot["visit"], identity=bs)}  # fmt: skip
    d1, d2 = theo[t], theo[t2]
    assert d1["dosage_instructions"] == "Uống — Ngày 2 lần, mỗi lần 1 viên. Sau ăn."
    assert d1["cach_dung_ct"]["kieu"] == "ngay"
    assert d1["cach_dung_ct"]["so_lan"] == 2
    assert d2["cach_dung_ct"] is None and d2["dosage_instructions"] == "bôi"

    # Đổi số lần → câu + bản chụp cùng đổi (đường sửa hướng dẫn tại chỗ).
    sua = {**gui, "id": d1["id"], "cach_dung_ct": {**HAI_LAN, "so_lan": 3}}
    await svc.luu_don_thuoc(
        visit_id=luot["visit"],
        dong=[sua, {**cu, "id": d2["id"]}],
        ly_do=None,
        identity=bs,
    )
    d1 = next(
        d
        for d in await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
        if d["drug_catalog_id"] == t
    )
    assert d1["dosage_instructions"].startswith("Uống — Ngày 3 lần")
    assert d1["cach_dung_ct"]["so_lan"] == 3


@pytest.mark.parametrize(("mac_dinh_ke", "so_ngay"), [(True, 60), (False, 1)])
async def test_cach_dung_don_vi_trong_theo_mac_dinh_ke(
    pool: asyncpg.Pool,  # noqa: F811
    mac_dinh_ke: bool,
    so_ngay: int,
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        t = await _ecanix(conn)
        await conn.execute(
            "UPDATE thuoc_quy_doi SET mac_dinh_ke = $1"
            " WHERE clinic_id = $2::uuid AND drug_catalog_id = $3::uuid",
            mac_dinh_ke,
            CLINIC,
            t,
        )

    kq = await cach_dung_db.tinh_don(
        pool,
        identity=bs,
        visit_id=None,
        dong=[_dong(t, "2", " ", CHU_HAI_LAN), _dong(t, "2", "viên", CHU_HAI_LAN)],
        kinh_lan_cuoi=None,
        chu_ky=None,
    )
    trong, vien = kq["dong"]
    assert trong["so_ngay"] == so_ngay
    assert vien["so_ngay"] == 1


@pytest.mark.parametrize(
    ("ct", "loi"),
    [
        ({**HAI_LAN, "moi_lan": None, "khoang_lan": [1, 2]}, "chọn"),
        ({**HAI_LAN, "so_lan": None, "khoang_so_lan": [1, 2]}, "chọn"),
        ({**HAI_LAN, "moi_lan": None}, "liều"),
        ({**HAI_LAN, "so_lan": None}, "số lần"),
        ({**HAI_LAN, "don_vi_lieu": " "}, "đơn vị liều"),
        ({**CHU_KY, "tu_ngay": None}, "chu kỳ kinh"),
        ({**CHU_KY, "den_ngay": None}, "chu kỳ kinh"),
        ({**CHU_KY, "tu_ngay": 26}, "chu kỳ kinh"),
    ],
)
async def test_cach_dung_chua_du_van_luu_giu_chu_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
    ct: dict[str, Any],
    loi: str,
) -> None:
    """Tự lưu giữa chừng không được làm hỏng cả đơn; chữ bác sĩ gõ không bị đè."""
    del loi
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        thuoc = await _ecanix(conn)
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    don = {
        "drug_catalog_id": thuoc,
        "drug_name": "Thử",
        "quantity": "1",
        "dosage": "Chữ cũ",
    }
    await svc.luu_don_thuoc(visit_id=luot["visit"], identity=bs, ly_do=None, dong=[don])
    truoc = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    sua = {**don, "id": truoc[0]["id"], "dosage": "Chữ chưa đủ", "cach_dung_ct": ct}
    await svc.luu_don_thuoc(visit_id=luot["visit"], identity=bs, ly_do=None, dong=[sua])
    [sau] = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert sau["dosage_instructions"] == "Chữ chưa đủ"
    assert sau["cach_dung_ct"] is not None


async def test_luu_khoang_da_chon_tao_cau_du_khong_gui_duong_dung(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        thuoc = await _ecanix(conn)
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    ct = {**HAI_LAN, "khoang_lan": [1, 2], "khoang_so_lan": [1, 2]}
    await svc.luu_don_thuoc(
        visit_id=luot["visit"],
        identity=bs,
        ly_do=None,
        dong=[
            {
                "drug_catalog_id": thuoc,
                "drug_name": "Thử",
                "quantity": "1",
                "dosage": "Chữ cũ sẽ được thay",
                "cach_dung_ct": ct,
            }
        ],
    )
    [dong] = await svc.doc_don_thuoc(visit_id=luot["visit"], identity=bs)
    assert dong["dosage_instructions"] == "Ngày 2 lần, mỗi lần 1 viên. Sau ăn."
    assert dong["cach_dung_ct"]["khoang_lan"] == ["1", "2"]


async def test_ngoai_danh_muc_co_cau_truc_bi_tu_choi() -> None:
    with pytest.raises(ValidationError):
        cach_dung_db.chuan_hoa_dong(
            {"drug_name": "gõ tay", "cach_dung_ct": HAI_LAN, "duong_dung": "Uống"}
        )
    # "Chỉ chữ" thì thuốc gõ tay vẫn lưu được, chữ giữ nguyên.
    ra = cach_dung_db.chuan_hoa_dong(
        {"drug_name": "gõ tay", "dosage": "bôi", "cach_dung_ct": {"kieu": "chu"}}
    )
    assert ra["dosage"] == "bôi" and ra["cach_dung_ct"]["kieu"] == "chu"


async def test_chu_ky_uoc_tinh_tu_phieu_kham(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        await _ngay_luot(conn, luot["visit"], "2026-11-26")
        await _phieu(conn, luot["visit"], "10/11/2026", "28")
        t = await _ecanix(conn)
    kq = await cach_dung_db.tinh_don(
        pool,
        identity=bs,
        visit_id=luot["visit"],
        dong=[_dong(t, "1", "hộp", CHU_CHU_KY)],
        kinh_lan_cuoi=None,
        chu_ky=None,
    )
    assert kq["kinh"]["nguon"] == "phieu" and kq["kinh"]["doc_duoc"]
    (d,) = kq["dong"]
    assert d["so_ngay"] == 21
    assert d["uoc_tinh"] == {
        "kinh_toi": date(2026, 12, 8),
        "bat_dau": date(2026, 12, 12),
        "het": date(2027, 1, 1),
    }


@pytest.mark.parametrize("rac", ["abc", "31/02/2026", ""])
async def test_lmp_rac_khong_uoc_tinh_khong_500(pool: asyncpg.Pool, rac: str) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        await _phieu(conn, luot["visit"], rac or "—", "28")
        t = await _ecanix(conn)
    for go_tay in (None, rac):
        kq = await cach_dung_db.tinh_don(
            pool,
            identity=bs,
            visit_id=luot["visit"],
            dong=[_dong(t, "1", "hộp", CHU_CHU_KY)],
            kinh_lan_cuoi=go_tay,
            chu_ky="28" if go_tay else None,
        )
        assert not kq["kinh"]["doc_duoc"]
        assert kq["dong"][0]["so_ngay"] == 21 and kq["dong"][0]["uoc_tinh"] is None


async def test_thieu_so_vien_moi_hop_roi_khai_o_danh_muc(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        ds = await _nguoi(conn, "PHARMACIST")
        luot = await _luot(conn, bs)
        t = await _thuoc(conn, "Thuốc hộp thử E", "hộp", 300000)
    hoi = [_dong(t, "1", "hộp", CHU_HAI_LAN)]
    kq = await cach_dung_db.tinh_don(
        pool, identity=bs, visit_id=luot["visit"], dong=hoi, kinh_lan_cuoi=None,
        chu_ky=None,
    )  # fmt: skip
    assert kq["dong"][0]["ly_do"].startswith("Chưa khai 1 hộp có bao nhiêu viên")

    ct = CachDung.model_validate({**HAI_LAN, "khoang_lan": [1, 2], "moi_lan": None})
    sau = await cach_dung_db.luu_mac_dinh(
        pool, identity=ds, thuoc_id=t, ct=ct, so_lieu=Decimal(30)
    )
    assert sau["so_lieu_moi_don_vi_goc"] == Decimal(30)
    assert sau["cau"] == "Ngày 2 lần, mỗi lần 1–2 viên. Sau ăn."
    kq = await cach_dung_db.tinh_don(
        pool, identity=bs, visit_id=luot["visit"], dong=hoi, kinh_lan_cuoi=None,
        chu_ky=None,
    )  # fmt: skip
    assert kq["dong"][0]["so_ngay"] == 15

    async with pool.acquire() as conn:
        mau = await cach_dung_db.gan_mac_dinh_ke_don(
            conn, CLINIC, [{"drug_catalog_id": t}, {"drug_catalog_id": None}]
        )
        nk = await conn.fetchval(
            "SELECT count(*) FROM event_log"
            " WHERE event_type = 'pharmacy.drug_usage_set' AND aggregate_id::text = $1",
            t,
        )
    assert mau[0]["cach_dung_ct"]["khoang_lan"] == ["1", "2"]
    assert mau[1]["cach_dung_ct"] is None
    assert nk == 1, "đổi mặc định phải có nhật ký"


async def test_chu_la_thi_lay_cach_dung_danh_muc(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Bác sĩ không khai gì: chữ dòng đọc không ra → cấu trúc kho khai ở Danh mục."""
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        ds = await _nguoi(conn, "PHARMACIST")
        t = await _ecanix(conn)
    await cach_dung_db.luu_mac_dinh(
        pool,
        identity=ds,
        thuoc_id=t,
        ct=CachDung.model_validate(HAI_LAN),
        so_lieu=None,
    )
    kq = await cach_dung_db.tinh_don(
        pool,
        identity=bs,
        visit_id=None,
        dong=[_dong(t, "1", "hộp", "Uống theo hướng dẫn"), _dong(t, "1", "hộp", "")],
        kinh_lan_cuoi=None,
        chu_ky=None,
    )
    assert [d["so_ngay"] for d in kq["dong"]] == [30, 30]
