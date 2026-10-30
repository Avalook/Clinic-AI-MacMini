"""Phiếu in "Tóm tắt bệnh án — 3 lần khám gần nhất" (Tuyền duyệt demo 30/10/2026).

Chọn đúng lượt (khám đã hoàn tất, bỏ bán lẻ / mua thuốc / lượt còn mở), thứ tự
cũ → mới, bỏ chọn lượt, ô trống khi không đo, ngưỡng + xu hướng ở máy chủ.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import pytest

from clinicai.api.v1.routers.ho_so_kham import tom_tat_kham_doc
from clinicai.services.tom_tat_kham import (
    chon_luot,
    doc_bo,
    doc_so_lan,
    hang_cua_node,
    la_luot_kham,
    noi_dung_phieu,
    sinh_hieu_luot,
    so_vn,
    tom_tat_chi_dinh,
    xu_huong_can_nang,
    xu_huong_huyet_ap,
)
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_doi_dich_vu_kham_db import _dung

# ── Hàm thuần ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rac", [None, "", "abc", "0", "4", "-1", "2.5", "99"])
def test_so_lan_rac_ve_3(rac: Any) -> None:
    assert doc_so_lan(rac) == 3


def test_so_lan_hop_le() -> None:
    assert [doc_so_lan(x) for x in ("1", "2", "3", 2)] == [1, 2, 3, 2]


def test_bo_chi_giu_uuid() -> None:
    a = str(uuid.uuid4())
    assert doc_bo(f"{a}, rác,,'; DROP") == {a}
    assert doc_bo(None) == set()


def _r(vid: str, **k: Any) -> dict[str, Any]:
    return {"visit_id": vid, "hoan_tat": True, "ban_le": False, "nhom": "KHAM", **k}


def test_la_luot_kham() -> None:
    assert la_luot_kham(_r("a"))
    assert la_luot_kham(_r("a", nhom=None))  # lượt Notion / chưa rõ loại = khám
    assert la_luot_kham(_r("a", nhom="KHAC"))
    assert not la_luot_kham(_r("a", ban_le=True))
    assert not la_luot_kham(_r("a", nhom="THUOC"))
    assert not la_luot_kham(_r("a", nhom="DIEU_TRI"))
    assert not la_luot_kham(_r("a", hoan_tat=False))


def test_chon_luot_cu_truoc_moi_sau_va_bo_chon() -> None:
    moi_truoc = [
        _r("e"),
        _r("ban", ban_le=True),
        _r("d"),
        _r("mo", hoan_tat=False),
        _r("c"),
        _r("b"),
        _r("a"),
    ]

    def ids(xs: list[Any]) -> list[str]:
        return [x["visit_id"] for x in xs]

    assert ids(chon_luot(moi_truoc, so_lan=3, bo=set())) == ["c", "d", "e"]
    assert ids(chon_luot(moi_truoc, so_lan=3, bo={"d"})) == ["b", "c", "e"]
    assert ids(chon_luot(moi_truoc, so_lan=1, bo=set())) == ["e"]
    assert chon_luot([], so_lan=3, bo=set()) == []


def test_so_vn() -> None:
    assert so_vn(36.8) == "36,8"
    assert so_vn("54.0") == "54"
    assert so_vn(None) is None
    assert so_vn("rác") is None


def test_sinh_hieu_luot_nguong_may_chu() -> None:
    assert sinh_hieu_luot(None) == ({}, [])
    o, bt = sinh_hieu_luot(
        {"systolic": 150, "diastolic": 95, "pulse": 130, "temperature": 36.8}
    )
    assert o["huyet_ap"] == "150/95" and o["nhiet"] == "36,8" and o["can_nang"] is None
    assert set(bt) == {"systolic", "diastolic", "pulse"}
    assert sinh_hieu_luot({"systolic": 110, "diastolic": 70})[1] == []


def test_xu_huong() -> None:
    assert xu_huong_huyet_ap([110, 115, 132]) == "↑ tăng dần"
    assert xu_huong_huyet_ap([130, 120]) == "↓ giảm"
    assert xu_huong_huyet_ap([110, 130, 120]) is None
    assert xu_huong_huyet_ap([110]) is None
    assert (
        xu_huong_can_nang([(date(2026, 8, 28), 54), (date(2026, 10, 27), 59)])
        == "+5 kg / 2 tháng"
    )
    assert (
        xu_huong_can_nang([(date(2026, 10, 1), 60), (date(2026, 10, 15), 58.5)])
        == "−1,5 kg / 2 tuần"
    )
    assert xu_huong_can_nang([(date(2026, 10, 1), 60)]) is None


def test_noi_dung_phieu_xep_dung_hang() -> None:
    khung = [
        {
            "ma": "B",
            "block": [
                {"ma": "x_reason", "ten": "Lý do khám bệnh", "kieu": "doan_van"},
                {
                    "ma": "x_hist",
                    "ten": "Bản thân",
                    "kieu": "doan_van",
                    "nhom": "Tiền sử bệnh",
                },
                {
                    "ma": "x_lmp",
                    "ten": "Kinh lần cuối",
                    "kieu": "text",
                    "nhom": "Tiền sử",
                },
                {"ma": "x_para", "ten": "PARA", "kieu": "text", "nhom": "Tiền sử"},
                {"ma": "x_allergy", "ten": "Chi tiết dị ứng", "kieu": "doan_van"},
                {
                    "ma": "x_sa",
                    "ten": "Siêu âm",
                    "kieu": "doan_van",
                    "nhom": "Cận lâm sàng",
                },
                {"ma": "x_ctm", "ten": "CTM", "kieu": "text", "nhom": "Cận lâm sàng"},
            ],
        },
        {
            "ma": "D",
            "block": [
                {"ma": "x_dx", "ten": "Chẩn đoán", "kieu": "doan_van"},
                {"ma": "x_tx", "ten": "Điều trị / xử lý", "kieu": "doan_van"},
            ],
        },
        {
            "ma": "G",
            "block": [{"ma": "x_ngay", "ten": "Ngày tái khám", "kieu": "ngay"}],
        },
    ]

    def g(v: str) -> dict[str, str]:
        return {"gia_tri": v}

    du_lieu = {
        "x_reason": g("Khám thai"),
        "x_hist": g("Mổ đẻ 2022"),
        "x_lmp": g("10/05/2026"),
        "x_para": g("1001"),
        "x_allergy": g("Penicillin"),
        "x_sa": g("1 thai sống"),
        "x_ctm": g("bình thường"),
        "x_dx": g("Thai 24w"),
        "x_tx": g(""),
        "x_ngay": g("2026-11-10"),
    }
    ra = noi_dung_phieu(khung, json.dumps(du_lieu))
    assert ra["ly_do"] == ["Khám thai"]
    assert ra["tien_su"] == ["Bản thân: Mổ đẻ 2022"]  # kinh cuối không phải tiền sử
    assert ra["para"] == "1001" and ra["di_ung"] == "Penicillin"
    assert ra["sieu_am"] == ["1 thai sống"] and ra["xet_nghiem"] == ["CTM: bình thường"]
    assert ra["chan_doan"] == ["Thai 24w"]
    assert ra["xu_ly"] == ["Tái khám 10/11/2026"]  # ô trống không in
    assert noi_dung_phieu("rác", None)["ly_do"] == []


def test_hang_cls_va_tom_tat_chi_dinh() -> None:
    assert hang_cua_node("DICHVU-SIEUAM") == "sieu_am"
    assert hang_cua_node("DICHVU-LAYMAU-MAU") == "xet_nghiem"
    assert hang_cua_node("DICHVU-THUTHUAT") == "thu_thuat"
    assert hang_cua_node(None) == "cls_khac"
    phieu = {
        "loai": "PHIEU",
        "trang_thai": "READY",
        "khung": [
            {
                "block": [
                    {"ma": "tim_thai", "ten": "Tim thai", "don_vi": "chu kỳ/phút"},
                    {"ma": "ket_luan", "ten": "Kết luận"},
                ]
            }
        ],
        "du_lieu": {
            "tim_thai": {"gia_tri": "145"},
            "ket_luan": {"gia_tri": "Ối bình thường"},
        },
    }
    t = tom_tat_chi_dinh({"ten_hien_thi": "SA thai", "ket_qua": [phieu]})
    assert t == {
        "chu": "SA thai: Ối bình thường",
        "tim_thai": "145 chu kỳ/phút",
        "tuoi_thai": None,
    }
    # Nháp không phải kết quả.
    nhap = {**phieu, "trang_thai": "DRAFT"}
    assert tom_tat_chi_dinh({"ten_hien_thi": "SA", "ket_qua": [nhap]})["chu"] == (
        "SA: chưa có kết quả"
    )
    assert tom_tat_chi_dinh({"ten_hien_thi": "SA", "ket_qua": [{"loai": "TEP"}]})[
        "chu"
    ] == ("SA: có ảnh / tệp kết quả")


# ── Trên Postgres thật ──────────────────────────────────────────────────────


async def _luot(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    ngay_lui: int,
    *,
    xong: bool = True,
    ban_le: bool = False,
    dv: str | None = None,
) -> str:
    """Một lượt check-in `ngay_lui` ngày trước; `xong` = phiên khám đã kết thúc."""
    luc = datetime.now(UTC) - timedelta(days=ngay_lui)
    vid = str(
        await pool.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, attending_doctor_id, status, checked_in_at, ban_le)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,"
            " 'IN_PROGRESS', $6, $7) RETURNING visit_id::text",
            CLINIC,
            ca["pid"],
            ca["loc"],
            None if ban_le else (dv or ca["dv"]),
            ca["bs"].staff_id,
            luc,
            ban_le,
        )
    )
    if xong:
        await pool.execute(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
            " doctor_staff_id, started_at, completed_at, outcome)"
            " VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'completed', $3::uuid,"
            " $4, $4, 'NO_SERVICES')",
            CLINIC,
            vid,
            ca["bs"].staff_id,
            luc,
        )
    return vid


async def _do(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    vid: str,
    tren: int,
    duoi: int,
    can: float,
) -> None:
    await pool.execute(
        "INSERT INTO vital_measurement (clinic_id, visit_id, systolic, diastolic,"
        " weight_kg, recorded_by) VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)",
        CLINIC,
        vid,
        tren,
        duoi,
        can,
        ca["bs"].staff_id,
    )


async def _doc(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    pid: str | None = None,
    **k: Any,
) -> dict[str, Any]:
    return await tom_tat_kham_doc(
        clinic_patient_id=UUID(pid or ca["pid"]),
        so_lan=k.get("so_lan"),
        bo=k.get("bo"),
        identity=ca["bs"],
        pool=pool,
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_tom_tat_chon_luot_thu_tu_o_trong_va_xu_huong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    thuoc = str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active, nhom)"
            " VALUES ($1::uuid, $2, 'Mua thuốc', true, 'THUOC') RETURNING id::text",
            CLINIC,
            f"TT-{uuid.uuid4().hex[:8]}",
        )
    )
    v50 = await _luot(pool, ca, 50)
    v40 = await _luot(pool, ca, 40)  # không đo sinh hiệu
    v30 = await _luot(pool, ca, 30)
    v20 = await _luot(pool, ca, 20)
    v10 = await _luot(pool, ca, 10)
    await _luot(pool, ca, 5, ban_le=True)  # chỉ mua thuốc — bỏ
    await _luot(pool, ca, 3, dv=thuoc)  # lượt mua thuốc — bỏ
    await _luot(pool, ca, 1, xong=False)  # còn đang khám — bỏ
    await _do(pool, ca, v30, 110, 70, 54)
    await _do(pool, ca, v20, 120, 75, 56.5)
    await _do(pool, ca, v10, 145, 92, 59)
    await pool.execute(
        "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu)"
        " SELECT $1::uuid, $2::uuid, 'PK', max(version), $3::jsonb"
        " FROM form_definition WHERE clinic_id = $1::uuid AND form_id = 'PK'"
        " AND trang_thai = 'PUBLISHED'",
        CLINIC,
        v10,
        json.dumps(
            {
                "pk_reason": {"nguon": "USER", "gia_tri": "Đau bụng dưới"},
                "pk_dx": {"nguon": "USER", "gia_tri": "Viêm âm đạo"},
                "pk_treatment": {"nguon": "USER", "gia_tri": "Đặt thuốc 7 ngày"},
                "pk_para": {"nguon": "USER", "gia_tri": "1001"},
                "pk_allergy": {"nguon": "USER", "gia_tri": "Penicillin"},
            }
        ),
    )
    await pool.execute(
        "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
        " clinic_patient_id, drug_name_raw, quantity, nguon)"
        " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, 'Sắt', '30 viên',"
        " 'BAC_SI' FROM visit v WHERE v.visit_id = $3::uuid",
        CLINIC,
        f"test-ttk-{uuid.uuid4().hex}",
        v10,
    )

    goi = await _doc(pool, ca)
    assert [x["visit_id"] for x in goi["luot"]] == [v30, v20, v10]
    assert goi["tong_lan_kham"] == 5 and goi["so_lan"] == 3
    assert [x["visit_id"] for x in goi["chon_duoc"]] == [v10, v20, v30, v40, v50]
    moi = goi["luot"][-1]
    assert moi["sinh_hieu"]["huyet_ap"] == "145/92"
    assert set(moi["bat_thuong"]) == {"systolic", "diastolic"}
    assert goi["luot"][0]["bat_thuong"] == []
    assert moi["xu_huong"] == {"huyet_ap": "↑ tăng dần", "can_nang": "+5 kg / 2 tuần"}
    assert moi["ly_do"] == ["Đau bụng dưới"]
    assert moi["chan_doan"] == ["Viêm âm đạo"]
    assert moi["xu_ly"] == ["Đặt thuốc 7 ngày"]
    assert moi["don"] == ["Sắt — 30 viên"]
    assert goi["nen_tang"]["para"] == "1001"
    assert goi["nen_tang"]["di_ung"] == "Penicillin"
    # Khách không có thai kỳ → khối sản khoa tự ẩn.
    assert goi["co_thai"] is False
    ten_bs = await pool.fetchval(
        "SELECT full_name FROM staff WHERE id = $1::uuid", ca["bs"].staff_id
    )
    assert goi["bac_si_ky"] == ten_bs == moi["bac_si"]

    # Bỏ chọn một lượt → lượt cũ hơn lấp vào; lượt không đo → ô trống.
    bo = await _doc(pool, ca, bo=f"{v20},rác")
    assert [x["visit_id"] for x in bo["luot"]] == [v40, v30, v10]
    assert bo["luot"][0]["sinh_hieu"] == {} and bo["luot"][0]["ly_do"] == []
    assert [x["bo"] for x in bo["chon_duoc"]] == [False, True, False, False, False]

    assert [x["visit_id"] for x in (await _doc(pool, ca, so_lan="1"))["luot"]] == [v10]
    assert len((await _doc(pool, ca, so_lan="rác"))["luot"]) == 3


@pytest.mark.db
@pytest.mark.asyncio
async def test_tom_tat_khach_khong_luot_va_mot_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    trong = await _doc(pool, ca)
    assert trong["luot"] == [] and trong["chon_duoc"] == []
    assert trong["tong_lan_kham"] == 0 and trong["bac_si_ky"] is None

    v = await _luot(pool, ca, 2)
    mot = await _doc(pool, ca)
    assert [x["visit_id"] for x in mot["luot"]] == [v]
    assert mot["luot"][0]["xu_huong"] == {}
    assert mot["khach"]["ho_ten"] == "Khách đổi dịch vụ"
    assert mot["co_thai"] is False and mot["luot"][0]["san_khoa"]["tuoi_thai"] is None

    # Có thai kỳ bao trùm ngày khám → tuổi thai = phép trừ từ dự sinh (máy chủ).
    ngay_kham = date.fromisoformat(mot["luot"][0]["ngay"])
    kinh_cuoi = ngay_kham - timedelta(days=100)
    await pool.execute(
        "INSERT INTO pregnancy (clinic_id, clinic_patient_id, location_id, outcome,"
        " lmp_date, edd_date) VALUES ($1::uuid, $2::uuid, $3::uuid, 'ONGOING', $4, $5)",
        CLINIC,
        ca["pid"],
        ca["loc"],
        kinh_cuoi,
        kinh_cuoi + timedelta(days=280),
    )
    thai = await _doc(pool, ca)
    assert thai["co_thai"] is True
    assert thai["luot"][0]["san_khoa"]["tuoi_thai"] == "14 tuần 2 ngày"
    assert thai["nen_tang"]["ky_kinh_cuoi"] == kinh_cuoi.strftime("%d/%m/%Y")
