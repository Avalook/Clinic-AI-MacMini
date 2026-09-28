"""Lấy mẫu + đối tác do NHÂN SỰ phòng khám làm (Tuyền chốt 29/09/2026).

1–3. Ai có lego/vị trí Đối tác làm được hết; không màn nào bắt buộc vai PARTNER.
4.   `/doi-tac` hiện đủ lịch sử các lần tải (tên, giờ, ai tải) — kể cả ngày cũ.
5.   Chọn ngày: việc đã gửi ngày cũ vẫn tìm lại được; "Đã lấy mẫu" idempotent,
     không bị lượt đã Hoàn tất chặn.
6–7. Bên thu thuộc TỪNG dịch vụ: chọn tay không bị suy-từ-phòng ghi đè; migration
     phân loại 4 mã KiotViet.
9.   Quyền đọc tệp: thêm người có quyền khối Đối tác / Phòng dịch vụ; vai
     PARTNER bên ngoài vẫn không.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.services.config_service import PriceListService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.tep_ket_qua_service import doc_duoc_tep_ket_qua
from tests.services.test_doi_tac_tu_thu_db import (
    HPV_NODE,
    _cd,
    _gia,
    _nguoi_vai,
    _viec_da_nhan,
)
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260929000020_ben_thu_theo_dich_vu.sql"
)


async def _cap(pool: asyncpg.Pool, staff_id: str, quyen: str, khoi: str) -> None:
    await pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
        " VALUES ($1::uuid, $2::uuid, $3, $4) ON CONFLICT DO NOTHING",
        CLINIC,
        staff_id,
        quyen,
        khoi,
    )


async def _nhan_su_trang(q: Quay) -> StaffIdentity:
    """Nhân sự phòng khám (vai tài khoản Thu ngân — ngoài NORMAL_READ_ROLES)
    CHƯA có lego nào: gỡ gói mẫu để phép thử chỉ đo đúng quyền được cấp thêm."""
    nv = await _nguoi_vai(q, "CASHIER")
    await q.pool.execute(
        "DELETE FROM capability_grant WHERE clinic_id = $1::uuid"
        " AND staff_id = $2::uuid",
        CLINIC,
        nv.staff_id,
    )
    return nv


async def _nhan_su_doi_tac(q: Quay) -> StaffIdentity:
    """Nhân sự PHÒNG KHÁM (không phải vai PARTNER) được bật lego Đối tác."""
    nv = await _nhan_su_trang(q)
    await _cap(q.pool, nv.staff_id, "partner.work", "doi_tac")
    return nv


async def _tep(q: Quay, oid: str, boi: str, ten: str, luc_sql: str = "now()") -> str:
    pid, aid = await q.pool.fetchrow(
        "SELECT v.clinic_patient_id::text, v.appointment_id::text FROM visit v"
        " WHERE v.visit_id = $1::uuid",
        q.visit_id,
    )
    tid = str(uuid.uuid4())
    await q.pool.execute(
        "INSERT INTO tep_ket_qua (id, clinic_id, clinic_patient_id, appointment_id,"
        " service_order_id, khoa, loai_tep, mime, so_byte, sha256,"
        " tai_len_boi_staff_id, ten_hien_thi, tai_len_luc)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6, 'PDF',"
        f" 'application/pdf', 1234, 'abc', $7::uuid, $8, {luc_sql})",
        tid,
        CLINIC,
        pid,
        aid,
        oid,
        f"{CLINIC}/{pid}/{tid}.pdf",
        boi,
        ten,
    )
    return tid


def _tim(ds: dict[str, Any], oid: str) -> dict[str, Any] | None:
    for k in ds["khach"]:
        for v in k["viec"]:
            if v["chi_dinh_id"] == oid:
                return dict(v)
    return None


# ---------------------------------------------------------------------------
# 4 + 5: danh sách theo ngày + lịch sử tệp
# ---------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.asyncio
async def test_viec_da_gui_ngay_cu_van_hien_khi_chon_ngay_ay(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    oid = await _viec_da_nhan(q)
    nv = await _nhan_su_doi_tac(q)
    # Việc từ HAI hôm trước, gửi tệp kết quả HÔM QUA.
    await pool.execute(
        "UPDATE service_order SET created_at = now() - interval '2 days',"
        " authorized_at = now() - interval '2 days',"
        " finished_at = now() - interval '2 days',"
        " ket_qua_luc = now() - interval '1 day' WHERE id = $1::uuid",
        oid,
    )
    await _tep(q, oid, nv.staff_id, "kq-hom-qua.pdf", "now() - interval '1 day'")
    svc = DoiTacService(pool)
    hom_qua = (hom_nay_vn() - timedelta(days=1)).isoformat()

    # Hôm nay: đã có kết quả từ hôm qua → rời bàn (như trước).
    hn = await svc.viec_doi_tac(identity=nv)
    assert hn["hom_nay"] is True and _tim(hn, oid) is None
    # Ngày rác = hôm nay, KHÔNG ném.
    rac = await svc.viec_doi_tac(identity=nv, ngay="2026-99-99")
    assert rac["ngay"] == hn["ngay"] and _tim(rac, oid) is None

    # Chọn HÔM QUA: việc hiện lại, kèm lịch sử tệp (tên, giờ, ai tải).
    hq = await svc.viec_doi_tac(identity=nv, ngay=hom_qua)
    assert hq["hom_nay"] is False and hq["ngay"] == hom_qua
    v = _tim(hq, oid)
    assert v is not None and v["trang_thai"] == "DA_GUI_KET_QUA"
    assert [t["ten"] for t in v["tep"]] == ["kq-hom-qua.pdf"]
    assert v["tep"][0]["boi"] == nv.full_name
    assert v["tep"][0]["thu_hoi"] is False
    # Nhân sự phòng khám có lego Đối tác MỞ được tệp; vai PARTNER thì không.
    assert hq["xem_tep"] is True
    dt = await _nguoi_vai(q, "PARTNER")
    assert (await svc.viec_doi_tac(identity=dt, ngay=hom_qua))["xem_tep"] is False

    # Gửi BỔ SUNG hôm nay → việc hiện ở hôm nay, đủ hai lần tải theo thứ tự.
    await _tep(q, oid, nv.staff_id, "kq-bo-sung.pdf")
    v = _tim(await svc.viec_doi_tac(identity=nv), oid)
    assert v is not None
    assert [t["ten"] for t in v["tep"]] == ["kq-hom-qua.pdf", "kq-bo-sung.pdf"]

    # Ngày không có hoạt động gì của việc này → không hiện.
    xa = (hom_nay_vn() - timedelta(days=5)).isoformat()
    assert _tim(await svc.viec_doi_tac(identity=nv, ngay=xa), oid) is None


# ---------------------------------------------------------------------------
# 5: "Đã lấy mẫu" idempotent, lượt đã Hoàn tất không chặn
# ---------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.asyncio
async def test_da_lay_mau_idempotent_tren_luot_da_hoan_tat(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ma = f"PHIM-{q.duoi}"
    node = "DICHVU-HINHANH-NGOAI"
    await _gia(q, ma, 1_500_000, node, ben="EXTERNAL_PARTNER", tu_lay=True)
    oid = await _cd(q, ma, node)
    await pool.execute(
        "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
        " VALUES ($1::uuid, $2::uuid, 'KHACH_DA_CHON')",
        CLINIC,
        oid,
    )
    # Lượt đã Hoàn tất (bác sĩ ký) — trước 29/09 lệnh ăn 409 VISIT_CLOSED.
    await pool.execute(
        "UPDATE visit SET status = 'FINALIZED', finalized_at = now(),"
        " finalized_by = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        q.bac_si.staff_id,
    )
    nv = await _nhan_su_doi_tac(q)
    svc = DoiTacService(pool)

    lan1 = await svc.doi_tac_da_lay_mau(order_id=oid, identity=nv, ghi_chu="2 ống")
    assert lan1["already"] is False
    moc = await pool.fetchrow(
        "SELECT exec_status, finished_at, performed_by::text AS ai"
        " FROM service_order WHERE id = $1::uuid",
        oid,
    )
    assert moc["exec_status"] == "performed" and moc["ai"] == nv.staff_id

    # Bấm lần hai (người khác, ngày cũ…) — không lỗi, không ghi nhận đôi.
    nv2 = await _nhan_su_doi_tac(q)
    lan2 = await svc.doi_tac_da_lay_mau(order_id=oid, identity=nv2, ghi_chu="bổ sung")
    assert lan2["already"] is True
    lai = await pool.fetchrow(
        "SELECT exec_status, finished_at, performed_by::text AS ai"
        " FROM service_order WHERE id = $1::uuid",
        oid,
    )
    assert lai["finished_at"] == moc["finished_at"] and lai["ai"] == nv.staff_id
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type ="
            " 'partner.sample_collected' AND aggregate_id = $1::uuid",
            oid,
        )
        == 1
    )
    # Lần sau chỉ GHI LẠI vào nhật ký.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type ="
            " 'partner.sample_noted_again' AND payload->>'order_id' = $1",
            oid,
        )
        == 1
    )
    assert (
        await pool.fetchval(
            "SELECT ghi_chu_lay_mau FROM doi_tac_nhan_viec"
            " WHERE service_order_id = $1::uuid",
            oid,
        )
        == "bổ sung"
    )
    # Lượt vẫn giữ trạng thái đã ký — lệnh không mở lại lượt.
    assert (
        await pool.fetchval(
            "SELECT status FROM visit WHERE visit_id = $1::uuid", q.visit_id
        )
        == "FINALIZED"
    )


# ---------------------------------------------------------------------------
# 6 + 7: bên thu thuộc từng dịch vụ
# ---------------------------------------------------------------------------


async def _ben(pool: asyncpg.Pool, pid: str) -> tuple[str, bool]:
    r = await pool.fetchrow(
        "SELECT billing_owner, billing_owner_chon_tay FROM service_price"
        " WHERE id = $1::uuid",
        pid,
    )
    return r["billing_owner"], r["billing_owner_chon_tay"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_ben_thu_chon_tay_khong_bi_phong_ghi_de(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    svc = PriceListService(pool)

    # Không chọn → mặc định theo phòng làm (như cũ), chưa đánh dấu chọn tay.
    mac_dinh = await svc.add(
        service_code=f"MD-{q.duoi}",
        name="Mặc định theo phòng",
        group="dich_vu",
        unit_price=100_000,
        identity=ql,
        node_code="DICHVU-LAYMAU-MAU",
    )
    assert await _ben(pool, mac_dinh) == ("EXTERNAL_PARTNER", False)
    await svc.update(price_id=mac_dinh, identity=ql, node_code="DICHVU-SIEUAM")
    assert await _ben(pool, mac_dinh) == ("CLINIC", False)

    # Chọn tay khi tạo → giữ dù phòng làm là bước làm bên ngoài.
    tay = await svc.add(
        service_code=f"TAY-{q.duoi}",
        name="Chọn tay",
        group="dich_vu",
        unit_price=100_000,
        identity=ql,
        node_code="DICHVU-LAYMAU-MAU",
        billing_owner="CLINIC",
    )
    assert await _ben(pool, tay) == ("CLINIC", True)
    await svc.update(price_id=tay, identity=ql, node_code="DICHVU-LAYMAU-AMDAO")
    assert await _ben(pool, tay) == ("CLINIC", True)

    # Chọn tay ở màn Bảng giá (sửa) rồi đổi phòng làm → vẫn giữ.
    await svc.update(price_id=mac_dinh, identity=ql, billing_owner="EXTERNAL_PARTNER")
    assert await _ben(pool, mac_dinh) == ("EXTERNAL_PARTNER", True)
    await svc.update(price_id=mac_dinh, identity=ql, node_code="DICHVU-SIEUAM")
    assert await _ben(pool, mac_dinh) == ("EXTERNAL_PARTNER", True)
    # Chọn + đổi phòng trong CÙNG một lần sửa: lựa chọn thắng.
    await svc.update(
        price_id=mac_dinh,
        identity=ql,
        node_code="DICHVU-LAYMAU-MAU",
        billing_owner="CLINIC",
    )
    assert await _ben(pool, mac_dinh) == ("CLINIC", True)

    # Rác → 422, không đổi gì.
    with pytest.raises(ValidationError):
        await svc.update(price_id=mac_dinh, identity=ql, billing_owner="đối tác")
    assert await _ben(pool, mac_dinh) == ("CLINIC", True)

    # Bảng giá trả cờ chọn tay cho màn.
    dong = {str(r["id"]): r for r in await svc.list(group="dich_vu", identity=ql)}
    assert dong[tay]["billing_owner_chon_tay"] is True
    assert dong[tay]["billing_owner"] == "CLINIC"


@pytest.mark.db
@pytest.mark.asyncio
async def test_migration_phan_loai_thu_ho_theo_kiotviet(pool: asyncpg.Pool) -> None:
    mong = {
        "SP000092": "EXTERNAL_PARTNER",
        "SP000075": "EXTERNAL_PARTNER",
        "SP000025": "CLINIC",
        "SP000076": "CLINIC",
    }

    async def doc() -> dict[str, tuple[str, bool]]:
        return {
            r["ma_kiotviet"]: (r["billing_owner"], r["billing_owner_chon_tay"])
            for r in await pool.fetch(
                "SELECT ma_kiotviet, billing_owner, billing_owner_chon_tay"
                " FROM service_price WHERE clinic_id = $1::uuid"
                " AND \"group\" = 'dich_vu' AND ma_kiotviet IS NOT NULL",
                CLINIC,
            )
        }

    # Trả 4 mã về "trạng thái trước migration" (DB dựng mới đã chạy migration
    # + seed) để đo đúng việc migration làm.
    await pool.execute(
        "UPDATE service_price SET billing_owner = CASE ma_kiotviet"
        " WHEN 'SP000092' THEN 'CLINIC' WHEN 'SP000075' THEN 'CLINIC'"
        " ELSE 'EXTERNAL_PARTNER' END, billing_owner_chon_tay = false"
        " WHERE clinic_id = $1::uuid AND \"group\" = 'dich_vu'"
        " AND ma_kiotviet IN ('SP000092', 'SP000075', 'SP000025', 'SP000076')",
        CLINIC,
    )
    truoc = await doc()
    assert set(mong) <= set(truoc)  # danh mục KiotViet có đủ 4 mã

    await pool.execute(MIGRATION.read_text(encoding="utf-8"))
    sau = await doc()
    for ma, ben in mong.items():
        assert sau[ma] == (ben, True), ma
    # Mã khác GIỮ NGUYÊN — bên thu lẫn cờ chọn tay.
    khac = {m: v for m, v in truoc.items() if m not in mong}
    assert khac and {m: sau[m] for m in khac} == khac

    # Chạy lại được: lần hai không đổi gì.
    await pool.execute(MIGRATION.read_text(encoding="utf-8"))
    assert await doc() == sau

    # Đổi phòng làm của SP000025 sang đúng phòng lấy mẫu (bước làm bên ngoài)
    # KHÔNG lật lại "phòng khám thu".
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    r = await pool.fetchrow(
        "SELECT id::text, node_code FROM service_price WHERE clinic_id = $1::uuid"
        " AND ma_kiotviet = 'SP000025' AND \"group\" = 'dich_vu'",
        CLINIC,
    )
    if r is not None and r["node_code"]:
        await PriceListService(pool).update(
            price_id=r["id"], identity=ql, node_code=r["node_code"]
        )
        assert await _ben(pool, r["id"]) == ("CLINIC", True)


# ---------------------------------------------------------------------------
# 9: quyền đọc tệp
# ---------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.asyncio
async def test_quyen_doc_tep_cho_nhan_su_doi_tac_va_phong(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    thu_ngan = await _nhan_su_trang(q)
    async with pool.acquire() as conn:
        assert await doc_duoc_tep_ket_qua(conn, thu_ngan) is False

    # Bật lego Đối tác → đọc được (xem/tải/in tệp mình vừa gửi).
    dt_nv = await _nhan_su_doi_tac(q)
    async with pool.acquire() as conn:
        assert await doc_duoc_tep_ket_qua(conn, dt_nv) is True

    # Quyền PHÒNG DỊCH VỤ chỉ ở MỘT phòng (hẹp theo phòng) → vẫn đọc được.
    phong_nv = await _nhan_su_trang(q)
    room = await pool.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid AND is_active"
        " ORDER BY sort LIMIT 1",
        CLINIC,
    )
    await pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi,"
        " scope_type, scope_id) VALUES ($1::uuid, $2::uuid,"
        " 'service.execute.start', 'thuc_hien', 'ROOM', $3::uuid)",
        CLINIC,
        phong_nv.staff_id,
        room,
    )
    async with pool.acquire() as conn:
        assert await doc_duoc_tep_ket_qua(conn, phong_nv) is True

    # Vai PARTNER (người ngoài) — kể cả có `partner.work` — KHÔNG đọc được.
    dt = await _nguoi_vai(q, "PARTNER")
    async with pool.acquire() as conn:
        assert await doc_duoc_tep_ket_qua(conn, dt) is False


# ---------------------------------------------------------------------------
# 5: hàng chờ phòng theo ngày — ngày rác không ném
# ---------------------------------------------------------------------------


@pytest.mark.db
@pytest.mark.asyncio
async def test_hang_cho_phong_theo_ngay(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    room = await pool.fetchval(
        "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn"
        " ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id"
        " WHERE r.clinic_id = $1::uuid AND r.is_active"
        " AND rn.node_code LIKE 'DICHVU-LAYMAU%' AND NOT r.la_doi_tac"
        " ORDER BY r.sort LIMIT 1",
        CLINIC,
    )
    bang = BangLuotKham(pool)
    hn = await bang.hang_cho(identity=ql, room_id=room, ngay=None)
    assert hn["hom_nay"] is True and hn["ngay"] == hom_nay_vn().isoformat()
    rac = await bang.hang_cho(identity=ql, room_id=room, ngay="'; rác")
    assert rac["hom_nay"] is True
    hom_qua = (hom_nay_vn() - timedelta(days=1)).isoformat()
    cu = await bang.hang_cho(identity=ql, room_id=room, ngay=hom_qua)
    assert cu["hom_nay"] is False and cu["ngay"] == hom_qua
    # Ngày cũ không có "chưa xếp phòng" / "sắp tới" — việc của hôm nay.
    assert cu["chua_xep_phong"] == [] and cu["sap_toi"] == []
    # Khách check-in HÔM NAY không lọt vào hàng chờ của hôm qua.
    assert all(d["visit_id"] != q.visit_id for d in cu["hang_cho"])


@pytest.mark.db
@pytest.mark.asyncio
async def test_viec_hpv_hom_nay_van_hien(pool: asyncpg.Pool) -> None:
    """Hồi quy: việc còn chờ hôm nay vẫn hiện như trước (không cần chọn ngày)."""
    q = await tao_quay(pool)
    ma = f"HPV2-{q.duoi}"
    await _gia(q, ma, 900_000, HPV_NODE, ben="EXTERNAL_PARTNER")
    oid = await _cd(q, ma, HPV_NODE, exec_status="performed")
    await pool.execute(
        "INSERT INTO doi_tac_nhan_viec (clinic_id, service_order_id, ly_do)"
        " VALUES ($1::uuid, $2::uuid, 'DA_LAY_MAU')",
        CLINIC,
        oid,
    )
    nv = await _nhan_su_doi_tac(q)
    v = _tim(await DoiTacService(pool).viec_doi_tac(identity=nv), oid)
    assert v is not None and v["trang_thai"] == "DA_LAY_MAU" and v["tep"] == []
