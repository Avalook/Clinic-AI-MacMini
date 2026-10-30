"""Theo dõi thuốc: thuốc đang ở đâu và đã đi qua những đâu (Tuyền 31/10/2026).

CHỈ ĐỌC, chỉ kho của cơ sở đang làm (`identity.location_id`). Hai phần:

* **Đang ở đâu** — mỗi đơn vị: ở kho, ở quầy, đã giao chờ gán lô, khách trả chờ
  kiểm, đã huỷ luỹ kế; và từng lô + hạn dùng. Hộp không cộng với viên.
* **Dòng thời gian** — sổ kho `inventory_txn` + hai loại việc KHÔNG có dòng sổ:
  giao chưa gán lô (kho chưa trừ) và thuốc trả được quyết "nhập lại bán được".

Lấy mọi loại dòng sổ trừ `SALE` / `SALE_REVERSAL` (cam kết bán, không đổi tồn) chứ
không liệt kê loại được phép: loại dòng mới thêm sau vẫn hiện, không bị lọc mất.
Tên hành động nằm MỘT chỗ — `HANH_DONG`; mã lạ ra `HANH_DONG_LA`, màn không vỡ.

Tồn trước → sau là của ĐÚNG LÔ TẠI NƠI ĐÓ (hàng `drug_batch`), không phải tổng
thuốc: một lần chuyển kho không đổi tổng, nên tổng sẽ tụt rồi hồi như mất thuốc.
Tính ngược từ tồn hiện tại như thẻ kho, đúng cả khi lô có tồn khởi điểm ngoài sổ.

Một phiếu chuyển là HAI dòng sổ (trừ ở nơi đi, cộng ở nơi đến) nhưng là MỘT việc:
gộp thành một sự kiện theo `phieu_kho_dong`, mang tồn của cả hai nơi.

Số "Tồn trên máy" = kho + quầy, đúng bằng tồn các lô. Hai phần hiện riêng, KHÔNG
cộng lần nữa: khách trả chờ kiểm đã NẰM TRONG tồn quầy; đã giao chờ gán lô thì kho
CHƯA trừ, nên `tren_ke` (thuốc thật trên kệ) = tồn trên máy − chờ gán.

Tên khách, mã BN: cùng mức quyền thẻ kho và hàng chờ gán lô (`pharmacy.view` /
`pharmacy.dispense`); màn này không trả SĐT.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, doc_ngay_xem
from clinicai.core.tran import canh_bao_neu_day

#: Số dòng mỗi trang trên màn.
SO_DONG_MOT_TRANG = 50
#: Excel lấy tối đa chừng này dòng mới nhất — màn nói rõ khi vượt.
XUAT_TOI_DA = 5000
#: Số gợi ý khi gõ tìm thuốc / số lô.
TIM_TOI_DA = 20
#: Số lô tối đa ở phần "đang ở đâu" của một thuốc.
LO_TOI_DA = 300

#: BẢNG NHÃN DUY NHẤT. Mã là `txn_type` của sổ, hoặc mã riêng do `_SU_KIEN` đặt
#: khi cùng một `txn_type` mang hai nghĩa. `DISPENSE_REVERSAL` khai sẵn cho nhánh
#: đảo lần giao; đổi tên loại ở nhánh ấy thì chỉ thêm một dòng ở đây.
HANH_DONG: dict[str, str] = {
    "RECEIVE": "Nhập kho",
    "TON_DAU": "Tồn đầu khi mở cơ sở",
    "CHUYEN_RA_QUAY": "Chuyển ra quầy",
    "TRA_VE_KHO": "Trả về kho",
    "HOAN_TAC_CHUYEN": "Hoàn tác chuyển kho",
    "CHUYEN_RA": "Chuyển kho (ra)",
    "CHUYEN_VAO": "Chuyển kho (vào)",
    "DISPENSE": "Giao cho khách",
    "GAN_LO": "Gán lô, trừ kho",
    "DISPENSE_REVERSAL": "Hoàn tác giao thuốc",
    "RETURN_RECEIVED": "Khách trả",
    "NHAP_LAI_BAN": "Nhập lại bán được",
    "DISCARD": "Huỷ",
    "HOAN_TAC_HUY": "Hoàn tác huỷ",
    "KIEM_KE_LECH": "Kiểm kê lệch",
    "HOAN_TAC_KIEM_KE": "Hoàn tác kiểm kê",
    "ADJUST": "Điều chỉnh",
}
HANH_DONG_LA = "Thay đổi kho khác"

_NOI = {"KHO": "Kho", "QUAY": "Quầy"}
_NHA_CC, _KHACH, _CHO_KIEM, _DA_HUY = "Nhà cung cấp", "Khách", "Chờ kiểm", "Đã huỷ"
#: Từ đâu → đến đâu theo mã; None = nơi của dòng (Kho / Quầy).
_TU_DEN: dict[str, tuple[str | None, str | None]] = {
    "RECEIVE": (_NHA_CC, None),
    "TON_DAU": ("Cơ sở khác", None),
    "CHUYEN_RA_QUAY": ("Kho", "Quầy"),
    "TRA_VE_KHO": ("Quầy", "Kho"),
    "DISPENSE": (None, _KHACH),
    "GAN_LO": (None, _KHACH),
    "DISPENSE_REVERSAL": (_KHACH, None),
    "RETURN_RECEIVED": (_KHACH, _CHO_KIEM),
    "NHAP_LAI_BAN": (_CHO_KIEM, None),
    "DISCARD": (None, _DA_HUY),
    "HOAN_TAC_HUY": (_DA_HUY, None),
}
_LOAI_KIEM = {"DAU": "đầu ca", "CUOI": "cuối ca", "DOT_XUAT": "đột xuất"}
_CA = {"SANG": "sáng", "CHIEU": "chiều", "TOI": "tối"}
#: Dấu `scripts/nhan-ban-co-so.py` ghi vào `reason` khi chép lô sang cơ sở mới.
_DAU_NHAN_BAN = "nhan-ban-co-so"
_MA_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
)
#: Cả câu chỉ là một mã máy (`nhap-tu-script`, `seed_demo`): không phải lời người ghi.
_MA_MAY = re.compile(r"[a-z0-9]+(?:[-_:.][a-z0-9]+)+")


# ── Hàm thuần ────────────────────────────────────────────────────────────


def nhan_hanh_dong(ma: Any) -> str:
    return HANH_DONG.get(str(ma), HANH_DONG_LA)


def tu_den(
    ma: str, noi: str | None, *, huong: str | None = None, ref_type: str | None = None
) -> tuple[str, str | None]:
    """Từ đâu → đến đâu. Việc tại chỗ (kiểm kê, điều chỉnh, mã lạ) chỉ có nơi."""
    o = _NOI.get(noi or "", noi or "—")
    if ma == "HOAN_TAC_CHUYEN":
        return ("Kho", "Quầy") if huong == "KHO_QUAY" else ("Quầy", "Kho")
    if ma == "DISCARD" and ref_type == "drug_return":
        return _CHO_KIEM, _DA_HUY
    if ma not in _TU_DEN:
        return o, None
    tu, den = _TU_DEN[ma]
    return tu or o, den or o


def ly_do_de_doc(v: Any) -> str | None:
    """Lý do để hiện ra màn: lời người ghi giữ nguyên, mã máy bỏ đi."""
    chu = " ".join(_MA_UUID.sub(" ", str(v or "")).split())
    if not chu or chu.startswith(_DAU_NHAN_BAN) or _MA_MAY.fullmatch(chu):
        return None
    return chu


def _uuid(v: Any) -> str | None:
    try:
        return str(UUID(str(v)))
    except ValueError:
        return None


def _chu_loc(v: Any) -> str | None:
    """Ô lọc văn bản: rỗng = không lọc; rác khớp 0 dòng, không ném."""
    chu = str(v or "").strip()[:100]
    return chu or None


def _so_trang(v: Any) -> int:
    try:
        return max(1, min(int(str(v)), 1_000_000))
    except ValueError:
        return 1


def khoang_loc(tu: Any, den: Any) -> tuple[date | None, date | None]:
    """Hai ô ngày người dùng gửi. Rác / rỗng → bỏ đầu ấy (xem mọi thời gian);
    đảo ngược thì đổi chỗ. Không bao giờ ném."""
    a, b = doc_ngay_xem(tu), doc_ngay_xem(den)
    if a and b and a > b:
        a, b = b, a
    return a, b


def gop_theo_don_vi(
    lo: list[dict[str, Any]], cho_gan_lo: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Tổng mỗi đơn vị từ các dòng lô + phần đã giao chờ gán lô (chưa có lô)."""
    tong: dict[str, dict[str, Any]] = {}

    def hang(don_vi: Any) -> dict[str, Any]:
        ten = str(don_vi or "").strip()
        return tong.setdefault(
            ten.lower(),
            {
                "don_vi": ten or None,
                "o_kho": Decimal(0),
                "o_quay": Decimal(0),
                "cho_gan_lo": Decimal(0),
                "cho_kiem": Decimal(0),
                "da_huy": Decimal(0),
            },
        )

    for d in lo:
        h = hang(d["don_vi"])
        for cot in ("o_kho", "o_quay", "cho_kiem", "da_huy"):
            h[cot] += Decimal(str(d[cot]))
    for d in cho_gan_lo:
        hang(d["don_vi"])["cho_gan_lo"] += Decimal(str(d["so_luong"]))
    ra = []
    for h in tong.values():
        ton = h["o_kho"] + h["o_quay"]
        ra.append({**h, "tong": ton, "tren_ke": ton - h["cho_gan_lo"]})
    return sorted(ra, key=lambda x: str(x["don_vi"] or ""))


def _ma_phieu(r: asyncpg.Record) -> str | None:
    if r["ma_phieu"]:
        return str(r["ma_phieu"])
    if r["kiem_ngay"] is None:
        return None
    ca = "" if r["kiem_loai"] == "DOT_XUAT" else f" {_CA.get(r['kiem_ca'], '')}"
    return (
        f"Kiểm {_LOAI_KIEM.get(r['kiem_loai'], '')}{ca} "
        f"{r['kiem_ngay'].strftime('%d/%m/%Y')}"
    )


def _ly_do(r: asyncpg.Record) -> str | None:
    """Dòng GAN_LO: giờ thuốc rời quầy nằm ở sổ chờ gán lô, sổ kho chỉ biết giờ gán."""
    if r["giao_luc"] is not None:
        luc: datetime = r["giao_luc"].astimezone(CLINIC_TZ)
        ai = f" bởi {r['nguoi_giao']}" if r["nguoi_giao"] else ""
        return f"Giao khách lúc {luc.strftime('%H:%M %d/%m/%Y')}{ai}"
    chu = ly_do_de_doc(r["ly_do"])
    if r["hoan_bang"]:
        hoan = f"Đã hoàn tác bằng phiếu {r['hoan_bang']}"
        return f"{chu} · {hoan}" if chu else hoan
    return chu


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    ma = str(r["ma"])
    tu, den = tu_den(ma, r["noi"], huong=r["huong"], ref_type=r["ref_type"])
    la_chuyen = r["noi_den"] is not None
    khach = r["khach"]
    if khach is None and _KHACH in (tu, den):
        khach = "Không rõ khách"  # đơn gốc hoặc hồ sơ không còn; dòng vẫn phải hiện
    return {
        "id": r["id"],
        "luc": r["luc"],
        "ma": ma,
        "hanh_dong": nhan_hanh_dong(ma),
        "tu": tu,
        "den": den,
        "noi": r["noi"],
        "noi_den": r["noi_den"],
        "so_lo": r["so_lo"],
        "han_dung": r["han_dung"],
        # Chuyển kho là một việc: số lượng không mang dấu, tồn có đủ hai nơi.
        "so_luong": abs(r["so_luong"]) if la_chuyen else r["so_luong"],
        "don_vi": r["don_vi"],
        "ton_truoc": r["ton_truoc"],
        "ton_sau": r["ton_sau"],
        "la_chuyen": la_chuyen,
        "ton_den_truoc": r["ton_den_truoc"],
        "ton_den_sau": r["ton_den_sau"],
        "nguoi_lam": r["nguoi_lam"],
        "khach": khach,
        "ma_bn": r["ma_bn"],
        "visit_id": str(r["visit_id"]) if r["visit_id"] else None,
        "ma_phieu": _ma_phieu(r),
        "ly_do": _ly_do(r),
        "chua_tru_kho": r["chua_tru_kho"],
    }


# ── SQL ──────────────────────────────────────────────────────────────────

# $1 phòng khám · $2 cơ sở · $3 thuốc. `so` tính tồn trên MỌI dòng của lô trước khi
# lọc, nên lọc ngày / loại không làm sai số. Không có N+1: lô → sổ đi theo chỉ mục
# (drug_batch_id, performed_at); tên người, khách chỉ nối cho đúng trang đang xem.
_SU_KIEN = """
WITH hang AS (
    SELECT b.id, b.batch_code, b.expiry_date, b.unit, b.noi_chua, b.quantity_on_hand
      FROM public.drug_batch b
     WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
       AND b.drug_catalog_id = $3::uuid
), so AS (
    SELECT t.id, t.performed_at, t.txn_type, t.quantity, t.reason, t.ref_type,
           t.ref_id, t.performed_by_staff_id, h.batch_code, h.expiry_date, h.unit,
           h.noi_chua,
           h.quantity_on_hand - coalesce(sum(t.quantity) OVER (
               PARTITION BY t.drug_batch_id
               ORDER BY t.performed_at DESC, t.id DESC
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ), 0) AS ton_sau
      FROM public.inventory_txn t
      JOIN hang h ON h.id = t.drug_batch_id
     WHERE t.clinic_id = $1::uuid
       AND t.txn_type NOT IN ('SALE', 'SALE_REVERSAL')
), su_kien AS (
    SELECT so.id::text AS id, so.performed_at AS luc,
           CASE
               WHEN pk.loai = 'CHUYEN' AND pk.hoan_tac_cua IS NOT NULL
                   THEN 'HOAN_TAC_CHUYEN'
               WHEN pk.loai = 'CHUYEN' AND pk.huong = 'KHO_QUAY' THEN 'CHUYEN_RA_QUAY'
               WHEN pk.loai = 'CHUYEN' AND pk.huong = 'QUAY_KHO' THEN 'TRA_VE_KHO'
               WHEN pk.loai = 'KIEM' OR so.ref_type = 'kiem_ke_ca' THEN 'KIEM_KE_LECH'
               WHEN so.ref_type = 'kiem_ke_ca_hoan' THEN 'HOAN_TAC_KIEM_KE'
               WHEN so.ref_type = 'discard_undo' THEN 'HOAN_TAC_HUY'
               WHEN gan.id IS NOT NULL THEN 'GAN_LO'
               WHEN so.txn_type = 'RECEIVE'
                    AND so.reason LIKE 'nhan-ban-co-so%' THEN 'TON_DAU'
               ELSE so.txn_type
           END AS ma,
           so.noi_chua AS noi, vao.noi_chua AS noi_den, so.ref_type, pk.huong,
           so.batch_code AS so_lo, so.expiry_date AS han_dung,
           so.quantity AS so_luong, so.unit AS don_vi,
           so.ton_sau - so.quantity AS ton_truoc, so.ton_sau,
           vao.ton_sau - vao.quantity AS ton_den_truoc, vao.ton_sau AS ton_den_sau,
           so.performed_by_staff_id AS nguoi_id, so.reason AS ly_do,
           pk.ma_phieu, hoan.ma_phieu AS hoan_bang,
           kc.ngay AS kiem_ngay, kc.ca AS kiem_ca, kc.loai AS kiem_loai,
           rx.visit_id, rx.clinic_patient_id, gan.giao_luc, gan.giao_boi,
           false AS chua_tru_kho
      FROM so
      LEFT JOIN public.phieu_kho pk
        ON so.ref_type = 'phieu_kho' AND pk.id = so.ref_id
       AND pk.clinic_id = $1::uuid
      LEFT JOIN public.kiem_ke_ca kc
        ON so.ref_type IN ('kiem_ke_ca', 'kiem_ke_ca_hoan') AND kc.id = so.ref_id
       AND kc.clinic_id = $1::uuid
      LEFT JOIN public.drug_return tra
        ON so.ref_type = 'drug_return' AND tra.id = so.ref_id
       AND tra.clinic_id = $1::uuid
      /* rx:gom-ca-lich-su: sổ kho trỏ dòng đơn đã giao; dòng đó bị đính chính sau
         này thì lần xuất, lần trả vẫn là sự thật. */
      LEFT JOIN public.prescription rx
        ON rx.id = CASE WHEN so.ref_type = 'prescription' THEN so.ref_id
                        ELSE tra.prescription_id END
       AND rx.clinic_id = $1::uuid
      LEFT JOIN public.thuoc_giao_chua_gan_lo gan
        ON gan.inventory_txn_id = so.id AND gan.clinic_id = $1::uuid
      LEFT JOIN public.phieu_kho hoan ON hoan.hoan_tac_cua = pk.id
      -- Gộp chuyển kho: dòng trừ ở nơi đi mang theo dòng cộng ở nơi đến.
      LEFT JOIN public.phieu_kho_dong pd
        ON pd.inventory_txn_nguon_id = so.id AND pd.clinic_id = $1::uuid
      LEFT JOIN so vao ON vao.id = pd.inventory_txn_id
     WHERE NOT (so.txn_type = 'CHUYEN_VAO' AND EXISTS (
               SELECT 1 FROM public.phieu_kho_dong dd
                WHERE dd.inventory_txn_id = so.id AND dd.clinic_id = $1::uuid))
    UNION ALL
    -- Nhập lại bán được: quyết định không đổi tồn nên không có dòng sổ.
    SELECT 'tra-' || r.id::text, coalesce(r.disposition_at, r.returned_at),
           'NHAP_LAI_BAN', h.noi_chua, NULL, 'drug_return', NULL,
           h.batch_code, h.expiry_date, r.returned_qty, h.unit, NULL, NULL, NULL, NULL,
           r.disposition_by, r.disposition_reason, NULL, NULL, NULL, NULL, NULL,
           rx.visit_id, rx.clinic_patient_id, NULL, NULL, false
      FROM public.drug_return r
      JOIN hang h ON h.id = r.drug_batch_id
      JOIN public.prescription rx
        ON rx.id = r.prescription_id AND rx.clinic_id = r.clinic_id
     WHERE r.clinic_id = $1::uuid AND r.disposition = 'BAN_LAI'
    UNION ALL
    -- Đã giao mà chưa gán lô: thuốc đã rời quầy, sổ kho chưa có gì. Gán xong thì
    -- dòng này nhường chỗ cho dòng sổ GAN_LO (giờ giao ghi trong lý do của dòng ấy).
    SELECT 'gan-' || g.id::text, g.giao_luc, 'DISPENSE', 'QUAY', NULL, 'prescription',
           NULL, NULL, NULL, -g.so_luong,
           coalesce(nullif(btrim(p.unit), ''),
                    (SELECT c.don_vi_ban FROM public.drug_catalog c
                      WHERE c.id = g.drug_catalog_id)),
           NULL, NULL, NULL, NULL, g.giao_boi, 'Chưa trừ kho, chờ gán lô',
           NULL, NULL, NULL, NULL, NULL, p.visit_id, p.clinic_patient_id,
           NULL, NULL, true
      FROM public.thuoc_giao_chua_gan_lo g
      JOIN public.prescription p
        ON p.id = g.prescription_id AND p.clinic_id = g.clinic_id
     WHERE g.clinic_id = $1::uuid AND g.drug_catalog_id = $3::uuid
       AND g.drug_batch_id IS NULL
       AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id), $2::uuid) = $2::uuid
)
"""

# $4 từ ngày · $5 đến ngày · $6 mã hành động · $7 nơi · $8 số lô · $9 người.
# So ngày ở SQL, không đổi sang mốc giờ ở Python: ngày cực đại cộng 1 sẽ tràn.
_KHOP = """
    ($4::date IS NULL
     OR (sk.luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= $4::date)
    AND ($5::date IS NULL
         OR (sk.luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date <= $5::date)
    AND ($6::text IS NULL OR sk.ma = $6::text)
    AND ($7::text IS NULL OR sk.noi = $7::text OR sk.noi_den = $7::text)
    AND ($8::text IS NULL OR sk.so_lo = $8::text)
    AND ($9::text IS NULL OR sk.nguoi_id::text = $9::text)
"""

_TRANG = (
    _SU_KIEN
    + """
SELECT sk.*, s.full_name AS nguoi_lam, gs.full_name AS nguoi_giao,
       pt.full_name AS khach, pt.patient_code AS ma_bn
  FROM (SELECT * FROM su_kien sk WHERE """
    + _KHOP
    + """
         ORDER BY sk.luc DESC, sk.id DESC LIMIT $10 OFFSET $11) sk
  LEFT JOIN public.staff s ON s.id = sk.nguoi_id
  LEFT JOIN public.staff gs ON gs.id = sk.giao_boi
  LEFT JOIN public.visit v ON v.visit_id = sk.visit_id
  LEFT JOIN public.patient pt
    ON pt.clinic_patient_id = coalesce(sk.clinic_patient_id, v.clinic_patient_id)
   AND pt.clinic_id = $1::uuid
 ORDER BY sk.luc DESC, sk.id DESC
"""
)

# Một câu ra cả danh sách chọn ở bộ lọc (chỉ thứ thuốc này có) lẫn tổng số dòng khớp.
_BO_LOC = (
    _SU_KIEN
    + """
SELECT sk.ma, sk.nguoi_id::text AS nguoi_id, max(s.full_name) AS nguoi_lam,
       count(*) FILTER (WHERE """
    + _KHOP
    + """) AS khop
  FROM su_kien sk
  LEFT JOIN public.staff s ON s.id = sk.nguoi_id
 GROUP BY sk.ma, sk.nguoi_id
"""
)


async def _dang_o_dau(
    conn: asyncpg.Connection, clinic_id: str, location_id: str | None, thuoc_id: str
) -> dict[str, Any]:
    lo = await conn.fetch(
        """
        WITH hang AS (
            SELECT b.id, b.batch_code, b.expiry_date, b.unit, b.noi_chua,
                   b.quantity_on_hand
              FROM public.drug_batch b
             WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
               AND b.drug_catalog_id = $3::uuid
        ), huy AS (
            -- Hoàn tác huỷ lô hết hạn ghi ADJUST dương, trừ đi cho đúng số còn huỷ.
            SELECT t.drug_batch_id, -sum(t.quantity) AS da_huy
              FROM public.inventory_txn t
              JOIN hang h ON h.id = t.drug_batch_id
             WHERE t.clinic_id = $1::uuid
               AND (t.txn_type = 'DISCARD' OR t.ref_type = 'discard_undo')
             GROUP BY t.drug_batch_id
        ), cho AS (
            SELECT r.drug_batch_id, sum(r.returned_qty) AS cho_kiem
              FROM public.drug_return r
              JOIN hang h ON h.id = r.drug_batch_id
             WHERE r.clinic_id = $1::uuid AND r.disposition IS NULL
             GROUP BY r.drug_batch_id
        )
        SELECT h.batch_code AS so_lo, h.expiry_date AS han_dung,
               min(h.unit) AS don_vi,
               coalesce(sum(h.quantity_on_hand) FILTER (WHERE h.noi_chua = 'KHO'), 0)
                   AS o_kho,
               coalesce(sum(h.quantity_on_hand) FILTER (WHERE h.noi_chua = 'QUAY'), 0)
                   AS o_quay,
               coalesce(sum(cho.cho_kiem), 0) AS cho_kiem,
               coalesce(sum(huy.da_huy), 0) AS da_huy,
               coalesce(h.expiry_date
                        < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date, false)
                   AS het_han
          FROM hang h
          LEFT JOIN huy ON huy.drug_batch_id = h.id
          LEFT JOIN cho ON cho.drug_batch_id = h.id
         GROUP BY h.batch_code, h.expiry_date, lower(btrim(h.unit))
         ORDER BY sum(h.quantity_on_hand) = 0, h.expiry_date NULLS LAST, h.batch_code
         LIMIT 300
        """,
        clinic_id,
        location_id,
        thuoc_id,
    )
    cho_gan = await conn.fetch(
        """
        SELECT coalesce(nullif(btrim(p.unit), ''), c.don_vi_ban) AS don_vi,
               sum(g.so_luong) AS so_luong
          FROM public.thuoc_giao_chua_gan_lo g
          /* rx:gom-ca-lich-su: thuốc ĐÃ giao vẫn phải tính dù dòng đơn sau đó bị
             bác sĩ đính chính — kệ đã thiếu thuốc ấy */
          JOIN public.prescription p
            ON p.id = g.prescription_id AND p.clinic_id = g.clinic_id
          JOIN public.drug_catalog c ON c.id = g.drug_catalog_id
         WHERE g.clinic_id = $1::uuid AND g.drug_catalog_id = $3::uuid
           AND g.drug_batch_id IS NULL
           AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id), $2::uuid)
               = $2::uuid
         GROUP BY 1
        """,
        clinic_id,
        location_id,
        thuoc_id,
    )
    canh_bao_neu_day("kho.theo_doi.lo", len(lo), LO_TOI_DA, clinic_id=clinic_id)
    ds_lo = [dict(r) for r in lo]
    return {
        "tong": gop_theo_don_vi(ds_lo, [dict(r) for r in cho_gan]),
        "lo": ds_lo,
    }


# ── Đọc ──────────────────────────────────────────────────────────────────


def _rong(trang: int) -> dict[str, Any]:
    return {
        "thuoc": None,
        "dang_o_dau": {"tong": [], "lo": []},
        "dong": [],
        "tong": 0,
        "trang": trang,
        "so_dong_mot_trang": SO_DONG_MOT_TRANG,
        "xuat_toi_da": XUAT_TOI_DA,
        "loc": {"hanh_dong": [], "nguoi": []},
    }


async def theo_doi_thuoc(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    thuoc: Any,
    tu: Any = None,
    den: Any = None,
    hanh_dong: Any = None,
    noi: Any = None,
    lo: Any = None,
    nguoi: Any = None,
    trang: Any = 1,
    so_dong: int = SO_DONG_MOT_TRANG,
) -> dict[str, Any]:
    """Một thuốc ở cơ sở đang làm: đang ở đâu + một trang dòng thời gian, mới nhất
    trước. Mã thuốc rác / không có trong phòng khám → kết quả rỗng, không ném."""
    so_trang = _so_trang(trang)
    thuoc_id = _uuid(thuoc)
    if thuoc_id is None:
        return _rong(so_trang)
    a, b = khoang_loc(tu, den)
    loc = (a, b, _chu_loc(hanh_dong), _chu_loc(noi), _chu_loc(lo), _chu_loc(nguoi))
    khoa = (identity.clinic_id, identity.location_id, thuoc_id)
    async with pool.acquire() as conn:
        tt = await conn.fetchrow(
            "SELECT c.id::text, c.name_raw AS ten, c.ma_hang, c.don_vi_ban,"
            " c.is_active AS dang_dung"
            " FROM public.drug_catalog c WHERE c.clinic_id = $1::uuid"
            " AND c.id = $2::uuid",
            identity.clinic_id,
            thuoc_id,
        )
        if tt is None:
            return _rong(so_trang)
        dang_o_dau = await _dang_o_dau(conn, *khoa)
        nhom = await conn.fetch(_BO_LOC, *khoa, *loc)
        rows = await conn.fetch(_TRANG, *khoa, *loc, so_dong, (so_trang - 1) * so_dong)
    ten_nguoi = {
        str(r["nguoi_id"]): r["nguoi_lam"]
        for r in nhom
        if r["nguoi_id"] and r["nguoi_lam"]
    }
    return {
        "thuoc": dict(tt),
        "dang_o_dau": dang_o_dau,
        "dong": [_dong(r) for r in rows],
        "tong": sum(int(r["khop"]) for r in nhom),
        "trang": so_trang,
        "so_dong_mot_trang": so_dong,
        "xuat_toi_da": XUAT_TOI_DA,
        "loc": {
            "hanh_dong": sorted(
                (
                    {"ma": ma, "nhan": nhan_hanh_dong(ma)}
                    for ma in {str(r["ma"]) for r in nhom}
                ),
                key=lambda x: x["nhan"],
            ),
            "nguoi": sorted(
                ({"id": k, "ten": v} for k, v in ten_nguoi.items()),
                key=lambda x: x["ten"],
            ),
        },
    }


async def xuat_theo_doi(
    pool: asyncpg.Pool, *, identity: StaffIdentity, thuoc: Any, **loc: Any
) -> dict[str, Any]:
    """Toàn bộ dòng khớp bộ lọc cho Excel, tối đa `XUAT_TOI_DA` dòng mới nhất."""
    kq = await theo_doi_thuoc(
        pool, identity=identity, thuoc=thuoc, trang=1, so_dong=XUAT_TOI_DA, **loc
    )
    canh_bao_neu_day(
        "kho.theo_doi.xuat", len(kq["dong"]), XUAT_TOI_DA, clinic_id=identity.clinic_id
    )
    return kq


async def tim_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, q: Any
) -> list[dict[str, Any]]:
    """Gợi ý theo tên thuốc (không dấu), mã hàng, số lô hoặc mã tem. Lô chỉ ở kho
    cơ sở đang làm, kể cả lô hết tồn; thuốc đã tắt vẫn ra (xếp sau).

    Dòng khớp lô có `so_lo` — chọn nó thì màn mở sẵn lọc lô ấy. Rỗng → rỗng.
    """
    chu = _chu_loc(q)
    if chu is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH mau AS (
                SELECT lower(replace(replace(public.f_unaccent($3), 'đ', 'd'),
                                     'Đ', 'D')) AS chu
            )
            SELECT id, ten, ma_hang, so_lo, dang_dung FROM (
                SELECT c.id::text AS id, c.name_raw AS ten, c.ma_hang,
                       NULL::text AS so_lo, c.is_active AS dang_dung
                  FROM public.drug_catalog c, mau
                 WHERE c.clinic_id = $1::uuid
                   AND (position(mau.chu IN lower(replace(replace(public.f_unaccent(
                            concat_ws(' ', c.name_raw, c.name_base)), 'đ', 'd'),
                            'Đ', 'D'))) > 0
                        OR position(lower($3) IN lower(coalesce(c.ma_hang, ''))) > 0)
                UNION
                SELECT c.id::text, c.name_raw, c.ma_hang, b.batch_code, c.is_active
                  FROM public.drug_batch b
                  JOIN public.drug_catalog c
                    ON c.id = b.drug_catalog_id AND c.clinic_id = b.clinic_id
                 WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
                   AND (position(lower($3) IN lower(b.batch_code)) > 0
                        OR position(lower($3) IN lower(b.ma_tem)) > 0)
            ) ket
             ORDER BY dang_dung DESC, so_lo NULLS FIRST, lower(ten)
             LIMIT 20
            """,
            identity.clinic_id,
            identity.location_id,
            chu,
        )
    canh_bao_neu_day("kho.theo_doi.tim", len(rows), TIM_TOI_DA)
    return [dict(r) for r in rows]
