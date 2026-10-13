"""Danh sách hoá đơn: "chưa trả lại khách", việc còn tồn, sự kiện sau thu — DB thật.

Màn chỉ để XEM: quầy / CSKH xử lý bằng nút có sẵn thì việc tồn tự hết.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.core.clock import now_vn
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.hoan_tien_service import HoanTienService
from tests.services.test_giam_gia_db import _thu
from tests.services.test_quay_thu_mot_hoa_don_db import _kich_ban

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _cua_luot(data: dict[str, Any], visit_id: str) -> list[dict[str, Any]]:
    return [v for v in data["viec_ton"] if v["visit_id"] == visit_id]


async def test_bo_dich_vu_sau_thu_thanh_chua_tra_lai_roi_tu_het_khi_hoan(
    pool: asyncpg.Pool,
) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    await _thu(q, sa, soi, hpv)  # 700k: khám 150 + SÂ 250 + Soi 300 (tiền mặt)
    await pool.execute(
        "UPDATE service_order SET exec_status='cancelled', cancel_reason='kê nhầm'"
        " WHERE id=$1::uuid",
        soi,
    )
    ql = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = DanhSachHoaDonService(pool)
    ngay = now_vn().date().isoformat()

    data = await svc.xem(identity=ql, tu=ngay, den=ngay, tim=f"TT-{q.duoi}")
    [khach] = data["khach"]
    assert khach["chua_tra_lai"] == 300_000
    assert (khach["da_thu_dich_vu"], khach["da_thu_thuoc"]) == (700_000, 0)
    assert [d["so_tien"] for d in khach["tien_thua"]] == [300_000]
    ton = _cua_luot(data, q.visit_id)
    assert [(v["loai"], v["so_tien"]) for v in ton] == [("CHUA_TRA_LAI", 300_000)]
    assert khach["viec_ton"] == ton
    assert data["tong"]["chua_tra_lai"] >= 300_000
    # Trong phiếu: sự kiện "bỏ dịch vụ sau thu" có giờ.
    [phieu] = khach["phieu"]
    bo = [e for e in phieu["su_kien"] if e["loai"] == "BO_DICH_VU"]
    assert len(bo) == 1 and bo[0]["so_tien"] == 300_000 and bo[0]["luc"]
    # Lọc "còn việc tồn" vẫn giữ khách này.
    loc = await svc.xem(
        identity=ql, tu=ngay, den=ngay, tim=f"TT-{q.duoi}", trang_thai="CON_VIEC_TON"
    )
    assert [k["id"] for k in loc["khach"]] == [khach["id"]]

    # Quầy bấm "Hoàn tiền thừa" (nút có sẵn) → việc tồn tự hết.
    await HoanTienService(pool).hoan_tien_thua(identity=ql, visit_id=q.visit_id)
    sau = await svc.xem(identity=ql, tu=ngay, den=ngay, tim=f"TT-{q.duoi}")
    [khach2] = sau["khach"]
    assert khach2["chua_tra_lai"] == 0
    assert not _cua_luot(sau, q.visit_id)
    hoan = [e for e in khach2["phieu"][0]["su_kien"] if e["loai"] == "HOAN_TIEN"]
    assert [e["so_tien"] for e in hoan] == [-300_000]


async def test_ck_chua_ve_va_ghi_no_la_viec_ton_moi_ngay(pool: asyncpg.Pool) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    await _thu(q, sa, soi, hpv, method="TRANSFER")  # CK → chờ xác minh
    q2, *_ = await _kich_ban(pool)
    await pool.execute(
        "INSERT INTO cong_no (clinic_id, visit_id, clinic_patient_id, so_tien,"
        " ly_do, ghi_boi) SELECT $1::uuid, $2::uuid, v.clinic_patient_id, 400000,"
        " 'quên ví', $3::uuid FROM visit v WHERE v.visit_id = $2::uuid",
        q2.thu_ngan.clinic_id,
        q2.visit_id,
        q2.thu_ngan.staff_id,
    )
    ql = replace(q.thu_ngan, role=ClinicRole.MANAGEMENT)
    svc = DanhSachHoaDonService(pool)
    # Việc tồn không theo ô ngày: xem một ngày rất cũ vẫn thấy.
    data = await svc.xem(identity=ql, tu="2026-01-01", den="2026-01-01")
    ck = _cua_luot(data, q.visit_id)
    assert [(v["loai"], v["so_tien"]) for v in ck] == [("CK_CHUA_VE", 700_000)]
    assert ck[0]["ten_loai"] == "Chuyển khoản chưa về" and ck[0]["ma"]
    no = _cua_luot(data, q2.visit_id)
    assert [(v["loai"], v["so_tien"], v["mo_ta"]) for v in no] == [
        ("GHI_NO", 400_000, "quên ví")
    ]
    assert data["tong"]["so_viec_ton"] == len(data["viec_ton"])
    # Lọc loại hoá đơn "thuốc": CK dịch vụ và ghi nợ (cấp lượt) không hiện.
    thuoc = await svc.xem(identity=ql, tu="2026-01-01", den="2026-01-01", loai="thuoc")
    assert not _cua_luot(thuoc, q.visit_id) and not _cua_luot(thuoc, q2.visit_id)
