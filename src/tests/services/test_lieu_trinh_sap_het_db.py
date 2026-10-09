"""Liệu trình "Sắp hết lộ trình" (Tuyền 08/10/2026) — danh sách CSKH, [Đã xử lý]
theo mốc (sổ chạm khách, hoàn tác được), chuông CSKH khi buổi làm xong.

    scripts/test-nhanh.sh src/tests/services/test_lieu_trinh_sap_het_db.py

Đặc tả: ``docs/KE-HOACH-LIEU-TRINH.md`` mục "Sắp hết lộ trình".
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import LIEU_TRINH_SAP_HET, DichVuDaXong
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.lieu_trinh_service import (
    MA_SAP_HET,
    SAP_HET_CON_TOI_DA,
    ly_do_sap_het,
    moc_sap_het,
)
from clinicai.services.thong_bao_service import ThongBaoService
from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService
from tests.chay_nguoi_dua_tin import chay_het
from tests.services.test_lieu_trinh_db import (
    LT,
    _nguoi_khong_quyen,
    chi_dinh,
    dang_ky,
    doc,
    dung_ca,
    lam_xong,
    luot,
)
from tests.services.test_lieu_trinh_tien_db import lt_da_tra_truoc
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


# ── Luật thuần ──────────────────────────────────────────────────────────────


def _lt(**kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": "x",
        "trang_thai": "DANG_LAM",
        "so_buoi": 10,
        "da_lam": 3,
        "da_tra": 0,
        "dung_tra_truoc": 0,
        "tra_le": 0,
    }
    d.update(kw)
    return d


def test_nguong_mot_cho() -> None:
    assert SAP_HET_CON_TOI_DA == 1


def test_ly_do_sap_het_thuan() -> None:
    # Còn nhiều buổi, chưa trả trước → không sắp hết.
    assert ly_do_sap_het(_lt()) is None
    # Còn đúng 1 buổi.
    assert ly_do_sap_het(_lt(da_lam=9)) == "còn 1 buổi"
    # Đã dùng hết buổi trả trước, còn buổi chưa trả.
    assert (
        ly_do_sap_het(_lt(da_tra=3, dung_tra_truoc=3))
        == "đã dùng hết 3 buổi trả trước, còn 7 buổi chưa trả"
    )
    # Cả hai.
    assert ly_do_sap_het(_lt(so_buoi=3, da_lam=2, da_tra=2, dung_tra_truoc=2)) == (
        "còn 1 buổi · đã dùng hết 2 buổi trả trước, còn 1 buổi chưa trả"
    )
    # Trả trước còn buổi chưa dùng → không.
    assert ly_do_sap_het(_lt(da_tra=5, dung_tra_truoc=3)) is None
    # Hết buổi trả trước nhưng phần còn lại đã trả lẻ → không có gì để trả.
    assert (
        ly_do_sap_het(_lt(so_buoi=6, da_lam=2, da_tra=2, dung_tra_truoc=2, tra_le=4))
        is None
    )
    # Không đang làm / đã đủ buổi → không.
    for tt in ("DE_XUAT", "XONG", "DUNG"):
        assert ly_do_sap_het(_lt(trang_thai=tt, da_lam=9)) is None
    assert ly_do_sap_het(_lt(da_lam=10)) is None
    # Thiếu trường / rỗng → không ném.
    assert ly_do_sap_het({}) is None
    assert ly_do_sap_het({"trang_thai": "DANG_LAM", "so_buoi": None}) is None


def test_moc_sap_het_doi_khi_so_doi() -> None:
    a = moc_sap_het(_lt(id="L", da_lam=9))
    assert a == f"{MA_SAP_HET}:L:9:10:0"
    assert moc_sap_het(_lt(id="L", da_lam=9, so_buoi=11)) != a
    assert moc_sap_het(_lt(id="L", da_lam=9, da_tra=1)) != a


# ── Có database ─────────────────────────────────────────────────────────────


async def _phat_xong(ca: LT, visit: str, order: str) -> None:
    """Như lệnh Xong của phòng: phát ``service.completed`` (người thật bấm)."""
    async with ca.pool.acquire() as conn:
        await emit_event(
            conn,
            ten="service.completed",
            clinic_id=CLINIC,
            aggregate_id=order,
            so_ke_tiep=True,
            payload=DichVuDaXong(
                visit_id=visit,
                service_order_id=order,
                attempt_id=str(uuid.uuid4()),
                attempt_no=1,
                execution_revision=1,
            ),
            boi=nguoi(ca.bac_si),
            correlation_id=visit,
        )
    await chay_het(ca.pool, LIEU_TRINH_SAP_HET)


async def _lam_buoi(ca: LT) -> tuple[str, str]:
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    await lam_xong(ca, o)
    await _phat_xong(ca, v, o)
    return v, o


async def _chuong(ca: LT, moc: str) -> list[asyncpg.Record]:
    return list(
        await ca.pool.fetch(
            "SELECT vai_nhan, nguoi_nhan_staff_id, duong_dan, tieu_de, da_xu_ly_luc"
            "  FROM thong_bao WHERE clinic_id = $1::uuid"
            "   AND nguon = 'lieu_trinh_sap_het' AND nguon_id = $2",
            CLINIC,
            moc,
        )
    )


async def _ds(ca: LT) -> list[dict[str, Any]]:
    kq = await ca.svc.cskh(identity=ca.cskh, loai="sap_het")
    assert kq["loai"] == "sap_het"
    return list(kq["lieu_trinh"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_sap_het_chuong_danh_sach_da_xu_ly_hoan_tac(pool: asyncpg.Pool) -> None:
    """Liệu trình 3 buổi trả trước 2 → làm buổi 1: chưa sắp hết; làm buổi 2:
    chuông CSKH (một lần cho mốc) + dòng "Sắp hết" có lý do → [Đã xử lý] → dòng
    ẩn → Hoàn tác → hiện lại; CSKH thêm buổi (đổi mốc) → hiện lại."""
    ca = await dung_ca(pool)
    lt, _ = await lt_da_tra_truoc(ca, 3, 2)

    await _lam_buoi(ca)
    hien = await doc(ca, lt["id"])
    assert hien["sap_het_ly_do"] is None
    assert lt["id"] not in [d["id"] for d in await _ds(ca)]

    await _lam_buoi(ca)
    hien = await doc(ca, lt["id"])
    assert (hien["da_lam"], hien["so_buoi"], hien["da_tra"]) == (2, 3, 2)
    moc = moc_sap_het(hien)
    ly_do = "còn 1 buổi · đã dùng hết 2 buổi trả trước, còn 1 buổi chưa trả"
    assert hien["sap_het_ly_do"] == ly_do

    # Chuông: đúng một, cho vai CSKH, mở thẳng tab Liệu trình.
    (c,) = await _chuong(ca, moc)
    assert c["vai_nhan"] == "CSKH" and c["nguoi_nhan_staff_id"] is None
    assert c["duong_dan"] == "/nhac-tai-kham?tab=lieu-trinh"
    assert ca.ten in c["tieu_de"]
    cua_cskh = await ThongBaoService(pool).cua_toi(identity=ca.cskh)
    assert any(t["nguon"] == "lieu_trinh_sap_het" for t in cua_cskh)
    cua_bs = await ThongBaoService(pool).cua_toi(identity=ca.bac_si)
    assert not any(t["nguon"] == "lieu_trinh_sap_het" for t in cua_bs)

    # Cùng mốc, sự kiện tới lần nữa (kể cả chuông đã đóng) → không réo lại.
    await pool.execute(
        "UPDATE thong_bao SET da_xu_ly_luc = now(), da_xu_ly_boi = $2::uuid"
        " WHERE clinic_id = $1::uuid AND nguon_id = $3",
        CLINIC,
        ca.cskh.staff_id,
        moc,
    )
    o2 = await pool.fetchval(
        "SELECT o.id::text FROM lieu_trinh_buoi b JOIN service_order o"
        "  ON o.id = b.service_order_id WHERE b.lieu_trinh_id = $1::uuid"
        "  AND b.go_luc IS NULL AND b.buoi_so = 2",
        lt["id"],
    )
    v2 = await pool.fetchval(
        "SELECT visit_id::text FROM service_order WHERE id = $1::uuid", o2
    )
    await _phat_xong(ca, v2, o2)
    assert len(await _chuong(ca, moc)) == 1

    # Danh sách CSKH: một dòng, có lý do.
    (x,) = [d for d in await _ds(ca) if d["id"] == lt["id"]]
    assert x["sap_het_ly_do"] == ly_do and x["ten_khach"] == "Chị Liệu Trình"

    # [Đã xử lý] → ghi sổ chạm khách đúng mốc, dòng rời danh sách.
    kq = await ca.svc.da_xu_ly_sap_het(identity=ca.cskh, lieu_trinh_id=lt["id"])
    assert kq["moc"] == moc and kq["da_co"] is False and kq["tuong_tac_id"]
    dong = await pool.fetchrow(
        "SELECT loai, kenh, ket_qua, trang_thai_ma, noi_dung, clinic_patient_id::text"
        "  AS khach FROM tuong_tac_cskh WHERE id = $1::uuid",
        kq["tuong_tac_id"],
    )
    assert (dong["loai"], dong["kenh"], dong["ket_qua"]) == (
        "KHAC",
        "KHONG_LIEN_HE",
        "BO_QUA",
    )
    assert dong["trang_thai_ma"] == moc and dong["khach"] == ca.khach
    assert lt["id"] not in [d["id"] for d in await _ds(ca)]
    # Bấm lại cùng mốc → trả dòng đã có, không ghi thêm.
    lai = await ca.svc.da_xu_ly_sap_het(identity=ca.cskh, lieu_trinh_id=lt["id"])
    assert lai["tuong_tac_id"] == kq["tuong_tac_id"] and lai["da_co"] is True
    # Khung khách: vẫn có chip (hồ sơ), kèm cờ đã xử lý.
    kh = await ca.svc.theo_khach(identity=ca.cskh, clinic_patient_id=ca.khach)
    (k,) = kh["lieu_trinh"]
    assert k["sap_het_ly_do"] == ly_do and k["sap_het_da_xu_ly"] is True

    # Hoàn tác (lệnh sẵn có của sổ chạm khách) → dòng hiện lại.
    await TuongTacCskhService(pool).hoan_tac(
        identity=ca.cskh, tuong_tac_id=kq["tuong_tac_id"]
    )
    assert lt["id"] in [d["id"] for d in await _ds(ca)]
    kh = await ca.svc.theo_khach(identity=ca.cskh, clinic_patient_id=ca.khach)
    assert kh["lieu_trinh"][0]["sap_het_da_xu_ly"] is False

    # Xử lý lại, rồi CSKH [Thêm buổi] (đăng ký 5 buổi) → mốc đổi → hiện lại với
    # lý do mới (vẫn hết buổi trả trước, còn 3 buổi chưa trả).
    await ca.svc.da_xu_ly_sap_het(identity=ca.cskh, lieu_trinh_id=lt["id"])
    assert lt["id"] not in [d["id"] for d in await _ds(ca)]
    await dang_ky(ca, lt["id"], so_buoi=5)
    (y,) = [d for d in await _ds(ca) if d["id"] == lt["id"]]
    assert y["sap_het_ly_do"] == ("đã dùng hết 2 buổi trả trước, còn 3 buổi chưa trả")


async def _dem_chuong(pool: asyncpg.Pool) -> int:
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM thong_bao WHERE clinic_id = $1::uuid"
            " AND nguon = 'lieu_trinh_sap_het'",
            CLINIC,
        )
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_sap_het_quyen_va_khong_sap_het(pool: asyncpg.Pool) -> None:
    """Không quyền CSKH → chặn; liệu trình không sắp hết → 409 có câu; buổi lẻ
    (không liệu trình) không réo; liệu trình đã dừng không ở danh sách."""
    ca = await dung_ca(pool)
    truoc = await _dem_chuong(pool)
    v = await luot(ca)
    o = await chi_dinh(ca, v)
    await lam_xong(ca, o)
    await _phat_xong(ca, v, o)
    assert await _dem_chuong(pool) == truoc

    lt, _ = await lt_da_tra_truoc(ca, 10, 5)
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.da_xu_ly_sap_het(identity=ca.cskh, lieu_trinh_id=lt["id"])
    assert e.value.error_code == "KHONG_SAP_HET"

    async with pool.acquire() as conn:
        ai = await _nguoi_khong_quyen(conn, ca.loc)
    with pytest.raises(SafetyGateError):
        await ca.svc.cskh(identity=ai, loai="sap_het")
    with pytest.raises(SafetyGateError):
        await ca.svc.da_xu_ly_sap_het(identity=ai, lieu_trinh_id=lt["id"])

    # Liệu trình 2 buổi, buổi 1 xong (khách đã nhận: buổi đã làm) → "còn 1
    # buổi" → dừng → rời danh sách.
    ca2 = await dung_ca(pool)
    v2 = await luot(ca2, dieu_tri=True)
    o2 = await chi_dinh(ca2, v2)
    mot = await ca2.svc.tao(
        identity=ca2.bac_si,
        visit_id=v2,
        so_buoi=2,
        service_order_id=o2,
        idempotency_key=f"lt-{uuid.uuid4().hex}",
    )
    lt_id = mot["lieu_trinh"]["id"]
    await lam_xong(ca2, o2)
    hien = await doc(ca2, lt_id)
    assert hien["trang_thai"] == "DANG_LAM" and hien["sap_het_ly_do"] == "còn 1 buổi"
    assert lt_id in [d["id"] for d in await _ds(ca2)]
    await ca2.svc.dung(
        identity=ca2.cskh,
        lieu_trinh_id=lt_id,
        expected_revision=hien["revision"],
        idempotency_key=f"lt-{uuid.uuid4().hex}",
    )
    assert lt_id not in [d["id"] for d in await _ds(ca2)]
