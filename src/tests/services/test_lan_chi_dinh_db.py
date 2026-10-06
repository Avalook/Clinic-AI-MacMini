"""Lần chỉ định (26/09/2026 — lát 4; ỔN ĐỊNH 06/10/2026).

Tuyền thử thật 06/10: vào ra Bàn khám rồi tick thêm thì TỰ thành lần 2. Nay:
mặc định vào LẦN HIỆN TẠI; chỉ lệnh "mở lần mới" (nút "Chỉ định thêm (lần N)")
mới sang lần kế. Dịch vụ đã chỉ định chỉ định lại được — là một dòng mới.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services.chi_dinh_service import (
    ChiDinhService,
    doc_lan_dang_thay,
    lan_cua_luot,
)
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lan(pool: asyncpg.Pool, visit: str) -> dict[str, int | None]:  # noqa: F811
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    return {d["service_order_id"]: d["lan"] for d in ds}


async def _lan_luot(pool: asyncpg.Pool, visit: str) -> dict[str, object]:  # noqa: F811
    async with pool.acquire() as conn:
        return await lan_cua_luot(conn, CLINIC, visit)


async def test_bam_gui_lan_hai_van_lan_1_chi_nut_mo_lan_moi_moi_sang_lan_2(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Kịch bản Tuyền: tick 3 → bỏ 2 → ra vào → tick thêm = vẫn lần 1;
    bấm "Chỉ định thêm (lần 2)" mới sang lần 2."""
    from clinicai.services.hoan_tac_service import HoanTacService

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, don_1 = await _kham_va_chi_dinh(pool, ca, visit)
    assert await _lan_luot(pool, visit) == {
        "hien_tai": 1,
        "ke_tiep": 2,
        "mo_moi_duoc": True,
    }
    svc = ChiDinhService(pool)
    kq = await svc.dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    don_2 = str(kq["order_ids"][0])
    assert don_2 != don_1, "chỉ định lại là một dòng MỚI, không gộp vào dòng cũ"
    assert kq["lan"] == 1, "bấm gửi lần hai (vào lại màn) KHÔNG tự sang lần 2"
    # Bỏ chỉ định không đổi lần; gửi tiếp vẫn lần 1.
    await HoanTacService(pool).huy_chi_dinh(
        order_id=don_2, identity=ca.bac_si, ly_do="nhầm", xac_nhan=True
    )
    kq = await svc.dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    assert kq["lan"] == 1
    # Nút "Chỉ định thêm (lần 2)".
    kq = await svc.dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
        lan_moi=True,
        lan_dang_thay=1,
    )
    assert kq["lan"] == 2
    # Sau đó gửi thường = vào lần 2 (lần hiện tại), không nhảy lần 3.
    kq = await svc.dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    assert kq["lan"] == 2
    lan = await _lan(pool, visit)
    assert lan[don_1] == 1
    assert await _lan_luot(pool, visit) == {
        "hien_tai": 2,
        "ke_tiep": 3,
        "mo_moi_duoc": True,
    }


async def test_mo_lan_moi_khi_lan_hien_tai_toan_dong_bo_thi_dung_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from clinicai.services.hoan_tac_service import HoanTacService

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, don_1 = await _kham_va_chi_dinh(pool, ca, visit)
    await HoanTacService(pool).huy_chi_dinh(
        order_id=don_1, identity=ca.bac_si, ly_do="nhầm", xac_nhan=True
    )
    assert await _lan_luot(pool, visit) == {
        "hien_tai": 1,
        "ke_tiep": 1,
        "mo_moi_duoc": False,
    }
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
        lan_moi=True,
        lan_dang_thay="rác",
    )
    assert kq["lan"] == 1, "không đẻ lần rỗng"


async def test_doc_lan_dang_thay_rac_tra_none() -> None:
    assert doc_lan_dang_thay("rác") is None
    assert doc_lan_dang_thay(None) is None
    assert doc_lan_dang_thay(True) is None
    assert doc_lan_dang_thay(-1) is None
    assert doc_lan_dang_thay("2") == 2


async def test_mot_lan_bam_nhieu_dich_vu_chung_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, _ = await _kham_va_chi_dinh(pool, ca, visit)
    ma_khac = await pool.fetchval(
        "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
        " AND active AND service_code <> $2 AND node_code IS NOT NULL LIMIT 1",
        CLINIC,
        ca.ma_dv,
    )
    assert ma_khac, "cần thêm một dịch vụ có phòng làm trong seed"
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv, ma_khac],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    lan = await _lan(pool, visit)
    assert {lan[str(i)] for i in kq["order_ids"]} == {1}, "một lần bấm = một lần"


async def test_hai_nguoi_cung_bam_mo_lan_moi_chi_ra_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Hai máy cùng thấy lần 1, cùng bấm "Chỉ định thêm (lần 2)": người sau vào
    lần 2 người trước vừa mở, không đẻ lần 3 (advisory lock + lần đang thấy)."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, _ = await _kham_va_chi_dinh(pool, ca, visit)
    svc = ChiDinhService(pool)
    a, b = await asyncio.gather(
        *(
            svc.dat_chi_dinh(
                consultation_id=con,
                service_codes=[ca.ma_dv],
                identity=ca.bac_si,
                idempotency_key=_khoa(),
                lan_moi=True,
                lan_dang_thay=1,
            )
            for _ in range(2)
        )
    )
    lan = await _lan(pool, visit)
    assert {lan[str(a["order_ids"][0])], lan[str(b["order_ids"][0])]} == {2}


async def test_trigger_nhap_nhan_so_luc_duyet_mang_sang_khong_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Luật ở trigger — mọi đường tạo chỉ định (kể cả đường nháp cũ) đi qua."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, _ = await _kham_va_chi_dinh(pool, ca, visit)
    moi = (
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, mang_tu_visit_id,"
        " recorded_by, authorized_by, authorized_at)"
        " SELECT $1::uuid, $2::uuid, $3::uuid, $4, 'x', o.node_code, $5, $6::uuid,"
        "        o.recorded_by, o.authorized_by, o.authorized_at"
        # Chép từ chỉ định ĐÃ DUYỆT của lượt — không ORDER thì LIMIT 1 có lúc
        # nhặt đúng dòng nháp vừa tạo (chưa người duyệt) → vi phạm CHECK.
        "   FROM service_order o WHERE o.visit_id = $2::uuid"
        "    AND o.exec_status = 'authorized' AND o.authorized_by IS NOT NULL"
        "  ORDER BY o.created_at LIMIT 1"
        " RETURNING id::text"
    )
    nhap = await pool.fetchval(
        moi.replace("o.authorized_by, o.authorized_at", "NULL, NULL"),
        CLINIC,
        visit,
        con,
        ca.ma_dv,
        "draft",
        None,
    )
    assert (
        await pool.fetchval(
            "SELECT lan_chi_dinh FROM service_order WHERE id = $1::uuid", nhap
        )
        is None
    ), "nháp chưa duyệt chưa có lần"
    mang = await pool.fetchval(moi, CLINIC, visit, con, ca.ma_dv, "authorized", visit)
    await pool.execute(
        "UPDATE service_order SET exec_status = 'authorized',"
        " authorized_by = recorded_by, authorized_at = now() WHERE id = $1::uuid",
        nhap,
    )
    so = {
        r["id"]: r["lan_chi_dinh"]
        for r in await pool.fetch(
            "SELECT id::text, lan_chi_dinh FROM service_order"
            " WHERE id = ANY($1::uuid[])",
            [nhap, mang],
        )
    }
    assert so[nhap] == 1, "nháp nhận số lúc được duyệt — vào lần hiện tại"
    assert so[mang] is None, "mang sang từ lượt trước không thuộc lần nào"


async def test_chi_dinh_lam_o_doi_tac_mang_trang_thai_ban_doi_tac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lát 4c: phiếu khám thấy việc ở đối tác tới đâu — cùng hàm với bàn đối tác."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    _con, don = await _kham_va_chi_dinh(pool, ca, visit)

    async def doi_tac() -> str | None:
        async with pool.acquire() as conn:
            ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
        [d] = [d for d in ds if d["service_order_id"] == don]
        tt = d["doi_tac"]
        return None if tt is None else str(tt)

    assert await doi_tac() is None, "làm tại phòng khám: không có trạng thái đối tác"
    ngoai = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid"
        " AND lam_ben_ngoai LIMIT 1",
        CLINIC,
    )
    assert ngoai, "seed cần một phòng làm bên ngoài"
    await pool.execute(
        "UPDATE service_order SET node_code = $2 WHERE id = $1::uuid", don, ngoai
    )
    assert await doi_tac() == "CHO_LAY_MAU"
    await pool.execute(
        "UPDATE service_order SET doi_tac_cho_tai_lieu_luc = now() WHERE id = $1::uuid",
        don,
    )
    assert await doi_tac() == "DA_NHAN_MAU"
    await pool.execute(
        "UPDATE service_order SET ket_qua_luc = now() WHERE id = $1::uuid", don
    )
    assert await doi_tac() == "DA_GUI_KET_QUA"


async def test_dong_ket_qua_co_ma_sp_gia_da_thu_da_xem_va_the_khach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Dữ liệu cho giao diện y hệt bản mẫu (27/09/2026)."""
    from clinicai.phieu_kham.mang_sang import doc_dau_phieu

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    _con, don = await _kham_va_chi_dinh(pool, ca, visit)
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    [d] = [x for x in ds if x["service_order_id"] == don]
    assert d["da_thu"] is False and d["da_xem_luc"] is None
    assert "gia" in d and "ma_kiotviet" in d
    tk = dau["the_khach"]
    assert tk["bac_si"], "bác sĩ của lượt (hoặc phiên khám chính)"
    assert tk["co_so"] and tk["loai_kham"]
    assert len(dau["the_sinh_hieu"]) == 9
