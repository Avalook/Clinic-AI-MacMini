"""Luật "khách khám lần mấy / đang trong chuỗi tái khám" — nay ở backend (24/09)."""

from __future__ import annotations

from clinicai.services.man_dat_lich_doc import dem_lan_kham


def test_chi_dem_luot_da_kham_xong_va_chuoi_tai_kham() -> None:
    kq = dem_lan_kham(
        [
            {"clinic_patient_id": "a", "status": "COMPLETED", "lich_truoc_id": None},
            {"clinic_patient_id": "a", "status": "CANCELLED", "lich_truoc_id": "x"},
            {"clinic_patient_id": "a", "status": "COMPLETED", "lich_truoc_id": None},
            {"clinic_patient_id": "b", "status": "CONFIRMED", "lich_truoc_id": "y"},
        ]
    )
    # Đặt rồi huỷ không tính là đã khám; lịch huỷ không giữ chuỗi tái khám.
    assert kq["a"] == {"soLanKham": 2, "laTaiKham": False}
    assert kq["b"] == {"soLanKham": 0, "laTaiKham": True}
