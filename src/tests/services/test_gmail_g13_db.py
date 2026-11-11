"""Gmail G13 (11/11/2026) — CHUYỂN tờ email "gắn theo lượt khám" vào chỉ định nhập
sau: lệnh bù (tờ cũ Từ chối, thư về hàng chờ, gán lại CÙNG khách vào chỉ định người
chọn). Dừng sớm ⇒ không đổi gì."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.xet_nghiem import gmail, gmail_vao_chi_dinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g3_db import Ca3, _dong, c3  # noqa: F401
from tests.services.test_gmail_g11_db import _nguoi, _to

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _theo_luot(pool: asyncpg.Pool, c3: Ca3) -> tuple[Any, Any]:  # noqa: F811
    """Thư về lúc khách CHƯA có chỉ định (chỉ định đang ở dạng huỷ) ⇒ tờ theo lượt;
    rồi "nhập chỉ định sau" (mở lại chỉ định, giờ tạo sau thư)."""
    v = await c3.viec(pool, ban_xn=False)
    goc = await pool.fetchval(
        "SELECT exec_status FROM service_order WHERE id = $1::uuid", v["oid"]
    )
    await pool.execute(
        "UPDATE service_order SET exec_status = 'cancelled' WHERE id = $1::uuid",
        v["oid"],
    )
    mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    to = await _to(pool, d["id"])
    assert (to["kh"], to["oid"], to["tt"]) == (v["kh"], None, "CHO_XAC_NHAN")
    await pool.execute(
        "UPDATE service_order SET exec_status = $2, created_at = now()"
        " WHERE id = $1::uuid",
        v["oid"],
        goc,
    )
    return v, d


async def test_chuyen_vao_chi_dinh_tu_choi_to_cu_va_phat_su_kien(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v, d = await _theo_luot(pool, c3)
    cu = (await _to(pool, d["id"]))["tep"]
    nguoi = await _nguoi(pool)
    ds = await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, nguoi, cu)
    assert [c["service_order_id"] for c in ds["chi_dinh"]] == [v["oid"]]
    kq = await gmail_vao_chi_dinh.vao_chi_dinh(
        pool, nguoi, {"tep_id": cu, "service_order_id": v["oid"]}
    )
    moi = await _to(pool, d["id"])
    assert moi["tep"] == kq["tep_id"] and moi["tep"] != cu
    assert (moi["kh"], moi["oid"]) == (v["kh"], v["oid"])
    tt_cu = await pool.fetchrow(
        "SELECT xac_nhan_trang_thai, xac_nhan_ly_do FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        cu,
    )
    assert tt_cu["xac_nhan_trang_thai"] == "TU_CHOI"
    assert "Chuyển vào chỉ định" in tt_cu["xac_nhan_ly_do"]
    su_kien = await pool.fetchval(
        "SELECT payload::text FROM domain_event"
        " WHERE event_type = 'lab.email_result_moved_to_order'"
        "   AND aggregate_id = $1::uuid",
        d["id"],
    )
    assert su_kien is not None and cu in su_kien and v["oid"] in su_kien
    # Bấm lại trên màn cũ: tờ cũ đã tháo khỏi thư ⇒ 404. Chỉ định đã có tờ (chính
    # chỉ định đang giữ tờ mới) không còn trong danh sách nhận.
    with pytest.raises(NotFoundError):
        await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, nguoi, cu)
    ds = await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, nguoi, moi["tep"])
    assert ds["chi_dinh"] == []


async def _them_cung_luot(pool: asyncpg.Pool, oid: str) -> str:  # noqa: F811
    """Chỉ định thứ hai CÙNG lượt, cùng dịch vụ đối tác (chép dòng có sẵn)."""
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "CREATE TEMP TABLE x ON COMMIT DROP AS"
            " SELECT * FROM service_order WHERE id = $1::uuid",
            oid,
        )
        moi = await conn.fetchval(
            "UPDATE x SET id = gen_random_uuid(), created_at = now(),"
            "       updated_at = now() RETURNING id::text"
        )
        await conn.execute("INSERT INTO service_order SELECT * FROM x")
    return str(moi)


async def test_chuyen_nham_a_thi_sua_sang_b_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Soát G13 (chặn): lượt có HAI chỉ định cùng đối tác, người chọn nhầm A ⇒ tờ ở A
    (chưa gửi khách) vẫn chuyển sang B được — không kẹt sai chỉ định."""
    v, d = await _theo_luot(pool, c3)
    b = await _them_cung_luot(pool, v["oid"])
    nguoi = await _nguoi(pool)
    cu = (await _to(pool, d["id"]))["tep"]
    ds = await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, nguoi, cu)
    assert {c["service_order_id"] for c in ds["chi_dinh"]} == {v["oid"], b}
    await gmail_vao_chi_dinh.vao_chi_dinh(
        pool, nguoi, {"tep_id": cu, "service_order_id": v["oid"]}
    )
    o_a = await _to(pool, d["id"])
    ds = await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, nguoi, o_a["tep"])
    assert [c["service_order_id"] for c in ds["chi_dinh"]] == [b]
    await gmail_vao_chi_dinh.vao_chi_dinh(
        pool, nguoi, {"tep_id": o_a["tep"], "service_order_id": b}
    )
    o_b = await _to(pool, d["id"])
    assert (o_b["oid"], o_b["kh"]) == (b, v["kh"])
    tt_a = await pool.fetchval(
        "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid", o_a["tep"]
    )
    assert tt_a in ("TU_CHOI", "THU_HOI")
    # Danh sách "Thư email đã gán" có nút chuyển cho tờ này (máy chủ tính).
    from clinicai.services.xet_nghiem import gmail_gan_lai

    dong = next(
        t
        for t in (await gmail_gan_lai.da_gan(pool, nguoi, ""))["thu"]
        if t["id"] == d["id"]
    )
    assert dong["chuyen_chi_dinh_duoc"] is True
    khong = next(
        t
        for t in (await gmail_gan_lai.da_gan(pool, await _nguoi(pool, False), ""))[
            "thu"
        ]
        if t["id"] == d["id"]
    )
    assert khong["chuyen_chi_dinh_duoc"] is False


async def test_dung_som_thi_khong_doi_gi(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Chỉ định của khách khác / id rác / thiếu quyền Xác nhận kết quả / tờ đã gửi
    khách ⇒ dừng, tờ và thư giữ nguyên."""
    v, d = await _theo_luot(pool, c3)
    khac = await c3.viec(pool, ban_xn=False)
    truoc = await _to(pool, d["id"])
    ca = [
        (await _nguoi(pool), khac["oid"], ConflictError),
        (await _nguoi(pool), "khong-phai-uuid", ConflictError),
        (await _nguoi(pool, xac_nhan=False), v["oid"], SafetyGateError),
    ]
    for nguoi, oid, loi in ca:
        with pytest.raises(loi):
            await gmail_vao_chi_dinh.vao_chi_dinh(
                pool, nguoi, {"tep_id": truoc["tep"], "service_order_id": oid}
            )
        assert await _to(pool, d["id"]) == truoc
    with pytest.raises(NotFoundError):
        await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, await _nguoi(pool), "rac")
    with pytest.raises(SafetyGateError):  # cửa GET cũng gác quyền
        await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(
            pool, await _nguoi(pool, xac_nhan=False), truoc["tep"]
        )
    # Hồ sơ khách đã ngưng ⇒ dừng TRƯỚC khi đụng tờ cũ.
    await pool.execute(
        "UPDATE patient SET is_active = false WHERE clinic_patient_id = $1::uuid",
        v["kh"],
    )
    with pytest.raises(ConflictError):
        await gmail_vao_chi_dinh.vao_chi_dinh(
            pool,
            await _nguoi(pool),
            {"tep_id": truoc["tep"], "service_order_id": v["oid"]},
        )
    assert await _to(pool, d["id"]) == truoc
    await pool.execute(
        "UPDATE patient SET is_active = true WHERE clinic_patient_id = $1::uuid",
        v["kh"],
    )
    # Tờ đã Hợp lệ VÀ đã gửi khách ⇒ không chuyển (khách đã nhận; dùng Gán lại).
    nguoi = await _nguoi(pool)
    await TepKetQuaService(pool).xac_nhan_tep(
        identity=nguoi, tep_id=truoc["tep"], trang_thai="HOP_LE"
    )
    await pool.execute(
        "UPDATE tep_ket_qua SET gui_luc = now(), gui_boi_staff_id = $2::uuid,"
        "       gui_kenh = 'ZALO' WHERE id = $1::uuid",
        truoc["tep"],
        nguoi.staff_id,
    )
    da_gui = await _to(pool, d["id"])
    with pytest.raises(ConflictError, match="đã gửi khách"):
        await gmail_vao_chi_dinh.vao_chi_dinh(
            pool, nguoi, {"tep_id": truoc["tep"], "service_order_id": v["oid"]}
        )
    assert await _to(pool, d["id"]) == da_gui


async def test_to_hop_le_chua_gui_thi_thu_hoi_roi_chuyen(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v, d = await _theo_luot(pool, c3)
    cu = (await _to(pool, d["id"]))["tep"]
    nguoi = await _nguoi(pool)
    await TepKetQuaService(pool).xac_nhan_tep(
        identity=nguoi, tep_id=cu, trang_thai="HOP_LE"
    )
    await gmail_vao_chi_dinh.vao_chi_dinh(
        pool, nguoi, {"tep_id": cu, "service_order_id": v["oid"]}
    )
    tt = await pool.fetchrow(
        "SELECT xac_nhan_trang_thai, thu_hoi_ly_do FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        cu,
    )
    assert tt["xac_nhan_trang_thai"] == "THU_HOI"
    assert "Chuyển vào chỉ định" in tt["thu_hoi_ly_do"]
    assert (await _to(pool, d["id"]))["oid"] == v["oid"]


async def test_chua_nhap_chi_dinh_thi_danh_sach_rong(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v, d = await _theo_luot(pool, c3)
    await pool.execute(
        "UPDATE service_order SET exec_status = 'cancelled' WHERE id = $1::uuid",
        v["oid"],
    )
    tep = (await _to(pool, d["id"]))["tep"]
    ds = await gmail_vao_chi_dinh.chi_dinh_nhan_duoc(pool, await _nguoi(pool), tep)
    assert ds["chi_dinh"] == []


async def test_hang_cho_xac_nhan_dua_to_theo_luot_len_dau(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Tờ theo lượt chỉ xử lý được ở màn này ⇒ đứng trước tờ có chỉ định (trần 100),
    kể cả khi tờ có chỉ định về TRƯỚC."""
    a = await c3.viec(pool, ban_xn=False)
    # Hàng chỉ lấy tờ có chỉ định của nút "làm bên ngoài" (như dịch vụ đối tác thật).
    await pool.execute(
        "UPDATE node_definition n SET lam_ben_ngoai = true FROM service_order o"
        " WHERE o.id = $1::uuid AND n.code = o.node_code AND n.clinic_id = o.clinic_id",
        a["oid"],
    )
    c3.thu(a["ten"], a["sdt"])
    await gmail.mot_vong(pool)  # tờ có chỉ định, về trước
    await pool.execute(
        "UPDATE tep_ket_qua SET tai_len_luc = now() - interval '1 day'"
        " WHERE clinic_patient_id = $1::uuid",
        a["kh"],
    )
    v, d = await _theo_luot(pool, c3)
    hang = await TepKetQuaService(pool).cho_xac_nhan(identity=await _nguoi(pool))
    vi_tri = {t["clinic_patient_id"]: i for i, t in enumerate(hang)}
    assert hang[vi_tri[a["kh"]]]["service_order_id"] == a["oid"]
    assert vi_tri[v["kh"]] < vi_tri[a["kh"]]
