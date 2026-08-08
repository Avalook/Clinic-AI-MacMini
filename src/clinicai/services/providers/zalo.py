"""Zalo ZNS — gửi tin cho bệnh nhân qua Zalo Official Account.

ĐÃ NỐI THẬT, CHƯA CÓ TÀI KHOẢN. Quang (08/08/2026): *"nối gửi Zalo thật đi,
nhưng chưa có Zalo thật, cứ mở sẵn thôi"*. Nên toàn bộ đường gọi ở đây là đường
thật — đúng endpoint, đúng thân yêu cầu, đúng cách đọc lỗi của Zalo. Ngày phòng
khám có Official Account, việc phải làm là điền hai biến môi trường, không phải
viết lại file này.

■ VÌ SAO ZNS CHỨ KHÔNG PHẢI "OA MESSAGE"

Hai API khác nhau, và chọn nhầm thì không có cách nào chữa bằng cấu hình:

  · `/v3.0/oa/message/cs` gửi theo `user_id` — mã Zalo cấp cho người ĐÃ QUAN
    TÂM Official Account. Phòng khám không có mã đó; họ có SỐ ĐIỆN THOẠI.
  · ZNS (`/message/template`) gửi theo SỐ ĐIỆN THOẠI, và gửi được cho người
    chưa từng quan tâm OA. Đây đúng là cảnh của phòng khám: nhắc lịch cho một
    người vừa gọi hotline đặt hẹn.

Đổi lại, ZNS chỉ gửi được TEMPLATE đã duyệt — không gửi được chữ tự do. Nên
hàm này nhận `template_id` + các trường của template, chứ không nhận một câu.

■ KHÔNG CÓ CẤU HÌNH THÌ NÓI KHÔNG CÓ

Bản cũ trả `{"ok": True, "stub": True}` — nói THÀNH CÔNG cho một việc chưa hề
xảy ra. Bất kỳ ai đọc `ok` để quyết định đều kết luận sai, và cách hỏng là:
phòng khám tin tin nhắn đã tới, không ai gọi điện nữa, bệnh nhân không đến.

Nay mọi đường ra đều mang `da_gui: bool` và một `ly_do` đọc được. `da_gui`
chỉ đúng khi Zalo trả `error == 0`.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
import structlog

logger = structlog.get_logger()

#: Endpoint ZNS thật. Đổi được bằng biến môi trường cho môi trường thử của Zalo.
ZNS_URL = os.environ.get(
    "ZALO_ZNS_URL", "https://business.openapi.zalo.me/message/template"
)

#: Zalo trả HTTP 200 cho cả lỗi nghiệp vụ; mã thật nằm trong thân, ở `error`.
#: Vài mã hay gặp — dịch sang tiếng Việt để người trực đọc được, thay vì thấy
#: "-124" rồi đi hỏi kỹ thuật.
_LOI_ZALO: dict[int, str] = {
    -124: "Access token không hợp lệ hoặc đã hết hạn.",
    -125: "Official Account chưa được cấp quyền gửi ZNS.",
    -132: "Template không tồn tại hoặc chưa được duyệt.",
    -133: "Dữ liệu điền vào template không khớp khai báo.",
    -134: "Số điện thoại không dùng Zalo.",
    -135: "Người nhận đã từ chối nhận tin từ Official Account này.",
    -136: "Số điện thoại không hợp lệ.",
    -139: "Tài khoản ZNS hết số dư.",
}

KetQuaGui = dict[str, Any]


def _chua_cau_hinh(thieu: str) -> KetQuaGui:
    return {
        "da_gui": False,
        "ly_do": "CHUA_CAU_HINH",
        "chi_tiet": f"Chưa khai {thieu}. Zalo chưa nối — hãy gọi điện cho khách.",
    }


def dang_bat() -> bool:
    """Zalo đã đủ cấu hình để gửi chưa.

    Giao diện hỏi câu này để biết nên hiện nút "Gửi qua Zalo" hay chỉ hiện
    "xác nhận đã gửi tay" — thay vì mời người dùng bấm một nút chắc chắn hỏng.
    """
    return bool(os.environ.get("ZALO_ZNS_ACCESS_TOKEN"))


def chuan_hoa_sdt(sdt: str) -> str | None:
    """Số Việt Nam về dạng 84xxxxxxxxx mà ZNS nhận.

    Phòng khám lưu số kiểu "0989862764"; ZNS đòi "84989862764". Gửi nguyên số
    có `0` đứng đầu thì Zalo trả -136 và người trực đọc thành "số sai" — trong
    khi số hoàn toàn đúng, chỉ sai định dạng.
    """
    so = "".join(c for c in (sdt or "") if c.isdigit())
    if not so:
        return None
    if so.startswith("84"):
        pass
    elif so.startswith("0"):
        so = "84" + so[1:]
    else:
        so = "84" + so
    # Số di động VN: 84 + 9 chữ số.
    return so if len(so) == 11 else None


async def gui_zns(
    *,
    sdt: str,
    template_id: str,
    du_lieu: dict[str, str],
    ma_theo_doi: str | None = None,
    het_gio_giay: float = 15.0,
) -> KetQuaGui:
    """Gửi một tin ZNS. Trả về kết quả CÓ THỂ ĐỌC ĐƯỢC, không ném ngoại lệ.

    Không ném vì mọi lời gọi đều nằm trong một thao tác của người dùng: CSKH
    bấm "gửi", và một ngoại lệ ở đây sẽ thành 500 trên màn — không nói được là
    Zalo từ chối hay mạng hỏng hay chưa cấu hình.
    """
    token = os.environ.get("ZALO_ZNS_ACCESS_TOKEN")
    if not token:
        return _chua_cau_hinh("ZALO_ZNS_ACCESS_TOKEN")
    if not template_id:
        return _chua_cau_hinh("mã template ZNS")

    so = chuan_hoa_sdt(sdt)
    if not so:
        return {
            "da_gui": False,
            "ly_do": "SDT_KHONG_HOP_LE",
            "chi_tiet": "Số điện thoại không đúng định dạng di động Việt Nam.",
        }

    than = {
        "phone": so,
        "template_id": template_id,
        "template_data": du_lieu,
    }
    if ma_theo_doi:
        than["tracking_id"] = ma_theo_doi

    try:
        async with httpx.AsyncClient(timeout=het_gio_giay) as client:
            r = await client.post(ZNS_URL, headers={"access_token": token}, json=than)
    except httpx.TimeoutException:
        return {
            "da_gui": False,
            "ly_do": "HET_GIO",
            "chi_tiet": (
                "Zalo không trả lời kịp. CHƯA CHẮC ĐÃ GỬI — kiểm tra rồi "
                "thử lại, đừng ghi là đã gửi."
            ),
        }
    except httpx.HTTPError as e:
        return {
            "da_gui": False,
            "ly_do": "KHONG_KET_NOI",
            "chi_tiet": f"Không gọi được Zalo: {type(e).__name__}.",
        }

    try:
        d = r.json()
    except ValueError:
        return {
            "da_gui": False,
            "ly_do": "TRA_LOI_LA",
            "chi_tiet": f"Zalo trả về thứ không đọc được (HTTP {r.status_code}).",
        }

    # ZALO TRẢ HTTP 200 CHO CẢ LỖI NGHIỆP VỤ. Đọc `error` trong thân, không đọc
    # mã HTTP — `r.raise_for_status()` ở đây sẽ cho mọi lỗi đi lọt.
    ma = d.get("error")
    if ma == 0:
        # KHÔNG log số điện thoại, không log nội dung: đây là dữ liệu bệnh nhân
        # và nhật ký đi ra ngoài máy (bài kiểm test_zalo_provider canh điều này).
        logger.info("zalo_zns_da_gui", template_id=template_id)
        return {
            "da_gui": True,
            "ly_do": "OK",
            "msg_id": (d.get("data") or {}).get("msg_id"),
        }

    logger.warning("zalo_zns_tu_choi", template_id=template_id, ma_loi=ma)
    return {
        "da_gui": False,
        "ly_do": "ZALO_TU_CHOI",
        "ma_loi": ma,
        "chi_tiet": _LOI_ZALO.get(ma, d.get("message") or f"Zalo từ chối (mã {ma})."),
    }


async def send_zalo(phone: str, message: str) -> dict[str, Any]:
    """Đường cũ, GIỮ CHỮ KÝ nhưng thôi nói dối.

    Bản trước trả `{"ok": True, "stub": True}` — nói THÀNH CÔNG cho một việc
    chưa hề xảy ra. Ai đọc `ok` để quyết định đều kết luận sai.

    ZNS không gửi được chữ tự do (chỉ template đã duyệt), nên hàm này không thể
    làm đúng việc nó hứa. Nó trả về thẳng "chưa nối" thay vì giả vờ.
    """
    logger.info("zalo_gui_chu_tu_do_khong_ho_tro")
    return {
        "ok": False,
        "da_gui": False,
        "ly_do": "KHONG_HO_TRO",
        "chi_tiet": (
            "ZNS chỉ gửi được template đã duyệt, không gửi chữ tự do. "
            "Dùng gui_zns(template_id=…)."
        ),
    }


LoaiTin = Literal["NHAC_HEN", "TRA_KET_QUA"]

#: Mỗi loại tin một template đã duyệt bên Zalo. Để ở biến môi trường vì mã
#: template do Zalo cấp cho TỪNG Official Account — ghi cứng vào code là phòng
#: khám thứ hai dùng hệ thống này sẽ gửi bằng template của phòng khám thứ nhất.
_BIEN_TEMPLATE: dict[str, str] = {
    "NHAC_HEN": "ZALO_ZNS_TEMPLATE_NHAC_HEN",
    "TRA_KET_QUA": "ZALO_ZNS_TEMPLATE_TRA_KET_QUA",
}


def template_cho(loai: str) -> str | None:
    """Mã template của một loại tin, hoặc None nếu phòng khám chưa khai."""
    bien = _BIEN_TEMPLATE.get(loai)
    return os.environ.get(bien) if bien else None
