"""Che dữ liệu khách cho staging online (01/10/2026).

scripts/staging-che-du-lieu.sql chạy trong giao dịch nạp bản sao lưu prod vào
staging (scripts/staging-nap-ban-sao.sh). Bài kiểm ở đây:

* Tĩnh: chốt chặn chạy nhầm (không có cờ phiên thì dừng), không BEGIN/COMMIT
  riêng, script nạp đặt cờ + chạy một giao dịch.
* Trên Postgres thật (mark db, trong giao dịch rồi ROLLBACK):
    - tên / SĐT / CCCD / địa chỉ / ngày sinh / người nhà / kênh liên lạc → giả,
      ghi chú tự do → "(đã che)", tên khách trong văn bản → tên giả;
    - JSON (event_log có trigger CHỈ-THÊM, ảnh chụp dòng đã xoá) che được mà
      trigger chặn không làm hỏng; trigger bật lại ĐÚNG trạng thái cũ;
    - chạy hai lần ra cùng kết quả (ổn định qua các đêm);
    - mọi cột định danh khách trong lược đồ đã được xếp loại trong _che_cot.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

REPO = Path(__file__).resolve().parents[2]
CHE_SQL = REPO / "scripts" / "staging-che-du-lieu.sql"
NAP_SH = REPO / "scripts" / "staging-nap-ban-sao.sh"

TEN_THAT = "Nguyễn Thị Thử Nghiệm"
TEN_NGUOI_NHA = "Trần Văn Người Nhà"
TEN_DA_XOA = "Lê Thị Đã Xoá"
SDT_THAT = "0987654321"
SDT_PHU = "0912345678"
CCCD_THAT = "001190012345"


def _cot_trong_sql() -> dict[tuple[str, str], str]:
    return {
        (b, c): cach
        for b, c, cach in re.findall(
            r"\('([a-z_0-9]+)', '([a-z_0-9]+)', '(rieng|xoa|chu|json|json_manh|giu)'\)",
            CHE_SQL.read_text(encoding="utf-8"),
        )
    }


# ── Tĩnh ─────────────────────────────────────────────────────────────────────
class TestChotChanTinh:
    def test_sql_dung_khi_thieu_co_phien(self) -> None:
        sql = CHE_SQL.read_text(encoding="utf-8")
        assert "current_setting('clinicai.che_cho_phep', true)" in sql
        assert "RAISE EXCEPTION" in sql

    def test_sql_khong_tu_mo_dong_giao_dich(self) -> None:
        dong = [
            ln.strip().upper()
            for ln in CHE_SQL.read_text(encoding="utf-8").splitlines()
            if not ln.strip().startswith("--")
        ]
        assert not any(ln.startswith(("BEGIN;", "COMMIT", "ROLLBACK")) for ln in dong)

    def test_script_nap_dat_co_va_chay_mot_giao_dich(self) -> None:
        sh = NAP_SH.read_text(encoding="utf-8")
        assert "SET LOCAL clinicai.che_cho_phep = 'staging';" in sh
        assert "--single-transaction" in sh
        # Che nằm TRONG khối nạp (trước khi commit), không phải một lệnh sau.
        assert sh.index('cat "$CHE_SQL"') < sh.index("--single-transaction")

    def test_danh_sach_cot_co_patient_va_khong_trung(self) -> None:
        cot = _cot_trong_sql()
        for c in (
            "full_name",
            "phone_primary",
            "national_id_number",
            "date_of_birth",
            "address",
        ):
            assert cot.get(("patient", c)) == "rieng"
        assert cot.get(("staff", "full_name")) == "giu"


# ── Trên Postgres thật ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def conn(test_db_url: str) -> AsyncIterator[asyncpg.Connection]:
    c = await asyncpg.connect(
        test_db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    tx = c.transaction()
    await tx.start()
    try:
        yield c
    finally:
        await tx.rollback()
        await c.close()


async def _gieo(c: asyncpg.Connection) -> dict[str, str]:
    clinic = await c.fetchval(
        "INSERT INTO clinic (code, name) VALUES ($1, 'PK thử che') RETURNING id::text",
        f"CHE{uuid.uuid4().hex[:8]}",
    )
    loc = await c.fetchval(
        """INSERT INTO clinic_location (code, name, clinic_id)
           VALUES ($1, 'Cơ sở thử', $2) RETURNING id::text""",
        f"L{uuid.uuid4().hex[:8]}",
        clinic,
    )
    staff = await c.fetchval(
        """INSERT INTO staff (primary_location_id, full_name, primary_department)
           VALUES ($1, 'Nhân Sự Giữ Nguyên', 'CSKH') RETURNING id::text""",
        loc,
    )
    bn = await c.fetchval(
        """INSERT INTO patient (patient_code, full_name, location_id, clinic_id,
               phone_primary, phone_secondary, national_id_number, date_of_birth,
               address, address_detail, guardian_name, patient_objection,
               van_de_di_kham)
           VALUES ($1, $2, $3, $4, $5, $6, $7, DATE '1990-05-17',
               '12 Phố Thật, Hà Nội', '12 Phố Thật', $8, 'Không muốn gọi điện', $9)
           RETURNING clinic_patient_id::text""",
        f"BN-CHE-{uuid.uuid4().hex[:6]}",
        TEN_THAT,
        loc,
        clinic,
        SDT_THAT,
        SDT_PHU,
        CCCD_THAT,
        TEN_NGUOI_NHA,
        f"Đau bụng, chị {TEN_THAT} dặn gọi {SDT_THAT}",
    )
    await c.execute(
        """INSERT INTO patient_next_of_kin (clinic_id, clinic_patient_id, full_name,
               phone, relation, zalo_id, notes)
           VALUES ($1, $2, $3, '0911111111', 'Chồng', 'zalo.that', 'Ghi chú riêng')""",
        clinic,
        bn,
        TEN_NGUOI_NHA,
    )
    await c.execute(
        """INSERT INTO patient_contact_channel (clinic_id, clinic_patient_id,
               channel_type, channel_value)
           VALUES ($1, $2, 'EMAIL', 'that@gmail.com'),
                  ($1, $2, 'ZALO', '0987654321')""",
        clinic,
        bn,
    )
    await c.execute(
        """INSERT INTO patient_sdt_them (clinic_id, clinic_patient_id, so_dien_thoai)
           VALUES ($1, $2, '0933333333')""",
        clinic,
        bn,
    )
    await c.execute(
        """INSERT INTO ghi_chu_khach (clinic_id, clinic_patient_id, noi_dung,
               tao_boi_staff_id)
           VALUES ($1, $2, 'Khách khó tính, nhà ở ngõ 5', $3)""",
        clinic,
        bn,
        staff,
    )
    await c.execute(
        """INSERT INTO thong_bao (clinic_id, vai_nhan, tieu_de, noi_dung, nguon,
               nguoi_goi_staff_id)
           VALUES ($1, 'CSKH', $2, $3, 'test', $4)""",
        clinic,
        f"Khách {TEN_THAT} đã tới",
        f"Gọi lại {TEN_DA_XOA} số +84987654321",
        staff,
    )
    # event_log có trigger CHỈ-THÊM chặn UPDATE.
    await c.execute(
        """INSERT INTO event_log (event_type, aggregate_type, aggregate_id, payload,
               source, clinic_id)
           VALUES ('patient.created', 'patient', $1::uuid, $2::jsonb, 'test', $3)""",
        bn,
        json.dumps(
            {
                "full_name": TEN_THAT,
                "phone_primary": SDT_THAT,
                "date_of_birth": "1990-05-17",
                "ghi_chu": f"gặp {TEN_THAT}",
                "dich_vu": "Siêu âm",
            },
            ensure_ascii=False,
        ),
        clinic,
    )
    lan = await c.fetchval(
        """INSERT INTO lan_don_du_lieu_thu (clinic_id, nguon, khach)
           VALUES ($1, 'script_moc', $2::jsonb) RETURNING id::text""",
        clinic,
        json.dumps([{"ten": TEN_DA_XOA}], ensure_ascii=False),
    )
    await c.execute(
        """INSERT INTO du_lieu_da_xoa (lan_id, bang, du_lieu)
           VALUES ($1, 'patient', $2::jsonb)""",
        lan,
        json.dumps(
            {
                "full_name": TEN_DA_XOA,
                "phone_primary": "0977777777",
                "address": "Nhà thật",
                "patient_objection": "x",
            },
            ensure_ascii=False,
        ),
    )
    return {"clinic": clinic, "bn": bn, "staff": staff, "lan": lan}


async def _che(c: asyncpg.Connection) -> None:
    await c.execute("SET LOCAL clinicai.che_cho_phep = 'staging'")
    await c.execute(CHE_SQL.read_text(encoding="utf-8"))


async def _anh_trigger(c: asyncpg.Connection) -> list[tuple[str, str, str]]:
    rows = await c.fetch(
        "SELECT c.relname, t.tgname, t.tgenabled::text FROM pg_trigger t"
        " JOIN pg_class c ON c.oid = t.tgrelid WHERE NOT t.tgisinternal"
        " AND c.relnamespace = 'public'::regnamespace ORDER BY 1, 2"
    )
    return [(r[0], r[1], r[2]) for r in rows]


@pytest.mark.db
@pytest.mark.asyncio
async def test_thieu_co_phien_thi_tu_choi(conn: asyncpg.Connection) -> None:
    with pytest.raises(asyncpg.RaiseError, match="chỉ chạy trong staging-nap-ban-sao"):
        await conn.execute(CHE_SQL.read_text(encoding="utf-8"))


@pytest.mark.db
@pytest.mark.asyncio
async def test_che_sach_dinh_danh_khach(conn: asyncpg.Connection) -> None:
    ids = await _gieo(conn)
    trigger_truoc = await _anh_trigger(conn)
    await _che(conn)

    p = await conn.fetchrow(
        "SELECT * FROM patient WHERE clinic_patient_id = $1::uuid", ids["bn"]
    )
    assert re.fullmatch(r"Khách \d{4,}", p["full_name"])
    assert re.fullmatch(r"09\d{8}", p["phone_primary"])
    assert re.fullmatch(r"08\d{8}", p["phone_secondary"])
    assert p["national_id_number"] != CCCD_THAT and len(p["national_id_number"]) == 12
    lech = (p["date_of_birth"] - date(1990, 5, 17)).days
    assert -14 <= lech <= 14
    assert "Phố Thật" not in p["address"] and "Phố Thật" not in p["address_detail"]
    assert p["guardian_name"].startswith("Người nhà khách ")
    assert p["patient_objection"] == "(đã che)"
    assert TEN_THAT not in p["van_de_di_kham"] and SDT_THAT not in p["van_de_di_kham"]
    assert "Đau bụng" in p["van_de_di_kham"]  # nội dung khám giữ lại
    assert SDT_THAT not in (p["sdt_tim_kiem"] or "")  # trigger tính lại từ số giả
    assert "khach" in p["full_name_unaccent"]

    k = await conn.fetchrow(
        "SELECT * FROM patient_next_of_kin WHERE clinic_patient_id = $1::uuid",
        ids["bn"],
    )
    assert k["full_name"].startswith("Người nhà khách ") and k["zalo_id"] is None
    assert k["phone"] != "0911111111" and k["notes"] == "(đã che)"

    kenh = {
        r["channel_type"]: r["channel_value"]
        for r in await conn.fetch(
            "SELECT channel_type, channel_value FROM patient_contact_channel"
            " WHERE clinic_patient_id = $1::uuid",
            ids["bn"],
        )
    }
    assert kenh["EMAIL"].endswith("@vi-du.invalid") and kenh["ZALO"] != SDT_THAT
    sdt_them = await conn.fetchval(
        "SELECT so_dien_thoai FROM patient_sdt_them WHERE clinic_patient_id = $1::uuid",
        ids["bn"],
    )
    assert sdt_them != "0933333333" and re.fullmatch(r"07\d{8}", sdt_them)

    assert (
        await conn.fetchval(
            "SELECT noi_dung FROM ghi_chu_khach WHERE clinic_patient_id = $1::uuid",
            ids["bn"],
        )
        == "(đã che)"
    )
    tb = await conn.fetchrow(
        "SELECT tieu_de, noi_dung FROM thong_bao WHERE nguoi_goi_staff_id = $1::uuid",
        ids["staff"],
    )
    assert TEN_THAT not in tb["tieu_de"] and p["full_name"] in tb["tieu_de"]
    assert TEN_DA_XOA not in tb["noi_dung"] and "+84987654321" not in tb["noi_dung"]

    ev = await conn.fetchval(
        "SELECT payload::text FROM event_log WHERE aggregate_id = $1::uuid", ids["bn"]
    )
    assert TEN_THAT not in ev and SDT_THAT not in ev and "1990-05-17" not in ev
    assert "Siêu âm" in ev  # dữ liệu không định danh giữ lại

    xoa = await conn.fetchval(
        "SELECT du_lieu::text FROM du_lieu_da_xoa WHERE lan_id = $1::uuid", ids["lan"]
    )
    assert TEN_DA_XOA not in xoa and "0977777777" not in xoa and "Nhà thật" not in xoa
    lan = await conn.fetchval(
        "SELECT khach::text FROM lan_don_du_lieu_thu WHERE id = $1::uuid", ids["lan"]
    )
    assert TEN_DA_XOA not in lan

    # Nhân sự giữ nguyên; trigger bật lại đúng trạng thái cũ.
    assert (
        await conn.fetchval(
            "SELECT full_name FROM staff WHERE id = $1::uuid", ids["staff"]
        )
        == "Nhân Sự Giữ Nguyên"
    )
    assert await _anh_trigger(conn) == trigger_truoc


@pytest.mark.db
@pytest.mark.asyncio
async def test_chay_hai_lan_ra_cung_ket_qua(conn: asyncpg.Connection) -> None:
    ids = await _gieo(conn)
    await _che(conn)
    lan1 = await conn.fetchrow(
        """SELECT full_name, phone_primary, date_of_birth, national_id_number
           FROM patient WHERE clinic_patient_id = $1::uuid""",
        ids["bn"],
    )
    await _che(conn)
    lan2 = await conn.fetchrow(
        """SELECT full_name, phone_primary, date_of_birth, national_id_number
           FROM patient WHERE clinic_patient_id = $1::uuid""",
        ids["bn"],
    )
    # Ngày sinh lệch theo mã khách nên lần hai lệch THÊM — chỉ năm/tên/SĐT/CCCD
    # phải giữ nguyên (đêm nào cũng nạp từ bản prod GỐC, không che chồng).
    assert lan1["full_name"] == lan2["full_name"]
    assert lan1["phone_primary"] == lan2["phone_primary"]
    assert lan1["national_id_number"] == lan2["national_id_number"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_moi_cot_dinh_danh_khach_da_duoc_xep_loai(
    conn: asyncpg.Connection,
) -> None:
    """Migration mới thêm cột tên/SĐT/email/địa chỉ/CCCD/ngày sinh mà quên che →
    đỏ ở đây, trước khi bản sao prod đưa dữ liệu thật lên staging."""
    mau = (
        r"(^|_)(full_name|ho_ten|phone|sdt|so_dien_thoai|email|address|dia_chi"
        r"|national_id|cccd|cmnd|date_of_birth|ngay_sinh|guardian|zalo|patient_info"
        r"|channel_value|nguoi_gioi_thieu|nguoi_nha)"
    )
    rows = await conn.fetch(
        "SELECT c.table_name, c.column_name FROM information_schema.columns c"
        " JOIN pg_class k ON k.relname = c.table_name"
        "  AND k.relnamespace = 'public'::regnamespace AND k.relkind = 'r'"
        " WHERE c.table_schema = 'public'"
        "  AND c.data_type IN ('text', 'character varying', 'date')"
        "  AND c.column_name ~ $1",
        mau,
    )
    da_xep = _cot_trong_sql()
    thieu = sorted(f"{r[0]}.{r[1]}" for r in rows if (r[0], r[1]) not in da_xep)
    assert not thieu, (
        "Cột định danh chưa được xếp loại trong scripts/staging-che-du-lieu.sql "
        f"(_che_cot — che hay 'giu'): {thieu}"
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_nhieu_khach_van_che_duoc(conn: asyncpg.Connection) -> None:
    """08/10/2026: hồ sơ cũ Notion làm số khách tăng vọt, bản lọc gộp MỌI tên
    vào một regex báo "regular expression is too complex" → nạp staging hỏng mỗi
    đêm. 5.000 khách phải che được, và tên trong văn bản vẫn bị thay."""
    ids = await _gieo(conn)
    clinic, loc = await conn.fetchrow(
        "SELECT clinic_id::text, location_id::text FROM patient"
        " WHERE clinic_patient_id = $1::uuid",
        ids["bn"],
    )
    await conn.execute(
        """INSERT INTO patient (patient_code, full_name, location_id, clinic_id)
           SELECT 'NHIEU-' || g || '-' || $3, 'Trần Thị Nhiều Khách ' || g,
                  $1::uuid, $2::uuid
             FROM generate_series(1, 5000) g""",
        loc,
        clinic,
        uuid.uuid4().hex[:6],
    )
    await _che(conn)
    con = await conn.fetchval(
        "SELECT count(*) FROM patient WHERE full_name LIKE 'Trần Thị Nhiều Khách %'"
    )
    assert con == 0
