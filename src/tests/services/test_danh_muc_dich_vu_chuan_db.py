"""Danh mục dịch vụ chuẩn 01/10/2026 + phòng làm — trên Postgres thật.

Tuyền 01/10: "đây là chuẩn; danh sách chỉ định đang thiếu rất nhiều; KHÔNG được
để dịch vụ nào bị lọt; cái nào XN thu hộ thì hiện đúng giá khách gửi, 0đ cũng
hiện". Kiểm:

* đồng bộ theo file (migration 20261002100000): mọi dòng file khớp một dịch vụ
  đang bán cùng tên + nhóm; XN thu hộ = thu hộ đối tác, giá đúng file kể cả 0đ;
  dịch vụ phòng khám thu KHÔNG bao giờ bị nạp 0đ; chạy lại không đổi gì;
* MỌI dịch vụ đang bán — KỂ CẢ phí khám (C21, 02/10/2026: "toàn bộ 93 dịch vụ
  phải chọn được ở bàn khám") — có trong danh mục chỉ định của phiếu khám và ô
  "Chỉ định thêm" của Bàn khám — tìm được PRP, NIPT, Liên cầu B, Khám nam khoa;
* Bảng giá dịch vụ & phòng: dịch vụ không phòng hiện "chưa có phòng", gán phòng
  tại chỗ là hết, bỏ gán là về theo nhóm việc; trang chủ đếm cùng luật.

    scripts/test-nhanh.sh -m db src/tests/services/test_danh_muc_dich_vu_chuan_db.py
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.phieu_kham import anh_xa_danh_muc as ax
from clinicai.services.clinic_config_service import ClinicConfigService
from clinicai.services.config_service import PriceListService, ma_dich_vu_theo_ten
from clinicai.services.danh_muc_dich_vu_service import (
    DanhMucDichVuService,
    dem_chua_co_phong,
)
from clinicai.services.phieu_kham_service import PhieuKhamService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_phong_lam_theo_dich_vu_db import _quan_ly
from tests.services.test_service_routing_db import RB, rb  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.quyen_gia import dich_vu_theo_nhom_mau

    dich_vu_theo_nhom_mau(monkeypatch)


def _ai() -> Any:
    return SimpleNamespace(clinic_id=CLINIC, staff_id=None)


async def _cho_qua(*_a: Any, **_k: Any) -> None:
    return None


async def _dong_bo(pool: asyncpg.Pool) -> asyncpg.Record:
    r = await pool.fetchrow(
        "SELECT * FROM public.dong_bo_danh_muc_dich_vu('kiot_0110')"
    )
    assert r is not None
    return r


async def test_dong_bo_theo_file_chuan_va_chay_lai_khong_doi(rb: RB) -> None:  # noqa: F811
    pool = rb.pool
    await _dong_bo(pool)
    nguon = await pool.fetch(
        "SELECT * FROM danh_muc_dich_vu_nguon WHERE nguon = 'kiot_0110' ORDER BY thu_tu"
    )
    assert len(nguon) == 93
    ghep = {
        r["thu_tu"]: r["service_price_id"]
        for r in await pool.fetch(
            "SELECT * FROM ghep_danh_muc_dich_vu('kiot_0110')"
            " WHERE clinic_id = $1::uuid",
            CLINIC,
        )
    }
    for x in nguon:
        if x["nhom"] == "Phí khám" and x["thu_tu"] not in ghep:
            continue  # phí khám đi theo loại khám — DB thử có thể không có
        assert x["thu_tu"] in ghep, f"lọt: {x['ten']}"
        sp = await pool.fetchrow(
            "SELECT name, category, active, unit_price, billing_owner, node_code"
            " FROM service_price WHERE id = $1::uuid",
            ghep[x["thu_tu"]],
        )
        assert sp is not None
        assert sp["name"] == x["ten"] and sp["category"] == x["nhom"] and sp["active"]
        if x["gia"] > 0:
            assert sp["unit_price"] == x["gia"], x["ten"]
        if x["nhom"] == "XN thu hộ":
            assert sp["billing_owner"] == "EXTERNAL_PARTNER", x["ten"]
            assert sp["unit_price"] == x["gia"], (
                f"thu hộ hiện đúng giá file: {x['ten']}"
            )
        if x["nhom"] != "Phí khám":
            assert sp["node_code"], f"dịch vụ phải có nhóm việc: {x['ten']}"
    # Tên đổi: TPC → Tropocel, RG → Regenlab (ánh xạ tay theo mã KiotViet).
    assert await pool.fetchval(
        "SELECT name FROM service_price WHERE clinic_id = $1::uuid"
        " AND ma_kiotviet = 'SP000140'",
        CLINIC,
    ) in (None, "Bơm PRP niêm mạc tử cung (Tropocel)", "Bơm PRP niêm mạc tử cung (TPC)")
    # Dịch vụ PHÒNG KHÁM THU không bao giờ bị nạp 0đ (nạp 0 là thu 0 đồng).
    assert not await pool.fetchval(
        "SELECT count(*) FROM service_price sp JOIN danh_muc_dich_vu_nguon x"
        "  ON x.nguon = 'kiot_0110' AND x.gia = 0"
        " AND khoa_ten_dich_vu(x.ten) = khoa_ten_dich_vu(sp.name)"
        " WHERE sp.billing_owner = 'CLINIC' AND sp.unit_price = 0"
    )
    # Hai dòng tiêu đề phiếu giấy cũ: tắt (không xoá).
    tat = await pool.fetch(
        "SELECT active FROM service_price WHERE clinic_id = $1::uuid"
        " AND service_code IN ('CLS_XET_NGHIEM_DICH_AM_DAO', 'CLS_LASER')",
        CLINIC,
    )
    assert all(not r["active"] for r in tat)
    lan2 = await _dong_bo(pool)
    assert (lan2["sua"], lan2["them"], lan2["tat"], lan2["gan_thu_thuat"]) == (
        0,
        0,
        0,
        0,
    )


async def test_moi_dich_vu_dang_ban_deu_chi_dinh_duoc(rb: RB) -> None:  # noqa: F811
    pool = rb.pool
    await _dong_bo(pool)
    # Một dịch vụ mới thêm tay, không mã KiotViet, không nhóm việc: vẫn hiện
    # (khoá ô kèm câu việc cần làm), không lọt im lặng.
    ten = f"Dịch vụ thử {uuid.uuid4().hex[:6]}"
    await PriceListService(pool).add(
        service_code="",
        name=ten,
        group="dich_vu",
        unit_price=100000,
        identity=_ai(),
        nhom="Siêu âm › Siêu âm thai",
    )
    tc = await PhieuKhamService(pool, kiem_quyen=_cho_qua).tham_chieu_that(
        identity=_ai()
    )
    muc = [m for n in tc["chi_dinh_cls"] for m in n["muc"]]
    co = {m["service_code"] for m in muc if m.get("service_code")}
    assert "CLS_GHE_DTT" in co or not await pool.fetchval(
        "SELECT active FROM service_price WHERE clinic_id = $1::uuid"
        " AND service_code = 'CLS_GHE_DTT'",
        CLINIC,
    ), "Ghế điện từ trường phải tìm được ở Chỉ định cận lâm sàng"
    can_co = {
        r["service_code"]
        for r in await pool.fetch(
            "SELECT service_code FROM danh_muc_dich_vu($1::uuid) WHERE active",
            CLINIC,
        )
    } - ax.KHONG_LIET_KE
    assert can_co - co == set(), f"lọt khỏi danh mục chỉ định: {can_co - co}"
    # Phí khám CŨNG là ô chỉ định (C21) — không còn bộ lọc phí khám.
    phi = {
        r["service_code"]
        for r in await pool.fetch(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND active AND \"group\" = 'dich_vu' AND category LIKE 'Phí khám%'",
            CLINIC,
        )
    }
    assert phi <= co, f"phí khám lọt khỏi danh mục chỉ định: {phi - co}"
    ten_co = " | ".join(m["nhan"] for m in muc)
    for tu in ("PRP", "NIPT", "Liên cầu B"):
        assert tu in ten_co, f"bác sĩ tìm “{tu}” phải thấy"
    # XN thu hộ 0đ hiện 0 (không phải "chưa có giá").
    lcb = [m for m in muc if m["nhan"] == "Liên cầu B"][0]
    assert lcb["gia"] == 0 and lcb["doi_tac_thu"]
    # Dịch vụ thêm tay: có mặt, gom đúng nhóm hàng, khoá vì chưa nhóm việc.
    [moi] = [m for m in muc if m["nhan"] == ten]
    assert moi["service_code"] == ma_dich_vu_theo_ten(ten)
    assert moi["nhom_hang"] == "Siêu âm › Siêu âm thai"
    assert moi["khoa"]

    # Ô "Chỉ định thêm" của Bàn khám đọc cùng danh mục.
    from clinicai.services.luot_kham_doc import BangLuotKham  # noqa: F401

    ban_kham = {
        r["service_code"]
        for r in await pool.fetch(
            "SELECT d.service_code FROM danh_muc_dich_vu($1::uuid) d WHERE d.active",
            CLINIC,
        )
    }
    assert can_co <= ban_kham


async def test_gan_phong_tai_cho_va_canh_bao_chua_co_phong(rb: RB) -> None:  # noqa: F811
    pool = rb.pool
    ql = await _quan_ly(rb)
    ten = f"DV chưa phòng {uuid.uuid4().hex[:6]}"
    await PriceListService(pool).add(
        service_code="",
        name=ten,
        group="dich_vu",
        unit_price=200000,
        identity=_ai(),
    )
    ma = ma_dich_vu_theo_ten(ten)
    async with pool.acquire() as conn:
        truoc = await dem_chua_co_phong(conn, CLINIC)
    goi = await DanhMucDichVuService(pool).doc(identity=ql)
    [d] = [d for d in goi["dich_vu"] if d["service_code"] == ma]
    assert d["chua_co_phong"] and not d["la_phi_kham"] and d["phong"] == []
    assert goi["so_chua_co_phong"] == truoc >= 1
    assert goi["sua_phong_duoc"] is True

    svc = ClinicConfigService(pool)
    kq = await svc.set_service_rooms(identity=ql, service_code=ma, room_ids=[rb.sa2])
    sau = kq["dich_vu"]
    assert sau["gan_rieng"] and not sau["chua_co_phong"]
    assert [p["id"] for p in sau["phong"]] == [rb.sa2]
    # Chưa có nhóm việc → lấy nhóm việc dịch vụ của phòng được gắn.
    assert sau["node_code"] == "DICHVU-SIEUAM"
    async with pool.acquire() as conn:
        assert await dem_chua_co_phong(conn, CLINIC) == truoc - 1

    # Bỏ gán riêng → về theo nhóm việc (mọi phòng siêu âm).
    kq = await svc.set_service_rooms(identity=ql, service_code=ma, room_ids=[])
    sau = kq["dich_vu"]
    assert not sau["gan_rieng"]
    assert {rb.sa1, rb.sa2} <= {p["id"] for p in sau["phong"]}

    # Rác: mã lạ, phòng lạ → câu lỗi, không 500.
    with pytest.raises(ValidationError):
        await svc.set_service_rooms(identity=ql, service_code="KHONG_CO", room_ids=[])
    with pytest.raises(ValidationError):
        await svc.set_service_rooms(
            identity=ql, service_code=ma, room_ids=["rac; drop", str(uuid.uuid4())]
        )


async def test_phi_kham_chua_nhom_viec_van_hien_va_gan_phong_duoc(
    rb: RB,  # noqa: F811
) -> None:
    """C21 (02/10/2026): phí khám mới thêm, chưa nhóm việc — KHÔNG biến mất:
    hiện "Chưa có phòng" ở Bảng giá, hiện (khoá kèm lý do) ở danh mục chỉ định;
    gán phòng tại chỗ là có nhóm việc + chỉ định được."""
    pool = rb.pool
    ql = await _quan_ly(rb)
    ma = f"KHAM_T{uuid.uuid4().hex[:6].upper()}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, active, category) VALUES ($1::uuid, $2, 'Phí khám thử',"
        " 'dich_vu', 300000, true, 'Phí khám')",
        CLINIC,
        ma,
    )
    d = await pool.fetchrow(
        "SELECT la_phi_kham, can_phong, chua_co_phong FROM danh_muc_dich_vu($1::uuid)"
        " WHERE service_code = $2",
        CLINIC,
        ma,
    )
    assert d is not None and d["la_phi_kham"] and d["can_phong"]
    assert d["chua_co_phong"], "phí khám chưa phòng phải hiện để gán"
    tc = await PhieuKhamService(pool, kiem_quyen=_cho_qua).tham_chieu_that(
        identity=_ai()
    )
    [m] = [m for n in tc["chi_dinh_cls"] for m in n["muc"] if m["service_code"] == ma]
    assert m["khoa"], "chưa nhóm việc → khoá kèm lý do, không ẩn"

    kq = await ClinicConfigService(pool).set_service_rooms(
        identity=ql, service_code=ma, room_ids=[rb.sa1, rb.sa2]
    )
    sau = kq["dich_vu"]
    assert sau["node_code"] and not sau["chua_co_phong"]
    assert {p["id"] for p in sau["phong"]} == {rb.sa1, rb.sa2}
    tc = await PhieuKhamService(pool, kiem_quyen=_cho_qua).tham_chieu_that(
        identity=_ai()
    )
    [m] = [m for n in tc["chi_dinh_cls"] for m in n["muc"] if m["service_code"] == ma]
    assert m["khoa"] is None


async def test_ca_93_dich_vu_file_chuan_chi_dinh_duoc_va_co_phong(
    rb: RB,  # noqa: F811
) -> None:
    """Mọi dòng file 01/10 khớp được một dịch vụ: có trong danh mục chỉ định,
    KHÔNG khoá, và có ít nhất một phòng nội bộ làm được (Tuyền 02/10)."""
    pool = rb.pool
    await _dong_bo(pool)
    tc = await PhieuKhamService(pool, kiem_quyen=_cho_qua).tham_chieu_that(
        identity=_ai()
    )
    # Mục C (Chỉ định cận lâm sàng — có ô tìm) phải tự đủ: thủ thuật của phiếu
    # giấy (Ghế điện từ trường…) cũng có ở đây, không chỉ ở mục F.
    muc = {
        m["service_code"]: m
        for n in tc["chi_dinh_cls"]
        for m in n["muc"]
        if m.get("service_code")
    }
    dong = await pool.fetch(
        "SELECT x.ten, d.service_code, d.node_code, d.chua_co_phong"
        "  FROM ghep_danh_muc_dich_vu('kiot_0110') g"
        "  JOIN danh_muc_dich_vu_nguon x ON x.nguon = 'kiot_0110'"
        "   AND x.thu_tu = g.thu_tu"
        "  JOIN danh_muc_dich_vu($1::uuid) d ON d.id = g.service_price_id"
        " WHERE g.clinic_id = $1::uuid",
        CLINIC,
    )
    assert dong
    for r in dong:
        assert r["service_code"] in muc, f"lọt khỏi bàn khám: {r['ten']}"
        # Tên hiện = tên file (nhãn phiếu giấy chỉ là dòng phụ) — gõ tên trong
        # file là tìm ra (C21: "Đo trương lực cơ sàn chậu máy Bio" từng chỉ hiện
        # dưới nhãn "Đo cơ lực âm đạo bằng máy (sàng lọc)").
        assert muc[r["service_code"]]["ten_dich_vu"] == r["ten"], r["ten"]
        if r["node_code"]:
            assert not muc[r["service_code"]]["khoa"], r["ten"]


async def test_bang_gia_them_nhom_hang_va_ma_tu_sinh(rb: RB) -> None:  # noqa: F811
    svc = PriceListService(rb.pool)
    ten = f"  Xét  nghiệm thử {uuid.uuid4().hex[:6]} "
    pid = await svc.add(
        service_code="",
        name=ten,
        group="dich_vu",
        unit_price=0,
        identity=_ai(),
        billing_owner="EXTERNAL_PARTNER",
        nhom="XN thu hộ",
    )
    r = await rb.pool.fetchrow(
        "SELECT service_code, category, unit_price FROM service_price"
        " WHERE id = $1::uuid",
        pid,
    )
    assert r is not None
    assert r["service_code"] == ma_dich_vu_theo_ten(ten)
    assert r["category"] == "XN thu hộ" and r["unit_price"] == 0
    # SQL và Python sinh cùng một mã cho cùng một tên.
    assert await rb.pool.fetchval(
        "SELECT 'DV_' || upper(substr(md5(khoa_ten_dich_vu($1)), 1, 10))", ten
    ) == ma_dich_vu_theo_ten(ten)
    await svc.update(
        price_id=pid,
        identity=_ai(),
        nhom=" Siêu âm › Siêu âm thai ",
        nhom_provided=True,
    )
    assert (
        await rb.pool.fetchval(
            "SELECT category FROM service_price WHERE id = $1::uuid", pid
        )
        == "Siêu âm>>Siêu âm thai"
    )
    await svc.update(price_id=pid, identity=_ai(), nhom="", nhom_provided=True)
    assert (
        await rb.pool.fetchval(
            "SELECT category FROM service_price WHERE id = $1::uuid", pid
        )
        is None
    )


async def test_nhom_dieu_tri_khoi_3_du_moi_dich_vu_dieu_tri_dung_thu_tu(
    rb: RB,  # noqa: F811
) -> None:
    """Khối 3 liệt kê ĐỦ dịch vụ của loại khám nhóm Điều trị, đúng thứ tự ô chọn
    lúc đặt lịch — phiếu giấy chỉ có 4 dòng, Laser tiền đình / 1 thành từng lọt
    (Tuyền 08/10)."""
    from clinicai.services.phieu_kham_service import NHOM_DIEU_TRI

    pool = rb.pool
    await _dong_bo(pool)
    can = [
        r["service_code"]
        for r in await pool.fetch(
            "SELECT sp.service_code FROM service_type st JOIN service_price sp"
            " ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id"
            " JOIN danh_muc_dich_vu($1::uuid) d ON d.service_code = sp.service_code"
            " WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI'"
            " AND coalesce(st.is_active, true) AND d.active"
            " ORDER BY st.thu_tu, st.name",
            CLINIC,
        )
    ]
    assert len(can) >= 2, "DB test phải có loại khám Điều trị"
    tc = await PhieuKhamService(pool, kiem_quyen=_cho_qua).tham_chieu_that(
        identity=_ai()
    )
    co = [
        t["service_code"]
        for t in tc["thu_thuat"]
        if t.get("nhom") == NHOM_DIEU_TRI and t.get("service_code")
    ]
    assert co[: len(can)] == can
    assert len(co) == len(set(co)), f"trùng dòng điều trị: {co}"
