"""Liệu trình điều trị nhiều buổi — B1 (mô hình, gắn/gỡ buổi, lịch sử, API).

Mỗi bài dựng MỘT dịch vụ nhóm DIEU_TRI riêng (mã ngẫu nhiên) + khách riêng —
không đụng bảng giá dữ liệu nạp, đổi giá thoải mái. Số # trong tên bài là dòng
của bảng tình huống ``docs/KE-HOACH-LIEU-TRINH.md`` Phần B. Tình huống chạm
tiền (trả trước, phủ buổi, cổng làm, nợ khi về, hoàn) ở
``test_lieu_trinh_tien_db.py`` (B2).
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.ho_so_dich_vu import sinh_chi_dinh_dieu_tri
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.lieu_trinh_service import (
    LieuTrinhService,
    con_lai,
    doc_ds_uuid,
    doc_ghi_chu,
    doc_so_buoi,
    doc_so_ngay,
)
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

GIA = 400_000


async def _nguoi_khong_quyen(conn: asyncpg.Connection, loc: str) -> StaffIdentity:
    """Tài khoản chưa được bật khối nào (preset mặc định nay "mở hết")."""
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ('Không quyền', 'CSKH', $1::uuid, true)"
        " RETURNING id::text",
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, 'CSKH', true) ON CONFLICT DO NOTHING",
        CLINIC,
        sid,
    )
    return StaffIdentity(
        staff_id=str(sid),
        auth_user_id=str(uuid.uuid4()),
        full_name="Không quyền",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


def _khoa() -> str:
    return f"lt-{uuid.uuid4().hex}"


@dataclass
class LT:
    pool: asyncpg.Pool
    loc: str
    bac_si: StaffIdentity
    cskh: StaffIdentity
    thu_ngan: StaffIdentity
    le_tan: StaffIdentity
    ma: str
    ten: str
    st: str
    sp: str
    khach: str
    node: str

    @property
    def svc(self) -> LieuTrinhService:
        return LieuTrinhService(self.pool)


async def dung_ca(pool: asyncpg.Pool, gia: int = GIA) -> LT:
    """Dịch vụ Điều trị riêng (bảng giá + loại khám nhóm DIEU_TRI) + một khách."""
    duoi = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        node = await conn.fetchval(
            "SELECT node_code FROM service_type st JOIN service_price sp"
            "   ON sp.id = st.service_price_id"
            " WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI'"
            "   AND sp.node_code IS NOT NULL LIMIT 1",
            CLINIC,
        )
        ma = f"LTDV-{duoi}"
        ten = f"Ghế điện thử {duoi}"
        sp = await conn.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, billing_owner, node_code)"
            " VALUES ($1::uuid, $2, $3, 'dich_vu', $4, 'CLINIC', $5)"
            " RETURNING id::text",
            CLINIC,
            ma,
            ten,
            gia,
            node or "DICHVU-THUTHUAT",
        )
        st = await conn.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, nhom,"
            " service_price_id, di_thang_phong)"
            " VALUES ($1::uuid, $2, $3, true, 'DIEU_TRI', $4::uuid, true)"
            " RETURNING id::text",
            CLINIC,
            f"DT-{duoi}",
            ten,
            sp,
        )
        khach = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary) VALUES ($1::uuid, $2, 'Chị Liệu Trình', $3::uuid,"
            " '0900000000') RETURNING clinic_patient_id::text",
            CLINIC,
            f"LT-{duoi}",
            loc,
        )
        return LT(
            pool=pool,
            loc=str(loc),
            bac_si=await _nguoi(conn, loc, "DOCTOR"),
            cskh=await _nguoi(conn, loc, "CSKH"),
            thu_ngan=await _nguoi(conn, loc, "CASHIER"),
            le_tan=await _nguoi(conn, loc, "RECEPTION"),
            ma=ma,
            ten=ten,
            st=str(st),
            sp=str(sp),
            khach=str(khach),
            node=str(node or "DICHVU-THUTHUAT"),
        )


async def luot(ca: LT, *, dieu_tri: bool = False, ngay_truoc: int = 0) -> str:
    """Một lượt mới của khách (+ phiên khám chính). ``dieu_tri`` = lượt đặt lịch
    Điều trị (loại khám trỏ dịch vụ của ca)."""
    async with ca.pool.acquire() as conn:
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at, service_type_id, created_at)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', $3::uuid,"
            "         now() - make_interval(days => $5), $4::uuid,"
            "         now() - make_interval(days => $5))"
            " RETURNING visit_id::text",
            CLINIC,
            ca.khach,
            ca.bac_si.staff_id,
            ca.st if dieu_tri else None,
            ngay_truoc,
        )
        await conn.execute(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind)"
            " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY')",
            CLINIC,
            vid,
        )
    return str(vid)


async def chi_dinh(ca: LT, visit: str, chon: str = "SELECTED") -> str:
    """Chỉ định dịch vụ điều trị của ca trong lượt (như bàn khám kê)."""
    return str(
        await ca.pool.fetchval(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " authorized_by, authorized_at, selection_status, routing_status)"
            " SELECT $1::uuid, $2::uuid, c.id, $3, $4, $5, 'authorized', $6::uuid,"
            "        $6::uuid, now(), $7, 'UNASSIGNED'"
            "   FROM consultation c WHERE c.visit_id = $2::uuid AND c.kind = 'PRIMARY'"
            " RETURNING id::text",
            CLINIC,
            visit,
            ca.ma,
            ca.ten,
            ca.node,
            ca.bac_si.staff_id,
            chon,
        )
    )


async def dat_trang_thai(ca: LT, order: str, **cot: Any) -> None:
    sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(cot))
    await ca.pool.execute(
        f"UPDATE service_order SET {sets} WHERE id = $1::uuid", order, *cot.values()
    )


async def lam_xong(ca: LT, order: str) -> None:
    await dat_trang_thai(ca, order, execution_status="COMPLETED")


async def tao(
    ca: LT, visit: str, so_buoi: int = 10, order: str | None = None, **kw: Any
) -> dict[str, Any]:
    kq = await ca.svc.tao(
        identity=ca.bac_si,
        visit_id=visit,
        so_buoi=so_buoi,
        service_order_id=order,
        service_code=None if order else ca.ma,
        idempotency_key=_khoa(),
        **kw,
    )
    return dict(kq["lieu_trinh"])


async def doc(ca: LT, lt_id: str) -> dict[str, Any]:
    return await ca.svc.chi_tiet(identity=ca.bac_si, lieu_trinh_id=lt_id)


async def buoi_song(ca: LT, order: str) -> asyncpg.Record | None:
    return await ca.pool.fetchrow(
        "SELECT lieu_trinh_id::text AS lt, buoi_so, tra_truoc FROM lieu_trinh_buoi"
        " WHERE service_order_id = $1::uuid AND go_luc IS NULL",
        order,
    )


async def dang_ky(ca: LT, lt_id: str, so_buoi: int | None = None) -> dict[str, Any]:
    hien = await doc(ca, lt_id)
    kq = await ca.svc.dang_ky(
        identity=ca.cskh,
        lieu_trinh_id=lt_id,
        expected_revision=hien["revision"],
        so_buoi=so_buoi,
        idempotency_key=_khoa(),
    )
    return dict(kq["lieu_trinh"])


# ── Luật thuần: đầu vào rác → rỗng / 422, không 500 ─────────────────────────


@pytest.mark.parametrize("rac", [None, "", "abc", "0", "-3", "201", 1.5, True, [], {}])
def test_doc_so_buoi_rac_tra_rong(rac: Any) -> None:
    assert doc_so_buoi(rac) is None


@pytest.mark.parametrize(
    "rac", [None, "", "x", "-1", "99999", True, "2026-13-45", "14 ngày", [], object()]
)
def test_doc_so_ngay_rac_tra_rong(rac: Any) -> None:
    assert doc_so_ngay(rac) is None


def test_doc_so_ngay_va_so_buoi_hop_le() -> None:
    assert doc_so_ngay("30") == 30 and doc_so_ngay(0) == 0
    assert doc_so_buoi(" 10 ") == 10 and doc_so_buoi(200) == 200


def test_doc_ghi_chu() -> None:
    assert doc_ghi_chu("  ") is None and doc_ghi_chu(None) is None
    assert doc_ghi_chu(" 2 buổi/tuần ") == "2 buổi/tuần"
    with pytest.raises(ValidationError):
        doc_ghi_chu("x" * 1001)
    with pytest.raises(ValidationError):
        doc_ghi_chu(123)


def test_doc_ds_uuid_bo_ma_rac() -> None:
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert doc_ds_uuid(f"{a}, rac,{b},{a},") == [a, b]
    assert doc_ds_uuid(None) == [] and doc_ds_uuid("2026-10-08") == []


def test_con_lai_thuan() -> None:
    d = con_lai(
        {"so_buoi": 10, "da_lam": 3, "da_tra": 5, "dung_tra_truoc": 2, "tra_le": 1}
    )
    assert d == {"con_lai": 7, "con_tra_truoc": 3, "chua_tra": 4}


def test_staging_che_cot_chu_cua_lieu_trinh() -> None:
    """#22: cột chữ tự do của liệu trình nằm trong danh sách che staging."""
    sql = (
        Path(__file__).resolve().parents[3] / "scripts/staging-che-du-lieu.sql"
    ).read_text(encoding="utf-8")
    for bang, cot in [
        ("lieu_trinh", "ghi_chu_lo_trinh"),
        ("lieu_trinh", "ly_do_dung"),
        ("lieu_trinh_lich_su", "ban_cu"),
        ("lieu_trinh_lich_su", "ban_moi"),
    ]:
        assert re.search(rf"\('{bang}', '{cot}', '(chu|json|json_manh)'\)", sql), (
            bang,
            cot,
        )


# ── DB ──────────────────────────────────────────────────────────────────────



@pytest.mark.db
@pytest.mark.asyncio
async def test_1_de_xuat_tu_chi_dinh_hom_nay_la_buoi_1(pool: asyncpg.Pool) -> None:
    """#1 (phần kế hoạch): bác sĩ đề xuất 10 buổi từ chỉ định hôm nay → buổi 1;
    khách chốt làm (SELECTED) → DANG_LAM, còn 9 sau khi làm xong buổi 1."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o = await chi_dinh(ca, v, chon="PENDING")
    lt = await tao(ca, v, 10, order=o, ghi_chu="2 buổi/tuần")
    assert lt["trang_thai"] == "DE_XUAT" and lt["don_gia"] == GIA
    assert lt["ghi_chu_lo_trinh"] == "2 buổi/tuần"
    b = await buoi_song(ca, o)
    assert b is not None and b["lt"] == lt["id"] and b["buoi_so"] == 1
    assert not b["tra_truoc"]
    await dat_trang_thai(ca, o, selection_status="SELECTED")
    assert (await doc(ca, lt["id"]))["trang_thai"] == "DANG_LAM"
    await lam_xong(ca, o)
    d = await doc(ca, lt["id"])
    assert (d["da_lam"], d["con_lai"]) == (1, 9)
    # Thẻ của lượt: liệu trình + chỉ định điều trị kèm buổi.
    the = await ca.svc.theo_luot(identity=ca.bac_si, visit_id=v)
    assert [x["id"] for x in the["lieu_trinh"]] == [lt["id"]]
    (c,) = the["chi_dinh"]
    assert c["order_id"] == o and c["buoi_so"] == 1 and c["can_chon"] is False


@pytest.mark.db
@pytest.mark.asyncio
async def test_chi_de_xuat_khong_lam_hom_nay(pool: asyncpg.Pool) -> None:
    """Nút "Chỉ đề xuất, không làm hôm nay": không chỉ định, thẻ lượt vẫn hiện."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    lt = await tao(ca, v, 6)
    assert lt["trang_thai"] == "DE_XUAT" and lt["buoi"] == []
    assert (
        await pool.fetchval("SELECT count(*) FROM service_order WHERE visit_id = $1", v)
        == 0
    )
    the = await ca.svc.theo_luot(identity=ca.bac_si, visit_id=v)
    assert [x["id"] for x in the["lieu_trinh"]] == [lt["id"]]


@pytest.mark.db
@pytest.mark.asyncio
async def test_4_khach_tu_choi_hom_nay_buoi_go_lt_ve_de_xuat_hien_cskh(
    pool: asyncpg.Pool,
) -> None:
    """#4: chỉ định NOT_SELECTED → buổi gỡ, LT ở DE_XUAT → danh sách CSKH."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o = await chi_dinh(ca, v, chon="PENDING")
    lt = await tao(ca, v, 10, order=o)
    await dat_trang_thai(ca, o, selection_status="NOT_SELECTED")
    assert await buoi_song(ca, o) is None
    d = await doc(ca, lt["id"])
    assert d["trang_thai"] == "DE_XUAT" and d["so_gan"] == 0
    ds = await ca.svc.cskh(identity=ca.cskh, loai="de_xuat")
    assert lt["id"] in [x["id"] for x in ds["lieu_trinh"]]
    # Khách đổi ý chọn lại → gắn lại đúng liệu trình (lần gỡ là tự động).
    await dat_trang_thai(ca, o, selection_status="SELECTED")
    b = await buoi_song(ca, o)
    assert b is not None and b["lt"] == lt["id"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_5_cskh_dang_ky_1_buoi_hoac_ca_lo_trinh(pool: asyncpg.Pool) -> None:
    """#5: CSKH [Đăng ký] → DANG_LAM (Q3: không thu gì ở đây)."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    lt = await tao(ca, v, 10)
    moi = await dang_ky(ca, lt["id"], so_buoi=1)
    assert moi["trang_thai"] == "DANG_LAM" and moi["so_buoi"] == 1
    assert moi["dang_ky_boi"] == ca.cskh.full_name
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", v
        )
        == 0
    )
    ca2 = await dung_ca(pool)
    v2 = await luot(ca2)
    lt2 = await tao(ca2, v2, 10)
    assert (await dang_ky(ca2, lt2["id"]))["so_buoi"] == 10
    # Người không có khối y khoa / trưởng ca không đề xuất được.
    async with pool.acquire() as conn:
        la = await _nguoi_khong_quyen(conn, ca.loc)
    with pytest.raises(SafetyGateError):
        await ca.svc.tao(
            identity=la,
            visit_id=v,
            so_buoi=3,
            service_code=ca.ma,
            idempotency_key=_khoa(),
        )


@pytest.mark.db
@pytest.mark.asyncio
async def test_6_19_dat_lich_dieu_tri_check_in_tu_gan_buoi_ke(
    pool: asyncpg.Pool,
) -> None:
    """#6/#19: lượt đặt lịch Điều trị (không qua bàn khám) → consumer sinh chỉ
    định → trigger gắn buổi kế của liệu trình đang làm."""
    ca = await dung_ca(pool)
    v1 = await luot(ca, ngay_truoc=7)
    o1 = await chi_dinh(ca, v1)
    lt = await tao(ca, v1, 10, order=o1)
    await lam_xong(ca, o1)
    v2 = await luot(ca, dieu_tri=True)
    async with pool.acquire() as conn, conn.transaction():
        o2 = await sinh_chi_dinh_dieu_tri(
            conn, clinic_id=CLINIC, visit_id=v2, nguoi_bam=None
        )
    assert o2 is not None
    b = await buoi_song(ca, o2)
    assert b is not None and (b["lt"], b["buoi_so"]) == (lt["id"], 2)
    chip = await ca.svc.chip(identity=ca.le_tan, visit_ids=f"{v2},rac")
    assert chip["chi_dinh"][o2]["buoi_so"] == 2
    assert chip["chi_dinh"][o2]["so_buoi"] == 10
    assert [x["lieu_trinh_id"] for x in chip["khach"][v2]] == [lt["id"]]


@pytest.mark.db
@pytest.mark.asyncio
async def test_7_huy_chi_dinh_buoi_tra_ve(pool: asyncpg.Pool) -> None:
    """#7 (phần buổi): bỏ chỉ định bằng lệnh thật → buổi gỡ, số buổi trả về."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o)
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o, identity=ca.bac_si, ly_do="Khách về không làm"
    )
    assert await buoi_song(ca, o) is None
    d = await doc(ca, lt["id"])
    assert d["so_gan"] == 0 and [b["go_cach"] for b in d["buoi"]] == ["TU_DONG"]
    # Lượt sau buổi kế lại là buổi 1 (số không bị chiếm bởi buổi đã gỡ).
    await dang_ky(ca, lt["id"])
    v2 = await luot(ca)
    o2 = await chi_dinh(ca, v2)
    assert (await buoi_song(ca, o2))["buoi_so"] == 1  # type: ignore[index]


@pytest.mark.db
@pytest.mark.asyncio
async def test_8_hoan_tac_xong_buoi_dem_da_lam_giam(pool: asyncpg.Pool) -> None:
    """#8: Xong buổi cuối → XONG; hoàn tác Xong → đếm giảm, về DANG_LAM."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 1, order=o)
    await lam_xong(ca, o)
    d = await doc(ca, lt["id"])
    assert (d["trang_thai"], d["da_lam"]) == ("XONG", 1)
    await dat_trang_thai(ca, o, execution_status="IN_PROGRESS")
    d = await doc(ca, lt["id"])
    assert (d["trang_thai"], d["da_lam"]) == ("DANG_LAM", 0)
    hs = await ca.svc.lich_su(identity=ca.bac_si, lieu_trinh_id=lt["id"])
    hanh = [x["hanh_dong"] for x in hs["dong"] if x["loai"] == "SUA"]
    assert hanh[:2] == ["TU_TRANG_THAI", "TU_TRANG_THAI"] and hanh[-1] == "TAO"


@pytest.mark.db
@pytest.mark.asyncio
async def test_10_doi_gia_bang_gia_giu_don_gia_chot(pool: asyncpg.Pool) -> None:
    """#10: đổi giá bảng giá giữa liệu trình → LT giữ đơn giá chốt; LT mới giá mới."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    lt = await tao(ca, v, 5)
    await pool.execute(
        "UPDATE service_price SET unit_price = 550000 WHERE id = $1::uuid", ca.sp
    )
    assert (await doc(ca, lt["id"]))["don_gia"] == GIA
    lt2 = await tao(ca, v, 3)
    assert lt2["don_gia"] == 550_000


@pytest.mark.db
@pytest.mark.asyncio
async def test_11_giam_so_buoi_duoi_so_gan_bi_chan_co_cau(pool: asyncpg.Pool) -> None:
    """#11 (phần buổi): giảm số buổi dưới số buổi đang gắn → 409 có câu; không
    khoá — gỡ buổi rồi giảm được. (Dưới số ĐÃ TRẢ: bài B2.)"""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o1 = await chi_dinh(ca, v)
    lt = await tao(ca, v, 3, order=o1)
    await dang_ky(ca, lt["id"])
    v2 = await luot(ca)
    o2 = await chi_dinh(ca, v2)
    hien = await doc(ca, lt["id"])
    assert hien["so_gan"] == 2
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.dieu_chinh(
            identity=ca.bac_si,
            lieu_trinh_id=lt["id"],
            expected_revision=hien["revision"],
            so_buoi=1,
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "SO_BUOI_DUOI_SO_GAN"
    await ca.svc.go(
        identity=ca.bac_si,
        service_order_id=o2,
        expected_lieu_trinh_id=lt["id"],
        idempotency_key=_khoa(),
    )
    hien = await doc(ca, lt["id"])
    kq = await ca.svc.dieu_chinh(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=hien["revision"],
        so_buoi=1,
        idempotency_key=_khoa(),
    )
    assert kq["lieu_trinh"]["so_buoi"] == 1


@pytest.mark.db
@pytest.mark.asyncio
async def test_13_lam_qua_so_buoi_tu_them_buoi_co_lich_su(pool: asyncpg.Pool) -> None:
    """#13: buổi thứ N+1 gắn vào → số buổi +1 tự động, có dòng lịch sử."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o1 = await chi_dinh(ca, v)
    lt = await tao(ca, v, 1, order=o1)
    v2 = await luot(ca)
    o2 = await chi_dinh(ca, v2)  # buổi 1 chưa xong → LT vẫn DANG_LAM
    b = await buoi_song(ca, o2)
    assert b is not None and b["buoi_so"] == 2
    d = await doc(ca, lt["id"])
    assert d["so_buoi"] == 2
    hs = await ca.svc.lich_su(identity=ca.bac_si, lieu_trinh_id=lt["id"])
    tu = [x for x in hs["dong"] if x.get("hanh_dong") == "TU_THEM_BUOI"]
    assert tu and tu[0]["ban_cu"]["so_buoi"] == 1 and tu[0]["ban_moi"]["so_buoi"] == 2
    # Gắn TAY vào liệu trình đã Xong → mở lại thành đang làm + thêm buổi.
    await lam_xong(ca, o1)
    await lam_xong(ca, o2)
    assert (await doc(ca, lt["id"]))["trang_thai"] == "XONG"
    v3 = await luot(ca)
    o3 = await chi_dinh(ca, v3)
    assert await buoi_song(ca, o3) is None  # không tự gắn vào liệu trình đã xong
    kq = await ca.svc.gan(
        identity=ca.bac_si,
        service_order_id=o3,
        lieu_trinh_id=lt["id"],
        idempotency_key=_khoa(),
    )
    assert kq["lieu_trinh"]["so_buoi"] == 3
    assert kq["lieu_trinh"]["trang_thai"] == "DANG_LAM"


@pytest.mark.db
@pytest.mark.asyncio
async def test_14_ke_lai_cung_dich_vu_gan_lt_cu_muon_moi_bam_ro(
    pool: asyncpg.Pool,
) -> None:
    """#14: bác sĩ kê lại cùng dịch vụ khi LT đang chạy → gắn LT cũ; lập LT mới
    từ chỉ định ấy phải xác nhận tách."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o1 = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o1)
    v2 = await luot(ca)
    o2 = await chi_dinh(ca, v2)
    assert (await buoi_song(ca, o2))["lt"] == lt["id"]  # type: ignore[index]
    with pytest.raises(LuotKhamConflictError) as e:
        await tao(ca, v2, 5, order=o2)
    assert e.value.error_code == "DA_GAN_LIEU_TRINH"
    assert e.value.chi_tiet == {"lieu_trinh_id": lt["id"]}
    moi = await tao(ca, v2, 5, order=o2, tach_khoi_lieu_trinh_cu=True)
    b = await buoi_song(ca, o2)
    assert b is not None and (b["lt"], b["buoi_so"]) == (moi["id"], 1)
    cu = await doc(ca, lt["id"])
    assert [x["go_cach"] for x in cu["buoi"] if not x["song"]] == ["CHUYEN"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_15_hai_lt_cung_dich_vu_khong_tu_gan_the_bat_chon(
    pool: asyncpg.Pool,
) -> None:
    """#15: 2 LT đang làm cùng dịch vụ → chỉ định mới không tự gắn; thẻ bắt chọn."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    a = await tao(ca, v, 10)
    b = await tao(ca, v, 4)
    await dang_ky(ca, a["id"])
    await dang_ky(ca, b["id"])
    v2 = await luot(ca)
    o = await chi_dinh(ca, v2)
    assert await buoi_song(ca, o) is None
    the = await ca.svc.theo_luot(identity=ca.bac_si, visit_id=v2)
    (c,) = the["chi_dinh"]
    assert c["can_chon"] is True
    assert {u["id"] for u in c["ung_vien"]} == {a["id"], b["id"]}
    kq = await ca.svc.gan(
        identity=ca.bac_si,
        service_order_id=o,
        lieu_trinh_id=b["id"],
        idempotency_key=_khoa(),
    )
    assert kq["changed"] and (await buoi_song(ca, o))["lt"] == b["id"]  # type: ignore[index]
    # Màn cầm bản cũ (tưởng chưa gắn) → 409, không gắn chồng.
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.gan(
            identity=ca.bac_si,
            service_order_id=o,
            lieu_trinh_id=a["id"],
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "STALE_LIEU_TRINH"


@pytest.mark.db
@pytest.mark.asyncio
async def test_17_hoan_tac_bo_chi_dinh_gan_lai(pool: asyncpg.Pool) -> None:
    """#17 (phần buổi): bỏ rồi hoàn tác bỏ → gắn lại đúng liệu trình; gỡ TAY
    thì hoàn tác trạng thái không tự gắn lại."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o)
    await dat_trang_thai(ca, o, exec_status="cancelled", execution_status="CANCELLED")
    assert await buoi_song(ca, o) is None
    await dat_trang_thai(ca, o, exec_status="authorized", execution_status="PENDING")
    b = await buoi_song(ca, o)
    assert b is not None and b["lt"] == lt["id"] and b["buoi_so"] == 1
    await ca.svc.go(
        identity=ca.bac_si,
        service_order_id=o,
        expected_lieu_trinh_id=lt["id"],
        idempotency_key=_khoa(),
    )
    await dat_trang_thai(ca, o, selection_status="NOT_SELECTED")
    await dat_trang_thai(ca, o, selection_status="SELECTED")
    assert await buoi_song(ca, o) is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_dung_mo_lai_lich_su_hoan_tac_revision(pool: asyncpg.Pool) -> None:
    """Dừng (không tự gắn buổi mới) → mở lại; mọi lệnh có lịch sử + Hoàn tác;
    cầm bản cũ → 409; bấm lại cùng khoá → cùng kết quả, không ghi hai lần."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    lt = await tao(ca, v, 10)
    lt = await dang_ky(ca, lt["id"])
    rev = lt["revision"]
    khoa = _khoa()
    kq = await ca.svc.dung(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=rev,
        ly_do="Khách chuyển nơi khác",
        idempotency_key=khoa,
    )
    lai = await ca.svc.dung(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=rev,
        ly_do="Khách chuyển nơi khác",
        idempotency_key=khoa,
    )
    assert lai == kq and kq["lieu_trinh"]["trang_thai"] == "DUNG"
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.dieu_chinh(
            identity=ca.bac_si,
            lieu_trinh_id=lt["id"],
            expected_revision=rev,
            ghi_chu="bản cũ",
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "STALE_LIEU_TRINH"
    v2 = await luot(ca)
    o = await chi_dinh(ca, v2)
    assert await buoi_song(ca, o) is None  # đã dừng: không tự gắn
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.gan(
            identity=ca.bac_si,
            service_order_id=o,
            lieu_trinh_id=lt["id"],
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "LIEU_TRINH_DA_DUNG"
    # Hoàn tác lần Dừng = mở lại.
    hs = await ca.svc.lich_su(identity=ca.bac_si, lieu_trinh_id=lt["id"])
    (dong_dung,) = [x for x in hs["dong"] if x.get("hoan_tac_duoc")]
    assert dong_dung["hanh_dong"] == "DUNG"
    kq = await ca.svc.hoan_tac(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        lich_su_id=dong_dung["id"],
        expected_revision=hs["revision"],
        idempotency_key=_khoa(),
    )
    assert kq["lieu_trinh"]["trang_thai"] == "DANG_LAM"
    assert kq["lieu_trinh"]["ly_do_dung"] is None
    # Dòng cũ không còn là mới nhất → không hoàn tác lại được.
    with pytest.raises(LuotKhamConflictError) as e:
        await ca.svc.hoan_tac(
            identity=ca.bac_si,
            lieu_trinh_id=lt["id"],
            lich_su_id=dong_dung["id"],
            expected_revision=kq["lieu_trinh"]["revision"],
            idempotency_key=_khoa(),
        )
    assert e.value.error_code == "KHONG_HOAN_TAC_DUOC"
    # Lịch sử chỉ thêm.
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "DELETE FROM lieu_trinh_lich_su WHERE lieu_trinh_id = $1::uuid", lt["id"]
        )
    # Điều chỉnh ghi chú → hoàn tác trả ghi chú cũ.
    hien = await doc(ca, lt["id"])
    kq = await ca.svc.dieu_chinh(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        expected_revision=hien["revision"],
        ghi_chu="3 buổi/tuần",
        so_buoi=12,
        idempotency_key=_khoa(),
    )
    assert (kq["lieu_trinh"]["so_buoi"], kq["lieu_trinh"]["ghi_chu_lo_trinh"]) == (
        12,
        "3 buổi/tuần",
    )
    hs = await ca.svc.lich_su(identity=ca.bac_si, lieu_trinh_id=lt["id"])
    (moi,) = [x for x in hs["dong"] if x.get("hoan_tac_duoc")]
    kq = await ca.svc.hoan_tac(
        identity=ca.bac_si,
        lieu_trinh_id=lt["id"],
        lich_su_id=moi["id"],
        expected_revision=hs["revision"],
        idempotency_key=_khoa(),
    )
    assert (kq["lieu_trinh"]["so_buoi"], kq["lieu_trinh"]["ghi_chu_lo_trinh"]) == (
        10,
        None,
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_cskh_dang_do_qua_x_ngay_chua_quay_lai(pool: asyncpg.Pool) -> None:
    """ "Đang dở, quá X ngày chưa quay lại": buổi cuối 20 ngày trước, không còn
    buổi chờ làm, không có lịch hẹn → có trong danh sách 14 ngày, không có ở 30."""
    ca = await dung_ca(pool)
    v = await luot(ca, ngay_truoc=20)
    o = await chi_dinh(ca, v)
    lt = await tao(ca, v, 10, order=o)
    await lam_xong(ca, o)
    ds = await ca.svc.cskh(identity=ca.cskh, loai="dang_do", qua_ngay="14")
    hit = [x for x in ds["lieu_trinh"] if x["id"] == lt["id"]]
    assert hit and hit[0]["ten_khach"] == "Chị Liệu Trình" and hit[0]["con_lai"] == 9
    ds = await ca.svc.cskh(identity=ca.cskh, loai="dang_do", qua_ngay=30)
    assert lt["id"] not in [x["id"] for x in ds["lieu_trinh"]]
    # Rác ở ô số ngày → mặc định 14, không 500.
    ds = await ca.svc.cskh(identity=ca.cskh, loai="dang_do", qua_ngay="mười bốn")
    assert ds["qua_ngay"] == 14
    with pytest.raises(ValidationError):
        await ca.svc.cskh(identity=ca.cskh, loai="khac")


@pytest.mark.db
@pytest.mark.asyncio
async def test_9_hai_phong_cung_gan_mot_lt_khong_trung_so_buoi(
    pool: asyncpg.Pool,
) -> None:
    """Hai chỉ định cùng liệu trình tạo đồng thời (hai giao dịch) → xếp hàng
    sau dòng liệu trình: hai buổi khác số, không trùng, không mất buổi."""
    ca = await dung_ca(pool)
    v = await luot(ca)
    lt = await tao(ca, v, 10)
    await dang_ky(ca, lt["id"])
    v1, v2 = await luot(ca), await luot(ca)
    o1, o2 = await asyncio.gather(chi_dinh(ca, v1), chi_dinh(ca, v2))
    so = sorted(
        [
            (await buoi_song(ca, o1))["buoi_so"],  # type: ignore[index]
            (await buoi_song(ca, o2))["buoi_so"],  # type: ignore[index]
        ]
    )
    assert so == [1, 2]
