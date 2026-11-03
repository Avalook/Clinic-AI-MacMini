"""Khối DÒNG TIỀN của báo cáo cuối ngày (Tuyền chốt 14/10/2026 — kế hoạch G4a).

Chỉ cộng những gì ĐÃ GHI: lần thu / huỷ / hoàn của tập báo cáo (đã lọc quyền,
ngày, ca, cơ sở) + sổ nợ hai chiều (`so_no`) của cùng khoảng. Không có số trôi:
nợ của kỳ là dòng sổ ghi trong kỳ, mở lại kỳ cũ không đổi.

Công thức khách đưa (recap 13/10/2026), đúng theo từng số:

    Thực thu        = Tổng thu về − Trả lại − Nợ − Giảm giá + Nợ thu được
    Doanh thu thuần = Tổng thu về − Giảm giá − Trả lại

  Mỗi khoản tính vào NGÀY NÓ XẢY RA (thu: giờ thu; huỷ: giờ huỷ; hoàn: giờ hoàn
  xong) — cùng luật màn Danh sách hoá đơn, nên hai màn ra cùng một số.

  * Tiền thu        = lần thu trong khoảng − phiếu huỷ trong khoảng (số SAU giảm).
  * Phiếu huỷ       = dòng RIÊNG: thao tác gạch lần thu bấm nhầm, không phải tiền
                      trả khách. Đã trừ ở Tiền thu; huỷ cùng ngày thì triệt tiêu.
  * Trả lại khách   = khoản hoàn ĐÃ XONG (hoàn đang chờ chỉ ghi chú).
  * Nợ              = nợ phát sinh trong kỳ trừ điều chỉnh (bỏ chỉ định sau khi
                      về, huỷ ghi nợ…) — từ sổ, không tính số dư đầu kỳ bật sổ.
  * Nợ thu được     = nợ giảm do lần thu trong kỳ (gồm cả phần giảm giá khi thu nợ).
  * Giảm giá        = giảm của lần thu còn hiệu lực (phiếu huỷ trừ ra).
  * Tổng thu về     = Tiền thu + Nợ + Giảm giá − Nợ thu được (giá trị hoá đơn
                      TRƯỚC giảm phát sinh trong kỳ; tiền thu nợ đã tính lúc ghi nợ).
  * Thực thu        = Tiền thu − Trả lại (tiền phòng khám đã cầm được).

"Tổng thu về" là chữ của recap 13/10 (bản 09:29 ghi "Dòng tiền vào" — đổi 03/11
vì kế toán hiểu "dòng tiền vào" là tiền thật, trong khi ô này là doanh thu gộp,
có cả nợ). Khoá JSON vẫn là ``dong_tien_vao``.

Nợ và Giảm giá không có tiền đi qua → không tách TM / CK. Sổ nợ tính chung dịch
vụ + thuốc: báo cáo lọc một loại thì không cộng sổ (Nợ = Nợ thu được = 0).
"""

from collections.abc import Mapping
from typing import Any


def _o(tong: int = 0, tm: int = 0, ck: int = 0) -> dict[str, int]:
    return {"tong": int(tong), "tien_mat": int(tm), "chuyen_khoan": int(ck)}


def dong_tien(bao_cao: Mapping[str, Any]) -> dict[str, Any]:
    """Các số của khối Dòng tiền + đối chiếu đẳng thức. Thuần."""
    tong = bao_cao.get("tong") or {}
    ht = {r["ma"]: r for r in bao_cao.get("theo_hinh_thuc", ())}

    def cot(ma: str, k: str) -> int:
        return int((ht.get(ma) or {}).get(k) or 0)

    def ck(k: str) -> int:
        return cot("TRANSFER", k) + cot("QR", k)

    phieu_huy = {
        **_o(int(tong.get("huy") or 0), cot("CASH", "huy"), ck("huy")),
        "so_phieu": int(tong.get("so_phieu_huy") or 0),
    }
    tien_thu = _o(
        int(tong.get("thu") or 0) - phieu_huy["tong"],
        cot("CASH", "thu") - phieu_huy["tien_mat"],
        ck("thu") - phieu_huy["chuyen_khoan"],
    )
    tra_lai = _o(int(tong.get("hoan") or 0), cot("CASH", "hoan"), ck("hoan"))
    giam_gia = int((bao_cao.get("giam_gia") or {}).get("giam") or 0)
    so_no = bao_cao.get("so_no_ky")
    if so_no:
        pt = so_no["PHAI_THU"]
        no = int(pt["phat_sinh"]) - int(pt["dieu_chinh"])
        t = pt["thu"]
        no_thu = {
            **_o(t["tong"], t["tien_mat"], t["chuyen_khoan"]),
            "giam_gia": int(t["giam_gia"]),
        }
    else:
        no = 0
        no_thu = {**_o(), "giam_gia": 0}
    dong_tien_vao = tien_thu["tong"] + no + giam_gia - no_thu["tong"]
    thuc_thu = _o(
        tien_thu["tong"] - tra_lai["tong"],
        tien_thu["tien_mat"] - tra_lai["tien_mat"],
        tien_thu["chuyen_khoan"] - tra_lai["chuyen_khoan"],
    )
    return {
        "dong_tien_vao": dong_tien_vao,
        "tien_thu": tien_thu,
        "tra_lai": tra_lai,
        "phieu_huy": phieu_huy,
        "hoan_cho": int(tong.get("hoan_cho") or 0),
        # Lần chờ CK đã huỷ (G4d, R1): ghi chú như hoàn đang chờ — không cộng.
        "ck_cho_da_huy": dict(bao_cao.get("ck_cho_da_huy") or {"so_lan": 0, "tong": 0}),
        "no": no,
        "giam_gia": giam_gia,
        "no_thu_duoc": no_thu,
        "thuc_thu": thuc_thu,
        "doanh_thu_thuan": dong_tien_vao - giam_gia - tra_lai["tong"],
        # Đẳng thức của khách — luôn đúng theo cách dựng; để màn / test thấy.
        "khop": dong_tien_vao - tra_lai["tong"] - no - giam_gia + no_thu["tong"]
        == thuc_thu["tong"],
        "so_no": so_no,
    }


def tom_tat_tai_chinh(bao_cao: Mapping[str, Any]) -> dict[str, Any]:
    """Khối tài chính cũ (giữ khoá cho màn / Excel hiện có) + ``dong_tien`` mới.

    Doanh thu lấy dòng hàng của phiếu PAID, không lấy số lần thu làm doanh thu.
    Hoàn tiền chỉ COMPLETED; ngày thuộc tập khoản hoàn tạo trong khoảng đã chọn.
    """
    tong = bao_cao.get("tong") or {}
    hang_hoa = bao_cao.get("hang_hoa") or {}
    doanh_thu = sum(int(v["tong"]["doanh_thu"]) for v in hang_hoa.values())
    doanh_thu_thuan = sum(int(v["tong"]["doanh_thu_thuan"]) for v in hang_hoa.values())
    hoan = {r["ma"]: int(r.get("hoan") or 0) for r in bao_cao.get("theo_hinh_thuc", ())}
    return {
        "so_phieu_thu": int(tong.get("so_phieu_thu") or 0),
        "doanh_thu": doanh_thu,
        "hoan_tien_mat": hoan.get("CASH", 0),
        "hoan_chuyen_khoan": hoan.get("TRANSFER", 0) + hoan.get("QR", 0),
        "giam_gia": int((bao_cao.get("giam_gia") or {}).get("giam") or 0),
        "doanh_thu_thuan": doanh_thu_thuan,
        "thuc_thu": int(tong.get("thuc_thu") or 0),
        "chua_co_du_lieu": [],
        "dong_tien": dong_tien(bao_cao),
        "pham_vi": {
            "so_phieu_thu": "Phiếu có ngày thu trong khoảng, gồm phiếu đã huỷ.",
            "doanh_thu": "Dòng hàng của phiếu còn hiệu lực, theo ngày thu.",
            "hoan": "Khoản đã hoàn, theo ngày lập khoản hoàn trong khoảng.",
            "doanh_thu_thuan": (
                "Doanh thu trừ giá trị dòng hàng đã hoàn trong tập báo cáo."
            ),
            "thuc_thu": "Tiền thu trừ phiếu huỷ và khoản đã hoàn trong tập báo cáo.",
        },
    }
