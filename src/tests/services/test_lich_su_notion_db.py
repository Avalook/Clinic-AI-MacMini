"""Lịch sử khám cũ nhập từ Notion (05/10/2026): nạp gói → đọc lại đúng người.

Kịch bản thật Tuyền hỏi: khách A đã khám nhiều lần trên Notion, hôm nay đến và
lễ tân tạo hồ sơ MỚI trên hệ thống. Khi nhập, các lượt Notion phải gắn vào ĐÚNG
hồ sơ hôm nay (khớp 9 số cuối SĐT + tên bỏ dấu), không tạo hồ sơ thứ hai; nạp
lại không sinh trùng; khách cũ không còn bị coi là "khách mới".
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.danh_sach_benh_nhan_service import DanhSachBenhNhanService
from clinicai.services.lich_su_notion_service import chi_tiet_luot, lich_su
from clinicai.services.nhap_lich_su_notion import nap
from tests.services.test_luot_kham_service_db import CLINIC, KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _sdt() -> str:
    return "09" + "".join(random.choice("0123456789") for _ in range(8))


def _ghi(thu_muc: Path, ten: str, dong: list[dict[str, Any]]) -> None:
    (thu_muc / f"{ten}.jsonl").write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in dong) + "\n"
    )


def _goi(tmp: Path, *, nguoi: list[dict[str, Any]], luot: list[dict[str, Any]]) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "manifest.json").write_text(json.dumps({"goi": "test"}))
    _ghi(tmp, "nguoi", nguoi)
    _ghi(tmp, "luot_kham", luot)
    dv, kq = [], []
    for lk in luot:
        d = str(uuid.uuid4())
        dv.append(
            {
                "notion_id": d,
                "nguoi_key": lk["nguoi_key"],
                "luot_kham_id": lk["notion_id"],
                "ma": "SERVICE-T",
                "ten_goc": ["[SA] Siêu âm thử"],
                "service_code": None,
                "nguoi_lam": ["BS Thử", "ĐD Thử"],
                "ngay": lk["ngay_kham"],
                "ten_goc_null_test": None,
            }
        )
        kq.append(
            {
                "notion_id": str(uuid.uuid4()),
                "nguoi_key": lk["nguoi_key"],
                "dich_vu_id": d,
                "luot_kham_id": lk["notion_id"],
                "ma": "KQSA-T",
                "tieu_de": "Kết quả siêu âm thử",
                "mo_ta": "- Tử cung bình thường",
                "ket_luan": "Chưa thấy bất thường",
                "bac_si_ky": None,  # JSON null — bộ nạp phải chịu được
                "da_co_noi_dung": True,
            }
        )
    _ghi(tmp, "dich_vu", dv)
    _ghi(tmp, "ket_qua", kq)
    for ten in ("xet_nghiem", "ke_thuoc", "lich_hen", "bat_thuong"):
        _ghi(tmp, ten, [])
    return tmp


def _luot(key: str, ngay: str, *, lan: int, cung_ngay: bool = False) -> dict[str, Any]:
    return {
        "notion_id": str(uuid.uuid4()),
        "nguoi_key": key,
        "ma": str(random.randint(1, 99999)),
        "ngay_kham": ngay,
        "nguon_ngay": "ngày tạo phiếu khám trên Notion",
        "lan_thu": lan,
        "thu_tu_khong_chac": cung_ngay,
        "loai_kham_goc": "Phụ khoa",
        "service_type_code": "PHU_KHOA",
        "bac_si_goc": "BS Thử",
        "staff_ten": None,
        "kham_tu_van": "HA 110/70",
        "chan_doan": f"Chẩn đoán lần {lan}",
    }


async def _khach_he_thong(
    conn: asyncpg.Connection, loc: str, ten: str, sdt: str
) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary) VALUES ($1::uuid, $2, $3, $4::uuid, $5)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"BN-T-{uuid.uuid4().hex[:8]}",
            ten,
            loc,
            sdt,
        )
    )


async def test_khach_a_tao_hom_nay_nhan_du_lich_su_notion(
    kb: KichBan, tmp_path: Path
) -> None:
    sdt = _sdt()
    async with kb.pool.acquire() as conn:
        a = await _khach_he_thong(conn, kb.location_id, "Nguyễn Thị Thử Ghép", sdt)
    key = f"hc:{uuid.uuid4()}"
    goi = _goi(
        tmp_path / "goi",
        nguoi=[
            {
                # Notion gõ khác hoa/thường + số kiểu +84 — vẫn là khách A.
                "nguoi_key": key,
                "ten": "nguyễn thị  thử ghép",
                "sdt": "+84" + sdt[1:],
                "ma": f"KHACH-T{random.randint(1, 10**6)}",
                "ho_so_notion": ["KHACH-T1", "LAMSANG-T1"],
                "nguon_ten": "hành chính",
                "notion_url": "https://www.notion.so/x",
            }
        ],
        luot=[
            _luot(key, "2026-04-01", lan=1),
            _luot(key, "2026-05-02", lan=2, cung_ngay=True),
            _luot(key, "2026-05-02", lan=3, cung_ngay=True),
        ],
    )

    thu = await nap(kb.pool, goi, that=False, clinic_id=CLINIC)
    assert thu["thu_kho"] is True
    async with kb.pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT count(*) FROM lich_su_notion.nguoi WHERE nguoi_key = $1", key
        ), "thử khô không được ghi gì"

    kq = await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    assert kq["tao_ho_so_moi"] == 0
    async with kb.pool.acquire() as conn:
        gan = await conn.fetchrow(
            "SELECT clinic_patient_id::text AS bn, cach_ghep FROM lich_su_notion.nguoi"
            " WHERE nguoi_key = $1",
            key,
        )
    assert gan["bn"] == a and gan["cach_ghep"] == "ghep_sdt_ten"

    ls = await lich_su(kb.pool, identity=kb.bac_si, clinic_patient_id=a)
    assert ls["co_lich_su"] and ls["co_noi_dung"]
    assert [
        (x["ngay_kham"], x["lan_thu"], x["thu_tu_khong_chac"]) for x in ls["luot"]
    ] == [
        ("2026-05-02", 3, True),
        ("2026-05-02", 2, True),
        ("2026-04-01", 1, False),
    ]
    ct = await chi_tiet_luot(kb.pool, identity=kb.bac_si, luot_id=ls["luot"][-1]["id"])
    assert ct["chan_doan"] == "Chẩn đoán lần 1"
    assert ct["dich_vu"][0]["nguoi_lam"] == ["BS Thử", "ĐD Thử"]
    assert ct["dich_vu"][0]["ket_qua"][0]["ket_luan"] == "Chưa thấy bất thường"

    # Nạp lại cùng gói: không thêm người, không thêm lượt.
    lai = await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    assert lai["tao_ho_so_moi"] == 0
    async with kb.pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM lich_su_notion.luot_kham"
                " WHERE clinic_patient_id = $1::uuid",
                a,
            )
            == 3
        )
        # Khách đã khám Phụ khoa trên Notion → không còn là "khách mới" của Phụ khoa.
        st = await conn.fetchval(
            "SELECT id FROM service_type"
            " WHERE clinic_id = $1::uuid AND code = 'PHU_KHOA'",
            CLINIC,
        )
        if st is not None:
            assert not await conn.fetchval(
                "SELECT la_khach_moi_cua_dich_vu($1::uuid, $2::uuid, $3, 'CHUA_TUNG')",
                CLINIC,
                a,
                st,
            )


async def test_khach_moi_tu_notion_va_trung_sdt_khac_ten(
    kb: KichBan, tmp_path: Path
) -> None:
    sdt = _sdt()
    async with kb.pool.acquire() as conn:
        me = await _khach_he_thong(conn, kb.location_id, "Trần Thị Mẹ Thử", sdt)
    key = f"hc:{uuid.uuid4()}"
    ma = f"KHACH-T{random.randint(1, 10**6)}"
    goi = _goi(
        tmp_path / "goi",
        nguoi=[
            {
                "nguoi_key": key,
                "ten": "Lê Văn Con Thử",
                "sdt": sdt,
                "ma": ma,
                "ghi_chu_lan_dau": "Nhập từ Notion — không có lượt khám nào",
            }
        ],
        luot=[],
    )
    kq = await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    assert kq["tao_ho_so_moi"] == 1
    async with kb.pool.acquire() as conn:
        moi = await conn.fetchrow(
            "SELECT p.clinic_patient_id::text AS id, p.nguon_nhap, p.patient_code"
            " FROM lich_su_notion.nguoi n JOIN patient p USING (clinic_patient_id)"
            " WHERE n.nguoi_key = $1",
            key,
        )
        assert moi["nguon_nhap"] == "notion" and moi["patient_code"] == ma
        assert moi["id"] != me, "cùng SĐT khác tên → KHÔNG gộp"
        canh = await conn.fetchval(
            "SELECT chi_tiet FROM lich_su_notion.bat_thuong"
            " WHERE loai = 'CO_THE_TRUNG_HO_SO_HE_THONG' AND notion_id = $1",
            key,
        )
        assert canh and "khác tên" in canh

    ls = await lich_su(kb.pool, identity=kb.bac_si, clinic_patient_id=moi["id"])
    assert ls["nguoi"]["ghi_chu_lan_dau"] == "Nhập từ Notion — không có lượt khám nào"
    assert ls["luot"] == []


async def test_khong_co_quyen_phieu_kham_thi_chi_thay_danh_sach(
    kb: KichBan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cố định "không có quyền xem phiếu khám": quyền mặc định của vai trên DB test
    # dùng chung bị test khác đổi (chạy riêng thì qua, chạy cả bộ thì không).
    # Điều cần kiểm ở đây là CÁCH dịch vụ chặn nội dung, không phải bảng quyền.
    import clinicai.services.lich_su_notion_service as lsn

    async def khong_co_quyen(conn: Any, identity: Any) -> bool:
        return False

    monkeypatch.setattr(lsn, "co_quyen_noi_dung", khong_co_quyen)
    async with kb.pool.acquire() as conn:
        a = await _khach_he_thong(conn, kb.location_id, "Phạm Thị Quyền Thử", _sdt())
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ('Test không quyền', 'CSKH', $1::uuid, true)"
            " RETURNING id::text",
            kb.location_id,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, 'CSKH', true)"
            # Bộ chạy song song: trigger/test khác có thể đã tạo dòng thành viên.
            " ON CONFLICT DO NOTHING",
            CLINIC,
            sid,
        )
        p = await conn.fetchrow(
            "SELECT full_name, phone_primary FROM patient"
            " WHERE clinic_patient_id = $1::uuid",
            a,
        )
    key = f"hc:{uuid.uuid4()}"
    goi = _goi(
        tmp_path / "goi",
        nguoi=[
            {
                "nguoi_key": key,
                "ten": p["full_name"],
                "sdt": p["phone_primary"],
                "ma": "X",
            }
        ],
        luot=[_luot(key, "2026-06-01", lan=1)],
    )
    await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    khong_quyen = StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="Test không quyền",
        department="CSKH",
        role=ClinicRole("CSKH"),
        clinic_id=CLINIC,
        location_id=kb.location_id,
        location_name="Cơ sở test",
    )
    ls = await lich_su(kb.pool, identity=khong_quyen, clinic_patient_id=a)
    assert ls["co_noi_dung"] is False
    assert ls["luot"][0]["chan_doan"] is None
    with pytest.raises(SafetyGateError):
        await chi_tiet_luot(kb.pool, identity=khong_quyen, luot_id=ls["luot"][0]["id"])


async def test_ho_so_cu_chua_hoat_dong_van_vao_danh_sach_benh_nhan(
    kb: KichBan, tmp_path: Path
) -> None:
    """06/10/2026: Danh sách bệnh nhân phân trang + tìm phía máy chủ, nên MỌI hồ
    sơ cũ từ Notion đều vào danh sách (bản 05/10 giấu hồ sơ chưa hoạt động vì
    màn nạp hết về trình duyệt); khách cũ quay lại (có lượt) vẫn hiện."""
    key = f"hc:{uuid.uuid4()}"
    ma = f"KHACH-T{random.randint(1, 10**6)}"
    goi = _goi(
        tmp_path / "goi",
        nguoi=[{"nguoi_key": key, "ten": "Đỗ Thị Cũ Thử", "sdt": _sdt(), "ma": ma}],
        luot=[],
    )
    await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    async with kb.pool.acquire() as conn:
        bn = await conn.fetchval(
            "SELECT clinic_patient_id::text FROM patient WHERE patient_code = $1", ma
        )

    async def co_trong_danh_sach() -> bool:
        ds = await DanhSachBenhNhanService(kb.pool).lay(identity=kb.bac_si, q=ma)
        return any(d["ho_so"]["clinic_patient_id"] == bn for d in ds["dong"])

    assert await co_trong_danh_sach()
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', now())",
            CLINIC,
            bn,
        )
    assert await co_trong_danh_sach()


async def test_man_dat_lich_nap_kem_khach_cu_theo_ma(
    kb: KichBan, tmp_path: Path
) -> None:
    """Màn Đặt lịch chỉ nạp 200 khách: hồ sơ cũ chưa hoạt động không chiếm chỗ,
    nhưng "Đặt lịch" từ Quản lý khách hàng (`?bn=<mã>`) phải chọn sẵn được."""
    from clinicai.services.man_dat_lich_doc import hub_dat_lich

    key = f"hc:{uuid.uuid4()}"
    ma = f"KHACH-T{random.randint(1, 10**6)}"
    goi = _goi(
        tmp_path / "goi",
        nguoi=[
            {"nguoi_key": key, "ten": "Vũ Thị Đặt Lịch Thử", "sdt": _sdt(), "ma": ma}
        ],
        luot=[],
    )
    await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    khong = await hub_dat_lich(kb.pool, identity=kb.le_tan)
    assert ma not in {p["patient_code"] for p in khong["patients"]}
    co = await hub_dat_lich(kb.pool, identity=kb.le_tan, bn=ma)
    assert co["patients"][0]["patient_code"] == ma


async def test_chuyen_luot_cu_thanh_luot_that(kb: KichBan, tmp_path: Path) -> None:
    """06/10: lượt cũ thành LƯỢT THẬT đã khám xong — đủ phiếu, chỉ định có kết
    quả, đơn thuốc — không rò thành việc; ngày đã có lượt thật thì không nhân đôi;
    chuyển lại không sinh trùng."""
    from clinicai.services.chuyen_luot_that import chuyen

    sdt = _sdt()
    async with kb.pool.acquire() as conn:
        a = await _khach_he_thong(conn, kb.location_id, "Trần Thị Chuyển Lượt", sdt)
        # Lượt thật trên hệ thống ngày 2026-05-02 (nhập song song cả hai nơi).
        await conn.execute(
            "INSERT INTO visit (clinic_id, clinic_patient_id, location_id, status,"
            " created_at) VALUES ($1::uuid, $2::uuid, $3::uuid, 'FINALIZED',"
            " '2026-05-02 09:00+07')",
            CLINIC,
            a,
            kb.location_id,
        )
    key = f"hc:{uuid.uuid4()}"
    goi = _goi(
        tmp_path / "goi",
        nguoi=[{"nguoi_key": key, "ten": "Trần Thị Chuyển Lượt", "sdt": sdt}],
        luot=[
            _luot(key, "2026-04-01", lan=1),
            _luot(key, "2026-04-20", lan=2),
            _luot(key, "2026-05-02", lan=3),
        ],
    )
    await nap(kb.pool, goi, that=True, clinic_id=CLINIC)

    thu = await chuyen(kb.pool, that=False)
    assert thu["thu_kho"] is True
    await chuyen(kb.pool, that=True)
    await chuyen(kb.pool, that=True)  # chạy lại: không nhân đôi

    async with kb.pool.acquire() as conn:
        luot = await conn.fetch(
            "SELECT a.status AS hen, v.status AS luot, v.closed_at IS NOT NULL AS dong,"
            " (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::time AS gio,"
            " (SELECT du_lieu->'pk_dx'->>'gia_tri' FROM phieu_kham_luot p"
            "   WHERE p.visit_id = v.visit_id) AS chan_doan,"
            " (SELECT count(*) FROM phieu_kham_lich_su h JOIN phieu_kham_luot p"
            "   ON p.id = h.phieu_id WHERE p.visit_id = v.visit_id) AS lich_su_sua"
            " FROM lich_su_notion.luot_that t JOIN visit v ON v.visit_id = t.visit_id"
            " JOIN appointment a ON a.id = t.appointment_id"
            " WHERE v.clinic_patient_id = $1::uuid ORDER BY a.slot_start",
            a,
        )
        assert [(r["hen"], r["luot"], r["dong"], str(r["gio"])) for r in luot] == [
            ("COMPLETED", "FINALIZED", True, "00:00:00")
        ] * 2, "2 lượt cũ khác ngày; ngày 02/05 đã có lượt thật thì không tạo thêm"
        assert [r["chan_doan"] for r in luot] == ["Chẩn đoán lần 1", "Chẩn đoán lần 2"]
        assert all(r["lich_su_sua"] == 0 for r in luot)
        cd = await conn.fetch(
            "SELECT s.exec_status, s.execution_status, s.selection_status,"
            " f.trang_thai, f.du_lieu->>'ket_luan' AS ket_luan"
            " FROM service_order s JOIN visit v ON v.visit_id = s.visit_id"
            " LEFT JOIN form_instance f ON f.service_order_id = s.id"
            " WHERE v.clinic_patient_id = $1::uuid AND s.service_code = 'HO_SO_CU'",
            a,
        )
        assert [tuple(r) for r in cd] == [
            ("performed", "COMPLETED", None, "READY", "Chưa thấy bất thường")
        ] * 2
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM lich_su_notion.luot_that t"
                " JOIN lich_su_notion.luot_kham l ON l.notion_id = t.notion_id"
                " WHERE l.clinic_patient_id = $1::uuid AND t.trung_luot_co_san",
                a,
            )
            == 1
        )

    # Khối hồ sơ cũ chỉ còn lượt trùng ngày; hai lượt kia đã vào lịch sử lượt khám.
    ls = await lich_su(kb.pool, identity=kb.bac_si, clinic_patient_id=a)
    assert [x["ngay_kham"] for x in ls["luot"]] == ["2026-05-02"]
    assert ls["so_luot_da_chuyen"] == 2


async def test_bo_sung_noi_dung_va_lien_ket_cho_luot_da_chuyen(
    kb: KichBan, tmp_path: Path
) -> None:
    """06/10: thân tờ kết quả tải bù SAU lần chuyển và link xem kết quả (trang
    xem phim, trang trả KQ lab — không phải tệp) phải vào lượt thật đã chuyển;
    chạy lại không lặp link; không ghi đè chữ đã có."""
    from clinicai.services.chuyen_luot_that import chuyen

    sdt = _sdt()
    async with kb.pool.acquire() as conn:
        await _khach_he_thong(conn, kb.location_id, "Lê Thị Bổ Sung", sdt)
    key = f"hc:{uuid.uuid4()}"
    lk = _luot(key, "2026-03-03", lan=1)
    goi = _goi(
        tmp_path / "goi",
        nguoi=[{"nguoi_key": key, "ten": "Lê Thị Bổ Sung", "sdt": sdt}],
        luot=[lk],
    )
    # Tờ kết quả CHƯA có thân (tải sau) + một xét nghiệm chỉ có link xem.
    kq = json.loads((goi / "ket_qua.jsonl").read_text().splitlines()[0])
    kq.update(mo_ta=None, ket_luan=None, da_co_noi_dung=False)
    _ghi(goi, "ket_qua", [kq])
    xn_id = str(uuid.uuid4())
    link = "https://viewer.example.vn/viewer?session=abc-123"
    _ghi(
        goi,
        "xet_nghiem",
        [
            {
                "notion_id": xn_id,
                "nguoi_key": key,
                "luot_kham_id": lk["notion_id"],
                "ma": "XN-T",
                "ngay": "2026-03-03",
                "noi_lam": ["Lab thử"],
                "ket_qua": "HPV (-)",
                "tep": [{"ten": link, "khoa": None}],
            }
        ],
    )
    await nap(kb.pool, goi, that=True, clinic_id=CLINIC)
    await chuyen(kb.pool, that=True)

    q_xn = (
        "SELECT f.du_lieu->>'noi_dung' FROM lich_su_notion.ban_ghi_that b"
        " JOIN form_instance f ON f.service_order_id = b.ban_ghi_id"
        " WHERE b.notion_id = $1::uuid"
    )
    q_kq = (
        "SELECT f.du_lieu->>'ket_luan' FROM lich_su_notion.ban_ghi_that b"
        " JOIN form_instance f ON f.service_order_id = b.ban_ghi_id"
        " WHERE b.notion_id = $1::uuid"
    )
    async with kb.pool.acquire() as conn:
        noi_dung = await conn.fetchval(q_xn, xn_id)
        assert noi_dung.startswith("HPV (-)") and link in noi_dung
        assert await conn.fetchval(q_kq, kq["notion_id"]) is None, "chưa có thân"
        # Thân tờ kết quả tải bù rồi nạp lại gói.
        await conn.execute(
            "UPDATE lich_su_notion.ket_qua SET mo_ta = 'Tử cung bình thường',"
            " ket_luan = 'Không thấy bất thường' WHERE notion_id = $1::uuid",
            kq["notion_id"],
        )
    await chuyen(kb.pool, that=True)
    await chuyen(kb.pool, that=True)
    async with kb.pool.acquire() as conn:
        assert await conn.fetchval(q_kq, kq["notion_id"]) == "Không thấy bất thường"
        noi_dung = await conn.fetchval(q_xn, xn_id)
        assert noi_dung.count(link) == 1, "chạy lại không lặp link"
