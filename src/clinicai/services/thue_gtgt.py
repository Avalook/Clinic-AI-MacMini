"""Thuế GTGT cho màn / tệp xuất của kế toán — hàm thuần, KHÔNG chạm vận hành.

Tuyền chốt 14/10/2026 (K1): giá trong bảng giá ĐÃ GỒM thuế; quầy, hoá đơn và
báo cáo ngày không tính thuế. Chỉ khi kế toán xuất hoá đơn mới tách ngược:
đơn giá chưa thuế = giá / (1 + t), làm tròn đồng, phần lệch do làm tròn dồn
vào dòng cuối để tổng tiền hàng + tiền thuế = đúng số tiền khách đã trả.

Thuế suất lưu dạng chữ ("8", "8.5", "0", "KCT", "KKKNT") để kế toán tự nhập
% bất kỳ. Giá trị rác → rỗng (không ném) — luật chung về đầu vào người dùng.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

#: Hai mã không phải con số của mẫu MISA: Không chịu thuế / Không kê khai nộp thuế.
KHONG_CHIU_THUE = "KCT"
KHONG_KE_KHAI = "KKKNT"
MA_KHONG_THUE = (KHONG_CHIU_THUE, KHONG_KE_KHAI)
#: Ba nhóm mặt hàng kế toán đặt thuế chung (mục 2c · Q16).
NHOM_HANG = ("DICH_VU", "THUOC", "VAT_TU")
#: Trần % cho phép tự nhập (chặn gõ nhầm 800).
TRAN_PHAN_TRAM = Decimal(100)
_MOT_DONG = Decimal(1)


def chuan_hoa_thue_suat(raw: Any) -> str | None:
    """ "8%", " 8,5 ", "kct" → "8", "8.5", "KCT". Rác / âm / trên 100 → None."""
    if raw is None or isinstance(raw, bool):
        return None
    chu = str(raw).strip().upper().replace(" ", "")
    if not chu:
        return None
    if chu in MA_KHONG_THUE:
        return chu
    chu = chu.removesuffix("%").replace(",", ".")
    try:
        so = Decimal(chu)
    except InvalidOperation:
        return None
    if not so.is_finite() or so < 0 or so > TRAN_PHAN_TRAM:
        return None
    so = so.normalize()
    # normalize() có thể ra dạng khoa học ("1E+1") — in lại bằng dấu chấm tĩnh.
    return format(so, "f")


def phan_tram(ma: str | None) -> Decimal | None:
    """Mã đã chuẩn hoá → số %; KCT/KKKNT → 0 (không có thuế); rỗng → None."""
    ma = chuan_hoa_thue_suat(ma)
    if ma is None:
        return None
    if ma in MA_KHONG_THUE:
        return Decimal(0)
    return Decimal(ma)


def chon_thue_suat(
    *,
    dong: Any = None,
    mat_hang: Any = None,
    nhom: Any = None,
) -> str | None:
    """Ưu tiên: sửa tay dòng > mặt hàng > nhóm > trống (Tuyền 14/10, Q16).

    Giá trị rác ở một tầng coi như chưa đặt ở tầng đó — rơi xuống tầng sau, để
    một ô gõ hỏng không che mất thuế suất đúng ở tầng dưới.
    """
    for tang in (dong, mat_hang, nhom):
        ma = chuan_hoa_thue_suat(tang)
        if ma is not None:
            return ma
    return None


def nguon_thue_suat(
    *, dong: Any = None, mat_hang: Any = None, nhom: Any = None
) -> tuple[str | None, str | None]:
    """(thuế suất, tầng quyết định: "dong" | "mat_hang" | "nhom" | None)."""
    for tang, gia_tri in (("dong", dong), ("mat_hang", mat_hang), ("nhom", nhom)):
        ma = chuan_hoa_thue_suat(gia_tri)
        if ma is not None:
            return ma, tang
    return None, None


def _tron_dong(x: Decimal) -> int:
    return int(x.quantize(_MOT_DONG, rounding=ROUND_HALF_UP))


def tach_thue(gom_thue: int, ma: str | None) -> tuple[int, int]:
    """Số đã gồm thuế → (tiền hàng chưa thuế, tiền thuế); tổng luôn = đầu vào."""
    p = phan_tram(ma)
    if p is None or p == 0 or gom_thue <= 0:
        return int(gom_thue), 0
    thue = _tron_dong(Decimal(gom_thue) * p / (Decimal(100) + p))
    return int(gom_thue) - thue, thue


def tach_thue_cac_dong(
    gom_thue: Sequence[int], ma: str | None
) -> tuple[list[int], int]:
    """Tách một HOÁ ĐƠN một thuế suất: (tiền hàng từng dòng, tổng tiền thuế).

    Tổng thuế tính MỘT lần trên tổng tiền hoá đơn (đúng cách phần mềm hoá đơn
    cộng); từng dòng làm tròn riêng, lệch dồn dòng cuối để
    Σ tiền hàng + tổng thuế = Σ đầu vào (= số khách trả).
    """
    tong = sum(int(x) for x in gom_thue)
    tong_hang, tong_thue = tach_thue(tong, ma)
    p = phan_tram(ma)
    if p is None or p == 0 or tong <= 0 or not gom_thue:
        return [int(x) for x in gom_thue], tong_thue
    hang = [
        _tron_dong(Decimal(int(x)) * Decimal(100) / (Decimal(100) + p))
        for x in gom_thue
    ]
    hang[-1] += tong_hang - sum(hang)
    return hang, tong_thue


def nhom_theo_thue_suat(
    dong: Sequence[Mapping[str, Any]],
) -> dict[str | None, list[Mapping[str, Any]]]:
    """Gom dòng theo `thue_suat` (khoá None = chưa đặt), giữ thứ tự xuất hiện."""
    out: dict[str | None, list[Mapping[str, Any]]] = {}
    for d in dong:
        out.setdefault(chuan_hoa_thue_suat(d.get("thue_suat")), []).append(d)
    return out


def dem_dong_chua_thue(dong: Sequence[Mapping[str, Any]]) -> int:
    """Số dòng chưa có thuế suất — màn xuất nhắc "N dòng chưa có thuế suất"."""
    return sum(1 for d in dong if chuan_hoa_thue_suat(d.get("thue_suat")) is None)


# ── Áp thuế lên hoá đơn (màn / tệp xuất của kế toán) ─────────────────────────
CHE_DO_TACH = "tach"  # mỗi thuế suất một hoá đơn (mẫu MISA 1 thuế suất)
CHE_DO_MOT = "mot"  # một hoá đơn (mẫu nhiều thuế suất — chờ chị Hoài)
#: Mẫu MISA chỉ nhận 0/5/8/10/KCT/KKKNT/KHAC ở cột K; % khác ghi KHAC.
MA_MISA = frozenset({"0", "5", "8", "10", KHONG_CHIU_THUE, KHONG_KE_KHAI})
MA_KHAC = "KHAC"
GHI_CHU_NHIEU_THUE = (
    "Nhiều thuế suất trong một hoá đơn — mẫu nhiều thuế suất chờ kế toán xác nhận"
)


def ma_cot_k(ma: str | None) -> str:
    """Giá trị ô K (thuế suất) của mẫu MISA; rỗng nếu chưa đặt."""
    if ma is None:
        return ""
    return ma if ma in MA_MISA else MA_KHAC


def _nhan(ma: str) -> str:
    return ma if ma in MA_KHONG_THUE else f"{ma}%"


def _mo_rong_giam_gia(dong: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """K2: dòng có giảm → dòng giá gốc + dòng chiết khấu (số âm), cùng thuế suất."""
    out: list[dict[str, Any]] = []
    for d in dong:
        giam = int(d.get("giam_gia") or 0)
        if giam <= 0:
            out.append(dict(d))
            continue
        sl = float(d.get("so_luong") or 0)
        goc = int(d["truoc_giam"])
        out.append(
            {
                **d,
                "thanh_tien": goc,
                "don_gia": goc if sl <= 0 else _gia(goc, sl),
            }
        )
        out.append(
            {
                **d,
                "ten": f"Chiết khấu — {d.get('ten') or ''}".rstrip(" —"),
                "dvt": "",
                "so_luong": 1,
                "don_gia": -giam,
                "thanh_tien": -giam,
                "giam_gia": 0,
                "truoc_giam": -giam,
            }
        )
    return out


def _gia(thanh_tien: int, so_luong: float) -> int | float:
    g = Decimal(thanh_tien) / Decimal(str(so_luong))
    return int(g) if g == g.to_integral_value() else float(round(g, 4))


def _dong_chua_thue(dong: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for d in dong if chuan_hoa_thue_suat(d.get("thue_suat")) is None)


def _ap_mot_thue(
    hd: Mapping[str, Any], dong: list[dict[str, Any]], ma: str | None
) -> dict[str, Any]:
    """Một nhóm dòng CÙNG thuế suất → hoá đơn: đơn giá / thành tiền CHƯA thuế."""
    tien = [int(d["thanh_tien"]) for d in dong]
    hang, thue = tach_thue_cac_dong(tien, ma)
    moi: list[dict[str, Any]] = []
    for d, h in zip(dong, hang, strict=True):
        sl = float(d.get("so_luong") or 0)
        moi.append({**d, "thanh_tien": h, "don_gia": _gia(h, sl) if sl > 0 else h})
    return {
        **hd,
        "dong": moi,
        "tong": sum(tien),
        "tien_hang": sum(hang),
        "tien_thue": thue if ma is not None else None,
        "thue_suat_ma": ma_cot_k(ma),
    }


def ap_thue_hoa_don(
    hd: Mapping[str, Any],
    *,
    che_do: str = CHE_DO_TACH,
    ghi_giam_gia: bool = False,
) -> list[dict[str, Any]]:
    """Một hoá đơn → 1..n hoá đơn đã tách thuế. Hàm thuần.

    - Chưa dòng nào có thuế suất (kế toán chưa đặt) và không bật ghi giảm giá →
      trả đúng như cũ (K/L trống, số tiền gồm thuế): xuất MISA hôm nay không đổi.
    - `tach`: mỗi thuế suất một hoá đơn; dòng chưa có thuế suất thành hoá đơn
      riêng, ô K/L trống (kế toán điền tay), nhắc "N dòng chưa có thuế suất".
    - `mot`: một hoá đơn; cùng một thuế suất thì K = thuế suất đó, nhiều thuế suất
      thì K trống, L = tổng tiền thuế (khung — mẫu nhiều thuế suất chờ xác nhận).
    - `ghi_giam_gia` (K2): mỗi dòng có giảm thành dòng giá gốc + dòng chiết khấu.
    Tổng (tiền hàng + tiền thuế) luôn bằng số khách trả của hoá đơn gốc.
    """
    dong = [dict(d) for d in hd.get("dong") or []]
    if ghi_giam_gia:
        dong = _mo_rong_giam_gia(dong)
    chua = _dong_chua_thue(dong)
    goc = {**hd, "dong": dong, "tien_hang": None, "tien_thue": None}
    goc["thue_suat_ma"] = ""
    goc["tong"] = sum(int(d["thanh_tien"]) for d in dong)
    if chua == len(dong):
        return [goc]
    nhom = nhom_theo_thue_suat(dong)
    ghi_chu = list(hd.get("ghi_chu") or [])
    if che_do == CHE_DO_MOT:
        ma_co = [m for m in nhom if m is not None]
        if len(ma_co) == 1 and not chua:
            return [{**_ap_mot_thue(hd, dong, ma_co[0]), "ghi_chu": ghi_chu}]
        # Nhiều thuế suất / có dòng chưa đặt: K trống, L = tổng thuế các nhóm.
        moi: list[dict[str, Any]] = []
        tong_thue = 0
        for ma, ds in nhom.items():
            if ma is None:
                moi.extend(dict(d) for d in ds)
                continue
            x = _ap_mot_thue(hd, [dict(d) for d in ds], ma)
            moi.extend(x["dong"])
            tong_thue += int(x["tien_thue"] or 0)
        dem = _dong_chua_thue(moi)
        nhac = [GHI_CHU_NHIEU_THUE] if len(ma_co) > 1 else []
        if dem:
            nhac.append(f"{dem} dòng chưa có thuế suất")
        return [
            {
                **goc,
                "dong": moi,
                "tien_hang": sum(int(d["thanh_tien"]) for d in moi),
                "tien_thue": tong_thue,
                "ghi_chu": [*ghi_chu, *nhac],
            }
        ]
    # Tách theo thuế suất (mặc định): mỗi nhóm một hoá đơn, giữ thứ tự dòng.
    out: list[dict[str, Any]] = []
    for ma, ds in nhom.items():
        if ma is None:
            out.append(
                {
                    **goc,
                    "dong": [dict(d) for d in ds],
                    "tong": sum(int(d["thanh_tien"]) for d in ds),
                    "ghi_chu": [
                        *ghi_chu,
                        f"{len(ds)} dòng chưa có thuế suất — ô thuế để trống",
                    ],
                }
            )
            continue
        x = _ap_mot_thue(hd, [dict(d) for d in ds], ma)
        x["ghi_chu"] = [
            *ghi_chu,
            *([f"Tách theo thuế suất {_nhan(ma)}"] if len(nhom) > 1 else []),
            *(
                [f"Thuế suất {ma}% ghi KHAC (ngoài 0/5/8/10)"]
                if ma_cot_k(ma) == MA_KHAC
                else []
            ),
        ]
        out.append(x)
    return out
