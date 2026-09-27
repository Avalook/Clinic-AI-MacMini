"""Thẻ sinh hiệu Y HỆT bản giao diện mẫu (27/09/2026): nhãn đầy đủ + đơn vị."""

from __future__ import annotations

from decimal import Decimal

from clinicai.phieu_kham.mang_sang import dung_sinh_hieu, dung_the_sinh_hieu


def test_dinh_dang_nhu_ban_mau() -> None:
    o = dung_the_sinh_hieu(
        dung_sinh_hieu(
            {
                "systolic": 118,
                "diastolic": 76,
                "pulse": 78,
                "temperature": Decimal("36.6"),
                "weight_kg": Decimal("54.0"),
                "height_cm": 158,
                "spo2": 98,
                "bmi": Decimal("21.63"),
                "respiratory_rate": 18,
                "pain_score": 2,
            }
        )
    )
    assert [(x["nhan"], x["gia_tri"]) for x in o] == [
        ("Mạch", "78 lần/phút"),
        ("Nhiệt độ", "36,6 °C"),
        ("Huyết áp", "118/76 mmHg"),
        ("Nhịp thở", "18 lần/phút"),
        ("SpO₂", "98 %"),
        ("Cân nặng", "54 kg"),
        ("Chiều cao", "158 cm"),
        ("BMI", "21,6"),
        ("Thang đau", "2/10"),
    ]


def test_chua_do_thi_trong_khong_bia() -> None:
    o = dung_the_sinh_hieu(dung_sinh_hieu(None))
    assert len(o) == 9 and all(x["gia_tri"] is None for x in o)
