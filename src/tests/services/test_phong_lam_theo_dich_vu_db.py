"""Phòng làm theo dịch vụ (Tuyền chốt 30/09/2026) — trên Postgres thật.

Dịch vụ CÓ dòng `clinic_room_service` → CHỈ các phòng được gắn làm được (vẫn
cùng cơ sở, đang mở, nhận khách). Dịch vụ không có dòng nào → theo node như cũ.
Một luật (`phong_lam_duoc`) cho gợi ý phòng, dây H4, lệnh xếp tay, hàng "chờ
nhận" của phòng, ô phòng ở quầy, và cảnh báo cấu hình.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55577/postgres \\
        .venv/bin/pytest -m db src/tests/services/test_phong_lam_theo_dich_vu_db.py
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services import service_routing_service as sr
from clinicai.services.clinic_config_service import ClinicConfigService
from clinicai.services.quay_thu_service import PhongQuay
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_service_routing_db import (  # noqa: F401
    RB,
    _assign,
    _cd,
    _loi,
    _o,
    rb,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quản lý ở test cấu hình là danh tính thật có preset MANAGEMENT; vẫn gắn
    quyền theo nhóm mẫu như các test cấu hình khác (cửa thật: test_lego_21_db)."""
    from tests.quyen_gia import dich_vu_theo_nhom_mau

    dich_vu_theo_nhom_mau(monkeypatch)


async def _ma_cd(b: RB, oid: str) -> str:
    return str(
        await b.pool.fetchval(
            "SELECT service_code FROM service_order WHERE id = $1::uuid", oid
        )
    )


async def _gan(b: RB, room_id: str, ma: str) -> None:
    await b.pool.execute(
        "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
        " VALUES ($1::uuid, $2::uuid, $3)",
        CLINIC,
        room_id,
        ma,
    )


async def _ten(b: RB, room_id: str) -> str:
    return str(
        await b.pool.fetchval(
            "SELECT name FROM clinic_room WHERE id = $1::uuid", room_id
        )
    )


async def test_dich_vu_gan_phong_chi_goi_y_phong_ay(rb: RB) -> None:  # noqa: F811
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    # Chưa gắn: như cũ — cả hai phòng siêu âm.
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert {rb.sa1, rb.sa2} <= {c["room_id"] for c in g["candidates"]}

    await _gan(rb, rb.sa2, ma)
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert [c["room_id"] for c in g["candidates"]] == [rb.sa2]
    assert g["trang_thai"] == sr.GOI_Y_CO_PHONG
    # Tập theo node thuần (màn cấu hình) vẫn đủ hai phòng; theo dịch vụ thì một.
    async with rb.pool.acquire() as conn:
        theo_node = {
            r.room_id for r in await sr.eligible_rooms(conn, CLINIC, "DICHVU-SIEUAM")
        }
        theo_dv = [
            r.room_id
            for r in await sr.eligible_rooms(
                conn, CLINIC, "DICHVU-SIEUAM", service_code=ma
            )
        ]
    assert {rb.sa1, rb.sa2} <= theo_node
    assert theo_dv == [rb.sa2]


async def test_xep_tay_sang_phong_khong_gan_bi_tu_choi_neu_ten_phong(
    rb: RB,  # noqa: F811
) -> None:
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.sa2, ma)
    loi = await _loi(_assign(rb, oid, rb.sa1, 0), "ROOM_NOT_SERVING_SERVICE")
    assert f"chỉ làm ở: {await _ten(rb, rb.sa2)}" in str(loi)
    assert (await _o(rb, oid))["routing_status"] == "UNASSIGNED"
    kq = await _assign(rb, oid, rb.sa2, 0)
    assert kq["room_id"] == rb.sa2 and kq["changed"]


async def test_gan_dich_vu_le_khong_can_node(rb: RB) -> None:  # noqa: F811
    """Phòng không có node siêu âm nhưng được gắn riêng dịch vụ → làm được; các
    phòng siêu âm theo node thì không còn làm dịch vụ ấy."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.khac_node, ma)
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert [c["room_id"] for c in g["candidates"]] == [rb.khac_node]
    await _loi(_assign(rb, oid, rb.sa1, 0), "ROOM_NOT_SERVING_SERVICE")
    assert (await _assign(rb, oid, rb.khac_node, 0))["room_id"] == rb.khac_node


async def test_gan_vao_phong_tat_thi_khong_con_phong_nao(rb: RB) -> None:  # noqa: F811
    """Gắn riêng vào phòng đã tắt: không rơi về node — báo KHÔNG CÓ PHÒNG."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.tat, ma)
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert g["candidates"] == [] and g["trang_thai"] == sr.GOI_Y_KHONG_CO_PHONG
    ov = await ClinicConfigService(rb.pool).overview(identity=rb.truong_ca)
    assert ma in {t["code"] for t in ov["config_missing"]}


async def test_h4_tu_xep_dung_phong_duoc_gan(rb: RB) -> None:  # noqa: F811
    """SA1 sort nhỏ hơn (được ưu tiên khi hoà), nhưng dịch vụ chỉ làm ở SA2."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.sa2, ma)
    async with rb.pool.acquire() as conn, conn.transaction():
        xep = await rb.svc.tu_xep_da_thu(
            conn,
            clinic_id=CLINIC,
            visit_id=rb.visit_id,
            staff_id=rb.truong_ca.staff_id,
            causation_id=rb.visit_id,
        )
    assert oid in xep
    assert (await _o(rb, oid))["room_id"] == rb.sa2


async def _h4(b: RB) -> list[str]:
    async with b.pool.acquire() as conn, conn.transaction():
        return await b.svc.tu_xep_da_thu(
            conn,
            clinic_id=CLINIC,
            visit_id=b.visit_id,
            staff_id=b.truong_ca.staff_id,
            causation_id=b.visit_id,
        )


async def test_h4_mo_het_phong_van_chi_tu_xep_dung_chuc_nang(rb: RB) -> None:  # noqa: F811
    """ "Mở hết phòng": dịch vụ gắn cho cả phòng siêu âm lẫn phòng lấy mẫu. Quầy
    chọn tay được cả hai (phong_lam_duoc), nhưng TỰ XẾP chỉ vào phòng có node
    siêu âm — phòng lấy mẫu không bao giờ được chọn dù vắng hơn."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    for r in (rb.sa1, rb.sa2, rb.khac_node):
        await _gan(rb, r, ma)
    # Danh sách chọn tay: giữ nguyên = mọi phòng được gắn.
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert {rb.sa1, rb.sa2, rb.khac_node} <= {c["room_id"] for c in g["candidates"]}
    xep = await _h4(rb)
    assert oid in xep
    assert (await _o(rb, oid))["room_id"] in (rb.sa1, rb.sa2)


async def test_h4_khong_phong_dung_chuc_nang_thi_cho_quay(rb: RB) -> None:  # noqa: F811
    """Dịch vụ chỉ gắn cho phòng KHÁC chức năng → không tự xếp, chờ quầy; xếp
    tay vào phòng ấy vẫn được."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.khac_node, ma)
    assert oid not in await _h4(rb)
    o = await _o(rb, oid)
    assert o["routing_status"] == "UNASSIGNED" and o["room_id"] is None
    kq = await _assign(rb, oid, rb.khac_node, 0)
    assert kq["room_id"] == rb.khac_node and kq["changed"]


async def test_h4_phong_du_kien_cua_nguoi_van_thang(rb: RB) -> None:  # noqa: F811
    """Phòng lễ tân chọn (kể cả khác chức năng, miễn phong_lam_duoc) thắng."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    for r in (rb.sa1, rb.khac_node):
        await _gan(rb, r, ma)
    await rb.pool.execute(
        "UPDATE service_order SET phong_du_kien_id = $2::uuid WHERE id = $1::uuid",
        oid,
        rb.khac_node,
    )
    assert oid in await _h4(rb)
    assert (await _o(rb, oid))["room_id"] == rb.khac_node


async def test_chon_phong_h4_thuan_tu_chon_theo_chuc_nang() -> None:
    uv = [{"room_id": "sai-viec"}, {"room_id": "dung-viec"}]
    cn = [{"room_id": "dung-viec"}]
    assert sr.chon_phong_h4(
        uv, None, chi_ap_phong_du_kien=False, ung_vien_chuc_nang=cn
    ) == ("dung-viec", None)
    assert sr.chon_phong_h4(
        uv, None, chi_ap_phong_du_kien=False, ung_vien_chuc_nang=[]
    ) == (None, sr.CHO_XEP_KHONG_DUNG_CHUC_NANG)
    assert sr.chon_phong_h4(
        [], None, chi_ap_phong_du_kien=False, ung_vien_chuc_nang=[]
    ) == (None, sr.CHO_XEP_KHONG_CO_PHONG)
    # Phòng người chọn thắng dù không đúng chức năng.
    assert sr.chon_phong_h4(
        uv, "sai-viec", chi_ap_phong_du_kien=False, ung_vien_chuc_nang=cn
    ) == ("sai-viec", None)
    assert "đúng chức năng" in sr.cau_cho_xep_phong(sr.CHO_XEP_KHONG_DUNG_CHUC_NANG)


async def test_hang_cho_nhan_va_o_phong_quay_theo_dich_vu(rb: RB) -> None:  # noqa: F811
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.sa2, ma)
    async with rb.pool.acquire() as conn:
        o_sa1 = {k["id"] for k in await sr.cho_nhan_vao_phong(conn, CLINIC, rb.sa1)}
        o_sa2 = {k["id"] for k in await sr.cho_nhan_vao_phong(conn, CLINIC, rb.sa2)}
        pq = PhongQuay(conn, CLINIC)
        phong = await pq.cua("DICHVU-SIEUAM", rb.visit_id, ma)
        khong_dv = await pq.cua("DICHVU-SIEUAM", rb.visit_id)
    assert oid not in o_sa1 and oid in o_sa2
    assert [p["id"] for p in phong] == [rb.sa2]
    assert {rb.sa1, rb.sa2} <= {p["id"] for p in khong_dv}


async def test_quay_thu_tra_phong_chon_duoc_da_thu_hep(rb: RB) -> None:  # noqa: F811
    """`da_tra_cho_vao_phong` mang khoá nội bộ node + dịch vụ cho quầy tính phòng."""
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    await _gan(rb, rb.sa2, ma)
    async with rb.pool.acquire() as conn:
        ds = await sr.da_tra_cho_vao_phong(conn, CLINIC, [rb.visit_id])
    [x] = [x for x in ds[rb.visit_id] if x["id"] == oid]
    assert x["service_code"] == ma and x["node_code"] == "DICHVU-SIEUAM"


async def _quan_ly(b: RB) -> Any:
    from tests.services.test_luot_kham_service_db import _nguoi

    async with b.pool.acquire() as conn:
        return await _nguoi(conn, b.loc, "MANAGEMENT")


async def test_api_cau_hinh_them_bo_dich_vu_cua_phong(rb: RB) -> None:  # noqa: F811
    ql = await _quan_ly(rb)
    svc = ClinicConfigService(rb.pool)
    oid = await _cd(rb)
    ma = await _ma_cd(rb, oid)
    kq = await svc.set_room_services(
        identity=ql, room_id=rb.sa2, service_codes=[ma, f" {ma} "]
    )
    assert kq["service_codes"] == [ma]
    ov = await svc.overview(identity=ql)
    phong = {
        r["room_id"]: r
        for loc in ov["locations"]
        for f in loc["floors"]
        for r in f["rooms"]
    }
    assert [d["ma"] for d in phong[rb.sa2]["dich_vu"]] == [ma]
    assert phong[rb.sa1]["dich_vu"] == []
    # Danh sách chọn được: dịch vụ nằm trong nhóm siêu âm, kèm "chỉ làm ở".
    [nhom] = [g for g in ov["viec_chon_duoc"] if g["node"] == "DICHVU-SIEUAM"]
    [d] = [d for d in nhom["dich_vu"] if d["ma"] == ma]
    assert d["chi_lam_o"] == [await _ten(rb, rb.sa2)]
    # Không mời node quản trị, không mời nhóm dịch vụ rỗng.
    moi = {g["node"] for g in ov["viec_chon_duoc"]}
    assert all(n.startswith(("KHAM-", "DICHVU-")) for n in moi)
    assert "DICHVU-DUYET-KETQUA" not in moi
    assert "DATLICH-06" not in moi

    # Bỏ hết: dịch vụ về luật node.
    await svc.set_room_services(identity=ql, room_id=rb.sa2, service_codes=[])
    g = await rb.svc.recommend(order_id=oid, identity=rb.truong_ca)
    assert {rb.sa1, rb.sa2} <= {c["room_id"] for c in g["candidates"]}


async def test_api_cau_hinh_tu_choi_ma_la_va_node_quan_tri(rb: RB) -> None:  # noqa: F811
    ql = await _quan_ly(rb)
    svc = ClinicConfigService(rb.pool)
    with pytest.raises(ValidationError, match="Không gắn được"):
        await svc.set_room_services(
            identity=ql, room_id=rb.sa1, service_codes=["KHONG_CO_MA_NAY"]
        )
    with pytest.raises(ValidationError, match="việc quản trị"):
        await svc.set_room_nodes(
            identity=ql, room_id=rb.sa1, node_codes=["DICHVU-SIEUAM", "DATLICH-06"]
        )
    # Node quản trị ĐÃ gắn từ trước thì giữ được (không bị chặn khi lưu lại).
    await rb.pool.execute(
        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
        " VALUES ($1::uuid, $2::uuid, 'DATLICH-06')",
        CLINIC,
        rb.sa1,
    )
    kq = await svc.set_room_nodes(
        identity=ql,
        room_id=rb.sa1,
        node_codes=["DICHVU-SIEUAM", "DATLICH-06", "KHAM-PHUKHOA"],
    )
    assert kq["ok"]


async def test_nap_san_chau_chay_lai_duoc(pool: asyncpg.Pool) -> None:
    """Seed: Ghế ĐTT, máy Bio, Vật lý trị liệu chỉ ở KN-SANCHAU; SP000083 là dịch
    vụ thủ thuật; SP000077 là phí khám (chưa có giá) chọn được ở mọi loại khám
    đang bật."""
    await pool.fetchrow("SELECT * FROM nap_phong_lam_theo_dich_vu()")
    lan2 = await pool.fetchrow("SELECT * FROM nap_phong_lam_theo_dich_vu()")
    assert tuple(lan2) == (0, 0, 0)
    san_chau = await pool.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid"
        " AND code = 'KN-SANCHAU'",
        CLINIC,
    )
    if san_chau is None:
        pytest.skip("DB thử không có phòng KN-SANCHAU")
    gan = {
        r["service_code"]
        for r in await pool.fetch(
            "SELECT service_code FROM clinic_room_service WHERE room_id = $1::uuid",
            san_chau,
        )
    }
    co = {
        r["service_code"]
        for r in await pool.fetch(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND (service_code IN ('CLS_GHE_DTT', 'CLS_GHE_DTT_DAU_CO',"
            " 'CLS_GHE_DTT_YEU_CO', 'CLS_BIOFEEDBACK', 'CLS_BIOFEEDBACK_CO_BAN',"
            " 'CLS_BIOFEEDBACK_NANG_CAO', 'CLS_DO_CO_LUC_AM_DAO')"
            " OR ma_kiotviet = 'SP000083')",
            CLINIC,
        )
    }
    assert co and co <= gan
    vltl = await pool.fetchrow(
        'SELECT service_code, node_code, unit_price, "group", billing_owner'
        " FROM service_price WHERE clinic_id = $1::uuid AND ma_kiotviet = 'SP000083'",
        CLINIC,
    )
    assert vltl is not None
    assert (vltl["node_code"], int(vltl["unit_price"]), vltl["group"]) == (
        "DICHVU-THUTHUAT",
        500000,
        "dich_vu",
    )
    # Chỉ Phòng Sàn chậu làm được (dù Thủ thuật 1, 2 có cả nhóm thủ thuật).
    async with pool.acquire() as conn:
        phong = await sr.eligible_rooms(
            conn, CLINIC, "DICHVU-THUTHUAT", service_code=vltl["service_code"]
        )
    assert {p.room_id for p in phong} <= {san_chau}
    tv = await pool.fetchrow(
        "SELECT id::text AS id, node_code, unit_price FROM service_price"
        " WHERE clinic_id = $1::uuid AND ma_kiotviet = 'SP000077'",
        CLINIC,
    )
    # KiotViet 0đ → để TRỐNG giá (không bao giờ nạp 0đ — 20260926000001).
    # Nhóm việc: trống lúc nạp; từ C21 (02/10/2026) phí khám được gắn nhóm
    # thủ thuật để chỉ định được (mig 20261003700000).
    assert tv is not None and tv["unit_price"] is None
    assert tv["node_code"] in (None, "DICHVU-THUTHUAT")
    thieu = await pool.fetchval(
        "SELECT count(*) FROM service_type st WHERE st.clinic_id = $1::uuid"
        " AND st.is_active AND NOT EXISTS (SELECT 1 FROM loai_kham_phi l"
        " WHERE l.service_type_id = st.id AND l.service_price_id = $2::uuid)",
        CLINIC,
        tv["id"],
    )
    assert thieu == 0


async def test_phong_khac_phong_kham_khong_gan_duoc(pool: asyncpg.Pool) -> None:
    """Trigger: phòng phải cùng phòng khám với dòng gắn."""
    rid = await pool.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid LIMIT 1", CLINIC
    )
    ma = await pool.fetchval(
        "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
        " AND \"group\" = 'dich_vu' LIMIT 1",
        CLINIC,
    )
    khac = str(uuid.uuid4())
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            khac,
            rid,
            ma,
        )
