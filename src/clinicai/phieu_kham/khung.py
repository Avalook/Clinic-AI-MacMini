"""Khung của 7 phiếu khám — nạp, kiểm hình, kiểm dữ liệu theo khoá ổn định.

KHOÁ LÀ ĐỊNH DANH, NHÃN CHỈ ĐỂ ĐỌC. Mọi ô mang khoá lấy nguyên từ nguồn
(`nt_endo_hist`, `hmvs_semen_3_2`…); lựa chọn của ô nhiều-chọn cũng là khoá
(`nt_endo_hist_2`), không phải chữ "Tuyến giáp". Gửi chữ lên thay mã thì bị chặn
ngay — một nhãn đổi chính tả là một hồ sơ cũ mất nghĩa.

HÌNH KHUNG = HÌNH CỦA ENGINE. `[{ma, ten, block: [{ma, ten, kieu, …}]}]` y như 18
mẫu kết quả, nên khung nằm được trong `form_definition` và xuất bản bản mới qua
`PublishFormVersion` mà engine không đổi dòng nào. Thêm vào khung ba thứ engine
bỏ qua được: `lua_chon` (mã + nhãn), `nhom` / `bang`
/ `hang` / `cot` (để vẽ lại đúng bố cục), và `lien_ket` ở cấp MỤC.

BA THUỘC TÍNH HIỂN THỊ (đợt 3, 27/09/2026 — góp ý phòng khám, bản v2). Engine
bỏ qua, màn đọc; khai trong DỮ LIỆU để màn không phải so tên nhóm:

* `thu_gon: true` (ô) — ô ẩn sau một chip tên ô; bấm chip mới hiện. Ô đã có
  giá trị luôn hiện: thu gọn không bao giờ giấu dữ liệu.
* `hien_khi: {o, la}` (ô) — ô chỉ hiện khi ô chọn `o` đang chọn mã `la`
  ("Chi tiết dị ứng thuốc" chỉ hiện khi "Dị ứng thuốc: Có"). Có chữ thì luôn hiện.
* `gap: true` (mọi ô của MỘT nhóm) — cả nhóm nằm trong ngăn gập, mặc định đóng,
  tự mở khi đã có ô điền (bảng kết quả CLS gõ tay).

Ô thêm sau khi trích nguồn mang `them_sau_nguon` (lý do) — để bộ đếm "khoá
của nguồn" vẫn đếm đúng nguồn.

MỤC LIÊN KẾT KHÔNG CÓ Ô. Chỉ định CLS, đơn thuốc, thủ thuật, sinh hiệu đã có chỗ
giữ riêng (service_order, prescription, vital_measurement). Phiếu chỉ khai "mục
này đọc từ đâu"; không nhận giá trị — hai nơi giữ cùng một sự thật là hai nơi
để lệch. Vì mục liên kết không có `block`, bộ đếm "còn N ô trống" của engine tự
bỏ qua chúng.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from clinicai.core.exceptions import ValidationError
from clinicai.services.form_engine_service import NGUON

THU_MUC = Path(__file__).with_name("dinh_nghia")

#: Bảy form profile đã chốt (Tuyền 22/09). Sản 1/2/3, SA1/2/3 là PHÒNG, không
#: phải phiếu — không bao giờ xuất hiện ở đây.
FORM_IDS: tuple[str, ...] = ("NT", "HMVS", "PK", "SK", "NK", "THU_THUAT", "SAN_CHAU")

#: HỒ SƠ ĐIỀU TRỊ (Tuyền chốt 09/10/2026): khung TRUNG TÍNH của lượt Điều trị —
#: hành chính + C, D, E, F, G, không A/B. KHÔNG phải một loại khám: không nằm
#: trong `FORM_IDS` (không ở danh sách chọn phiếu, không gắn loại khám), chỉ là
#: chỗ lưu chẩn đoán / lời dặn / tái khám khi bác sĩ ghi ở lượt Điều trị — để
#: bản in và mọi chỗ gom theo phiếu không thấy lượt Điều trị thành "thủ thuật".
HO_SO_DIEU_TRI = "HO_SO_DIEU_TRI"

#: Mọi khung lưu được ở `phieu_kham_luot` (bảy phiếu + hồ sơ điều trị).
PHIEU_IDS: tuple[str, ...] = (*FORM_IDS, HO_SO_DIEU_TRI)

#: Nhóm trên `form_definition.nhom` — tách phiếu khám khỏi 18 mẫu kết quả.
NHOM = "PHIEU_KHAM"

#: Kiểu ô mà bảy phiếu dùng. Engine hiểu thêm vài kiểu nữa (`cap_do`, `anh`…);
#: phiếu khám chưa cần thì chưa mở, để ô lạ bị bắt ngay lúc kiểm khung.
KIEU = frozenset({"text", "so", "ngay", "doan_van", "chon", "nhieu_chon"})

#: Mục liên kết: dữ liệu thật ở module khác, phiếu chỉ đọc.
LIEN_KET = frozenset({"mang_sang", "chi_dinh_cls", "don_thuoc", "chi_dinh_thu_thuat"})

_MA = re.compile(r"^[a-z][a-z0-9_]*$")
_MA_MUC = re.compile(r"^[A-Z][A-Z_]*$")

#: Trần độ dài — lưới an toàn, không phải luật chuyên môn.
_TRAN = {"text": 2_000, "doan_van": 20_000}


# ---------------------------------------------------------------------------
# Nạp
# ---------------------------------------------------------------------------
@cache
def _doc(form_id: str) -> dict[str, Any]:
    if form_id not in PHIEU_IDS:
        raise ValidationError(f"“{form_id}” không phải một trong bảy phiếu khám.")
    dn = json.loads((THU_MUC / f"{form_id}.json").read_text(encoding="utf-8"))
    kiem_dinh_nghia(dn)
    return dict(dn)


def dinh_nghia(form_id: str) -> dict[str, Any]:
    """Định nghĩa đầy đủ của một phiếu (bản sao — sửa không làm bẩn bộ nhớ đệm)."""
    return copy.deepcopy(_doc(form_id))


def tat_ca() -> list[dict[str, Any]]:
    return [dinh_nghia(f) for f in FORM_IDS]


@cache
def _tham_chieu() -> dict[str, Any]:
    return dict(
        json.loads((THU_MUC / "tham_chieu_nguon.json").read_text(encoding="utf-8"))
    )


def tham_chieu_nguon() -> dict[str, Any]:
    """Danh mục C / F / thuốc của NGUỒN — nhãn chờ ánh xạ, chưa phải định danh.

    Mỗi mục mang `service_code` / `drug_catalog_id` = None cho tới khi người làm
    danh mục gắn mã thật. Không ai được tự điền chỗ ấy bằng cách so tên.
    """
    return copy.deepcopy(_tham_chieu())


def la_phieu_kham(form_id: str | None) -> bool:
    return form_id in PHIEU_IDS


# ---------------------------------------------------------------------------
# Kiểm hình khung — chạy lúc nạp, và trước khi xuất bản bản mới
# ---------------------------------------------------------------------------
def kiem_dinh_nghia(dn: dict[str, Any]) -> None:
    """Hình của một định nghĩa phiếu. Sai thì dừng NGAY, không nạp nửa vời."""
    fid = dn.get("form_id")
    if fid not in PHIEU_IDS:
        raise ValidationError(f"form_id lạ: {fid!r}")
    if dn.get("nhom") != NHOM:
        raise ValidationError(f"{fid}: nhóm phải là {NHOM}")
    kiem_khung(dn.get("khung"), form_id=fid)


def kiem_khung(khung: Any, *, form_id: str) -> None:
    if not isinstance(khung, list) or not khung:
        raise ValidationError(f"{form_id}: khung trống.")
    ma_muc: set[str] = set()
    ma_o: set[str] = set()
    for muc in khung:
        m = muc.get("ma")
        if not isinstance(m, str) or not _MA_MUC.match(m) or m in ma_muc:
            raise ValidationError(f"{form_id}: mã mục lạ hoặc trùng {m!r}")
        ma_muc.add(m)
        lk = muc.get("lien_ket")
        if lk is not None and lk.get("loai") not in LIEN_KET:
            raise ValidationError(f"{form_id}.{m}: liên kết lạ {lk!r}")
        blocks = muc.get("block")
        if not isinstance(blocks, list):
            raise ValidationError(f"{form_id}.{m}: thiếu danh sách ô")
        # Chỉ định và thủ thuật là của service_order: phiếu không có ô nào để
        # tự giữ một bản sao danh sách chỉ định.
        if lk and lk["loai"] in {"chi_dinh_cls", "chi_dinh_thu_thuat"} and blocks:
            raise ValidationError(f"{form_id}.{m}: mục chỉ định không được có ô")
        for b in blocks:
            _kiem_o(b, form_id=form_id, ma_o=ma_o)
        _kiem_gap_theo_nhom(blocks, form_id=form_id, ma_muc=m)
    _kiem_hien_khi(khung, form_id=form_id)


def _kiem_o(b: dict[str, Any], *, form_id: str, ma_o: set[str]) -> None:
    ma = b.get("ma")
    if not isinstance(ma, str) or not _MA.match(ma):
        raise ValidationError(f"{form_id}: khoá ô không hợp lệ {ma!r}")
    if ma in ma_o:
        raise ValidationError(f"{form_id}: khoá ô trùng {ma}")
    ma_o.add(ma)
    if b.get("kieu") not in KIEU:
        raise ValidationError(f"{form_id}.{ma}: kiểu lạ {b.get('kieu')!r}")
    if not (b.get("ten") or "").strip():
        raise ValidationError(f"{form_id}.{ma}: thiếu nhãn")
    _kiem_hien_thi(b, form_id=form_id, ma=ma)
    if b["kieu"] in {"chon", "nhieu_chon"}:
        lc = b.get("lua_chon")
        if not isinstance(lc, list) or not lc:
            raise ValidationError(f"{form_id}.{ma}: ô chọn không có lựa chọn")
        for o in lc:
            om = o.get("ma")
            if not isinstance(om, str) or not _MA.match(om):
                raise ValidationError(f"{form_id}.{ma}: mã lựa chọn lạ {om!r}")
            # Mã lựa chọn đi chung không gian khoá với ô: một mã chỉ có MỘT
            # nghĩa trong cả phiếu.
            if om in ma_o:
                raise ValidationError(f"{form_id}.{ma}: mã lựa chọn trùng {om}")
            ma_o.add(om)
            if not (o.get("ten") or "").strip():
                raise ValidationError(f"{form_id}.{ma}.{om}: lựa chọn thiếu nhãn")


def _kiem_hien_thi(b: dict[str, Any], *, form_id: str, ma: str) -> None:
    """Kiểu của ba thuộc tính hiển thị trên MỘT ô (xem docstring đầu tệp)."""
    for k in ("thu_gon", "gap"):
        if k in b and not isinstance(b[k], bool):
            raise ValidationError(
                f"{form_id}.{ma}: `{k}` phải là true/false, nhận {b[k]!r}"
            )
    if "them_sau_nguon" in b and not (
        isinstance(b["them_sau_nguon"], str) and b["them_sau_nguon"].strip()
    ):
        raise ValidationError(f"{form_id}.{ma}: `them_sau_nguon` phải là một câu lý do")
    hk = b.get("hien_khi")
    if hk is not None:
        if (
            not isinstance(hk, dict)
            or set(hk) != {"o", "la"}
            or not all(isinstance(hk[k], str) and _MA.match(hk[k]) for k in ("o", "la"))
        ):
            raise ValidationError(
                f"{form_id}.{ma}: `hien_khi` phải có dạng"
                f" {{o: <mã ô>, la: <mã lựa chọn>}}, nhận {hk!r}"
            )
    # Ô trong BẢNG vẽ theo hàng × cột: giấu một ô là thủng một lỗ giữa bảng.
    if b.get("bang") and (b.get("thu_gon") or hk is not None):
        raise ValidationError(f"{form_id}.{ma}: ô trong bảng không thu gọn / ẩn được")
    if b.get("thu_gon") and hk is not None:
        raise ValidationError(
            f"{form_id}.{ma}: một ô chỉ một cách ẩn (thu_gon HOẶC hien_khi)"
        )


def _kiem_gap_theo_nhom(
    blocks: list[dict[str, Any]], *, form_id: str, ma_muc: str
) -> None:
    """`gap` là của NHÓM (ô liền nhau cùng `nhom` — đúng cách màn gom): mọi ô
    trong nhóm phải cùng một giá trị, không thì nửa nhóm gập nửa nhóm không."""
    truoc: tuple[Any, bool] | None = None
    for b in blocks:
        cap = (b.get("nhom"), bool(b.get("gap")))
        if truoc is not None and truoc[0] == cap[0] and truoc[1] != cap[1]:
            raise ValidationError(
                f"{form_id}.{ma_muc}: nhóm {cap[0]!r} có ô gập, ô không — `gap` phải"
                " giống nhau ở mọi ô của nhóm"
            )
        truoc = cap


def _kiem_hien_khi(khung: list[dict[str, Any]], *, form_id: str) -> None:
    """`hien_khi` trỏ vào một ô CHỌN có thật trong phiếu và một mã lựa chọn của
    chính ô ấy — trỏ sai là một ô không bao giờ hiện."""
    o_theo_ma = cac_o(khung)
    for ma, b in o_theo_ma.items():
        hk = b.get("hien_khi")
        if hk is None:
            continue
        dich = o_theo_ma.get(hk["o"])
        if dich is None or hk["o"] == ma:
            raise ValidationError(
                f"{form_id}.{ma}: `hien_khi` trỏ ô không có {hk['o']!r}"
            )
        if dich["kieu"] not in {"chon", "nhieu_chon"}:
            raise ValidationError(f"{form_id}.{ma}: `hien_khi` phải trỏ một ô chọn")
        if hk["la"] not in {o["ma"] for o in dich["lua_chon"]}:
            raise ValidationError(
                f"{form_id}.{ma}: ô {hk['o']} không có lựa chọn {hk['la']!r}"
            )


def cac_o(khung: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """{khoá ô: ô} — chỉ ô nhận giá trị, không có mục liên kết."""
    return {b["ma"]: b for muc in khung for b in muc.get("block", [])}


# ---------------------------------------------------------------------------
# Kiểm dữ liệu một lần lưu
# ---------------------------------------------------------------------------
def kiem_du_lieu(
    khung: list[dict[str, Any]], du_lieu: Any
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    """Chuẩn hoá một lần tự lưu theo đúng khung mà phiếu đã ghim.

    Trả `(sach, canh_bao)`:

    * Khoá lạ, nguồn lạ, mã lựa chọn lạ → CHẶN. Đó là lỗi định danh: lưu vào
      là có một ô không ai đọc được, hoặc một lựa chọn không thuộc phiếu.
    * Số / ngày không đọc được → thành RỖNG kèm cảnh báo, KHÔNG ném (luật
      CLAUDE.md: hàm nhận ngày giờ người dùng trả rỗng thay vì ném — đã có ba
      lần 500 vì bỏ luật này). Cảnh báo trả về để màn nói ra, không nuốt im.
    """
    if not isinstance(du_lieu, dict):
        raise ValidationError("Dữ liệu phiếu phải là một bảng {khoá ô: giá trị}.")
    o_theo_ma = cac_o(khung)
    sach: dict[str, dict[str, Any]] = {}
    canh_bao: list[dict[str, str]] = []
    for ma, o in du_lieu.items():
        dinh = o_theo_ma.get(ma)
        if dinh is None:
            raise ValidationError(f"Ô “{ma}” không có trong phiếu này.")
        if not isinstance(o, dict) or "gia_tri" not in o:
            raise ValidationError(f"Ô “{ma}” phải có dạng {{gia_tri, nguon}}.")
        nguon = o.get("nguon", "USER")
        if nguon not in NGUON:
            raise ValidationError(f"Ô “{ma}” có nguồn lạ: {nguon}.")
        gia, loi = _chuan_hoa(dinh, o["gia_tri"])
        if loi:
            canh_bao.append({"ma": ma, "ten": dinh["ten"], "loi": loi})
        sach[ma] = {"gia_tri": gia, "nguon": nguon}
    return sach, canh_bao


def _chuan_hoa(dinh: dict[str, Any], gia: Any) -> tuple[Any, str | None]:
    kieu = dinh["kieu"]
    if gia is None:
        return ([] if kieu == "nhieu_chon" else ""), None

    if kieu == "nhieu_chon":
        if not isinstance(gia, list) or not all(isinstance(x, str) for x in gia):
            raise ValidationError(f"Ô “{dinh['ma']}” phải là danh sách mã lựa chọn.")
        hop_le = [o["ma"] for o in dinh["lua_chon"]]
        la = sorted(set(gia) - set(hop_le))
        if la:
            raise ValidationError(
                f"Ô “{dinh['ma']}” không có lựa chọn {', '.join(la)}"
                " — gửi MÃ lựa chọn, không gửi chữ hiển thị."
            )
        # Giữ thứ tự của khung, bỏ trùng: cùng một tập chọn luôn lưu ra cùng
        # một mảng, nên so "có đổi gì không" không báo đổi oan.
        chon = set(gia)
        return [m for m in hop_le if m in chon], None

    if kieu == "chon":
        if not isinstance(gia, str):
            raise ValidationError(f"Ô “{dinh['ma']}” phải là một mã lựa chọn.")
        if gia and gia not in {o["ma"] for o in dinh["lua_chon"]}:
            raise ValidationError(f"Ô “{dinh['ma']}” không có lựa chọn {gia}.")
        return gia, None

    if not isinstance(gia, str | int | float) or isinstance(gia, bool):
        raise ValidationError(f"Ô “{dinh['ma']}” nhận chữ hoặc số.")

    if kieu == "so":
        return _doc_so(gia)
    if kieu == "ngay":
        return _doc_ngay(gia)

    chu = str(gia)
    tran = _TRAN.get(kieu, _TRAN["text"])
    if len(chu) > tran:
        raise ValidationError(f"Ô “{dinh['ma']}” dài quá {tran} ký tự.")
    return chu, None


def _doc_so(gia: str | int | float) -> tuple[str, str | None]:
    """Số → chuỗi số chuẩn (dấu chấm thập phân). Không đọc được → rỗng."""
    chu = str(gia).strip().replace(",", ".")
    if not chu:
        return "", None
    try:
        so = float(chu)
    except ValueError:
        return "", f"“{gia}” không phải số — ô được để trống."
    if so != so or so in (float("inf"), float("-inf")):
        return "", f"“{gia}” không phải số — ô được để trống."
    return (str(int(so)) if so.is_integer() else repr(so)), None


def doc_ngay(gia: Any) -> date | None:
    """`YYYY-MM-DD` (ô date của trình duyệt) hoặc `DD/MM/YYYY`. Rác → None."""
    if not isinstance(gia, str):
        return None
    chu = gia.strip()
    for mau in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(chu, mau).date()
        except ValueError:
            continue
    return None


def _doc_ngay(gia: str | int | float) -> tuple[str, str | None]:
    if str(gia).strip() == "":
        return "", None
    d = doc_ngay(str(gia))
    if d is None:
        return "", f"“{gia}” không phải ngày — ô được để trống."
    return d.isoformat(), None


__all__ = [
    "FORM_IDS",
    "KIEU",
    "LIEN_KET",
    "NHOM",
    "cac_o",
    "dinh_nghia",
    "doc_ngay",
    "kiem_dinh_nghia",
    "kiem_du_lieu",
    "kiem_khung",
    "la_phieu_kham",
    "tat_ca",
    "tham_chieu_nguon",
]
