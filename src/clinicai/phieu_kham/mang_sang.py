"""Dữ liệu MANG SANG phiếu: hành chính, sinh hiệu, ghi chú bác sĩ tư vấn.

Nguồn ghi rõ hai câu: *"đồng bộ từ Điều dưỡng"* và *"hiển thị dữ liệu đã có tại
đây, không bắt nhập lại"*. Nên phần này CHỈ ĐỌC. Sinh hiệu sai thì sửa ở màn đo
sinh hiệu — phiếu không có ô nào để gõ đè, vì một con số có hai chỗ sửa là một
con số có hai giá trị.

KHOÁ = đúng `data-bind` của nguồn (`vitals.blood_pressure`, `patient.code`…),
để màn vẽ dải hành chính tra thẳng theo `HANH_CHINH.lien_ket.truong` của khung,
không có bảng dịch khoá nào ở giữa.

KHÔNG TÍNH HỘ. BMI lấy đúng con số điều dưỡng đã lưu; chưa lưu thì để trống.
Tự tính từ cân nặng/chiều cao ở đây là đẻ ra một giá trị không ai nhập và không
ai xác nhận, rồi in lên phiếu như thể điều dưỡng đã đo.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ

#: Thứ tự y như dải sinh hiệu trên phiếu nguồn.
TRUONG_SINH_HIEU: tuple[tuple[str, str], ...] = (
    ("vitals.blood_pressure", "HA"),
    ("vitals.pulse", "Mạch"),
    ("vitals.weight", "CN"),
    ("vitals.height", "CC"),
    ("vitals.temperature", "Nhiệt"),
    ("vitals.spo2", "SpO₂"),
    ("vitals.bmi", "BMI"),
    ("vitals.respiratory_rate", "NT"),
    ("vitals.pain_score", "Đau"),
)

TRUONG_HANH_CHINH: tuple[tuple[str, str], ...] = (
    ("patient.name", "Bệnh nhân"),
    ("patient.birth_year", "Năm sinh"),
    ("patient.code", "Mã BN"),
    ("encounter.date", "Ngày khám"),
)

#: THÔNG TIN HỒ SƠ đồng bộ sang phiếu khám (Tuyền 24/09/2026: "các thông tin
#: trong form khách hàng mới phải thực sự đồng bộ cho hồ sơ khám"). Đọc THẲNG
#: từ bảng `patient` mỗi lần mở phiếu — sửa hồ sơ là phiếu thấy ngay, không có
#: bản chép thứ hai. Thứ tự = thứ tự hiện trên phiếu.
TRUONG_HO_SO: tuple[tuple[str, str], ...] = (
    ("patient.date_of_birth", "Ngày sinh"),
    ("patient.gender", "Giới tính"),
    ("patient.phone", "SĐT"),
    ("patient.phone_family", "SĐT người nhà"),
    ("patient.national_id", "CCCD"),
    ("patient.ethnicity", "Dân tộc"),
    ("patient.nationality", "Quốc tịch"),
    ("patient.occupation", "Nghề nghiệp"),
    ("patient.address", "Địa chỉ"),
    ("patient.guardian", "Người giám hộ"),
    ("patient.location", "Cơ sở"),
    ("patient.referrer", "Người giới thiệu"),
    ("patient.reason", "Vấn đề đi khám"),
)

_GIOI_TINH = {"F": "Nữ", "M": "Nam", "FEMALE": "Nữ", "MALE": "Nam", "O": "Khác"}


def dia_chi_benh_nhan(bn: Mapping[str, Any]) -> str | None:
    """Địa chỉ có cấu trúc (chi tiết · phường · tỉnh) — rơi về ô tự do cũ."""
    phan = [bn.get("address_detail"), bn.get("ward_name"), bn.get("province_name")]
    co = [str(x).strip() for x in phan if x and str(x).strip()]
    return ", ".join(co) if co else (bn.get("address") or None)


def dung_ho_so(benh_nhan: Mapping[str, Any] | None) -> dict[str, Any]:
    """Các ô hồ sơ. Thiếu gì để None — màn in "—", không bịa."""
    bn = benh_nhan or {}
    ngay = bn.get("date_of_birth")
    gt = bn.get("gender")
    return {
        "patient.date_of_birth": ngay.strftime("%d/%m/%Y") if ngay else None,
        "patient.gender": _GIOI_TINH.get(str(gt).upper(), gt) if gt else None,
        "patient.phone": bn.get("phone_primary"),
        "patient.phone_family": bn.get("phone_secondary"),
        "patient.national_id": bn.get("national_id_number"),
        "patient.ethnicity": bn.get("ethnicity"),
        "patient.nationality": bn.get("nationality"),
        "patient.occupation": bn.get("occupation"),
        "patient.address": dia_chi_benh_nhan(bn),
        "patient.guardian": bn.get("guardian_name"),
        "patient.location": bn.get("location_name"),
        "patient.referrer": bn.get("nguoi_gioi_thieu"),
        "patient.reason": bn.get("van_de_di_kham"),
    }


#: `vital_measurement` → khoá nguồn. Huyết áp ghép riêng.
_COT_SINH_HIEU = {
    "vitals.pulse": "pulse",
    "vitals.weight": "weight_kg",
    "vitals.height": "height_cm",
    "vitals.temperature": "temperature",
    "vitals.spo2": "spo2",
    "vitals.bmi": "bmi",
    "vitals.respiratory_rate": "respiratory_rate",
    "vitals.pain_score": "pain_score",
}


def _so(v: Any) -> int | float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, int | float) and not isinstance(v, bool):
        return v
    return None


#: Thẻ sinh hiệu (27/09/2026 — Y HỆT bản giao diện mẫu): nhãn ĐẦY ĐỦ + ĐƠN VỊ,
#: đúng thứ tự bản mẫu. Dải cũ viết tắt (HA, CN…) vẫn giữ cho bản in / màn cũ.
THE_SINH_HIEU: tuple[tuple[str, str, str], ...] = (
    ("vitals.pulse", "Mạch", "lần/phút"),
    ("vitals.temperature", "Nhiệt độ", "°C"),
    ("vitals.blood_pressure", "Huyết áp", "mmHg"),
    ("vitals.respiratory_rate", "Nhịp thở", "lần/phút"),
    ("vitals.spo2", "SpO₂", "%"),
    ("vitals.weight", "Cân nặng", "kg"),
    ("vitals.height", "Chiều cao", "cm"),
    ("vitals.bmi", "BMI", ""),
    ("vitals.pain_score", "Thang đau", "/10"),
)


def _so_vn(v: Any) -> str:
    """36.6 → "36,6"; 21.634 → "21,6"; 78 → "78" (dấu phẩy thập phân kiểu Việt)."""
    if isinstance(v, float) and not v.is_integer():
        return f"{round(v, 1)}".replace(".", ",")
    if isinstance(v, float):
        return str(int(v))
    return str(v)


def dung_the_sinh_hieu(sinh_hieu: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Chín ô của thẻ sinh hiệu: {nhan, gia_tri} — chưa đo thì gia_tri None.

    Thang đau ghép liền "2/10"; đơn vị khác cách một khoảng ("78 lần/phút")."""
    ra: list[dict[str, Any]] = []
    for khoa, nhan, don_vi in THE_SINH_HIEU:
        v = sinh_hieu.get(khoa)
        if v is None or v == "":
            gt = None
        else:
            chu = v if isinstance(v, str) else _so_vn(v)
            gt = (
                f"{chu}{don_vi}"
                if don_vi.startswith("/")
                else f"{chu} {don_vi}".strip()
            )
        ra.append({"khoa": khoa, "nhan": nhan, "gia_tri": gt})
    return ra


def dung_hanh_chinh(
    benh_nhan: Mapping[str, Any] | None, *, vao_luc: datetime | None
) -> dict[str, Any]:
    """Bốn ô hành chính. Thiếu gì để None — màn in "—", không bịa."""
    bn = benh_nhan or {}
    nam = bn.get("birth_year")
    if nam is None and bn.get("date_of_birth") is not None:
        nam = bn["date_of_birth"].year
    return {
        "patient.name": bn.get("full_name"),
        "patient.birth_year": int(nam) if nam is not None else None,
        "patient.code": bn.get("patient_code"),
        # Ngày khám theo giờ PHÒNG KHÁM: 23:30 giờ UTC là ngày hôm sau ở đây.
        "encounter.date": (
            vao_luc.astimezone(CLINIC_TZ).date().isoformat() if vao_luc else None
        ),
    }


def dung_sinh_hieu(do: Mapping[str, Any] | None) -> dict[str, Any]:
    """Chín ô sinh hiệu từ MỘT lần đo. Chưa đo lần nào → cả chín là None."""
    if do is None:
        return {k: None for k, _ in TRUONG_SINH_HIEU}
    tren, duoi = do.get("systolic"), do.get("diastolic")
    kq: dict[str, Any] = {
        "vitals.blood_pressure": (
            f"{tren}/{duoi}" if tren is not None and duoi is not None else None
        )
    }
    for khoa, cot in _COT_SINH_HIEU.items():
        kq[khoa] = _so(do.get(cot))
    return kq


#: Ô "Chẩn đoán" của từng loại phiếu khám v5 (mục D) — khoá ổn định của nguồn,
#: theo thứ tự ưu tiên khi một lượt có hơn một phiếu. Bản in phiếu kết quả ghi
#: "Chẩn đoán lâm sàng" từ đây (bản mẫu 27/09/2026); chưa ghi thì bỏ dòng ấy.
MA_CHAN_DOAN: tuple[str, ...] = (
    "pk_dx",
    "nt_dx",
    "nk_dx",
    "sc_dx",
    "sk_conclusion",
    "hmvs_dx_w",
    "hmvs_dx_m",
    "hmvs_dx_mix",
)


def chan_doan_tu_phieu(du_lieu: Mapping[str, Any] | None) -> str | None:
    """Câu chẩn đoán đầu tiên CÓ CHỮ trong dữ liệu một phiếu khám (hoặc None)."""
    for ma in MA_CHAN_DOAN:
        o = (du_lieu or {}).get(ma)
        gt = o.get("gia_tri") if isinstance(o, Mapping) else None
        if isinstance(gt, str) and gt.strip():
            return gt.strip()
    return None


async def doc_chan_doan(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> str | None:
    """Chẩn đoán bác sĩ chính đã ghi trên phiếu khám của lượt — chỉ đọc."""
    rows = await conn.fetch(
        "SELECT du_lieu FROM phieu_kham_luot"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid ORDER BY tao_luc",
        clinic_id,
        visit_id,
    )
    for r in rows:
        dl = r["du_lieu"]
        cd = chan_doan_tu_phieu(json.loads(dl) if isinstance(dl, str) else dl)
        if cd:
            return cd
    return None


async def doc_dau_phieu(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    """Đọc phần mang sang cho một lượt. Chỉ ĐỌC — không ghi bảng module nào.

    Sinh hiệu: lần đo MỚI NHẤT của ĐÚNG lượt này. Mỗi lần đo là một dòng không
    sửa đè, nên "mới nhất" là điều dưỡng sửa lại lần cuối.
    """
    bn = await conn.fetchrow(
        "SELECT p.full_name, p.patient_code, p.birth_year, p.date_of_birth,"
        "       p.gender, p.phone_primary, p.phone_secondary, p.national_id_number,"
        "       p.ethnicity, p.nationality, p.occupation, p.address,"
        "       p.address_detail, p.ward_name, p.province_name, p.guardian_name,"
        "       p.nguoi_gioi_thieu, p.van_de_di_kham, l.name AS location_name,"
        "       v.checked_in_at, lv.name AS co_so_luot, st.name AS loai_kham,"
        "       bc.name AS kenh_dat, a.so_booking, a.so_tiep_don,"
        # Đầu trang bản in (27/09/2026): tên phòng khám + địa chỉ CƠ SỞ của lượt
        # (cơ sở chưa ghi địa chỉ thì rơi về địa chỉ phòng khám).
        "       ck.name AS phong_kham,"
        "       coalesce(nullif(btrim(lv.address), ''), nullif(btrim(l.address), ''),"
        "                ck.address) AS dia_chi_co_so,"
        # Bác sĩ của LƯỢT; lượt chưa gán thì bác sĩ phiên khám chính đầu tiên.
        "       coalesce(d.full_name, ("
        "           SELECT s.full_name FROM consultation c"
        "             JOIN staff s ON s.id = c.doctor_staff_id"
        "            WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id"
        "              AND c.kind = 'PRIMARY'"
        "            ORDER BY c.round_no LIMIT 1)) AS bac_si"
        "  FROM visit v"
        "  JOIN patient p"
        "    ON p.clinic_id = v.clinic_id AND p.clinic_patient_id = v.clinic_patient_id"
        "  LEFT JOIN clinic_location l"
        "    ON l.id = p.location_id AND l.clinic_id = p.clinic_id"
        "  LEFT JOIN clinic_location lv"
        "    ON lv.id = v.location_id AND lv.clinic_id = v.clinic_id"
        "  JOIN clinic ck ON ck.id = v.clinic_id"
        "  LEFT JOIN service_type st ON st.id = v.service_type_id"
        "  LEFT JOIN staff d ON d.id = v.attending_doctor_id"
        "  LEFT JOIN appointment a"
        "    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
        "  LEFT JOIN booking_channel bc"
        "    ON bc.clinic_id = a.clinic_id AND bc.code = a.booking_channel"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )
    do = await conn.fetchrow(
        "SELECT m.systolic, m.diastolic, m.pulse, m.temperature, m.weight_kg,"
        "       m.height_cm, m.spo2, m.bmi, m.respiratory_rate, m.pain_score,"
        "       m.created_at, s.full_name AS nguoi_do"
        "  FROM vital_measurement m"
        "  LEFT JOIN staff s ON s.id = m.recorded_by"
        " WHERE m.clinic_id = $1::uuid AND m.visit_id = $2::uuid"
        " ORDER BY m.created_at DESC, m.id DESC LIMIT 1",
        clinic_id,
        visit_id,
    )
    # "A. Khám của bác sĩ tư vấn". Hai nguồn:
    #  · phiên TƯ VẤN (24/09/2026 — ô chữ tự do của bác sĩ tư vấn): mỗi lần lưu
    #    thêm một dòng, nên chỉ lấy BẢN MỚI NHẤT của mỗi phiên;
    #  · ghi chú cũ của phiên khám BAN ĐẦU (PRIMARY, lối ghi chú đã tắt): giữ
    #    nguyên văn theo thứ tự đã ghi, cho lượt cũ.
    # Trước 24/09 chỉ đọc PRIMARY — bác sĩ tư vấn ghi gì bác sĩ chính cũng
    # không thấy ở mục này.
    ghi_chu = await conn.fetch(
        """
        SELECT body, created_at, round_no, consultation_id FROM (
            SELECT DISTINCT ON (c.id)
                   n.body, n.created_at, c.round_no, c.id::text AS consultation_id
              FROM consultation_note n
              JOIN consultation c
                ON c.clinic_id = n.clinic_id AND c.id = n.consultation_id
             WHERE n.clinic_id = $1::uuid AND c.visit_id = $2::uuid
               AND c.kind = 'TU_VAN'
             ORDER BY c.id, n.created_at DESC, n.id DESC
        ) tv
        WHERE body <> ''
        UNION ALL
        SELECT n.body, n.created_at, c.round_no, c.id::text
          FROM consultation_note n
          JOIN consultation c
            ON c.clinic_id = n.clinic_id AND c.id = n.consultation_id
         WHERE n.clinic_id = $1::uuid AND c.visit_id = $2::uuid
           AND c.kind = 'PRIMARY'
        ORDER BY created_at
        """,
        clinic_id,
        visit_id,
    )
    return {
        # Nhãn đi kèm dữ liệu: màn không giữ bản chép thứ hai của "HA", "CN"…
        "nhan": dict(TRUONG_HANH_CHINH + TRUONG_SINH_HIEU + TRUONG_HO_SO),
        "hanh_chinh": {
            **dung_hanh_chinh(
                dict(bn) if bn else None, vao_luc=bn["checked_in_at"] if bn else None
            ),
            **dung_ho_so(dict(bn) if bn else None),
        },
        # Thứ tự các ô HỒ SƠ hiện thêm dưới dải hành chính của khung phiếu.
        "ho_so": [k for k, _ in TRUONG_HO_SO],
        "sinh_hieu": dung_sinh_hieu(dict(do) if do else None),
        "sinh_hieu_luc": do["created_at"].isoformat() if do else None,
        # Thẻ khách + thẻ sinh hiệu Y HỆT bản giao diện mẫu (27/09/2026).
        "the_khach": {
            "bac_si": bn["bac_si"] if bn else None,
            "kenh_dat": bn["kenh_dat"] if bn else None,
            "co_so": (bn["co_so_luot"] or bn["location_name"]) if bn else None,
            "loai_kham": bn["loai_kham"] if bn else None,
            # Số booking + số check-in ở MỌI khâu khám (Tuyền 27/09).
            "so_booking": bn["so_booking"] if bn else None,
            "so_tiep_don": bn["so_tiep_don"] if bn else None,
            "phong_kham": bn["phong_kham"] if bn else None,
            "dia_chi_co_so": bn["dia_chi_co_so"] if bn else None,
        },
        "the_sinh_hieu": dung_the_sinh_hieu(dung_sinh_hieu(dict(do) if do else None)),
        "sinh_hieu_nguoi": do["nguoi_do"] if do else None,
        "tu_van": [
            {
                "noi_dung": r["body"],
                "luc": r["created_at"].isoformat(),
                "vong": r["round_no"],
                "consultation_id": r["consultation_id"],
            }
            for r in ghi_chu
        ],
    }


__all__ = [
    "MA_CHAN_DOAN",
    "THE_SINH_HIEU",
    "TRUONG_HANH_CHINH",
    "TRUONG_SINH_HIEU",
    "chan_doan_tu_phieu",
    "dia_chi_benh_nhan",
    "doc_chan_doan",
    "doc_dau_phieu",
    "dung_hanh_chinh",
    "dung_the_sinh_hieu",
    "dung_sinh_hieu",
]
