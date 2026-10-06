"""Ô tìm khách màn Đặt lịch tìm trên TOÀN BỘ hồ sơ (06/10/2026).

Sáng 06/10 nạp ~8.600 khách cũ từ Notion. Màn Đặt lịch chỉ nạp 200 khách mới
tạo gần nhất rồi lọc trên trình duyệt → lễ tân gõ tên / số khách cũ không ra,
dễ tạo hồ sơ trùng. Canh ở đây:
  * hồ sơ ``nguon_nhap='notion'`` chưa hoạt động TÌM RA được (tên không dấu,
    mã, một phần SĐT có dấu cách / chấm / gạch);
  * khớp ĐÚNG mã / ĐÚNG số lên trước, rồi khách có lượt gần nhất;
  * tối đa ``TRAN_TIM`` kết quả; hồ sơ đã ẩn (``is_active`` false) không ra;
  * ô tìm rác (rỗng, 1 ký tự, quá dài, NUL, toàn ký tự ILIKE) → rỗng, không ném.

DB test dùng chung: mỗi test dùng một "đuôi" chữ ngẫu nhiên trong tên để chỉ
khớp đúng hồ sơ của nó.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.services.man_dat_lich_doc import (
    TIM_TOI_DA,
    TRAN_TIM,
    doc_o_tim,
    hub_dat_lich,
    tim_khach,
)
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung


def _duoi() -> str:
    """Một "từ" chữ cái ngẫu nhiên — tên chỉ khớp đúng hồ sơ của test này."""
    return "".join(random.choice("bcdghklmnpqrstvx") for _ in range(9))


def _sdt() -> str:
    return "09" + "".join(random.choice("0123456789") for _ in range(8))


async def _khach(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    ten: str,
    *,
    ma: str | None = None,
    sdt: str | None = None,
    notion: bool = False,
    hien: bool = True,
) -> str:
    return str(
        await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary, nguon_nhap, is_active)"
            " VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, $7)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            ma or f"DLTK-{uuid.uuid4().hex[:8]}",
            ten,
            ca.loc,
            sdt,
            "notion" if notion else None,
            hien,
        )
    )


async def _luot_da_xong(pool: asyncpg.Pool, ca: Ca, pid: str, ngay_truoc: int) -> None:  # noqa: F811
    bd = datetime.now(UTC) - timedelta(days=ngay_truoc)
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, 'COMPLETED')",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        bd,
        bd + timedelta(minutes=15),
    )


def _ma(out: dict) -> list[str]:
    return [p["clinic_patient_id"] for p in out["patients"]]


# ── Hàm thuần: ô tìm rác ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rac",
    [
        None,
        "",
        "   ",
        "a",
        " a ",
        "%%%",
        "_",
        "%_",
        "\\\\",
        "((,))",
        "\x00",
        "\x00\x00\x00",
        "a\x00",
        "x" * (TIM_TOI_DA + 1),
        "0912345678" * 20,
    ],
)
def test_o_tim_rac_thanh_none(rac: object) -> None:
    assert doc_o_tim(rac) is None


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("  Nguyễn   Thị  ", "Nguyễn Thị"),
        ("ng", "ng"),
        ("0912.345-678", "0912.345-678"),
        ("an\x00h", "an h"),
        ("50%_off", "50 off"),
        (12345, "12345"),
    ],
)
def test_o_tim_hop_le_duoc_lam_sach(vao: object, ra: str) -> None:
    assert doc_o_tim(vao) == ra


# ── Truy vấn thật ──────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_khach_cu_notion_tim_ra_bang_ten_khong_dau_ma_va_mot_phan_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    d = _duoi()
    sdt = _sdt()
    ma = f"KHACH-T{random.randint(10**6, 10**7)}"
    pid = await _khach(
        pool, ca, f"Đặng Thị Ánh {d.capitalize()}", ma=ma, sdt=sdt, notion=True
    )
    # Màn cũ: 200 khách nạp sẵn KHÔNG có hồ sơ Notion chưa hoạt động.
    hub = await hub_dat_lich(pool, identity=ca.le_tan)
    assert pid not in _ma(hub)

    for q in (
        f"dang thi anh {d}",  # không dấu
        f"Đặng Thị Ánh {d}",  # có dấu
        ma.lower(),  # mã, khác hoa thường
        f"{sdt[:4]} {sdt[4:7]}",  # một phần số, có dấu cách
        f"{sdt[:4]}.{sdt[4:7]}-{sdt[7:]}",  # đủ số, chấm + gạch
    ):
        out = await tim_khach(pool, identity=ca.le_tan, q=q)
        assert pid in _ma(out), q
        p = next(p for p in out["patients"] if p["clinic_patient_id"] == pid)
        # Đủ trường form đặt lịch đang dùng.
        assert p["patient_code"] == ma
        assert p["phone_primary"] == sdt
        assert p["location_id"] == ca.loc
        for k in ("full_name", "sdt_tim_kiem", "date_of_birth", "gender", "address"):
            assert k in p


@pytest.mark.db
@pytest.mark.asyncio
async def test_khop_dung_ma_hoac_so_len_truoc_roi_luot_gan_nhat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    d = _duoi()
    # Ba khách cùng tên: chưa khám (mới tạo nhất) · khám 10 ngày trước · 2 ngày.
    chua = await _khach(pool, ca, f"Lê Thị {d}")
    xa = await _khach(pool, ca, f"Lê Thị {d}")
    gan = await _khach(pool, ca, f"Lê Thị {d}")
    await _luot_da_xong(pool, ca, xa, 10)
    await _luot_da_xong(pool, ca, gan, 2)
    out = await tim_khach(pool, identity=ca.le_tan, q=f"le thi {d}")
    assert _ma(out) == [gan, xa, chua]
    # Nhãn "khám lần mấy" đi kèm (cùng luật với hub).
    assert out["lan_kham"][gan]["soLanKham"] == 1
    assert chua not in out["lan_kham"]

    # Gõ ĐÚNG mã: người ấy lên đầu dù người kia (mã dài hơn, cùng tiền tố) vừa khám.
    goc = f"DLTK{random.randint(10**5, 10**6)}"
    dung_ma = await _khach(pool, ca, f"Hồ Thị {d}", ma=goc)
    dai_hon = await _khach(pool, ca, f"Hồ Thị {d}", ma=f"{goc}9")
    await _luot_da_xong(pool, ca, dai_hon, 1)
    out = await tim_khach(pool, identity=ca.le_tan, q=goc)
    assert _ma(out)[:2] == [dung_ma, dai_hon]

    # Gõ ĐÚNG số: người có số ấy lên đầu, dù người kia (số người nhà CHỨA cả
    # chuỗi ấy — một số dài hơn) vừa khám.
    sdt = _sdt()
    dung_so = await _khach(pool, ca, f"Vũ Thị {d}", sdt=sdt)
    so_khac = await _khach(pool, ca, f"Vũ Thị {d}", sdt=_sdt())
    await pool.execute(
        "UPDATE patient SET phone_secondary = $2 WHERE clinic_patient_id = $1::uuid",
        so_khac,
        "8" + sdt,
    )
    await _luot_da_xong(pool, ca, so_khac, 1)
    out = await tim_khach(pool, identity=ca.le_tan, q=f"{sdt[:4]} {sdt[4:]}")
    assert _ma(out)[:2] == [dung_so, so_khac]
    # Một PHẦN số: không ai khớp đúng → người vừa khám lên trước.
    out = await tim_khach(pool, identity=ca.le_tan, q=sdt[1:])
    assert _ma(out)[:2] == [so_khac, dung_so]


@pytest.mark.db
@pytest.mark.asyncio
async def test_toi_da_hai_muoi_va_bo_ho_so_da_an(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    d = _duoi()
    for _ in range(TRAN_TIM + 5):
        await _khach(pool, ca, f"Trần Thị {d}", notion=True)
    an = await _khach(pool, ca, f"Trần Văn Ẩn {d}", notion=True, hien=False)
    out = await tim_khach(pool, identity=ca.le_tan, q=d)
    assert len(out["patients"]) == TRAN_TIM
    out = await tim_khach(pool, identity=ca.le_tan, q=f"tran van an {d}")
    assert an not in _ma(out)


@pytest.mark.db
@pytest.mark.asyncio
async def test_o_tim_rac_tra_rong_khong_nem(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    for rac in (None, "", "a", "%%%", "_%", "\x00\x00", "x" * 500, "((,))"):
        out = await tim_khach(pool, identity=ca.le_tan, q=rac)
        assert out == {"patients": [], "lan_kham": {}}, repr(rac)
    # Lạ nhưng hợp lệ: không ném, trả danh sách (thường rỗng).
    for la in ("'; DROP TABLE patient; --", "😀😀", "ñ​́", "��"):
        out = await tim_khach(pool, identity=ca.le_tan, q=la)
        assert isinstance(out["patients"], list)
