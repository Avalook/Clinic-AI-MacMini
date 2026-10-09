#!/usr/bin/env python3
# ruff: noqa: E501 — câu mẫu lâm sàng dài, cắt dòng làm khó đối chiếu với PDF
"""Dựng RUỘT 18 mẫu kết quả (khung v2) — theo mẫu phòng khám đang dùng thật.

Tuyền 23/09/2026 khuya: "các form này nó lặp lại, họ muốn mặc định là điền sẵn,
họ sửa lại rồi lưu rồi in được và nó đồng bộ sang bác sĩ chính … nếu muốn chắc
hơn thì xem các file pdf".

NGUỒN: 16 PDF mẫu kết quả (xuất từ Notion của phòng khám, ~/Downloads/Dr4women)
là CHUẨN — chi tiết hơn chi-dinh.html. chi-dinh.html chỉ dùng cho các ô chọn
(BI-RADS, TIRADS, loại song thai, Oxford) và 3 mẫu xét nghiệm (không có PDF mẫu).

    python3 scripts/phieu-kham/dung-mau-ket-qua.py

Ghi `src/clinicai/phieu_kham/mau_ket_qua.json`. Sửa nội dung = sửa file này rồi
chạy lại + xuất bản bản mới (migration mới); không sửa tay JSON.

BA LUẬT CỐ Ý (vì an toàn lâm sàng, không phải vì tiện):
  * CÂU BÌNH THƯỜNG → điền sẵn (`mac_dinh`, nguồn TEMPLATE_DEFAULT). Hoàn tất =
    người ký nhận CẢ câu mẫu — engine đổi nguồn sang USER lúc bấm.
  * SỐ ĐO và CÂU CỦA RIÊNG MỘT BỆNH NHÂN ("dính 50%", "có 01 nang thứ cấp") →
    KHÔNG điền sẵn, chỉ gợi ý đơn vị. In ra một con số không ai đo là nguy hiểm.
  * XÉT NGHIỆM (HPV, PCR, tổng quát) KHÔNG điền sẵn "ÂM TÍNH": kết quả xét nghiệm
    điền sẵn là một kết quả giả chờ người bấm nhầm Hoàn tất.
Không có khung thông tin bệnh nhân / chữ ký: hệ thống in từ hồ sơ.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RA = Path(__file__).resolve().parents[2] / "src/clinicai/phieu_kham/mau_ket_qua.json"

O = dict[str, Any]  # noqa: E741 — "ô" của phiếu

#: `goi_y` là ĐƠN VỊ THUẦN → ô mang thêm `don_vi` (in "89.6 mm"); cùng danh sách
#: với migration 20261009300000_o_tuy_chon_don_vi.sql.
DON_VI_THUAN = {
    "mm",
    "cm",
    "cm/s",
    "chu kỳ/phút",
    "lần/phút",
    "điểm",
    "%",
    "ml",
    "gram",
    "grams",
}


def chu(ma: str, ten: str, mac_dinh: str = "", goi_y: str = "") -> O:
    o: O = {"ma": ma, "ten": ten, "kieu": "text"}
    if mac_dinh:
        o["mac_dinh"] = mac_dinh
    if goi_y:
        o["goi_y"] = goi_y
    if goi_y in DON_VI_THUAN:
        o["don_vi"] = goi_y
    return o


def doan(ma: str, ten: str, mac_dinh: str = "", goi_y: str = "") -> O:
    o = chu(ma, ten, mac_dinh, goi_y)
    o["kieu"] = "doan_van"
    o.pop("don_vi", None)  # đoạn văn không có đơn vị
    return o


def chon(ma: str, ten: str, ds: list[str], mac_dinh: str = "") -> O:
    o: O = {"ma": ma, "ten": ten, "kieu": "chon", "chon": ds}
    if mac_dinh:
        o["mac_dinh"] = mac_dinh
    return o


def muc(ma: str, ten: str, *block: O) -> O:
    return {"ma": ma, "ten": ten, "block": list(block)}


def khac(mac_dinh: str = "Không.") -> O:
    return muc(
        "hinh_anh_khac",
        "Hình ảnh khác",
        doan("hinh_anh_khac", "Hình ảnh khác", mac_dinh),
    )


def ket_luan(mac_dinh: str = "") -> O:
    return muc("ket_luan", "Kết luận", doan("ket_luan", "Kết luận", mac_dinh))


def de_nghi() -> O:
    # Tuỳ chọn: để trống không bị nhắc "còn trống" lúc Hoàn tất (09/10/2026).
    return muc(
        "de_nghi", "Đề nghị", {**doan("de_nghi", "Đề nghị / lời dặn"), "tuy_chon": True}
    )


MM = "mm"
BT = "Bình thường."
NHU_MO = "Nhu mô đều. Không thấy khối khu trú."
TUOI_MAU = "Không thấy bất thường tưới máu."
DONG_CHAY = "Tốc độ dòng chảy trong giới hạn bình thường, không có mảng vữa xơ."
THANH_MACH = (
    "Không thấy mảng vữa xơ, không thấy huyết khối bám thành. "
    "Thành mạch liên tục, không thấy lóc tách."
)
TU_THE = ["Ngả trước", "Ngả sau", "Trung gian"]
AM_DUONG = ["ÂM TÍNH", "DƯƠNG TÍNH"]


def ben(tien_to: str, ten: str, *o: O) -> list[O]:
    """Cùng bộ ô cho hai bên / hai thai: khoá có tiền tố, nhãn có tên bên."""
    return [
        {**x, "ma": f"{tien_to}_{x['ma']}", "ten": f"{ten} — {x['ten']}"} for x in o
    ]


def thong_so_thai(efw: str) -> list[O]:
    return [
        chu("crl", "Chiều dài đầu mông (CRL)", goi_y=MM),
        chu("ga", "Tuổi thai ước tính (GA)", goi_y="… tuần … ngày"),
        chu("edd", "Dự kiến sinh", goi_y="dd/mm/yyyy"),
        chu("fhr", "Tim thai (FHR)", goi_y="… chu kỳ/phút"),
        chu("nt", "Độ mờ da gáy (NT)", goi_y=MM),
        chu("bpd", "Đường kính lưỡng đỉnh (BPD)", goi_y=MM),
        chu("hc", "Chu vi vòng đầu (HC)", goi_y=MM),
        chu("ac", "Chu vi vòng bụng (AC)", goi_y=MM),
        chu("fl", "Chiều dài xương đùi (FL)", goi_y=MM),
        chu("efw", "Cân nặng ước tính (EFW)", goi_y=efw),
    ]


def sinh_trac_q23() -> list[O]:
    return [
        chu("vp", "Kích thước não thất bên (Vp)", BT),
        chu("tieu_nao", "Đường kính tiểu não (Cerebellum)", BT),
        chu("ho_sau", "Hố sau (CM)", BT),
        chu("bod", "Đường kính hai hốc mắt (BOD)", BT),
        chu("nbl", "Độ dài xương mũi (NBL)", BT),
        chu("hl", "Độ dài xương cánh tay (HL)", BT),
    ]


PHAN_PHU_THAI = [
    chu("nhau_thai", "Nhau thai", "Không thấy máu tụ sau nhau. Độ dày bình thường."),
    chu(
        "day_ron", "Dây rốn", "2 động mạch, 1 tĩnh mạch, hiện tại chưa thấy bất thường."
    ),
    chu("nuoc_oi", "Nước ối", "Chưa thấy bất thường."),
]

MAU: dict[str, tuple[str, list[O]]] = {
    "KQ_SA_OBUNG": (
        "Kết quả siêu âm ổ bụng",
        [
            muc(
                "mo_ta",
                "Mô tả hình ảnh",
                doan(
                    "gan",
                    "Gan",
                    "Kích thước bình thường, nhu mô đều, không có hình khối khu trú bất "
                    "thường. Tĩnh mạch cửa không giãn, không có huyết khối. Đường mật trong "
                    "và ngoài gan không giãn.",
                ),
                chu(
                    "tui_mat",
                    "Túi mật",
                    "Không giãn, thành mỏng, dịch mật trong, không có sỏi.",
                ),
                chu(
                    "tuy",
                    "Tụy",
                    "Kích thước bình thường, nhu mô đều, ống tụy không giãn.",
                ),
                chu(
                    "lach", "Lách", "Kích thước bình thường, nhu mô đều, không có khối."
                ),
                doan(
                    "than_phai",
                    "Thận phải",
                    "Kích thước bình thường, nhu mô đều và dày bình thường. Đài bể thận không "
                    "giãn, niệu quản không giãn, không có sỏi.",
                ),
                doan(
                    "than_trai",
                    "Thận trái",
                    "Kích thước bình thường, nhu mô đều và dày bình thường. Đài bể thận không "
                    "giãn, niệu quản không giãn, không có sỏi.",
                ),
                chu("bang_quang", "Bàng quang", "Thành mỏng, không có sỏi."),
                chu("tieu_khung", "Tiểu khung", "Không thấy khối bất thường."),
            ),
            khac(),
            ket_luan("Hiện tại không thấy bất thường trên hình ảnh siêu âm ổ bụng."),
            de_nghi(),
        ],
    ),
    "KQ_SA_VU": (
        "Kết quả siêu âm tuyến vú",
        [
            muc(
                "mo_ta",
                "Mô tả hình ảnh tuyến vú",
                *ben(
                    "trai",
                    "Bên trái",
                    chu("nhu_mo", "Nhu mô", NHU_MO),
                    chu("tuoi_mau", "Tưới máu", TUOI_MAU),
                ),
                *ben(
                    "phai",
                    "Bên phải",
                    chu("nhu_mo", "Nhu mô", NHU_MO),
                    chu("tuoi_mau", "Tưới máu", TUOI_MAU),
                ),
                chu("ho_nach", "Hố nách hai bên", "Không thấy hạch to bất thường."),
                chon(
                    "birads",
                    "Phân loại BI-RADS",
                    [
                        "BI-RADS 1: Bình thường",
                        "BI-RADS 2: Tổn thương lành tính",
                        "BI-RADS 3: Khả năng lành tính (>98%)",
                        "BI-RADS 4: Nghi ngờ ác tính",
                    ],
                    "BI-RADS 1: Bình thường",
                ),
            ),
            khac(),
            ket_luan("Hiện tại không thấy bất thường hình ảnh tuyến vú."),
            de_nghi(),
        ],
    ),
    "KQ_SA_GIAP": (
        "Kết quả siêu âm tuyến giáp",
        [
            muc(
                "mo_ta",
                "Mô tả hình ảnh tuyến giáp",
                *ben(
                    "trai",
                    "Thùy trái",
                    chu("nhu_mo", "Nhu mô", NHU_MO),
                    chu("tuoi_mau", "Tưới máu", TUOI_MAU),
                ),
                *ben(
                    "phai",
                    "Thùy phải",
                    chu("nhu_mo", "Nhu mô", NHU_MO),
                    chu("tuoi_mau", "Tưới máu", TUOI_MAU),
                ),
                chu("eo", "Eo tuyến", "Nhu mô đều, không thấy khối khu trú."),
                chu("hach_co", "Hạch cổ hai bên", "Không thấy hạch to bất thường."),
                chon(
                    "tirads",
                    "Phân loại TIRADS",
                    [
                        "TIRADS 1: Tuyến giáp bình thường",
                        "TIRADS 2: Lành tính",
                        "TIRADS 3: Khả năng lành tính",
                        "TIRADS 4: Nghi ngờ",
                    ],
                    "TIRADS 1: Tuyến giáp bình thường",
                ),
            ),
            khac(),
            ket_luan("Hiện tại không thấy bất thường hình ảnh tuyến giáp."),
            de_nghi(),
        ],
    ),
    "KQ_SA_MACH_CANH": (
        "Kết quả siêu âm động mạch cảnh",
        [
            *[
                muc(
                    t,
                    ten,
                    *ben(
                        t,
                        ten,
                        chu("cca", "Động mạch cảnh chung (CCA)", DONG_CHAY),
                        chu("hanh_canh", "Hành cảnh", DONG_CHAY),
                        chu("ica", "Động mạch cảnh trong (ICA)", DONG_CHAY),
                        chu("va", "Động mạch đốt sống (VA)", DONG_CHAY),
                    ),
                )
                for t, ten in (("trai", "Bên trái"), ("phai", "Bên phải"))
            ],
            khac(),
            ket_luan(
                "Hiện tại hình ảnh phổ sóng và tốc độ dòng chảy hệ thống động mạch cảnh "
                "hai bên trong giới hạn bình thường."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_MACH_THAN": (
        "Kết quả siêu âm động mạch thận",
        [
            *[
                muc(
                    t,
                    ten,
                    *ben(
                        t,
                        ten,
                        *[
                            x
                            for d, dten in (
                                ("goc", "Đoạn gốc"),
                                ("ron", "Đoạn rốn thận"),
                                ("nhu_mo", "Đoạn nhu mô"),
                            )
                            for x in (
                                chu(f"{d}_psv", f"{dten} — PSV", goi_y="cm/s"),
                                chu(f"{d}_edv", f"{dten} — EDV", goi_y="cm/s"),
                                chu(f"{d}_ri", f"{dten} — RI", goi_y="0.xx"),
                            )
                        ],
                        chu("thanh_mach", "Thành mạch", THANH_MACH),
                    ),
                )
                for t, ten in (
                    ("trai", "Động mạch thận trái"),
                    ("phai", "Động mạch thận phải"),
                )
            ],
            khac(),
            ket_luan(
                "Hiện tại hình ảnh phổ sóng và tốc độ dòng chảy hệ thống động mạch thận "
                "hai bên trong giới hạn bình thường."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_DOPPLER_AM_VAT": (
        "Siêu âm Doppler âm vật",
        [
            muc(
                "am_vat",
                "Siêu âm âm vật",
                chu(
                    "cau_truc",
                    "Cấu trúc",
                    "Không thấy bất thường cấu trúc quy đầu âm vật, thân âm vật, hành tiền "
                    "đình và thể hang âm vật.",
                ),
                chu("vat_hang_phai", "Vật hang — bên phải", goi_y="… x … mm"),
                chu("vat_hang_trai", "Vật hang — bên trái", goi_y="… x … mm"),
                chu("vat_xop_phai", "Vật xốp — bên phải", goi_y="… x … mm"),
                chu("vat_xop_trai", "Vật xốp — bên trái", goi_y="… x … mm"),
                chu("than_am_vat", "Thân âm vật", goi_y="… x … mm"),
            ),
            muc(
                "dm_vat_hang",
                "ĐM vật hang",
                *[
                    x
                    for t, ten in (("phai", "Bên phải"), ("trai", "Bên trái"))
                    for x in ben(
                        t,
                        ten,
                        chu("vmax", "Vmax", goi_y="cm/s"),
                        chu("ri", "RI", goi_y="0.xx"),
                        chu("pho", "Phổ Doppler", "Dạng một pha đỉnh nhọn."),
                    )
                ],
            ),
            khac(),
            ket_luan(
                "Cấu trúc giải phẫu và tuần hoàn âm vật trong giới hạn bình thường."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_TINH_HOAN": (
        "Kết quả siêu âm tinh hoàn",
        [
            *[
                muc(
                    t,
                    ten,
                    *ben(
                        t,
                        ten,
                        chu("kich_thuoc", "Kích thước", goi_y="… x … x … mm"),
                        chu("mao_tinh", "Mào tinh hoàn", "Không thấy bất thường."),
                        chu("nhu_mo", "Nhu mô", "Đồng nhất, không thấy khối khu trú."),
                        chu("tm_truoc", "TM thừng tinh trước Valsalva", goi_y=MM),
                        chu("tm_sau", "TM thừng tinh sau Valsalva", goi_y=MM),
                        chu(
                            "trao_nguoc",
                            "Dòng trào ngược",
                            "Không thấy dòng trào ngược.",
                        ),
                    ),
                )
                for t, ten in (("trai", "Tinh hoàn trái"), ("phai", "Tinh hoàn phải"))
            ],
            khac(),
            ket_luan(
                "Hình ảnh siêu âm tinh hoàn hai bên hiện tại không thấy bất thường."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_TC_BT": (
        "Kết quả siêu âm tử cung buồng trứng",
        [
            muc(
                "mo_ta",
                "Mô tả hình ảnh",
                chu(
                    "buong_trung_trai",
                    "Buồng trứng trái",
                    "Sơ bộ chưa thấy bất thường.",
                ),
                chu(
                    "buong_trung_phai",
                    "Buồng trứng phải",
                    "Sơ bộ chưa thấy bất thường.",
                ),
                chu("hinh_thai_tc", "Hình thái tử cung", BT),
                chon("tu_the", "Tư thế tử cung", TU_THE, "Ngả trước"),
                chu(
                    "co_tc",
                    "Cơ tử cung",
                    "Tương đối đồng nhất, không thấy khối bất thường.",
                ),
                chu("niem_mac", "Niêm mạc tử cung", goi_y=MM),
                chu("douglas", "Túi cùng Douglas", "Không có dịch."),
            ),
            khac(),
            ket_luan("Hiện tại không thấy bất thường hình ảnh tử cung buồng trứng."),
            de_nghi(),
        ],
    ),
    "KQ_SA_TC_PP": (
        "Kết quả siêu âm tử cung phần phụ",
        [
            muc(
                "mo_ta",
                "Mô tả hình ảnh",
                chon("tu_the", "Tư thế tử cung", TU_THE, "Ngả trước"),
                chu(
                    "hinh_thai_tc",
                    "Hình thái tử cung",
                    "Bình thường, kích thước không to.",
                ),
                chu(
                    "co_tc",
                    "Cơ tử cung",
                    "Tương đối đồng nhất, không thấy khối bất thường.",
                ),
                chu("niem_mac", "Niêm mạc tử cung", goi_y=MM),
                chu(
                    "buong_trung_phai",
                    "Buồng trứng phải",
                    "Sơ bộ chưa thấy bất thường.",
                ),
                chu(
                    "buong_trung_trai",
                    "Buồng trứng trái",
                    "Sơ bộ chưa thấy bất thường.",
                ),
            ),
            khac("Túi cùng Douglas không có dịch."),
            ket_luan("Hiện tại không thấy bất thường hình ảnh tử cung phần phụ."),
            de_nghi(),
        ],
    ),
    "KQ_SA_THAI_SOM": (
        "Kết quả siêu âm thai sớm (dưới 11 tuần)",
        [
            muc(
                "mo_ta",
                "Mô tả hình ảnh",
                chu("so_luong_thai", "Số lượng thai trong buồng tử cung", "01 thai"),
                chu("crl", "Chiều dài đầu mông (CRL)", goi_y=MM),
                chu("ga", "Tuổi thai ước tính (GA)", goi_y="… tuần … ngày"),
                chu("edd", "Dự kiến sinh", goi_y="dd/mm/yyyy"),
                chu("fhr", "Tim thai (FHR)", "Dương tính"),
            ),
            khac("Không thấy tụ dịch dưới màng nuôi."),
            ket_luan(
                "Hình ảnh 01 thai trong buồng tử cung, tương đương … tuần … ngày. "
                "Tim thai dương tính."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_THAI_QUY_1": (
        "Kết quả siêu âm thai quý I",
        [
            muc(
                "tham_so",
                "Tham số sinh học",
                chu("so_luong_thai", "Số lượng thai trong buồng tử cung", "01 thai"),
                *thong_so_thai("… ± … grams"),
                chu("nbl", "Độ dài xương mũi (NBL)", goi_y=MM),
            ),
            muc(
                "hinh_thai",
                "Hình thái thai nhi",
                doan(
                    "dau_mat_co",
                    "Đầu mặt cổ",
                    "Đường giữa cân đối. Đám rối mạch mạc lấp đầy não thất bên. Hố sau bình "
                    "thường. Không có khuyết hàm trên.",
                ),
                doan(
                    "nguc_bung_tu_chi",
                    "Ngực - bụng và tứ chi",
                    "Lồng ngực cân đối. Mỏm tim quay trái. Thành bụng liên tục. Đủ 4 chi.",
                ),
            ),
            khac("Nhau thai bám rộng. Khảo sát Doppler không thấy bất thường."),
            ket_luan(
                "Hình ảnh 01 thai trong buồng tử cung, tương đương … tuần … ngày. "
                "Tim thai dương tính, cử động thai tốt."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_THAI_QUY_23": (
        "Kết quả siêu âm thai quý II - III",
        [
            muc(
                "tham_so",
                "Tham số sinh học",
                chu("so_luong_thai", "Số lượng thai trong buồng tử cung", "01 thai"),
                chu("ga", "Tuổi thai ước tính (GA)", goi_y="… tuần … ngày"),
                chu("edd", "Dự kiến sinh (theo quý I)", goi_y="dd/mm/yyyy"),
                chu("fhr", "Tim thai (FHR)", goi_y="… chu kỳ/phút"),
                chu("ngoi_thai", "Ngôi thai"),
                chu("bpd", "Đường kính lưỡng đỉnh (BPD)", goi_y=MM),
                chu("hc", "Chu vi vòng đầu (HC)", goi_y=MM),
                chu("ac", "Chu vi vòng bụng (AC)", goi_y=MM),
                chu("fl", "Chiều dài xương đùi (FL)", goi_y=MM),
                chu("efw", "Cân nặng ước tính (EFW)", goi_y="… ± … grams"),
            ),
            muc(
                "hinh_thai",
                "Hình thái thai nhi",
                *sinh_trac_q23(),
                doan(
                    "dau_mat_co",
                    "Đầu mặt cổ",
                    "Hai bán cầu đại não cân đối. Hộp vách trong suốt rõ. Xương vòm sọ liên "
                    "tục. Môi trên liên tục. Nhãn cầu cân đối, thủy tinh thể rõ.",
                ),
                doan(
                    "tim_long_nguc",
                    "Tim và lồng ngực",
                    "Lồng ngực cân đối. Mỏm tim quay trái, đủ 4 buồng tim, đại động mạch bắt "
                    "chéo.",
                ),
                chu("o_bung", "Ổ bụng", "Bóng dạ dày rõ. Quan sát thấy thận hai bên."),
                chu(
                    "tu_chi",
                    "Tứ chi",
                    "Đủ 4 chi. Bàn tay tư thế nắm. Sơ bộ chưa thấy bất thường trục chi.",
                ),
            ),
            muc("phan_phu", "Phần phụ thai nhi", *PHAN_PHU_THAI),
            khac("Khảo sát Doppler chưa thấy bất thường."),
            ket_luan(
                "Hình ảnh 01 thai trong buồng tử cung. Tim thai dương tính, cử động thai "
                "tốt."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_SONG_THAI_QUY_1": (
        "Kết quả siêu âm song thai quý I",
        [
            muc(
                "chung",
                "Mô tả hình ảnh",
                chu("so_luong_thai", "Số lượng thai trong buồng tử cung", "02 thai"),
                chon(
                    "loai_song_thai",
                    "Loại song thai",
                    [
                        "1 bánh nhau - 2 buồng ối (MCDA)",
                        "2 bánh nhau - 2 buồng ối (DCDA)",
                        "1 bánh nhau - 1 buồng ối (MCMA)",
                    ],
                ),
            ),
            *[
                muc(
                    f"thai_{t}",
                    f"Thai {t.upper()}",
                    *ben(
                        t,
                        f"Thai {t.upper()}",
                        *thong_so_thai("… ± 200 grams"),
                        doan(
                            "dau_mat_co",
                            "Đầu mặt cổ",
                            "Xương sọ bình thường. Đường giữa bình thường. Đám rối mạch mạc "
                            "lấp đầy não thất bên. Quan sát rõ các cấu trúc Thalamus, "
                            "Midbrain, Brainstem. Hố sau bình thường. Chỉ số BS/BSOB < 1. "
                            "Không có khuyết hàm trên. Độ dài xương mũi (NBL) bình thường. "
                            "Góc FMF < 85°. Chỉ số PT/NBL < 0.6. IT (não thất IV) < 2.5 mm.",
                        ),
                        doan(
                            "lung_nguc_bung_chi",
                            "Vùng lưng, ngực - bụng và tứ chi",
                            "Cột sống bình thường. Da vùng lưng liên tục. Hai trường phổi cân "
                            "đối. Không thấy mass lồng ngực. Không thấy tràn dịch vùng ngực. "
                            "Hình dạ dày góc trên trái. Thành bụng liên tục. Không thấy thoát "
                            "vị thành bụng. Đủ 4 chi. Mỗi chi đủ 3 đoạn.",
                        ),
                    ),
                )
                for t in ("a", "b")
            ],
            khac("Nhau thai bám rộng."),
            ket_luan(
                "Song thai sống phát triển đồng đều, NT trong giới hạn bình thường."
            ),
            de_nghi(),
        ],
    ),
    "KQ_SA_SONG_THAI_QUY_23": (
        "Kết quả siêu âm song thai quý II - III",
        [
            muc(
                "chung",
                "Mô tả hình ảnh",
                chu("so_luong_thai", "Số lượng thai trong buồng tử cung", "02 thai"),
            ),
            *[
                muc(
                    f"thai_{t}",
                    f"Thai {t.upper()}",
                    *ben(
                        t,
                        f"Thai {t.upper()}",
                        chu("ga", "Tuổi thai ước tính (GA)", goi_y="… tuần … ngày"),
                        chu("edd", "Dự kiến sinh (theo quý I)", goi_y="dd/mm/yyyy"),
                        chu("fhr", "Tim thai (FHR)", goi_y="… chu kỳ/phút"),
                        chu("bpp", "Trắc đồ sinh vật lý (BPP)", goi_y="…/8"),
                        chu("ngoi_thai", "Ngôi thai"),
                        chu("bpd", "Đường kính lưỡng đỉnh (BPD)", goi_y=MM),
                        chu("hc", "Chu vi vòng đầu (HC)", goi_y=MM),
                        chu("ac", "Chu vi vòng bụng (AC)", goi_y=MM),
                        chu("fl", "Chiều dài xương đùi (FL)", goi_y=MM),
                        chu("efw", "Cân nặng ước tính (EFW)", goi_y="… ± 300 grams"),
                        *sinh_trac_q23(),
                        chu("foot", "Độ dài bàn chân (Foot)", BT),
                    ),
                )
                for t in ("a", "b")
            ],
            muc(
                "hinh_thai",
                "Hình thái thai nhi",
                chu("dau_mat_co", "Đầu mặt cổ hai thai", "Chưa thấy bất thường."),
                chu("tim_long_nguc", "Tim và lồng ngực", "Chưa thấy bất thường."),
                chu("o_bung", "Ổ bụng", "Chưa thấy bất thường."),
                chu("tu_chi", "Tứ chi", "Chưa thấy bất thường."),
            ),
            muc(
                "phan_phu",
                "Phần phụ thai nhi",
                chu(
                    "nhau_thai",
                    "Nhau thai",
                    "Không thấy máu tụ sau nhau. Độ dày bình thường.",
                ),
                chu(
                    "day_ron",
                    "Dây rốn hai thai",
                    "2 động mạch, 1 tĩnh mạch, hiện tại chưa thấy bất thường.",
                ),
                chu("nuoc_oi", "Nước ối", "Chưa thấy bất thường."),
                chu("doppler", "Khảo sát Doppler", "Sơ bộ chưa thấy bất thường."),
            ),
            khac(""),
            ket_luan("Hiện tại không thấy bất thường ở tuần thai này."),
            de_nghi(),
        ],
    ),
    "KQ_SOI_AM_HO": (
        "Phiếu soi âm hộ",
        [
            muc(
                "ket_qua",
                "Kết quả soi âm hộ",
                chu("quy_dau_am_vat", "Quy đầu âm vật", BT),
                chu("tien_dinh_am_ho", "Tiền đình âm hộ", BT),
                chu("test_ran", "Test rặn", "Không sa."),
                chon(
                    "oxford",
                    "Cơ lực âm đạo theo Oxford cải tiến",
                    ["Độ 0", "Độ 1", "Độ 2", "Độ 3", "Độ 4", "Độ 5"],
                ),
            ),
            ket_luan(),
            de_nghi(),
        ],
    ),
    "KQ_XN_HPV": (
        "Kết quả xét nghiệm HPV Genotype",
        [
            muc(
                "ket_qua",
                "Kết quả",
                # Sáu cột đúng như phiếu trả của đối tác (Multiplex Real-time PCR, 40 type).
                chon("hpv_16", "HPV type 16", AM_DUONG),
                chon("hpv_18", "HPV type 18", AM_DUONG),
                chon("nguy_co_cao_khac", "18 type HPV nguy cơ cao khác", AM_DUONG),
                chon("hpv_6", "HPV type 6", AM_DUONG),
                chon("hpv_11", "HPV type 11", AM_DUONG),
                chon("nguy_co_thap_khac", "18 type HPV nguy cơ thấp khác", AM_DUONG),
            ),
            ket_luan(),
            de_nghi(),
        ],
    ),
    "KQ_XN_PCR_STDS": (
        "KQXN PCR 13 tác nhân gây bệnh lây truyền tình dục",
        [
            muc(
                "ket_qua",
                "Kết quả",
                doan(
                    "ket_qua_chi_tiet",
                    "Kết quả 13 tác nhân",
                    goi_y="Ghi từng tác nhân dương tính; tệp của đối tác đính kèm ở Ảnh · tệp",
                ),
            ),
            ket_luan(),
            de_nghi(),
        ],
    ),
    "KQ_XN_TONG_QUAT": (
        "Phiếu kết quả xét nghiệm Tổng Quát (TrueMedicine)",
        [
            muc(
                "ket_qua",
                "Kết quả",
                doan(
                    "ket_qua_chi_tiet",
                    "Kết quả chi tiết",
                    goi_y="Tệp của đối tác đính kèm ở Ảnh · tệp; ghi chỉ số bất thường",
                ),
            ),
            ket_luan(),
            de_nghi(),
        ],
    ),
}


def main() -> None:
    ra: dict[str, Any] = {}
    for form_id, (ten, khung) in MAU.items():
        ma = [b["ma"] for m in khung for b in m["block"]]
        assert len(ma) == len(set(ma)), f"{form_id}: khoá ô trùng"
        ra[form_id] = {"ten": ten, "khung": khung}
    RA.write_text(
        json.dumps({"mau": ra}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    tong = sum(len(m["block"]) for v in ra.values() for m in v["khung"])
    print(f"{len(ra)} mẫu, {tong} ô → {RA}")


if __name__ == "__main__":
    main()
