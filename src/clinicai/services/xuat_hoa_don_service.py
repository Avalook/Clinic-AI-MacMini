"""Xuất hoá đơn GTGT theo ĐÚNG mẫu nhập của phần mềm hoá đơn (MISA meInvoice).

Kế toán không phải gõ tay lại từng phiếu thu (Tuyền 13/10/2026). File dựng từ
CHÍNH tệp mẫu kế toán gửi (`mau/hoa_don_gtgt_1_thue_suat.xlsx`) — giữ nguyên
hàng tiêu đề cột, font, độ rộng cột; BỎ 8 dòng chữ hướng dẫn phía trên của mẫu
(Tuyền 13/10: file tải về chỉ còn bảng) → tiêu đề ở dòng 1, dữ liệu từ dòng 2.
Ô nào hệ thống chưa có dữ liệu (mã số thuế, thuế suất, tiền thuế…) để TRỐNG.

Một phiếu thu = một hoá đơn. Không tự tạo con số: tiền lấy từ dòng phiếu đã thu
(sau giảm giá), trừ phần đã hoàn xong theo đúng dòng.
"""

from __future__ import annotations

import io
import warnings
from collections.abc import Mapping, Sequence
from copy import copy
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import asyncpg
from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.hoa_don_cong_ty_service import doc_cong_ty_cho_phieu
from clinicai.services.hoa_don_excel import HINH_THUC
from clinicai.services.thue_gtgt import (
    CHE_DO_MOT,
    CHE_DO_TACH,
    ap_thue_hoa_don,
    nguon_thue_suat,
)

MAU = Path(__file__).parent / "mau" / "hoa_don_gtgt_1_thue_suat.xlsx"
#: Hàng tiêu đề cột trong TỆP MẪU (dòng 1–8 phía trên là chữ hướng dẫn — bỏ).
TIEU_DE_MAU = 9
#: Dòng đầu tiên của dữ liệu trong FILE XUẤT (tiêu đề đã lên dòng 1).
DONG_DAU = 2
#: Dịch vụ không ghi đơn vị trên phiếu → "Lần" (đúng ví dụ trong mẫu kế toán gửi).
DVT_DICH_VU = "Lần"
_NGUON_DICH_VU = frozenset({"exam", "service_order", "lieu_trinh"})
#: Dòng hoá đơn thuộc nhóm hàng nào — kế toán đặt thuế suất theo nhóm (Q16).
NHOM_THUOC = "THUOC"
NHOM_VAT_TU = "VAT_TU"
NHOM_DICH_VU = "DICH_VU"
_NHOM_THEO_NGUON = {"prescription": NHOM_THUOC, "vat_tu": NHOM_VAT_TU}

#: Câu gợi ý khi bấm vào ô — chép nguyên văn từ mẫu. openpyxl không đọc được
#: phần mở rộng x14 chứa chúng nên phải gắn lại, để file giống mẫu khi mở.
GOI_Y: tuple[tuple[str, str], ...] = (
    (
        "A1:A1100",
        "- Nhập số thứ tự của hóa đơn\n"
        "- Chú ý: Mỗi số thứ tự sẽ tương ứng với 1 hóa đơn",
    ),
    ("B1:B1100", "Nhập Ngày hóa đơn"),
    ("C1:C1100", "Nhập Tên đơn vị mua hàng\n"),
    ("D1:D1100", "Nhập Địa chỉ đơn vị mua hàng\n"),
    ("E1:E1100", "Nhập Mã số thuế đơn vị mua hàng"),
    ("F1:F1100", "Nhập Tên người mua hàng"),
    ("G1:I1100", "Nhập Email người nhận hóa đơn"),
    ("J1:J1100", "Nhập hình thức thanh toán"),
    (
        "K1:K1100",
        "Nhập thuế suất thuế GTGT: \n- 0: 0%\n- 5: 5%\n- 8: 8%\n- 10: 10%\n"
        "- KCT: Không chịu thuế GTGT\n- KKKNT: Không kê khai nộp thuế GTGT\n"
        "- KHAC: Trường hợp khác",
    ),
    ("L1:L1100", "Nhập tổng tiền thuế GTGT của hóa đơn\n"),
    ("M1:M1100", "Nhập Tên hàng hóa/dịch vụ\n"),
    ("N1:N1100", "Nhập Đơn vị tính"),
    ("O1:O1100", "Nhập Số lượng\n"),
    ("P1:P1100", "Nhập Đơn giá\n"),
    ("Q1:Q1100", "Nhập Thành tiền\n"),
)

_THEM_DONG = """
SELECT bl.id::text id, bl.unit, bl.source_type,
 coalesce(nullif(btrim(dc.ma_hang), ''), nullif(btrim(o.service_code), '')) ma,
 -- Thuế suất theo MẶT HÀNG (kế toán đặt): thuốc → drug_catalog; dịch vụ →
 -- service_price cùng mã; vật tư bán thêm → service_price của dòng vật tư.
 coalesce(dc.thue_suat_ma, sp_dv.thue_suat_ma, sp_vt.thue_suat_ma) thue_mh
FROM payment_bill_line bl
LEFT JOIN drug_catalog dc ON dc.id=bl.drug_catalog_id AND dc.clinic_id=bl.clinic_id
LEFT JOIN service_order o ON bl.source_type='service_order'
 AND o.clinic_id=bl.clinic_id AND o.id::text=bl.source_id
LEFT JOIN service_price sp_dv ON sp_dv.clinic_id=bl.clinic_id
 AND sp_dv."group"='dich_vu' AND sp_dv.service_code=o.service_code
LEFT JOIN luot_vat_tu lv ON bl.source_type='vat_tu'
 AND lv.clinic_id=bl.clinic_id AND lv.id::text=bl.source_id
LEFT JOIN service_price sp_vt ON sp_vt.id=lv.service_price_id
 AND sp_vt.clinic_id=bl.clinic_id
WHERE bl.clinic_id=$1::uuid AND bl.payment_cycle_id=ANY($2::uuid[])
"""
_THUE_NHOM = "SELECT nhom, thue_suat_ma FROM thue_suat_nhom WHERE clinic_id=$1::uuid"
_THEM_KHACH = """
SELECT pc.payment_cycle_id::text id,
 coalesce(nullif(btrim(p.address), ''),
   nullif(concat_ws(', ', nullif(btrim(p.address_detail), ''),
     nullif(btrim(p.ward_name), ''), nullif(btrim(p.province_name), '')), ''))
   dia_chi,
 nullif(btrim(p.national_id_number), '') cccd,
 coalesce(nullif(btrim(p.email), ''),
   (SELECT c.channel_value FROM patient_contact_channel c
     WHERE c.clinic_id=p.clinic_id AND c.clinic_patient_id=p.clinic_patient_id
       AND c.channel_type='EMAIL'
     ORDER BY c.is_primary DESC, c.created_at DESC LIMIT 1)) email
FROM payment_cycle pc
JOIN visit v ON v.visit_id=pc.visit_id AND v.clinic_id=pc.clinic_id
LEFT JOIN patient p ON p.clinic_patient_id=v.clinic_patient_id
 AND p.clinic_id=v.clinic_id
WHERE pc.clinic_id=$1::uuid AND pc.payment_cycle_id=ANY($2::uuid[])
"""


def _ngay(iso: Any) -> str:
    """ISO → "dd/mm/yyyy" giờ Việt Nam; rác → rỗng (không ném)."""
    try:
        return (
            datetime.fromisoformat(str(iso)).astimezone(CLINIC_TZ).strftime("%d/%m/%Y")
        )
    except (TypeError, ValueError):
        return ""


def _don_gia(thanh_tien: int, so_luong: float) -> int | float:
    if so_luong <= 0:
        return thanh_tien
    gia = Decimal(thanh_tien) / Decimal(str(so_luong))
    return int(gia) if gia == gia.to_integral_value() else float(round(gia, 4))


def _tron_dong(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _so(x: float) -> int | float:
    return int(x) if float(x).is_integer() else x


def dung_hoa_don(
    khach: Sequence[Mapping[str, Any]],
    them_dong: Mapping[str, Mapping[str, Any]],
    them_khach: Mapping[str, Mapping[str, Any]],
    thue_nhom: Mapping[str, str] | None = None,
    ghi_de: Mapping[str, str] | None = None,
    them_cong_ty: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Phiếu thu trong kỳ → danh sách hoá đơn theo giờ thu. Hàm thuần.

    Bỏ phiếu đã huỷ và phiếu thu ngoài kỳ (chỉ có hoàn / huỷ trong kỳ). Dòng
    đã hoàn xong trừ đúng số tiền / số lượng hoàn; còn 0 thì bỏ dòng; phiếu
    không còn dòng nào thì bỏ phiếu. Hoàn đang chờ chưa trừ — ghi chú để kế
    toán xem lại.

    Mỗi dòng mang `thue_suat` / `thue_nguon` (kế toán đặt: sửa tay dòng > mặt
    hàng > nhóm; rỗng = chưa đặt). Chưa đặt gì thì số tiền không đổi.
    """
    phieu = [
        (k, p)
        for k in khach
        for p in k.get("phieu") or []
        if p.get("thu_trong_ky") and p.get("trang_thai") != "DA_HUY"
    ]
    phieu.sort(key=lambda kp: (str(kp[1].get("thu_luc") or ""), str(kp[1]["id"])))
    out: list[dict[str, Any]] = []
    for k, p in phieu:
        hoan_tien: dict[str, int] = {}
        hoan_sl: dict[str, float] = {}
        hoan_khong_dong = 0
        cho_hoan = 0
        for r in p.get("hoan") or []:
            if r.get("trang_thai") == "PENDING":
                cho_hoan += int(r.get("so_tien") or 0)
            if r.get("trang_thai") != "COMPLETED":
                continue
            dong_hoan = r.get("dong") or []
            if not dong_hoan:
                hoan_khong_dong += int(r.get("so_tien") or 0)
            for d in dong_hoan:
                hoan_tien[d["id"]] = hoan_tien.get(d["id"], 0) + int(d["thanh_tien"])
                hoan_sl[d["id"]] = hoan_sl.get(d["id"], 0.0) + float(d["so_luong"])
        dong: list[dict[str, Any]] = []
        for d in p.get("dong") or []:
            tien = int(d["thanh_tien"]) - hoan_tien.get(d["id"], 0)
            if tien <= 0:
                continue
            sl = float(d["so_luong"]) - hoan_sl.get(d["id"], 0.0)
            if sl <= 0:
                sl = float(d["so_luong"])
            them = them_dong.get(d["id"]) or {}
            dvt = (them.get("unit") or "").strip()
            if not dvt and them.get("source_type") in _NGUON_DICH_VU:
                dvt = DVT_DICH_VU
            goc = int(d["thanh_tien"])
            # Giảm giá đã chia cho dòng; hoàn một phần thì giảm còn lại theo tỉ lệ.
            giam = int(d.get("giam_gia") or 0)
            if giam and tien != goc:
                giam = _tron_dong(Decimal(giam) * tien / goc)
            nhom = _NHOM_THEO_NGUON.get(
                str(them.get("source_type") or ""), NHOM_DICH_VU
            )
            thue, nguon_thue = nguon_thue_suat(
                dong=(ghi_de or {}).get(d["id"]),
                mat_hang=them.get("thue_mh"),
                nhom=(thue_nhom or {}).get(nhom),
            )
            dong.append(
                {
                    "id": d["id"],
                    "ten": str(d.get("ten") or ""),
                    "ma": str(them.get("ma") or ""),
                    "nhom": nhom,
                    "thue_suat": thue,
                    "thue_nguon": nguon_thue,
                    "dvt": dvt,
                    "so_luong": _so(sl),
                    "don_gia": _don_gia(tien, sl),
                    "thanh_tien": tien,
                    # Số TRƯỚC giảm / phần giảm của dòng — chỉ để kế toán bật
                    # "ghi giảm giá trên hoá đơn" (K2); thanh_tien vẫn là SAU giảm.
                    "giam_gia": giam,
                    "truoc_giam": tien + giam,
                }
            )
        if not dong:
            continue
        kh = them_khach.get(p["id"]) or {}
        ct = (them_cong_ty or {}).get(p["id"]) or {}
        ghi_chu = []
        if hoan_khong_dong:
            ghi_chu.append(
                f"Có hoàn {hoan_khong_dong:,}đ không theo dòng — kiểm lại".replace(
                    ",", "."
                )
            )
        if cho_hoan:
            ghi_chu.append(f"Đang chờ hoàn {cho_hoan:,}đ".replace(",", "."))
        # HĐ công ty (Q15/Q19): đơn vị mua = công ty; CHỈ địa chỉ + email của công
        # ty — không đưa SĐT / CCCD / địa chỉ / email cá nhân của khách vào file.
        # Ô "người mua" để trống trừ khi người ghi có điền.
        la_hd_cong_ty = bool(ct.get("ten_cong_ty"))
        out.append(
            {
                "stt": len(out) + 1,
                "payment_cycle_id": p["id"],
                "ma_phieu": p.get("ma"),
                "kind": p.get("kind"),
                "ngay": _ngay(p.get("thu_luc")),
                "ten_khach": k.get("ten") or "",
                "ma_bn": k.get("ma_bn"),
                "la_hd_cong_ty": la_hd_cong_ty,
                "ten_cong_ty": ct.get("ten_cong_ty") or "",
                "dia_chi_cong_ty": ct.get("dia_chi_cong_ty") or "",
                "dia_chi": (
                    ct.get("dia_chi_cong_ty") or ""
                    if la_hd_cong_ty
                    else kh.get("dia_chi") or ""
                ),
                "ma_so_thue": ct.get("ma_so_thue") or "",
                "nguoi_mua": (
                    ct.get("nguoi_mua") or "" if la_hd_cong_ty else k.get("ten") or ""
                ),
                "email": (
                    ct.get("email_nhan_hd") or ""
                    if la_hd_cong_ty
                    else kh.get("email") or ""
                ),
                "so_dien_thoai": ""
                if la_hd_cong_ty
                else (k.get("so_dien_thoai") or ""),
                "cccd": "" if la_hd_cong_ty else (kh.get("cccd") or ""),
                "hinh_thuc": HINH_THUC.get(str(p.get("hinh_thuc") or ""), ""),
                "dong": dong,
                "tong": sum(d["thanh_tien"] for d in dong),
                "ghi_chu": ghi_chu,
            }
        )
    return out


def _chu(cell: Any, value: str) -> None:
    """Ghi CHỮ (kể cả chữ bắt đầu bằng "=") — không bao giờ thành công thức."""
    cell.value = value
    cell.data_type = "s"


def xlsx_misa(hoa_don: Sequence[Mapping[str, Any]]) -> bytes:
    """Đổ hoá đơn vào bản sao tệp mẫu; trả bytes .xlsx sửa được như mẫu."""
    with warnings.catch_warnings():
        # Mẫu có phần mở rộng x14 (câu gợi ý) openpyxl không đọc — gắn lại dưới.
        warnings.simplefilter("ignore", UserWarning)
        wb = load_workbook(MAU)
    ws = wb.active
    assert ws is not None
    cao_tieu_de = ws.row_dimensions[TIEU_DE_MAU].height
    ws.delete_rows(1, TIEU_DE_MAU - 1)
    # delete_rows không dời chiều cao dòng → gỡ chiều cao cũ, gắn lại cho tiêu đề.
    for r in [r for r in ws.row_dimensions if r <= TIEU_DE_MAU]:
        del ws.row_dimensions[r]
    ws.row_dimensions[1].height = cao_tieu_de
    mau_dong = [ws.cell(DONG_DAU, c)._style for c in range(1, 18)]
    # Xoá dòng ví dụ + công thức mẫu (dữ liệu → hết): file chỉ còn dữ liệu thật,
    # không còn công thức để phần mềm nhập đọc nhầm ô rỗng.
    for row in ws.iter_rows(min_row=DONG_DAU, max_row=max(ws.max_row, DONG_DAU)):
        for cell in row:
            cell.value = None
            cell.hyperlink = None  # ô email ví dụ của mẫu gắn link mailto
    r = DONG_DAU
    for hd in hoa_don:
        for i, d in enumerate(hd["dong"]):
            dau = i == 0
            # HĐ công ty: C=tên cty, D=địa chỉ cty, E=MST, H/I (SĐT/CCCD) trống —
            # `dung_hoa_don` đã chọn đúng giá trị cho từng loại, ở đây chỉ chép.
            la_ct = hd.get("la_hd_cong_ty")
            van_ban = {
                1: str(hd["stt"]),
                2: hd["ngay"],
                3: hd["ten_cong_ty"] if la_ct else hd["ten_khach"],
                4: hd["dia_chi"],
                5: hd["ma_so_thue"],
                6: hd["nguoi_mua"],
                7: hd["email"],
                8: hd.get("so_dien_thoai", ""),
                9: hd.get("cccd", ""),
                10: hd["hinh_thuc"],
            }
            for c in range(1, 18):
                ws.cell(r, c)._style = copy(mau_dong[c - 1])
            for c, v in van_ban.items():
                # Thông tin chung chỉ ghi ở dòng đầu của hoá đơn (như ví dụ mẫu);
                # số thứ tự lặp ở mọi dòng để phần mềm gom dòng vào đúng hoá đơn.
                if v and (dau or c == 1):
                    _chu(ws.cell(r, c), str(v))
            k = str(hd.get("thue_suat_ma") or "")
            if dau and k:
                # Mẫu tính thuế bằng công thức trên ô K → con số phải là SỐ.
                ws.cell(r, 11).value = int(k) if k.isdigit() else k
            if dau and hd.get("tien_thue") is not None:
                ws.cell(r, 12).value = hd["tien_thue"]
            _chu(ws.cell(r, 13), d["ten"])
            if d["dvt"]:
                _chu(ws.cell(r, 14), d["dvt"])
            ws.cell(r, 15).value = d["so_luong"]
            ws.cell(r, 16).value = d["don_gia"]
            ws.cell(r, 17).value = d["thanh_tien"]
            r += 1
    for sqref, loi_nhac in GOI_Y:
        dv = DataValidation(
            allow_blank=True, showInputMessage=True, prompt=loi_nhac, sqref=sqref
        )
        ws.add_data_validation(dv)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class XuatHoaDonService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def doc_goc(
        self,
        *,
        identity: StaffIdentity,
        tu: str | None = None,
        den: str | None = None,
        loai: str | None = None,
        co_so: str | None = None,
        ghi_de: Mapping[str, str] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """(phạm vi, hoá đơn GỐC — số tiền gồm thuế, chưa tách). Cùng cổng quyền /
        phạm vi với Danh sách hoá đơn (không tự dựng luật). Màn "Theo hàng hoá" đọc
        từ đây để số của nó không bao giờ bị tách thuế làm lệch."""
        data = await DanhSachHoaDonService(self.pool).xem(
            identity=identity, tu=tu, den=den, loai=loai, co_so=co_so
        )
        ids = [p["id"] for k in data["khach"] for p in k["phieu"]]
        async with self.pool.acquire() as conn:
            them_dong = {
                r["id"]: dict(r)
                for r in await conn.fetch(_THEM_DONG, identity.clinic_id, ids)
            }
            them_khach = {
                r["id"]: dict(r)
                for r in await conn.fetch(_THEM_KHACH, identity.clinic_id, ids)
            }
            thue_nhom = {
                r["nhom"]: r["thue_suat_ma"]
                for r in await conn.fetch(_THUE_NHOM, identity.clinic_id)
            }
            them_cong_ty = await doc_cong_ty_cho_phieu(conn, identity.clinic_id, ids)
        goc = dung_hoa_don(
            data["khach"], them_dong, them_khach, thue_nhom, ghi_de, them_cong_ty
        )
        return data, goc

    async def xem(
        self,
        *,
        identity: StaffIdentity,
        tu: str | None = None,
        den: str | None = None,
        loai: str | None = None,
        co_so: str | None = None,
        che_do: str | None = None,
        ghi_giam_gia: bool = False,
        ghi_de: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """`che_do` (khi một phiếu có nhiều thuế suất): "tach" (mặc định) = mỗi thuế
        suất một hoá đơn, "mot" = một hoá đơn. `ghi_giam_gia` = K2 (dòng giá gốc +
        dòng chiết khấu). `ghi_de` = sửa tay thuế suất từng dòng {id dòng: mã}.
        Rác ở các tham số này → bỏ qua, không ném."""
        data, goc = await self.doc_goc(
            identity=identity, tu=tu, den=den, loai=loai, co_so=co_so, ghi_de=ghi_de
        )
        mode = CHE_DO_MOT if che_do == CHE_DO_MOT else CHE_DO_TACH
        hoa_don = [
            hd
            for h in goc
            for hd in ap_thue_hoa_don(h, che_do=mode, ghi_giam_gia=bool(ghi_giam_gia))
        ]
        # Tách thuế suất sinh nhiều hoá đơn từ một phiếu: số thứ tự (cột A) phải
        # duy nhất, phần mềm hoá đơn gom dòng theo nó.
        for i, hd in enumerate(hoa_don, 1):
            hd["stt"] = i
        return {
            "tu": data["tu"],
            "den": data["den"],
            "co_so": data.get("co_so"),
            "hoa_don": hoa_don,
            "so_hoa_don": len(hoa_don),
            "so_dong": sum(len(h["dong"]) for h in hoa_don),
            "tong": sum(h["tong"] for h in hoa_don),
            "tien_thue": sum(int(h["tien_thue"] or 0) for h in hoa_don),
            "dong_chua_thue": sum(
                1 for h in goc for d in h["dong"] if d["thue_suat"] is None
            ),
            "che_do": mode,
            "ghi_giam_gia": bool(ghi_giam_gia),
        }
