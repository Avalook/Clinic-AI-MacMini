"""Nhập kho theo đơn vị nào, đổi ra đơn vị kho bao nhiêu — nói bằng lời người
(kế hoạch docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 2, 16 dòng PR C).

Câu hỏi cũ "1 hộp = ? hộp 30 viên" làm người nhập trả lời 30 (số viên trong hộp):
Aktiv 47 hộp thành 1.410, Ecanix 305 hộp thành 18.300. Từ 26/11:
  · Đơn vị nhập CHỌN trong danh sách đơn vị đã khai của thuốc (gốc + đơn vị khai thêm).
    Đơn vị chưa khai → từ chối, chỉ đường khai ở Danh mục. Máy không tự nhớ đơn vị lạ.
  · Nhận diện đơn vị bằng `BangDonVi` (cùng luật với hoá đơn, kho): "hộp" của thuốc
    gốc "hộp 30 viên" LÀ đơn vị gốc — không hỏi đổi nữa.
  · Câu hỏi "1 hộp có bao nhiêu viên?" và kết quả "47 hộp = 1.410 viên" do máy chủ
    viết; màn chỉ vẽ.
Thuốc chưa khai đơn vị gốc: giữ như cũ (không đổi, lô lấy chữ gõ) — có cảnh báo ở màn.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.don_vi_thuoc import (
    HE_SO_TOI_DA,
    BangDonVi,
    chuan,
    doc_bang,
    so_dep,
)
from clinicai.services.thuoc.gia_dong import so_luong_sach

#: Hệ số lần này lệch quá ngần ấy lần so với hệ số đã khai thì bắt xác nhận — gõ
#: thừa/thiếu một số 0 là lỗi hay gặp nhất và làm lệch tồn cả chục lần.
NGUONG_LA = Decimal(10)
BA_SO_LE = Decimal("0.001")


def so_nhom_nghin(x: Decimal | int | None) -> str:
    """Số kiểu Việt Nam cho câu người đọc: 1410 → "1.410", 0.5 → "0,5"."""
    if x is None:
        return ""
    d = Decimal(str(x)).quantize(BA_SO_LE, rounding=ROUND_HALF_UP).normalize()
    nguyen, _, le = format(abs(d), "f").partition(".")
    nhom = f"{int(nguyen):,}".replace(",", ".")
    return ("-" if d < 0 else "") + nhom + (f",{le}" if le else "")


def doc_he_so(v: Any) -> Decimal:
    """Ô "1 hộp có bao nhiêu viên?" → số. Rác / 0 / âm / quá lớn → câu tiếng Việt."""
    try:
        hs = Decimal(str(v).replace(",", ".").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Số quy đổi phải là một con số (vd 30).") from exc
    if not hs.is_finite() or hs <= 0:
        raise ValidationError("Số quy đổi phải lớn hơn 0 (vd 30).")
    if hs > HE_SO_TOI_DA:
        raise ValidationError(
            f"Số quy đổi quá lớn (tối đa {so_nhom_nghin(HE_SO_TOI_DA)}) — "
            "kiểm tra lại có gõ thừa số 0 không."
        )
    hs = hs.quantize(BA_SO_LE, rounding=ROUND_HALF_UP)
    if hs <= 0:
        raise ValidationError("Số quy đổi quá nhỏ (tối đa 3 số lẻ).")
    return hs


def cau_hoi(don_vi: str, goc: str) -> str:
    return f"1 {don_vi} có bao nhiêu {goc}?"


def cau_ket_qua(so: Decimal, don_vi: str, he_so: Decimal, goc: str) -> str:
    """ "47 hộp = 1.410 viên" — đủ hai chiều để người nhập soi lại."""
    return f"{so_nhom_nghin(so)} {don_vi} = {so_nhom_nghin(so * he_so)} {goc}"


def cac_don_vi_nhap(bang: BangDonVi) -> list[dict[str, Any]]:
    """Đơn vị chọn được ở ô nhập: gốc trước, rồi mọi đơn vị đã khai (kể cả chỉ để
    nhập / đang tắt bán — vẫn nhập được theo hộp)."""
    if not bang.co_goc:
        return []
    ra = [
        {
            "don_vi": bang.goc,
            "he_so": "1",
            "goc": True,
            "nhan": f"{bang.goc} (kho đếm theo {bang.goc})",
        }
    ]
    for d in sorted(bang.dong.values(), key=lambda x: (x.he_so, x.don_vi)):
        ra.append(
            {
                "don_vi": d.don_vi,
                "he_so": so_dep(d.he_so),
                "goc": False,
                "nhan": f"{d.don_vi} (1 {d.don_vi} có "
                f"{so_nhom_nghin(d.he_so)} {bang.goc})",
            }
        )
    return ra


def _chua_khai(bang: BangDonVi, unit: str) -> str:
    ds = ", ".join(f"“{d['don_vi']}”" for d in cac_don_vi_nhap(bang))
    return (
        f"Thuốc này chưa khai đơn vị “{unit}”. Chọn một đơn vị đã khai ({ds}), "
        f"hoặc thêm “{unit}” ở Danh mục kho → Sửa → Đơn vị bán thêm "
        f"({cau_hoi(unit, bang.goc)})."
    )


async def xet_quy_doi(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    unit: str,
    he_so: Any = None,
) -> dict[str, Any]:
    """Nhập theo `unit` thì có phải đổi về đơn vị gốc (đơn vị kho đếm) không.

    Trả `{can_doi, don_vi_ban, don_vi, he_so_da_nho, he_so, la, loi, cac_don_vi}`:
    `don_vi` = chữ đã khai ứng với `unit`; `he_so` = gõ vào, không thì đã khai;
    `la` = gõ lệch hơn `NGUONG_LA` lần so với đã khai; `loi` = đơn vị chưa khai
    (không ném — màn xem trước cần danh sách để chọn lại). Hệ số rác → ném."""
    bang = (await doc_bang(conn, identity.clinic_id, [drug_catalog_id])).get(
        str(drug_catalog_id), BangDonVi()
    )
    kq: dict[str, Any] = {
        "can_doi": False,
        "don_vi_ban": bang.goc or None,
        "don_vi": (unit or "").strip(),
        "he_so_da_nho": None,
        "he_so": None,
        "la": False,
        "loi": None,
        "cac_don_vi": cac_don_vi_nhap(bang),
    }
    if not bang.co_goc or not chuan(unit):
        return kq
    if bang.la_goc(unit):
        return {**kq, "don_vi": bang.goc}
    khai = bang.nhan_ra(unit)
    if khai is None:
        return {**kq, "can_doi": True, "loi": _chua_khai(bang, unit.strip())}
    nho = bang.he_so(khai)
    hs = nho
    if he_so is not None and str(he_so).strip() != "":
        hs = doc_he_so(he_so)
    la = nho is not None and hs is not None and max(hs / nho, nho / hs) > NGUONG_LA
    return {
        **kq,
        "can_doi": True,
        "don_vi": khai,
        "he_so_da_nho": nho,
        "he_so": hs,
        "la": la,
    }


async def xem_truoc_quy_doi(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    unit: str,
    he_so: Any = None,
    so_luong: Any = None,
) -> dict[str, Any]:
    """Xem trước một dòng nhập (`GET /pharmacy/quy-doi`): đơn vị chọn được, câu hỏi,
    kết quả hai chiều, có cần xác nhận hệ số lạ. Chỉ đọc — không nhớ hệ số. Số
    lượng rác → không có kết quả (không ném); hệ số rác → câu tiếng Việt."""
    async with pool.acquire() as conn:
        x = await xet_quy_doi(
            conn,
            identity=identity,
            drug_catalog_id=drug_catalog_id,
            unit=unit,
            he_so=he_so,
        )
    dv, ban, hs = x["don_vi"], x["don_vi_ban"], x["he_so"]
    doi_duoc = x["can_doi"] and not x["loi"]
    kq: dict[str, Any] = {
        "can_doi": x["can_doi"],
        "don_vi_ban": ban,
        "don_vi": dv,
        "he_so_da_nho": x["he_so_da_nho"],
        "he_so": hs,
        "can_xac_nhan": x["la"],
        "cac_don_vi": x["cac_don_vi"],
        "loi": x["loi"],
        "cau_hoi": cau_hoi(dv, ban) if doi_duoc else None,
        "so_luong_quy_doi": None,
        "ket_qua": None,
    }
    luong = so_luong_sach(so_luong)
    if doi_duoc and hs is not None and luong is not None and luong > 0:
        kq["so_luong_quy_doi"] = (luong * hs).quantize(BA_SO_LE)
        kq["ket_qua"] = cau_ket_qua(luong, dv, hs, ban)
    return kq
