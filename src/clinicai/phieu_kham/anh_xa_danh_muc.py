"""Ghép nhãn của phiếu v5 với mã THẬT của phòng khám (IP-4, 23/09/2026).

Tuyền chốt 23/09 tối: "các cái dịch vụ hay thủ thuật này kia đều có hết" — danh
mục đủ nằm ở `chi-dinh.html` (bảng giá KiotViet + liều dùng Notion). Ở đây là
bảng ghép VIẾT TAY, từng dòng một, KHÔNG so tên tự động: so tên là cách một dịch
vụ lặng lẽ trỏ nhầm sang dịch vụ khác.

* Mục C / F: nhãn nguồn → `service_code`. Mã có sẵn (seed V5-A) giữ nguyên; dịch
  vụ chưa có trong danh mục thì migration 20260924000009 thêm với giá của
  `chi-dinh.html`. Giá đã có trong DB KHÔNG bị đè (giá là quyết định kinh
  doanh) — chỉ điền chỗ còn trống.
* Thuốc: mẫu `rx_NNN` → `drug_catalog.name_raw` ĐÚNG NGUYÊN VĂN. Dòng kho gộp
  nhiều thuốc ("Difavon/Diflucan/…") hay tách hàm lượng mơ hồ thì KHÔNG ghép —
  dòng đơn đi dạng tên thô, quầy thuốc xác định thuốc như vẫn làm.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DichVuPhieu:
    ma: str  # service_code
    ten: str  # tên trong danh mục (khi phải thêm mới)
    node: str  # phòng/khu làm: node_definition.code
    gia: int  # giá chi-dinh.html (VND)
    loai: str = "Thủ thuật"  # service_price.category khi thêm mới


#: Nhãn mục C (đúng chữ trong nguồn) → dịch vụ.
CLS: dict[str, DichVuPhieu] = {
    "Đo mật độ xương": DichVuPhieu(
        "CLS_DO_MAT_DO_XUONG", "Đo mật độ xương", "DICHVU-DXA", 200000
    ),
    "Test nước tiểu": DichVuPhieu(
        "CLS_NUOC_TIEU", "Nước tiểu", "DICHVU-LAYMAU-NUOCTIEU", 50000
    ),
    "Chạy monitoring": DichVuPhieu(
        "CLS_CHAY_MONITORING", "Chạy monitoring", "DICHVU-THUTHUAT", 200000
    ),
    "XN máu": DichVuPhieu(
        "CLS_XET_NGHIEM_MAU", "Xét nghiệm máu", "DICHVU-LAYMAU-MAU", 350000
    ),
    "*XN dịch âm đạo": DichVuPhieu(
        "CLS_XET_NGHIEM_DICH_AM_DAO",
        "Xét nghiệm dịch âm đạo",
        "DICHVU-LAYMAU-AMDAO",
        300000,
    ),
    "• HPV": DichVuPhieu(
        "CLS_HPV", "Xét nghiệm HPV", "DICHVU-SANGLOC-COTUCUNG", 950000, "Tầng 1"
    ),
    "• ThinPrep": DichVuPhieu(
        "CLS_THINPREP", "ThinPrep", "DICHVU-SANGLOC-COTUCUNG", 650000, "Tầng 1"
    ),
    "• PCR 12 loại VK": DichVuPhieu(
        "CLS_PCR_12_VK",
        "PCR 12 loại vi khuẩn",
        "DICHVU-LAYMAU-AMDAO",
        1200000,
        "Tầng 1",
    ),
    "SÂ 3D thai <12 tuần": DichVuPhieu(
        "CLS_SIEU_AM_3D_THAI_12_TUAN",
        "Siêu âm 3D thai <12 tuần",
        "DICHVU-SIEUAM",
        250000,
    ),
    "SÂ 3D thai >12 tuần": DichVuPhieu(
        "CLS_SIEU_AM_3D_THAI_12_TUAN_2",
        "Siêu âm 3D thai >12 tuần",
        "DICHVU-SIEUAM",
        300000,
    ),
    "SÂ thai 6D": DichVuPhieu(
        "CLS_SIEU_AM_THAI_6D", "Siêu âm thai 6D", "DICHVU-SIEUAM", 400000
    ),
    "SÂ đầu dò độ dài CTC": DichVuPhieu(
        "CLS_SIEU_AM_DAU_DO_DO_DAI_CTC",
        "Siêu âm đầu dò độ dài CTC",
        "DICHVU-SIEUAM",
        50000,
    ),
    "SÂ 2D TC-BT": DichVuPhieu(
        "CLS_SIEU_AM_2D_TC_BT", "Siêu âm 2D TC-BT", "DICHVU-SIEUAM", 250000
    ),
    "SÂ 4D TC-BT": DichVuPhieu(
        "CLS_SIEU_AM_4D_TC_BT", "Siêu âm 4D TC-BT", "DICHVU-SIEUAM", 350000
    ),
    "SÂ bơm nước tử cung": DichVuPhieu(
        "CLS_SIEU_AM_BOM_NUOC_TU_CUNG",
        "Siêu âm bơm nước tử cung",
        "DICHVU-SIEUAM",
        800000,
    ),
    "SÂ khớp": DichVuPhieu("CLS_SIEU_AM_KHOP", "Siêu âm khớp", "DICHVU-SIEUAM", 150000),
    "SÂ ổ bụng": DichVuPhieu(
        "CLS_SIEU_AM_O_BUNG", "Siêu âm ổ bụng", "DICHVU-SIEUAM", 250000
    ),
    "SÂ tuyến vú": DichVuPhieu("CLS_SIEU_AM_VU", "Siêu âm vú", "DICHVU-SIEUAM", 200000),
    "SÂ tuyến giáp": DichVuPhieu(
        "CLS_SIEU_AM_TUYEN_GIAP", "Siêu âm tuyến giáp", "DICHVU-SIEUAM", 200000
    ),
    "SÂ dopper ĐM cảnh": DichVuPhieu(
        "CLS_SIEU_AM_DOPPLER_MACH_CANH",
        "Siêu âm doppler mạch cảnh",
        "DICHVU-SIEUAM",
        400000,
    ),
    "SÂ dopper ĐM thận": DichVuPhieu(
        "CLS_SIEU_AM_DOPPLER_DM_THAN",
        "Siêu âm doppler ĐM thận",
        "DICHVU-SIEUAM",
        400000,
    ),
    "SÂ dopper âm vật": DichVuPhieu(
        "CLS_SIEU_AM_DOPPLER_AM_VAT", "Siêu âm doppler âm vật", "DICHVU-SIEUAM", 150000
    ),
    # "3D sàn chậu" trong danh mục cũ có thể là cùng dịch vụ — KHÔNG đoán, thêm
    # mã riêng; phòng khám gộp sau nếu đúng là một.
    "SÂ dopper 4D sàn chậu": DichVuPhieu(
        "CLS_SIEU_AM_4D_SAN_CHAU",
        "Siêu âm doppler 4D sàn chậu",
        "DICHVU-SIEUAM",
        500000,
        "Sàn chậu",
    ),
    "SÂ Doppler dương vật": DichVuPhieu(
        "CLS_SIEU_AM_DOPPLER_DUONG_VAT",
        "Siêu âm Doppler dương vật",
        "DICHVU-SIEUAM",
        300000,
        "Nam khoa",
    ),
    "SÂ Doppler tinh hoàn": DichVuPhieu(
        "CLS_SIEU_AM_TINH_HOAN", "Siêu âm tinh hoàn / Doppler", "DICHVU-SIEUAM", 350000
    ),
    "Đo cơ lực âm đạo bằng máy (sàng lọc)": DichVuPhieu(
        "CLS_DO_CO_LUC_AM_DAO",
        "Đo cơ lực âm đạo bằng máy (sàng lọc)",
        "DICHVU-THUTHUAT",
        300000,
        "Sàn chậu",
    ),
    "• Yếu cơ": DichVuPhieu(
        "CLS_GHE_DTT_YEU_CO",
        "Trải nghiệm 5 phút ghế ĐTT — yếu cơ",
        "DICHVU-THUTHUAT",
        150000,
        "Sàn chậu",
    ),
    "• Đau cơ": DichVuPhieu(
        "CLS_GHE_DTT_DAU_CO",
        "Trải nghiệm 5 phút ghế ĐTT — đau cơ",
        "DICHVU-THUTHUAT",
        150000,
        "Sàn chậu",
    ),
    "Khám sàn chậu": DichVuPhieu(
        "CLS_KHAM_SAN_CHAU", "Khám sàn chậu", "DICHVU-THUTHUAT", 300000, "Sàn chậu"
    ),
    "XQ vú (chụp vú ép)": DichVuPhieu(
        "CLS_CHUP_VU_EP", "Chụp vú ép", "DICHVU-HINHANH-NGOAI", 500000
    ),
    "MRI tuyến vú": DichVuPhieu(
        "CLS_CHUP_MRI_VU", "Chụp MRI vú", "DICHVU-HINHANH-NGOAI", 2500000
    ),
    "XQ TC – vòi trứng": DichVuPhieu(
        "CLS_CHUP_TU_CUNG_VOI_TRUNG",
        "Chụp tử cung – vòi trứng",
        "DICHVU-HINHANH-NGOAI",
        1200000,
    ),
}

#: Mục F: mã thủ thuật nguồn (`procedure_N`) → dịch vụ.
THU_THUAT: dict[str, DichVuPhieu] = {
    "procedure_1": DichVuPhieu(
        "CLS_DAT_VONG_NOI_TIET", "Đặt vòng nội tiết", "DICHVU-THUTHUAT", 5000000
    ),
    "procedure_2": DichVuPhieu("CLS_THAO_VONG", "Tháo vòng", "DICHVU-THUTHUAT", 350000),
    "procedure_3": DichVuPhieu(
        "CLS_CAY_QUE_TRANH_THAI", "Cấy que tránh thai", "DICHVU-THUTHUAT", 2600000
    ),
    "procedure_4": DichVuPhieu(
        "CLS_THAO_QUE_TRANH_THAI", "Tháo que tránh thai", "DICHVU-THUTHUAT", 700000
    ),
    "procedure_5": DichVuPhieu(
        "CLS_SOI_BUONG_TU_CUNG", "Soi buồng tử cung", "DICHVU-THUTHUAT", 6000000
    ),
    "procedure_6": DichVuPhieu(
        "CLS_HUT_BUONG_TU_CUNG", "Hút buồng tử cung", "DICHVU-THUTHUAT", 2000000
    ),
    "procedure_7": DichVuPhieu(
        "CLS_SOI_CO_TU_CUNG", "Soi cổ tử cung", "DICHVU-SANGLOC-COTUCUNG", 400000
    ),
    "procedure_8": DichVuPhieu("CLS_SOI_AM_HO", "Soi âm hộ", "DICHVU-THUTHUAT", 250000),
    "procedure_9": DichVuPhieu(
        "CLS_NONG_BAO_QUY_DAU_AV", "Nong bao quy đầu âm vật", "DICHVU-THUTHUAT", 1000000
    ),
    "procedure_10": DichVuPhieu(
        "CLS_TACH_BAO_QUY_DAU_AV", "Tách bao quy đầu âm vật", "DICHVU-THUTHUAT", 7000000
    ),
    # Danh mục cũ có "Biofeedback cơ bản / nâng cao" (giá khác nhau): phiếu chỉ
    # ghi "Biofeedback" 900k — không đoán là gói nào, thêm mã riêng.
    "procedure_11": DichVuPhieu(
        "CLS_BIOFEEDBACK", "Biofeedback", "DICHVU-THUTHUAT", 900000, "Sàn chậu"
    ),
    "procedure_12": DichVuPhieu(
        "CLS_GHE_DTT", "Ghế điện từ trường (ĐTT)", "DICHVU-THUTHUAT", 500000, "Sàn chậu"
    ),
    "procedure_13": DichVuPhieu(
        "CLS_LASER", "Laser sàn chậu", "DICHVU-THUTHUAT", 7000000, "Sàn chậu"
    ),
    "procedure_14": DichVuPhieu(
        "CLS_LASER_TRE_HOA", "Laser trẻ hoá", "DICHVU-THUTHUAT", 7000000, "Sàn chậu"
    ),
    "procedure_15": DichVuPhieu(
        "CLS_LASER_ST_SSD", "Laser ST/SSD", "DICHVU-THUTHUAT", 15000000, "Sàn chậu"
    ),
}

#: Mẫu thuốc nguồn → `drug_catalog.name_raw` NGUYÊN VĂN (không có = tên thô).
THUOC: dict[str, str] = {
    "rx_001": "Venice 5MTHF",
    "rx_002": "Androgel",
    "rx_003": "Aspilet",
    "rx_004": "Assimicin",
    "rx_005": "Flepgo 100mg",
    "rx_006": "Benate fort oinment",
    "rx_007": "Besuto gold mama",
    "rx_008": "Betmiga 50mg",
    "rx_009": "Canesten cream 20g",
    "rx_010": "Ecanix D3",
    "rx_011": "Cavidagel",
    "rx_012": "Cefnirvid 300 (cefdinir)",
    "rx_013": "Cetrotide",
    "rx_014": "Coq10 blackmores",
    "rx_015": "Cumlaude lubripiu (B)",
    "rx_016": "Cumlaude lab lubripiu viên đặt",
    "rx_017": "Cumlaude prebiotic",
    "rx_018": "DHA NataPure",
    "rx_019": "DHEA Avemos",
    "rx_020": "Daikyn 0.5mg (estriol)",
    "rx_021": "Dalacin C",
    "rx_022": "Dermolivo viên đặt",
    "rx_023": "Dermolivo gel",
    "rx_024": "Diane",
    "rx_025": "Dienosis 2mg hộp 28 viên",
    "rx_026": "Difavon",
    "rx_027": "Diflucan",
    "rx_028": "Dipherelin 3.75",
    "rx_029": "Docyxycline",
    "rx_030": "Dunium (clomiphen citrat)",
    "rx_031": "Dunium (clomiphen citrat)",
    "rx_032": "Duphaston",
    "rx_033": "durapil",
    "rx_034": "Estrogel",
    "rx_035": "Estrogel pump",
    "rx_036": "Eulac",
    "rx_037": "Fersen",
    "rx_038": "Femoston 1/10",
    "rx_039": "Femoston 1/5",
    "rx_040": "Filrosy (progesteron 200mg)",
    "rx_041": "Fluconazole",
    "rx_042": "Folic mum",
    "rx_043": "Follitrope",
    "rx_044": "Fosamax plus 70mg/2800iu",
    "rx_045": "Gemapaxane",
    "rx_046": "Glucophage XR 750mg",
    "rx_047": "GonalF",
    "rx_048": "Ivf C 5000",
    "rx_049": "IVF M 150",
    "rx_050": "Indurat 5mg",
    "rx_051": "Intimate",
    "rx_052": "Aktiv isoflavon",
    "rx_053": "Kofio (estriol)",
    "rx_054": "Letrozole (Femara) (10v/15v)",
    "rx_055": "Levina 5",
    "rx_056": "Lomexin 200mg",
    "rx_057": "Magnella",
    "rx_058": "Meclon",
    "rx_059": "Mensterona",
    "rx_060": "Metronidazol",
    "rx_061": "Viên đặt nystatin 100.000ui",
    "rx_062": "Ovagrow",
    "rx_063": "Ovitrelle",
    "rx_064": "Pruzena",
    "rx_065": "Tadalafin 5mg",
    "rx_066": "Usartestos",
    "rx_067": "Utrogestan 100mg",
    "rx_068": "Utrogestan 200",
    "rx_069": "Valiera",
    "rx_070": "Vitcofol",
    "rx_071": "Yspuripax",
    "rx_072": "Zincodin",
    "rx_073": "Zolmed",
}


def tat_ca_dich_vu() -> list[DichVuPhieu]:
    """Mỗi mã một lần (hai nhãn có thể trỏ cùng một dịch vụ)."""
    ra: dict[str, DichVuPhieu] = {}
    for d in (*CLS.values(), *THU_THUAT.values()):
        ra.setdefault(d.ma, d)
    return list(ra.values())


__all__ = ["CLS", "THUOC", "THU_THUAT", "DichVuPhieu", "tat_ca_dich_vu"]
