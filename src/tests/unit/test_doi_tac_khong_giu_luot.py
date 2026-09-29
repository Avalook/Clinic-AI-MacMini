"""Nút của đối tác chỉ GHI SỰ KIỆN, không giữ lượt khám (Tuyền chốt 28/09/2026).

"bên đối tác bận việc chưa nhấn cũng được không sao, mình cứ open nhé, cứ coi
như thao tác để ghi lại sự kiện … quan trọng nhất vẫn là phục vụ khách".

Ghim ba chỗ bằng mã nguồn (luật nằm trong SQL, test DB lo phần chạy thật):
  1. câu "việc còn dở giữ lượt" bỏ việc làm bên ngoài;
  2. khép lượt (kham_xong) và đóng lượt ở quầy dùng câu ấy;
  3. "Nhận mẫu · chờ tài liệu" không còn đòi "Đã lấy mẫu" trước.
Và một chỗ KHÔNG đổi: bác sĩ kết thúc phiên vẫn sinh yêu cầu "cần kết quả" cho
việc đối tác (câu gốc CHI_DINH_CON_VIEC_SQL).
"""

from __future__ import annotations

import inspect

from clinicai.services import checkout_service, doi_tac_service, luot_kham_service
from clinicai.services.luot_kham_chung import (
    CHI_DINH_CON_VIEC_GIU_LUOT_SQL,
    CHI_DINH_CON_VIEC_SQL,
)


def test_cau_giu_luot_bo_viec_doi_tac() -> None:
    assert CHI_DINH_CON_VIEC_GIU_LUOT_SQL.startswith(CHI_DINH_CON_VIEC_SQL)
    assert "lam_ben_ngoai" in CHI_DINH_CON_VIEC_GIU_LUOT_SQL
    assert "lam_ben_ngoai" not in CHI_DINH_CON_VIEC_SQL


def test_khep_luot_va_dong_luot_dung_cau_giu_luot() -> None:
    assert "CHI_DINH_CON_VIEC_GIU_LUOT_SQL" in inspect.getsource(checkout_service)
    khep = inspect.getsource(luot_kham_service.LuotKhamService._ket_thuc_neu_xong)
    assert "CHI_DINH_CON_VIEC_GIU_LUOT_SQL" in khep


def test_ket_thuc_phien_van_tinh_viec_doi_tac() -> None:
    nguon = inspect.getsource(luot_kham_service)
    # Chỗ dựng yêu cầu "cần kết quả" khi bác sĩ kết thúc phiên đọc lam_ben_ngoai
    # và vẫn dùng câu gốc.
    assert "need_mac_dinh(\n" in nguon or "need_mac_dinh(" in nguon
    assert "+ CHI_DINH_CON_VIEC_SQL\n" in nguon


def test_cho_tai_lieu_khong_doi_lay_mau_truoc() -> None:
    assert "SAMPLE_NOT_READY" not in inspect.getsource(doi_tac_service)


def test_nhan_mau_la_xong() -> None:
    """Tuyền 29/09/2026: NHẬN MẪU là XONG — trạng thái bàn đối tác + vòng đọc."""
    from clinicai.services.doi_tac_service import (
        VIEC_DOI_TAC_XONG,
        trang_thai_doi_tac,
    )
    from clinicai.services.luot_kham_chung import CO_KET_QUA_VONG_SQL

    assert (
        trang_thai_doi_tac(exec_status="performed", cho_tai_lieu=True, co_ket_qua=False)
        == "DA_NHAN_MAU"
    )
    assert VIEC_DOI_TAC_XONG == {"DA_NHAN_MAU", "DA_GUI_KET_QUA"}
    # Mốc nhận mẫu thoả yêu cầu vòng đọc; mọi câu đọc vòng dùng chung câu này.
    assert "doi_tac_cho_tai_lieu_luc IS NOT NULL" in CO_KET_QUA_VONG_SQL
    nguon = inspect.getsource(luot_kham_service)
    assert nguon.count("CO_KET_QUA_VONG_SQL") >= 4
    assert "partner.sample_received" in inspect.getsource(doi_tac_service)
