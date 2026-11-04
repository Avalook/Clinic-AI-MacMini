"""Ba nhóm việc của luật "đứng đâu làm việc đó" (Tuyền chia 04/11/2026).

A — ai cũng có. B — gắn phòng: làm được khi hôm nay đứng phòng có chức năng ấy
(`phong_chuc_nang`, màn Cấu trúc phòng khám chỉ tick được khối nhóm B). C — theo
người: cấp riêng ở màn Phân quyền. Khối không thuộc A/B là C.

Bốn mục chưa chốt hẳn (ds_benh_nhan cho mọi người?, duyet_ket_qua B hay C, CSKH
có phòng không, trưởng ca mặc nhiên làm mọi việc B?) — xếp tạm như dưới.
"""

from __future__ import annotations

from clinicai.permissions.catalogue import KHOI

NHOM_A: frozenset[str] = frozenset(
    {
        "ds_benh_nhan",
        "lich_lam_viec",
        "viec_can_xu_ly",
        "dat_lich",
        "them_benh_nhan",
        "xem_nha_thuoc",
    }
)

NHOM_B: frozenset[str] = frozenset(
    {
        "tiep_don",
        "chon_dich_vu",
        "dieu_phoi",
        "thu_tien_dv",
        "thu_tien_thuoc",
        "nha_thuoc",
        "sinh_hieu",
        "tu_van",
        "kham",
        "chi_dinh",
        "ghi_benh_an",
        "hoan_tat_kham",
        "thuc_hien",
        "ket_qua",
        "duyet_ket_qua",
        "xac_nhan_ket_qua",
        "doi_tac",
        "kho_vat_tu",
    }
)

# Chỉ làm được ở ĐÚNG phòng đứng (như lego Phòng dịch vụ).
KHOI_THEO_PHONG: frozenset[str] = frozenset({"thuc_hien"})


def nhom_cua(work_pack: str) -> str:
    if work_pack in NHOM_A:
        return "A"
    if work_pack in NHOM_B:
        return "B"
    if work_pack in KHOI:
        return "C"
    return "?"


__all__ = ["KHOI_THEO_PHONG", "NHOM_A", "NHOM_B", "nhom_cua"]
