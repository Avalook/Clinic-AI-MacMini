"""K1 (Tuyền 14/10/2026): thuế KHÔNG chạm vận hành.

Quầy thu, hoá đơn, báo cáo ngày không được đọc / ghi cột thuế. Chỉ ba nơi biết tới
chúng: dịch vụ đặt thuế, dịch vụ xuất hoá đơn của kế toán, hàm thuần tách thuế.
"""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "clinicai"
DUOC_PHEP = {
    "services/thue_gtgt.py",
    "services/thue_suat_service.py",
    "services/xuat_hoa_don_service.py",
}
TU_KHOA = ("thue_suat_ma", "thue_suat_nhom", "thue_mh")


def test_chi_ke_toan_doc_ghi_cot_thue() -> None:
    lo = []
    for f in SRC.rglob("*.py"):
        rel = f.relative_to(SRC).as_posix()
        if rel in DUOC_PHEP:
            continue
        txt = f.read_text(encoding="utf-8")
        if any(k in txt for k in TU_KHOA):
            lo.append(rel)
    assert lo == [], f"thuế rò vào vận hành: {lo}"
    # Chống xanh giả: hai tệp được phép thật sự dùng.
    for rel in DUOC_PHEP:
        assert "thue_suat" in (SRC / rel).read_text(encoding="utf-8")
