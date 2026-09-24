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


async def doc_dau_phieu(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    """Đọc phần mang sang cho một lượt. Chỉ ĐỌC — không ghi bảng module nào.

    Sinh hiệu: lần đo MỚI NHẤT của ĐÚNG lượt này. Mỗi lần đo là một dòng không
    sửa đè, nên "mới nhất" là điều dưỡng sửa lại lần cuối.
    """
    bn = await conn.fetchrow(
        "SELECT p.full_name, p.patient_code, p.birth_year, p.date_of_birth,"
        "       v.checked_in_at"
        "  FROM visit v"
        "  JOIN patient p"
        "    ON p.clinic_id = v.clinic_id AND p.clinic_patient_id = v.clinic_patient_id"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )
    do = await conn.fetchrow(
        "SELECT systolic, diastolic, pulse, temperature, weight_kg, height_cm,"
        "       spo2, bmi, respiratory_rate, pain_score, created_at"
        "  FROM vital_measurement"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        " ORDER BY created_at DESC, id DESC LIMIT 1",
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
        "nhan": dict(TRUONG_HANH_CHINH + TRUONG_SINH_HIEU),
        "hanh_chinh": dung_hanh_chinh(
            dict(bn) if bn else None, vao_luc=bn["checked_in_at"] if bn else None
        ),
        "sinh_hieu": dung_sinh_hieu(dict(do) if do else None),
        "sinh_hieu_luc": do["created_at"].isoformat() if do else None,
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
    "TRUONG_HANH_CHINH",
    "TRUONG_SINH_HIEU",
    "doc_dau_phieu",
    "dung_hanh_chinh",
    "dung_sinh_hieu",
]
