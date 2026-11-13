"""BỘ NÃO trợ lý — một lượt: tin khách vào, NHÁP trả lời ra (người duyệt rồi
mới gửi). Không biết hãng model, không biết kênh (giả lập / Zalo / Messenger).

Thứ tự trong một lượt:
  1. Luật chặn bằng code (`luat_chan`) — trúng thì trả câu cố định, KHÔNG gọi model.
  2. Vòng model ⇄ công cụ, tối đa `SO_VONG_TOI_DA` — model nhỏ hay gọi lặp vô tận.
  3. Hết vòng mà chưa có chữ → chuyển người, không trả nháp rỗng.

Vòng lặp tự viết thay cho orchestrator LangGraph sẵn có: cái đó gắn với
Anthropic và checkpointer riêng; lịch sử ở đây là danh sách `Tin` do nơi gọi
giữ (bảng hội thoại ở PR sau), nên vòng lặp chỉ cần ~50 dòng đọc được.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from clinicai.ports.mo_hinh import GoiCongCu, KetQuaMoHinh, MoHinhError, MoHinhPort, Tin
from clinicai.services.tro_ly_khach import luat_chan
from clinicai.services.tro_ly_khach.cong_cu import CHUYEN_NGUOI, BoCongCu, ket_qua_chu
from clinicai.services.tro_ly_khach.loi_nhac import (
    HE_THONG_PHAN_LOAI,
    NHAN_Y_DINH,
    PHIEN_BAN,
    he_thong_tra_loi,
)

SO_VONG_TOI_DA = 5
#: Số tin cũ gửi kèm. Đủ nhớ mạch một cuộc nhắn; dài hơn thì tốn token mà
#: không thêm gì (tóm tắt hội thoại cũ là việc PR sau).
SO_TIN_NHO = 20

CAU_CHUYEN_NGUOI = (
    "Dạ, em chuyển câu hỏi của chị cho nhân viên phòng khám, chị đợi em một chút nhé ạ."
)
CAU_MO_HINH_LOI = (
    "Dạ, hệ thống trả lời tự động đang bận, em chuyển cho nhân viên hỗ trợ chị ngay ạ."
)


@dataclass
class BuocCongCu:
    ten: str
    tham_so: dict[str, Any]
    ket_qua: dict[str, Any]


@dataclass
class KetQuaTroLy:
    nhap: str
    chuyen_nguoi: bool = False
    ly_do_chuyen: str | None = None
    ghi_chu_chuyen: str | None = None
    #: "khan_cap" / "y_khoa" khi luật code chặn trước model.
    chan_boi_code: str | None = None
    buoc: list[BuocCongCu] = field(default_factory=list)
    model: str = ""
    phien_ban_loi_nhac: str = PHIEN_BAN
    token_vao: int = 0
    token_ra: int = 0
    thoi_gian_ms: int = 0
    so_vong: int = 0
    lan_goi_ids: list[str] = field(default_factory=list)
    loi: str | None = None
    #: Tin mới phát sinh trong lượt (tin khách + các lượt tro_ly/kết quả công cụ),
    #: để nơi gọi nối vào lịch sử cho lượt sau.
    tin_moi: list[Tin] = field(default_factory=list)


def cat_lich_su(lich_su: Sequence[Tin], n: int = SO_TIN_NHO) -> list[Tin]:
    """N tin cuối, nhưng BẮT ĐẦU từ một tin khách: cắt rơi giữa cặp gọi công
    cụ / kết quả thì tin đầu là `tool_result` mồ côi → Anthropic trả 400."""
    cuoi = list(lich_su[-n:])
    while cuoi and cuoi[0].vai != "khach":
        cuoi.pop(0)
    return cuoi


async def tra_loi(
    mo_hinh: MoHinhPort,
    *,
    tin_khach: str,
    lich_su: Sequence[Tin],
    bo_cong_cu: BoCongCu,
    luc: datetime,
) -> KetQuaTroLy:
    tin_vao = Tin("khach", tin_khach)
    chan = luat_chan.kiem_tra(tin_khach)
    if chan is not None:
        return KetQuaTroLy(
            nhap=chan.cau_tra_loi,
            chuyen_nguoi=True,
            ly_do_chuyen=chan.loai,
            ghi_chu_chuyen=f"luật code: '{chan.tu_khoa}'",
            chan_boi_code=chan.loai,
            model=mo_hinh.ten,
            tin_moi=[tin_vao, Tin("tro_ly", chan.cau_tra_loi)],
        )

    kq = KetQuaTroLy(nhap="", model=mo_hinh.ten, tin_moi=[tin_vao])
    he_thong = he_thong_tra_loi(luc)
    cong_cu = bo_cong_cu.danh_sach()
    for vong in range(1, SO_VONG_TOI_DA + 1):
        kq.so_vong = vong
        try:
            r = await mo_hinh.tra_loi(
                he_thong=he_thong,
                tin=[*cat_lich_su(lich_su), *kq.tin_moi],
                cong_cu=cong_cu,
            )
        except MoHinhError as e:
            kq.loi = str(e)
            kq.nhap, kq.chuyen_nguoi = CAU_MO_HINH_LOI, True
            kq.ly_do_chuyen = kq.ly_do_chuyen or "mo_hinh_loi"
            return kq
        kq.token_vao += r.token_vao
        kq.token_ra += r.token_ra
        kq.thoi_gian_ms += r.thoi_gian_ms
        if r.lan_goi_id:
            kq.lan_goi_ids.append(r.lan_goi_id)
        kq.tin_moi.append(Tin("tro_ly", r.chu, r.goi_cong_cu))
        if not r.goi_cong_cu:
            kq.nhap = r.chu.strip()
            break
        for g in r.goi_cong_cu:
            ket_qua = await _chay(g, bo_cong_cu, kq)
            kq.buoc.append(BuocCongCu(g.ten, g.tham_so, ket_qua))
            kq.tin_moi.append(Tin("ket_qua_cong_cu", ket_qua_chu(ket_qua), ma_goi=g.ma))
    if not kq.nhap:
        kq.nhap = CAU_CHUYEN_NGUOI
        kq.chuyen_nguoi = True
        kq.ly_do_chuyen = kq.ly_do_chuyen or "het_vong"
    return kq


async def _chay(g: GoiCongCu, bo_cong_cu: BoCongCu, kq: KetQuaTroLy) -> dict[str, Any]:
    if g.ten == CHUYEN_NGUOI:
        kq.chuyen_nguoi = True
        kq.ly_do_chuyen = str(g.tham_so.get("ly_do") or "khong_ro")
        kq.ghi_chu_chuyen = str(g.tham_so.get("ghi_chu") or "") or None
        return {"da_chuyen": True}
    return await bo_cong_cu.chay(g.ten, g.tham_so)


def doc_nhan(chu: str) -> str:
    """Nhãn đầu tiên xuất hiện trong câu model trả; không có thì 'khac'.
    Xét nhãn dài trước để 'hoi_y_khoa' không bị nuốt bởi nhãn ngắn hơn."""
    s = luat_chan.bo_dau(chu)
    vi_tri = [(s.find(n), n) for n in sorted(NHAN_Y_DINH, key=len, reverse=True)]
    co = [(i, n) for i, n in vi_tri if i >= 0]
    return min(co)[1] if co else "khac"


async def phan_loai(
    mo_hinh: MoHinhPort, tin_khach: str
) -> tuple[str, KetQuaMoHinh | None]:
    """Ý định của một tin (+ kết quả model để đếm token). Khẩn do code quyết,
    không hỏi model."""
    chan = luat_chan.kiem_tra(tin_khach)
    if chan is not None:
        return ("khan_cap" if chan.loai == "khan_cap" else "hoi_y_khoa"), None
    try:
        r = await mo_hinh.tra_loi(
            he_thong=HE_THONG_PHAN_LOAI,
            tin=[Tin("khach", tin_khach)],
            max_tokens=20,
            tinh_nang="tro_ly_phan_loai",
        )
    except MoHinhError:
        return "khac", None
    return doc_nhan(r.chu), r


__all__ = [
    "CAU_CHUYEN_NGUOI",
    "SO_VONG_TOI_DA",
    "BuocCongCu",
    "KetQuaTroLy",
    "doc_nhan",
    "phan_loai",
    "tra_loi",
]
