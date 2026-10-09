"""Liệu trình — phần máy chủ cho giao diện C1 (hồ sơ khám + quầy thu dịch vụ).

* Thẻ liệu trình (``theo_luot``): nút do máy chủ quyết (điều chỉnh / dừng / mở
  lại, tạo / gỡ / tách / chọn), [Hoàn tác] lần sửa mới nhất, dịch vụ cho lối
  "Chỉ đề xuất", nơi làm từng buổi.
* Bảng quầy: lượt CHỈ có dòng trả trước chưa thu vẫn hiện ở quầy dịch vụ.
* Phiếu thu in: dòng trả trước đánh dấu liệu trình.
* #16 (giữ chặn): huỷ / hoàn tác lần thu trả trước đã dùng buổi → câu rõ cho quầy.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.lieu_trinh_service import nut_chi_dinh, nut_lieu_trinh
from clinicai.services.lieu_trinh_tien import CAU_HUY_TRA_TRUOC_DA_DUNG
from clinicai.services.payment_service import PaymentService
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_lieu_trinh_db import (
    GIA,
    LT,
    _khoa,
    chi_dinh,
    dang_ky,
    doc,
    dung_ca,
    lam_xong,
    luot,
    tao,
)
from tests.services.test_lieu_trinh_tien_db import lt_da_tra_truoc, thu, tra_truoc
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


# ── Luật thuần ──────────────────────────────────────────────────────────────


def test_nut_lieu_trinh_theo_trang_thai() -> None:
    for tt in ("DE_XUAT", "DANG_LAM", "XONG"):
        assert nut_lieu_trinh({"trang_thai": tt}) == {
            "dieu_chinh": True,
            "dung": True,
            "mo_lai": False,
        }
    assert nut_lieu_trinh({"trang_thai": "DUNG"}) == {
        "dieu_chinh": False,
        "dung": False,
        "mo_lai": True,
    }
    # Rác → coi như chưa dừng (lệnh vẫn gác lại).
    assert nut_lieu_trinh({})["mo_lai"] is False


def test_nut_chi_dinh() -> None:
    chua: dict[str, Any] = {"song": True, "lieu_trinh_id": None, "ung_vien": []}
    assert nut_chi_dinh(chua) == {
        "tao": True,
        "go": False,
        "tach": False,
        "chon": False,
        "khach_chon": False,
    }
    # Buổi lẻ + bác sĩ đã ĐỀ XUẤT lộ trình cùng dịch vụ → [Khách chọn lộ trình].
    de_xuat: dict[str, Any] = {
        "song": True,
        "lieu_trinh_id": None,
        "ung_vien": [{"id": "d", "trang_thai": "DE_XUAT"}],
    }
    assert nut_chi_dinh(de_xuat)["khach_chon"] is True
    assert nut_chi_dinh(de_xuat)["chon"] is True
    gan: dict[str, Any] = {
        "song": True,
        "lieu_trinh_id": "a",
        "ung_vien": [{"id": "a"}],
    }
    assert nut_chi_dinh(gan) == {
        "tao": False,
        "go": True,
        "tach": True,
        "chon": False,
        "khach_chon": False,
    }
    hai: dict[str, Any] = {
        "song": True,
        "lieu_trinh_id": "a",
        "ung_vien": [{"id": "a"}, {"id": "b"}],
    }
    assert nut_chi_dinh(hai)["chon"] is True
    # Chỉ định đã bỏ / không làm: không nút nào.
    bo: dict[str, Any] = {
        "song": False,
        "lieu_trinh_id": None,
        "ung_vien": [{"id": "b"}],
    }
    assert not any(nut_chi_dinh(bo).values())
    assert not any(nut_chi_dinh({}).values())


# ── DB ──────────────────────────────────────────────────────────────────────


async def _the(ca: LT, visit: str) -> dict[str, Any]:
    return await ca.svc.theo_luot(identity=ca.bac_si, visit_id=visit)


@pytest.mark.db
@pytest.mark.asyncio
async def test_the_lieu_trinh_nut_hoan_tac_dich_vu_noi_lam(pool: asyncpg.Pool) -> None:
    """Thẻ: chỉ định chưa gắn → [Tạo]; tạo + khách chọn → buổi 1 "chưa làm",
    nút gỡ/tách; điều
    chỉnh → [Hoàn tác] trỏ đúng dòng lịch sử; dừng → chỉ còn Mở lại; buổi làm
    tại bàn khám ghi "Bàn khám"; dịch vụ nhóm Điều trị có trong lối đề xuất."""
    ca = await dung_ca(pool)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    t = await _the(ca, v)
    (c,) = t["chi_dinh"]
    assert c["nut"]["tao"] and not c["nut"]["go"]
    assert t["lieu_trinh"] == []
    assert ca.ma in {d["service_code"] for d in t["dich_vu_de_xuat"]}
    assert t["ghi_duoc"] is True

    lt = await tao(ca, v, 10, order=o)
    t = await _the(ca, v)
    (c,) = t["chi_dinh"]
    (x,) = t["lieu_trinh"]
    assert (c["lieu_trinh_id"], c["buoi_so"]) == (lt["id"], 1)
    assert c["nut"] == {
        "tao": False,
        "go": True,
        "tach": True,
        "chon": False,
        "khach_chon": False,
    }
    assert c["chu_buoi"] == "Buổi 1/10 · chưa làm"
    assert x["nut"] == {"dieu_chinh": True, "dung": True, "mo_lai": False}
    # Khách chọn luôn lúc lập = một lần đăng ký → Hoàn tác được.
    assert x["hoan_tac"] is not None and x["hoan_tac"]["hanh_dong"] == "DANG_KY"

    kq = await ca.svc.dieu_chinh(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=x["revision"],
        so_buoi=12,
        ghi_chu="2 buổi / tuần",
        idempotency_key=_khoa(),
    )
    (x,) = (await _the(ca, v))["lieu_trinh"]
    assert x["hoan_tac"] is not None and x["hoan_tac"]["hanh_dong"] == "DIEU_CHINH"
    ls = await ca.svc.lich_su(identity=ca.bac_si, lieu_trinh_id=lt["id"])
    (moi,) = [d for d in ls["dong"] if d.get("hoan_tac_duoc")]
    assert moi["id"] == x["hoan_tac"]["lich_su_id"]
    await ca.svc.hoan_tac(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        lich_su_id=x["hoan_tac"]["lich_su_id"],
        expected_revision=kq["lieu_trinh"]["revision"],
        idempotency_key=_khoa(),
    )
    (x,) = (await _the(ca, v))["lieu_trinh"]
    assert x["so_buoi"] == 10

    await ca.svc.dung(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=x["revision"],
        ly_do=None,
        idempotency_key=_khoa(),
    )
    (x,) = (await _the(ca, v))["lieu_trinh"]
    assert x["trang_thai"] == "DUNG"
    assert x["nut"] == {"dieu_chinh": False, "dung": False, "mo_lai": True}

    # Nơi làm của buổi: lần làm tại bàn khám → "Bàn khám".
    (b,) = x["buoi"]
    assert b["noi_lam"] is None  # chưa làm, chưa xếp phòng
    await pool.execute(
        "INSERT INTO service_execution_attempt (clinic_id, service_order_id,"
        " attempt_no, routing_revision_snapshot, status, started_by, started_at,"
        " noi_lam)"
        " VALUES ($1::uuid, $2::uuid, 1, 0, 'IN_PROGRESS', $3::uuid, now(),"
        " 'BAN_KHAM')",
        CLINIC,
        o,
        ca.bac_si.staff_id,
    )
    (x,) = (await _the(ca, v))["lieu_trinh"]
    (b,) = x["buoi"]
    assert b["order_id"] == o and b["noi_lam"] == "Bàn khám"


@pytest.mark.db
@pytest.mark.asyncio
async def test_quay_hien_luot_chi_co_dong_tra_truoc(pool: asyncpg.Pool) -> None:
    """Lượt KHÔNG có chỉ định nào, quầy đặt "trả trước 2 buổi" → lượt hiện ở bảng
    quầy dịch vụ, chờ thu, hoá đơn có dòng liệu trình; thu xong thì rời hàng
    chờ. Phiếu thu in dòng đánh dấu liệu trình."""
    ca = await dung_ca(pool)
    v1 = await luot(ca, dieu_tri=True, ngay_truoc=3)
    lt = await tao(ca, v1, 5)
    await dang_ky(ca, lt["id"])
    # Lượt Điều trị (không tự thu phí khám), chưa có chỉ định / đơn / khám xong.
    v2 = await luot(ca, dieu_tri=True)
    bang = CashierBoardService(pool)

    b = await bang.board(identity=ca.thu_ngan, modes=["dich_vu"])
    assert v2 not in b["ds_cho_thu"]

    await tra_truoc(ca, v2, lt["id"], 2)
    b = await bang.board(identity=ca.thu_ngan, modes=["dich_vu"])
    assert v2 in b["ds_cho_thu"]
    (item,) = [i for i in b["items"] if i["visit_id"] == v2]
    assert item["cho_thu"] is True
    (dong,) = [d for d in item["quay_thu"]["phong_kham"] if d["loai"] == "lieu_trinh"]
    assert (dong["so_buoi"], dong["gia"]) == (2, 2 * GIA)
    assert item["quay_thu"]["tong"] == 2 * GIA

    cyc = await thu(ca, v2)
    b = await bang.board(identity=ca.thu_ngan, modes=["dich_vu"])
    assert v2 not in b["ds_cho_thu"]
    assert (await doc(ca, lt["id"]))["da_tra"] == 2

    p = await QuayThuService(pool).phieu(identity=ca.thu_ngan, id_=cyc)
    (d,) = p["dong"]
    assert d["lieu_trinh"] is True
    assert d["ten"] == f"{ca.ten} — trả trước 2 buổi"
    assert d["thanh_tien"] == 2 * GIA


@pytest.mark.db
@pytest.mark.asyncio
async def test_16_huy_lan_thu_tra_truoc_da_dung_cau_ro(pool: asyncpg.Pool) -> None:
    """#16 GIỮ chặn: buổi đã làm bằng tiền trả trước → hoàn tác lần thu bị từ
    chối với câu chỉ lối hoàn phần chưa dùng (không phải câu kỹ thuật)."""
    ca = await dung_ca(pool)
    lt, cyc = await lt_da_tra_truoc(ca, 4, 1)
    v = await luot(ca, dieu_tri=True)
    o = await chi_dinh(ca, v)
    await lam_xong(ca, o)
    with pytest.raises(LuotKhamConflictError) as e:
        await PaymentService(pool).hoan_tac(
            payment_cycle_id=cyc, ly_do=None, identity=ca.thu_ngan
        )
    assert e.value.error_code == "PHU_VUOT_DA_TRA"
    assert str(e.value) == CAU_HUY_TRA_TRUOC_DA_DUNG
    d = await doc(ca, lt["id"])
    assert (d["da_tra"], d["dung_tra_truoc"]) == (1, 1)
