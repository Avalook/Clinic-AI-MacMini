"""Kiểm KHUNG một mẫu kết quả trước khi xuất bản (27/09/2026 — màn sửa mẫu).

Trước đây `POST /bieu-mau/{form_id}/xuat-ban` nhận mọi thứ: kiểu ô lạ, `ma` trùng,
ô chọn không có lựa chọn — tất cả lọt vào `form_definition` và chỉ lộ ra lúc bác
sĩ mở phiếu (ô không vẽ được, hai ô ghi đè cùng một giá trị). Nay quản lý tự sửa
mẫu trên màn, nên luật nằm ở đây, một chỗ, test được không cần DB.

KHÔNG bắt buộc mục "Kết luận": 5 mẫu dựng đúng theo PDF nguồn chuẩn (siêu âm giáp,
mạch cảnh, doppler âm vật, soi âm hộ, PCR) không có mục ấy — bắt buộc là chặn sửa
chính những mẫu theo nguồn chuẩn. Màn sửa nhắc nhẹ thay vì chặn.

`ma` ô là KHOÁ của dữ liệu đã điền (`du_lieu[ma]`) nên phải duy nhất trong CẢ mẫu,
không chỉ trong một mục. Giữ `ma` cũ khi đổi tên là việc của màn sửa; ở đây chỉ
kiểm hình dạng.
"""

from __future__ import annotations

import re
from typing import Any

from clinicai.core.exceptions import ValidationError

KIEU_O = ("text", "doan_van", "so", "ngay", "chon")
#: Cách VẼ một ô chọn (chỉ là hiển thị — giá trị lưu vẫn là MỘT chuỗi như ô chọn
#: thường). Không khai = hộp thả xuống. "o_tick" = các ô tích nhanh xếp hàng
#: ngang, tích ô này bỏ ô kia (Tuyền 29/09/2026: "Kết luận nhanh" phiếu đo mật
#: độ xương — Bình thường / Tiền loãng xương / Loãng xương).
HIEN_THI_CHON = frozenset({"o_tick"})
_MA = re.compile(r"^[a-z0-9_]{1,64}$")
_KHOA_MUC = {"ma", "ten", "block", "cot"}
_KHOA_O = {"ma", "ten", "kieu", "chon", "goi_y", "mac_dinh", "hien_thi"}
TRAN_MUC = 40
TRAN_O = 300
#: Tệp kết quả gắn `ben` 0..7 (CHECK ở `tep_ket_qua`) — bảng quá 8 cột thì bên
#: thứ 9 không có chỗ gắn ảnh.
TRAN_COT = 8
TRAN_LUA_CHON = 30


def _chu(v: Any, nhan: str, *, toi_da: int, bat_buoc: bool = True) -> str | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        if bat_buoc:
            raise ValidationError(f"{nhan}: chưa có tên.")
        return None
    if not isinstance(v, str):
        raise ValidationError(f"{nhan}: phải là chữ.")
    s = v.strip()
    if len(s) > toi_da:
        raise ValidationError(f"{nhan}: dài quá {toi_da} ký tự.")
    return s


def kiem_khung_mau(khung: Any) -> list[dict[str, Any]]:
    """Trả khung đã chuẩn hoá (bỏ khoảng trắng thừa); sai thì ValidationError
    với câu nói rõ MỤC nào, Ô nào."""
    if not isinstance(khung, list) or not khung:
        raise ValidationError("Mẫu phải có ít nhất một mục.")
    if len(khung) > TRAN_MUC:
        raise ValidationError(f"Mẫu quá {TRAN_MUC} mục.")

    ma_muc: set[str] = set()
    ma_o: set[str] = set()
    ra: list[dict[str, Any]] = []
    for i, m in enumerate(khung, start=1):
        if not isinstance(m, dict):
            raise ValidationError(f"Mục {i}: sai dạng.")
        la = set(m) - _KHOA_MUC
        if la:
            raise ValidationError(f"Mục {i}: có trường lạ {sorted(la)}.")
        ten_muc = _chu(m.get("ten"), f"Mục {i}", toi_da=200)
        nhan_muc = f"Mục “{ten_muc}”"
        ma = m.get("ma")
        if not isinstance(ma, str) or not _MA.match(ma):
            raise ValidationError(f"{nhan_muc}: mã mục không hợp lệ.")
        if ma in ma_muc:
            raise ValidationError(f"{nhan_muc}: trùng mã mục “{ma}”.")
        ma_muc.add(ma)

        cot_ra: list[dict[str, str]] | None = None
        if m.get("cot") is not None:
            cot = m["cot"]
            if not isinstance(cot, list) or not 1 <= len(cot) <= TRAN_COT:
                raise ValidationError(f"{nhan_muc}: bảng phải có 1–{TRAN_COT} cột.")
            cot_ra = []
            ma_cot: set[str] = set()
            for c in cot:
                if not isinstance(c, dict) or set(c) - {"ma", "ten"}:
                    raise ValidationError(f"{nhan_muc}: cột sai dạng.")
                if not isinstance(c.get("ma"), str) or not _MA.match(c["ma"]):
                    raise ValidationError(f"{nhan_muc}: mã cột không hợp lệ.")
                if c["ma"] in ma_cot:
                    raise ValidationError(f"{nhan_muc}: trùng mã cột “{c['ma']}”.")
                ma_cot.add(c["ma"])
                ten_cot = _chu(c.get("ten"), nhan_muc, toi_da=80) or ""
                cot_ra.append({"ma": c["ma"], "ten": ten_cot})

        block = m.get("block")
        if not isinstance(block, list) or not block:
            raise ValidationError(f"{nhan_muc}: chưa có ô nào.")
        block_ra: list[dict[str, Any]] = []
        for o in block:
            if not isinstance(o, dict):
                raise ValidationError(f"{nhan_muc}: ô sai dạng.")
            ten_o = _chu(o.get("ten"), f"{nhan_muc} → ô", toi_da=200)
            nhan_o = f"{nhan_muc} → ô “{ten_o}”"
            la = set(o) - _KHOA_O
            if la:
                raise ValidationError(f"{nhan_o}: có trường lạ {sorted(la)}.")
            ma = o.get("ma")
            if not isinstance(ma, str) or not _MA.match(ma):
                raise ValidationError(f"{nhan_o}: mã ô không hợp lệ.")
            if ma in ma_o:
                raise ValidationError(
                    f"{nhan_o}: trùng mã “{ma}” với một ô khác — hai ô sẽ ghi đè "
                    "cùng một giá trị."
                )
            ma_o.add(ma)
            kieu = o.get("kieu")
            if kieu not in KIEU_O:
                raise ValidationError(f"{nhan_o}: kiểu ô “{kieu}” không có.")
            moi: dict[str, Any] = {"ma": ma, "ten": ten_o, "kieu": kieu}

            if kieu == "chon":
                chon = o.get("chon")
                if not isinstance(chon, list) or not chon:
                    raise ValidationError(f"{nhan_o}: ô chọn phải có lựa chọn.")
                if len(chon) > TRAN_LUA_CHON:
                    raise ValidationError(f"{nhan_o}: quá {TRAN_LUA_CHON} lựa chọn.")
                sach = [_chu(x, nhan_o, toi_da=120) for x in chon]
                if len(set(sach)) != len(sach):
                    raise ValidationError(f"{nhan_o}: lựa chọn bị trùng.")
                moi["chon"] = sach
            elif o.get("chon") not in (None, []):
                raise ValidationError(f"{nhan_o}: chỉ ô kiểu chọn mới có lựa chọn.")

            hien_thi = o.get("hien_thi")
            if hien_thi is not None:
                if kieu != "chon":
                    raise ValidationError(
                        f"{nhan_o}: chỉ ô kiểu chọn mới có cách hiển thị."
                    )
                if hien_thi not in HIEN_THI_CHON:
                    raise ValidationError(
                        f"{nhan_o}: cách hiển thị “{hien_thi}” không có."
                    )
                moi["hien_thi"] = hien_thi

            goi_y = _chu(o.get("goi_y"), nhan_o, toi_da=60, bat_buoc=False)
            if goi_y:
                moi["goi_y"] = goi_y

            md = o.get("mac_dinh")
            if isinstance(md, dict):
                if cot_ra is None:
                    raise ValidationError(
                        f"{nhan_o}: mặc định theo cột chỉ có ở mục dạng bảng."
                    )
                la = set(md) - {c["ma"] for c in cot_ra}
                if la:
                    raise ValidationError(
                        f"{nhan_o}: mặc định cho cột lạ {sorted(la)}."
                    )
                md_sach = {
                    k: s
                    for k, v in md.items()
                    if (s := _chu(v, nhan_o, toi_da=2000, bat_buoc=False))
                }
                if md_sach:
                    moi["mac_dinh"] = md_sach
            elif md is not None:
                s = _chu(md, nhan_o, toi_da=2000, bat_buoc=False)
                if s:
                    if kieu == "chon" and s not in moi["chon"]:
                        raise ValidationError(
                            f"{nhan_o}: mặc định phải là một trong các lựa chọn."
                        )
                    moi["mac_dinh"] = s
            block_ra.append(moi)
            if len(ma_o) > TRAN_O:
                raise ValidationError(f"Mẫu quá {TRAN_O} ô.")

        muc_ra: dict[str, Any] = {"ma": m["ma"], "ten": ten_muc, "block": block_ra}
        if cot_ra is not None:
            muc_ra["cot"] = cot_ra
        ra.append(muc_ra)
    return ra


__all__ = ["HIEN_THI_CHON", "KIEU_O", "kiem_khung_mau"]
