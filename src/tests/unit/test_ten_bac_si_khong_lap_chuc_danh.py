"""Chỗ tự ghép "BS " trước tên bác sĩ không được lặp chức danh.

Prod đổi tên bác sĩ thành "Bác sĩ <họ tên>" (16/10/2026); các câu dưới đây từng
nối cứng `BS {tên}` nên ra "BS Bác sĩ Phan Chí Thành". Quy tắc chung ở
`lan_bac_si.ten_bac_si`.
"""

from __future__ import annotations

import pytest

from clinicai.events.consumers.nhac_tai_kham import noi_dung_chuong
from clinicai.services.nhan_tai_phong import cau_ban_kham
from clinicai.services.notification_templates import (
    ca_moi_cho_xep,
    lich_moi,
    xoa_ca_bac_si,
)
from clinicai.services.so_sua_chi_dinh_service import cau_xoa

CO_CHUC = "Bác sĩ Phan Chí Thành"
TRAN = "Phan Chí Thành"


@pytest.mark.parametrize("ten", [CO_CHUC, "BS Thành", "bác sĩ Thành"])
def test_ten_da_co_chuc_danh_khong_lap(ten: str) -> None:
    for tin in (
        lich_moi({"ten_bac_si": ten}),
        xoa_ca_bac_si({"bac_si_da_go": ten}),
        ca_moi_cho_xep({"ten_bac_si": ten, "ca": "SANG"}),
        noi_dung_chuong({"bac_si": ten}),
        cau_ban_kham(ten),
        cau_xoa(
            {
                "boi_ten": "Nguyễn A",
                "boi_vai": "MANAGEMENT",
                "boi_staff_id": "1",
                "bac_si_chinh_id": "2",
                "bac_si_chinh_ten": ten,
            }
        ),
    ):
        assert "BS BS" not in tin and "BS Bác sĩ" not in tin, tin
        assert "bác sĩ Bác sĩ" not in tin and "bác sĩ BS" not in tin, tin
        assert ten in tin, tin


def test_ten_tran_van_duoc_gan_chuc_danh() -> None:
    assert lich_moi({"ten_bac_si": TRAN}).endswith(f"BS {TRAN}")
    assert f"Gỡ ca bác sĩ {TRAN}" in xoa_ca_bac_si({"bac_si_da_go": TRAN})
    assert f"BS {TRAN} có ca sáng" in ca_moi_cho_xep({"ten_bac_si": TRAN, "ca": "SANG"})
    assert f"BS {TRAN}" in noi_dung_chuong({"bac_si": TRAN})
    assert cau_ban_kham(TRAN) == f"bàn khám BS {TRAN}"


def test_thieu_ten_giu_cau_cu() -> None:
    assert lich_moi({}).endswith("BS chờ xếp bác sĩ")
    assert cau_ban_kham(None) == "bàn khám"
