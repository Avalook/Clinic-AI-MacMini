"""SỔ NỢ HAI CHIỀU theo lượt (Tuyền chốt 14/10/2026 — kế hoạch G4b).

Kế toán giữ hai sổ cho mỗi lượt ĐÃ VỀ:

  * PHAI_THU — khách nợ phòng khám: đúng luật chặn check-out ``no_khi_ve``
    (dịch vụ đã/đang làm, vật tư đã thêm, thuốc đã lấy mà chưa có lần thu nào
    phủ) + chuyển khoản CHỜ xác minh (tiền chưa về thì vẫn là nợ — một khoản,
    ghi chú "chờ xác minh"; xác minh xong mới là "nợ thu được", đúng ngày).
  * PHAI_TRA — phòng khám nợ khách: tiền thừa (chỉ định đã bỏ / không làm, dịch
    vụ khám đã bỏ tick — ``dong_tien_thua``) + đã thu mà chưa làm khi khách đã
    về. "Giữ lại tiền thừa" vẫn là nợ khách. Không có hạn 90 ngày.

"Đã về" = lượt đã check-out, hoặc lượt của ngày trước (giờ VN) chưa đóng — cùng
điều kiện mục "Đã thu – khách về chưa làm". Lượt đang ở phòng khám hôm nay thì
số dư = 0: tiền còn đang xử lý ở quầy, chưa thành nợ.

Một chỗ ghi duy nhất (``ghi_chenh_lech``): đọc số dư HIỆN TẠI bằng chính các
hàm trên, so với số dư cuối trong sổ, khác thì thêm một dòng chênh lệch. Không
sửa dòng cũ — số của ngày đã qua không bao giờ đổi. Vì đọc trạng thái hiện tại
nên sự kiện tới trễ / tới hai lần vẫn ra một kết quả; sự kiện đã ghi thì im
(chỉ mục duy nhất theo sự kiện). Postgres ép số dư sau = trước + chênh.

Đang làm dở lúc khách về (``in_progress``) = khách ĐÃ NHẬN dịch vụ ở cả hai
chiều (14/10/2026): chưa thu thì là nợ, đã thu thì không phải nợ khách.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg
import structlog

from clinicai.services.co_so_bao_cao import sql_cua_co_so_ngung
from clinicai.services.cong_no_service import no_khi_ve
from clinicai.services.hoan_tac_service import tien_da_thu_cua_chi_dinh
from clinicai.services.tien_thua_service import dong_tien_thua

logger = structlog.get_logger(__name__)

PHAI_THU = "PHAI_THU"
#: Loại khoản "phòng khám nợ khách" từ thuốc (G4d · R3/T2).
THUOC = "THUOC"
PHAI_TRA = "PHAI_TRA"
CHIEU = (PHAI_THU, PHAI_TRA)

#: Sự kiện → vì sao số dư đổi (cột ``loai``). Sự kiện lạ = ĐỐI CHIẾU.
LOAI_THEO_SU_KIEN: dict[str, str] = {
    "visit.checked_out": "KHI_VE",
    "visit.left_early": "KHI_VE",
    "visit.reopened": "MO_LAI_LUOT",
    "cong_no.ghi": "GHI_NO",
    "cong_no.huy": "GHI_NO",
    "payment.service_collected": "THU",
    "payment.medicine_collected": "THU",
    "payment.collection_undone": "HUY_PHIEU",
    "payment.refunded": "HOAN_TIEN",
    "service_order.cancelled": "DOI_CHI_DINH",
    "service_order.restored": "DOI_CHI_DINH",
    "service_order.carried_over": "DOI_CHI_DINH",
    "service.started": "DOI_CHI_DINH",
    "service.completed": "DOI_CHI_DINH",
    "service.not_performed": "DOI_CHI_DINH",
    "service.start_cancelled": "DOI_CHI_DINH",
    "service.completion_undone": "DOI_CHI_DINH",
    "visit.supply_changed": "DOI_CHI_DINH",
    "visit.exam_service_changed": "DOI_CHI_DINH",
    "medicine.dispensed": "DOI_CHI_DINH",
    "medicine.returned": "TRA_THUOC",
    "prescription.saved": "DOI_CHI_DINH",
}

#: Lượt đối chiếu định kỳ (worker su-kien): mỗi bao lâu một vòng.
NHIP_GIAY = 600
#: Ghi số dư đầu kỳ: mỗi bao lâu một lô, tới khi hết lượt cũ.
NHIP_DAU_KY_GIAY = 60
#: Số lượt tối đa một vòng đối chiếu xét lại (số dư ≠ 0 + lượt mới về).
DOI_CHIEU_MOI_VONG = 300
#: Số lượt CŨ (trước mốc bật sổ) một lô ghi số dư đầu kỳ. ~14k lượt ≈ 47 lô.
#: Lượt cũ bị đụng tới (thu nợ…) TRƯỚC khi tới lô của nó thì phần đổi ấy không
#: vào sổ (không biết số dư cũ) — chạy nhanh, lượt gần đây đi trước để thu hẹp.
DAU_KY_MOI_VONG = 300
#: Lượt đã về trong khoảng này được đối chiếu lại (bắt hoàn xong / thất bại…).
DOI_CHIEU_SO_GIO = 48

#: "Đã về" xét TẠI GIỜ `$3` (giờ sự kiện): sự kiện xảy ra trước lúc khách về
#: không sinh nợ — kể cả khi bên nhận chạy trễ, lúc lượt đã đóng (chênh lệch ấy
#: thuộc về sự kiện check-out, đúng "vì sao").
_LUOT_SQL = """
SELECT v.clinic_patient_id::text AS clinic_patient_id,
       ((v.closed_at IS NOT NULL AND v.closed_at <= $3)
        OR (v.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           < ($3 AT TIME ZONE 'Asia/Ho_Chi_Minh')::date) AS da_ve
  FROM public.visit v
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""

#: Chỉ định đã thu mà CHƯA làm (chưa bắt đầu) — khách về là phòng khám nợ khách.
_CHUA_LAM_SQL = """
SELECT o.id::text AS id, o.service_name AS ten
  FROM public.service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND o.exec_status IN ('authorized', 'assigned')
   AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
"""

#: Lần thu CHỜ xác minh của lượt — số GỐC (trước giảm) mà lần chờ đang phủ.
_CK_CHO_SQL = """
SELECT coalesce(c.original_amount, c.amount) AS goc
  FROM public.payment_cycle c
 WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
   AND c.status = 'PENDING_VERIFICATION'
"""

#: THUỐC phòng khám nợ khách (G4d · R3 + T2, Tuyền chốt E/T2 14/10) — theo DÒNG
#: ĐƠN (kể cả dòng đã gỡ vì đính chính — tiền vẫn nằm ở dòng cũ):
#:   đã thu (lần thu PAID) − đã hoàn (đang chờ / xong) − đã giao + khách trả lại.
#: > 0 = thu rồi chưa giao mà khách về, khách trả thuốc chọn "Giữ lại", hoặc dòng
#: đã thu bị đính chính chưa giao. Lượt BÁN LẺ tự đóng lúc thu → chỉ tính từ hôm
#: sau (cùng ngày khách còn đứng ở quầy chờ giao). Cùng luật cho lần thu thuốc
#: xảy ra SAU khi lượt đã đóng và CÙNG ngày với `$3` (check-out trước, quay lại
#: quầy mua thuốc sau — Tuyền 14/10: không báo động giả); qua ngày vẫn là nợ thật.
_THUOC_PHAI_TRA_SQL = """
WITH dong AS (
    SELECT bl.source_id AS rx_id, max(bl.name_snapshot) AS ten,
           sum(bl.quantity) AS da_thu, max(bl.unit_price) AS don_gia,
           coalesce(sum(h.sl), 0) AS da_hoan
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
      LEFT JOIN LATERAL (
           SELECT sum(l.quantity) AS sl
             FROM public.payment_refund_line l
             JOIN public.payment_refund r
               ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
            WHERE l.clinic_id = bl.clinic_id AND l.payment_bill_line_id = bl.id
              AND r.status IN ('PENDING', 'COMPLETED')) h ON true
      JOIN public.visit vt
        ON vt.clinic_id = c.clinic_id AND vt.visit_id = c.visit_id
     WHERE bl.clinic_id = $1::uuid AND c.visit_id = $2::uuid AND c.status = 'PAID'
       AND bl.source_type = 'prescription' AND bl.billing_owner = 'CLINIC'
       AND NOT (vt.closed_at IS NOT NULL
                AND coalesce(c.paid_at, c.created_at) > vt.closed_at
                AND (coalesce(c.paid_at, c.created_at)
                       AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                    = ($3 AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
     GROUP BY bl.source_id
)
SELECT d.ten, d.don_gia,
       d.da_thu - d.da_hoan - p.dispensed_qty
         + coalesce((SELECT sum(t.returned_qty) FROM public.drug_return t
                      WHERE t.clinic_id = $1::uuid
                        AND t.prescription_id = p.id), 0) AS con
  FROM dong d
  JOIN public.prescription p
       /* rx:gom-ca-lich-su: tiền thu ở dòng đã đính chính vẫn là nợ khách */
    ON p.clinic_id = $1::uuid AND p.id::text = d.rx_id
  JOIN public.visit v ON v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
 WHERE NOT (coalesce(v.ban_le, false)
            AND (v.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                = ($3 AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
"""

_CUOI_SQL = """
SELECT so_du FROM public.so_no
 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND chieu = $3
 ORDER BY seq DESC LIMIT 1
"""

_GHI_SQL = """
INSERT INTO public.so_no
    (clinic_id, visit_id, clinic_patient_id, chieu, so_tien, so_du, loai,
     su_kien_id, su_kien_ten, boi, luc, chi_tiet)
VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::uuid, $9, $10::uuid,
        $11, $12::jsonb)
ON CONFLICT (clinic_id, su_kien_id, chieu) WHERE su_kien_id IS NOT NULL
DO NOTHING
RETURNING id::text
"""


@dataclass
class SoDu:
    """Số dư HIỆN TẠI của một lượt ở hai chiều, kèm các khoản tạo nên nó."""

    phai_thu: int = 0
    phai_tra: int = 0
    chi_tiet: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {PHAI_THU: [], PHAI_TRA: []}
    )

    def cua(self, chieu: str) -> int:
        return self.phai_thu if chieu == PHAI_THU else self.phai_tra


def chenh_lech(truoc: int, sau: int) -> int:
    """Phần phải ghi vào sổ (có dấu). Thuần."""
    return int(sau) - int(truoc)


async def _khoa(conn: asyncpg.Connection, clinic_id: str, visit_id: str) -> None:
    # Cùng khoá với trigger `so_no_kiem_so_du`: hai bên ghi cùng lượt xếp hàng.
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext('so_no:' || $1 || ':' || $2))",
        str(clinic_id),
        str(visit_id),
    )


async def so_du_hien_tai(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str, luc: datetime
) -> tuple[SoDu, str | None]:
    """(số dư, clinic_patient_id). Lượt chưa về TẠI ``luc`` / không có → số dư 0.

    Các khoản đọc theo trạng thái hiện tại; chỉ điều kiện "đã về" xét tại
    ``luc``."""
    luot = await conn.fetchrow(_LUOT_SQL, clinic_id, visit_id, luc)
    if luot is None:
        return SoDu(), None
    sd = SoDu()
    if not luot["da_ve"]:
        return sd, luot["clinic_patient_id"]
    no = await no_khi_ve(conn, clinic_id=clinic_id, visit_id=visit_id)
    thu = [{"ten": d.ten, "so_tien": d.so_tien, "loai": d.source_type} for d in no.dong]
    # Chuyển khoản CHỜ xác minh: tiền chưa về thì vẫn là nợ (Tuyền 14/10) —
    # `no_khi_ve` coi lần chờ là đã phủ (để check-out qua), sổ thì cộng lại
    # đúng số gốc lần chờ đang giữ. Xác minh → giảm đúng lúc tiền vào (THU);
    # huỷ lần chờ → các dòng hiện lại trong `no_khi_ve`, số dư không đổi.
    for r in await conn.fetch(_CK_CHO_SQL, clinic_id, visit_id):
        thu.append(
            {
                "ten": "Chuyển khoản chờ xác minh",
                "so_tien": int(r["goc"]),
                "loai": "CK_CHO",
            }
        )
    sd.chi_tiet[PHAI_THU] = thu
    sd.phai_thu = sum(int(d["so_tien"] or 0) for d in thu)
    thua = (await dong_tien_thua(conn, clinic_id, [visit_id])).get(visit_id, [])
    tra = [
        {"ten": d["ten"], "so_tien": int(d["so_tien"]), "loai": d["loai"]} for d in thua
    ]
    chua = await conn.fetch(_CHUA_LAM_SQL, clinic_id, visit_id)
    tien = await tien_da_thu_cua_chi_dinh(conn, clinic_id, [str(r["id"]) for r in chua])
    for r in chua:
        t = tien.get(str(r["id"]))
        con = (t["da_thu"] - t["da_hoan"]) if t else 0
        if con > 0:
            tra.append({"ten": r["ten"], "so_tien": int(con), "loai": "CHUA_LAM"})
    for r in await conn.fetch(_THUOC_PHAI_TRA_SQL, clinic_id, visit_id, luc):
        con_sl = Decimal(str(r["con"] or 0))
        if con_sl > 0 and r["don_gia"] is not None:
            tien_thuoc = int(
                (con_sl * Decimal(str(r["don_gia"]))).quantize(
                    Decimal(1), rounding=ROUND_HALF_UP
                )
            )
            if tien_thuoc > 0:
                tra.append({"ten": r["ten"], "so_tien": tien_thuoc, "loai": THUOC})
    sd.chi_tiet[PHAI_TRA] = tra
    sd.phai_tra = sum(int(d["so_tien"]) for d in tra)
    return sd, luot["clinic_patient_id"]


async def ghi_chenh_lech(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    loai: str,
    luc: datetime,
    su_kien_id: str | None = None,
    su_kien_ten: str | None = None,
    boi: str | None = None,
) -> list[dict[str, Any]]:
    """Tính lại số dư của lượt, ghi phần chênh mỗi chiều. Trả các dòng đã ghi.

    Gọi trong giao dịch của nơi gọi (bên nhận sự kiện / lượt đối chiếu).
    """
    await _khoa(conn, clinic_id, visit_id)
    sd, patient_id = await so_du_hien_tai(conn, clinic_id, visit_id, luc)
    if patient_id is None:
        return []
    out: list[dict[str, Any]] = []
    for chieu in CHIEU:
        truoc = int(await conn.fetchval(_CUOI_SQL, clinic_id, visit_id, chieu) or 0)
        sau = sd.cua(chieu)
        so = chenh_lech(truoc, sau)
        if so == 0:
            continue
        rid = await conn.fetchval(
            _GHI_SQL,
            clinic_id,
            visit_id,
            patient_id,
            chieu,
            so,
            sau,
            loai,
            su_kien_id,
            su_kien_ten,
            boi,
            luc,
            json.dumps(sd.chi_tiet[chieu], ensure_ascii=False),
        )
        if rid is not None:
            out.append({"id": rid, "chieu": chieu, "so_tien": so, "so_du": sau})
    return out


# ── đọc sổ cho báo cáo ─────────────────────────────────────────────────────

#: Dòng sổ trong kỳ; dòng THU kèm lần thu đã đóng nợ (để tách TM / CK).
_KY_SQL = """
SELECT n.chieu, n.loai, n.so_tien, c.amount AS lan_thu_tien, c.method AS lan_thu_ht,
       (SELECT coalesce(jsonb_agg(jsonb_build_object(
                   'hinh_thuc', p.hinh_thuc, 'so_tien', p.so_tien)), '[]'::jsonb)
          FROM public.payment_cycle_phan p
         WHERE p.clinic_id = c.clinic_id AND p.cycle_id = c.payment_cycle_id) AS phan
  FROM public.so_no n
  LEFT JOIN public.domain_event e
    ON n.loai = 'THU' AND e.event_id = n.su_kien_id
  LEFT JOIN public.payment_cycle c
    ON c.clinic_id = n.clinic_id AND c.payment_cycle_id = e.aggregate_id
 WHERE n.clinic_id = $1::uuid AND n.luc >= $2 AND n.luc < $3
   AND ($4::uuid IS NULL
        OR public.co_so_cua_luot(n.clinic_id, n.visit_id) = $4::uuid)
"""

#: Tổng số dư cuối của mọi lượt tính tới một mốc (đầu kỳ / cuối kỳ).
_SO_DU_TOI_SQL = """
SELECT chieu, coalesce(sum(so_du), 0)::bigint AS so_du
  FROM (SELECT DISTINCT ON (visit_id, chieu) chieu, so_du
          FROM public.so_no
         WHERE clinic_id = $1::uuid AND luc < $2
           AND ($3::uuid IS NULL
                OR public.co_so_cua_luot(clinic_id, visit_id) = $3::uuid)
         ORDER BY visit_id, chieu, seq DESC) x
 GROUP BY chieu
"""


def _so(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _phan_tien(dong: Mapping[str, Any]) -> tuple[int, int]:
    """(tiền mặt, chuyển khoản) của lần thu đã đóng nợ, tính trên phần tiền đổ
    vào nợ (không quá số nợ giảm). Phần còn lại của số nợ giảm là giảm giá."""
    giam_no = -_so(dong.get("so_tien"))
    tien = min(giam_no, _so(dong.get("lan_thu_tien")))
    if tien <= 0:
        return 0, 0
    phan = dong.get("phan") or []
    if isinstance(phan, str):
        phan = json.loads(phan)
    tm = sum(_so(p.get("so_tien")) for p in phan if p.get("hinh_thuc") == "CASH")
    ck = sum(_so(p.get("so_tien")) for p in phan if p.get("hinh_thuc") != "CASH")
    if tm + ck <= 0:
        return (tien, 0) if dong.get("lan_thu_ht") == "CASH" else (0, tien)
    tm_vao = tien * tm // (tm + ck)
    return tm_vao, tien - tm_vao


def gom_so_no_ky(dong: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Cộng các dòng sổ trong kỳ. Thuần.

    PHAI_THU: ``phat_sinh`` (tăng, trừ đầu kỳ) · ``dieu_chinh`` (giảm không phải
    do thu: bỏ chỉ định sau khi về, huỷ ghi nợ, mở lại lượt…) · ``thu`` (giảm do
    lần thu: tổng / tiền mặt / chuyển khoản / phần giảm giá). PHAI_TRA:
    ``phat_sinh`` · ``giam`` (hoàn, làm bù, điều chỉnh). ``dau_ky``: số dư ghi lúc
    bật sổ trong kỳ (chỉ để biết, không là phát sinh)."""
    out: dict[str, Any] = {
        PHAI_THU: {
            "phat_sinh": 0,
            "dieu_chinh": 0,
            "thu": {"tong": 0, "tien_mat": 0, "chuyen_khoan": 0, "giam_gia": 0},
            "dau_ky": 0,
        },
        PHAI_TRA: {"phat_sinh": 0, "giam": 0, "dau_ky": 0},
    }
    for d in dong:
        chieu = d.get("chieu")
        so = _so(d.get("so_tien"))
        if chieu not in out or so == 0:
            continue
        o = out[chieu]
        if d.get("loai") == "DAU_KY":
            o["dau_ky"] += so
        elif so > 0:
            o["phat_sinh"] += so
        elif chieu == PHAI_TRA:
            o["giam"] += -so
        elif d.get("loai") == "THU":
            tm, ck = _phan_tien(d)
            t = o["thu"]
            t["tong"] += -so
            t["tien_mat"] += tm
            t["chuyen_khoan"] += ck
            t["giam_gia"] += -so - tm - ck
        else:
            o["dieu_chinh"] += -so
    return out


async def doc_so_no_ky(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    tu_luc: datetime,
    den_luc: datetime,
    co_so: str | None = None,
) -> dict[str, Any]:
    """Sổ nợ của kỳ [tu_luc, den_luc): phát sinh / giảm theo loại + số dư đầu,
    cuối kỳ mỗi chiều. Đầu + phát sinh − giảm (+ đầu kỳ bật sổ) = cuối."""
    ky = gom_so_no_ky(
        dict(r) for r in await conn.fetch(_KY_SQL, clinic_id, tu_luc, den_luc, co_so)
    )
    for ten, moc in (("so_du_dau", tu_luc), ("so_du_cuoi", den_luc)):
        so_du = {
            r["chieu"]: int(r["so_du"])
            for r in await conn.fetch(_SO_DU_TOI_SQL, clinic_id, moc, co_so)
        }
        for chieu in CHIEU:
            ky[chieu][ten] = so_du.get(chieu, 0)
    return ky


#: Vì sao lượt đang có số dư — khi lễ tân không ghi nợ (không có lý do người gõ).
NHAN_LOAI: dict[str, str] = {
    "DAU_KY": "Nợ từ trước khi bật sổ",
    "KHI_VE": "Khách về khi còn khoản này",
    "MO_LAI_LUOT": "Mở lại lượt",
    "GHI_NO": "Ghi nợ",
    "THU": "Thu còn thiếu",
    "HUY_PHIEU": "Huỷ phiếu sau khi khách về",
    "HOAN_TIEN": "Hoàn tiền",
    "DOI_CHI_DINH": "Dịch vụ / thuốc đổi sau khi khách về",
    "TRA_THUOC": "Khách trả thuốc",
    "DOI_CHIEU": "Máy đối chiếu phát hiện",
}

#: Số dư CUỐI còn > 0 của từng lượt ở một chiều, mới nhất trước.
_SO_DU_MO_SQL = (
    """
WITH cuoi AS (
    SELECT DISTINCT ON (n.visit_id)
           n.id, n.visit_id, n.clinic_patient_id, n.so_du, n.chi_tiet, n.loai,
           n.luc, n.boi
      FROM public.so_no n
     WHERE n.clinic_id = $1::uuid AND n.chieu = $2
     ORDER BY n.visit_id, n.seq DESC
)
SELECT c.id::text AS id, c.visit_id::text AS visit_id,
       c.clinic_patient_id::text AS patient_id, c.so_du, c.chi_tiet, c.loai,
       c.luc, p.full_name AS ten, p.patient_code AS ma_bn, s.full_name AS nguoi,
       -- NGÀY THẬT của lượt (G4a nối màn, 14/10/2026): `c.luc` là giờ DÒNG SỔ — với
       -- DAU_KY là mốc bật sổ, không phải tuổi khoản nợ ("1 giờ" gây hiểu lầm).
       v.created_at AS luot_tao_luc, v.closed_at AS luot_dong_luc,
       k.id::text AS cong_no_id, k.ly_do AS ly_do_ghi_no,
       -- Đọc HIỆN TẠI, không lấy từ chi_tiet: huỷ lần chờ không đổi số dư nên
       -- sổ không có dòng mới — chi_tiet dòng cũ vẫn ghi "chờ CK".
       (SELECT coalesce(sum(coalesce(pc.original_amount, pc.amount)), 0)
          FROM public.payment_cycle pc
         WHERE pc.clinic_id = $1::uuid AND pc.visit_id = c.visit_id
           AND pc.status = 'PENDING_VERIFICATION')::bigint AS dang_cho_ck
  FROM cuoi c
  LEFT JOIN public.visit v ON v.clinic_id = $1::uuid AND v.visit_id = c.visit_id
  LEFT JOIN public.patient p ON p.clinic_patient_id = c.clinic_patient_id
  LEFT JOIN public.staff s ON s.id = c.boi
  LEFT JOIN LATERAL (
       SELECT id, ly_do FROM public.cong_no
        WHERE clinic_id = $1::uuid AND visit_id = c.visit_id
        ORDER BY ghi_luc DESC LIMIT 1) k ON true
 WHERE c.so_du > 0
   AND ($3::uuid IS NULL OR public.co_so_cua_luot($1::uuid, c.visit_id) = $3::uuid)
   -- Không chọn cơ sở → không đếm lượt của cơ sở NGỪNG (14/10/2026); sổ không đổi.
   AND ($3::uuid IS NOT NULL OR NOT $4::boolean OR NOT """
    + sql_cua_co_so_ngung("$1", "public.co_so_cua_luot($1::uuid, c.visit_id)")
    + """)
 ORDER BY c.luc DESC
"""
)


async def doc_so_du_mo(
    conn: asyncpg.Connection,
    clinic_id: str,
    chieu: str,
    co_so: str | None = None,
    *,
    bo_co_so_ngung: bool = True,
) -> list[dict[str, Any]]:
    """Các lượt đang có số dư ở ``chieu`` (mọi ngày, không hạn). Mỗi dòng: lượt,
    khách, ``so_du``, ``chi_tiet`` (các khoản), ``ly_do`` (lý do ghi nợ của lễ
    tân nếu có, không thì vì sao sổ ghi), ``nguoi``, ``luc`` (giờ dòng sổ),
    ``luot_tao_luc`` / ``luot_dong_luc`` (ngày thật của lượt), ``cong_no_id``.

    ``co_so`` rỗng + ``bo_co_so_ngung`` (mặc định): không đếm lượt của cơ sở đã
    NGỪNG hoạt động — chỉ ẩn khỏi màn tồn đọng, sổ không đổi; chọn đúng cơ sở
    ngừng thì vẫn đọc đủ."""
    out: list[dict[str, Any]] = []
    for r in await conn.fetch(_SO_DU_MO_SQL, clinic_id, chieu, co_so, bo_co_so_ngung):
        d = dict(r)
        ct = d["chi_tiet"]
        d["chi_tiet"] = json.loads(ct) if isinstance(ct, str) else list(ct or [])
        d["so_du"] = int(d["so_du"])
        d["dang_cho_ck"] = int(d["dang_cho_ck"] or 0) if chieu == PHAI_THU else 0
        ly_do = d.pop("ly_do_ghi_no") or NHAN_LOAI.get(str(d["loai"]), str(d["loai"]))
        if d["dang_cho_ck"]:
            ly_do = f"{ly_do} — đã chuyển khoản, chờ xác minh"
        d["ly_do"] = ly_do
        out.append(d)
    return out


# ── lượt đối chiếu định kỳ ─────────────────────────────────────────────────

#: Lượt cần xét lại: còn số dư ở một chiều, hoặc vừa về trong DOI_CHIEU_SO_GIO.
_CAN_XET_SQL = """
WITH cuoi AS (
    SELECT DISTINCT ON (visit_id, chieu) visit_id, so_du
      FROM public.so_no
     WHERE clinic_id = $1::uuid
     ORDER BY visit_id, chieu, seq DESC
)
SELECT visit_id::text AS visit_id FROM cuoi WHERE so_du <> 0
UNION
SELECT v.visit_id::text FROM public.visit v
 WHERE v.clinic_id = $1::uuid
   AND (v.closed_at >= now() - make_interval(hours => $2)
        OR (v.closed_at IS NULL
            AND v.created_at >= now() - make_interval(hours => $2 + 24)))
LIMIT $3
"""

_DAU_KY_LO_SQL = """
SELECT v.visit_id::text AS visit_id, v.created_at
  FROM public.visit v
 WHERE v.clinic_id = $1::uuid
   AND v.created_at < $2
   AND (v.created_at, v.visit_id) < ($3, $4::uuid)
 ORDER BY v.created_at DESC, v.visit_id DESC
 LIMIT $5
"""


_MOC_SQL = """
SELECT clinic_id::text AS clinic_id, bat_dau, dau_ky_den,
       dau_ky_den_id::text AS dau_ky_den_id, dau_ky_xong
  FROM public.so_no_moc
"""


async def dau_ky_mot_vong(pool: asyncpg.Pool) -> dict[str, int]:
    """Một lô số dư đầu kỳ cho mọi phòng khám chưa xong. Không bao giờ ném.

    ``con`` = số phòng khám CHƯA ghi xong đầu kỳ (0 = worker thôi gọi)."""
    ket = {"dau_ky": 0, "dong": 0, "con": 0}
    try:
        async with pool.acquire() as conn:
            mocs = await conn.fetch(_MOC_SQL)
        for m in mocs:
            if not m["dau_ky_xong"] and not await _dau_ky(pool, m, ket):
                ket["con"] += 1
    except Exception:
        logger.exception("so_no_dau_ky_hong")
        ket["con"] += 1
    return ket


async def doi_chieu_mot_vong(pool: asyncpg.Pool) -> dict[str, int]:
    """Một vòng đối chiếu cho mọi phòng khám ĐÃ ghi xong đầu kỳ (trước đó thì
    lượt cũ chưa có dòng nào sẽ bị ghi nhầm là "đối chiếu"). Không bao giờ ném."""
    ket = {"doi_chieu": 0, "dong": 0}
    try:
        async with pool.acquire() as conn:
            mocs = await conn.fetch(_MOC_SQL)
        for m in mocs:
            if m["dau_ky_xong"]:
                await _doi_chieu(pool, m["clinic_id"], ket)
    except Exception:
        logger.exception("so_no_doi_chieu_hong")
    return ket


async def _doi_chieu(pool: asyncpg.Pool, clinic_id: str, ket: dict[str, int]) -> None:
    async with pool.acquire() as conn:
        ids = [
            str(r["visit_id"])
            for r in await conn.fetch(
                _CAN_XET_SQL, clinic_id, DOI_CHIEU_SO_GIO, DOI_CHIEU_MOI_VONG
            )
        ]
    for vid in ids:
        async with pool.acquire() as conn, conn.transaction():
            rows = await ghi_chenh_lech(
                conn,
                clinic_id=clinic_id,
                visit_id=vid,
                loai="DOI_CHIEU",
                luc=await conn.fetchval("SELECT now()"),
            )
        ket["doi_chieu"] += 1
        ket["dong"] += len(rows)


async def _dau_ky(pool: asyncpg.Pool, moc: asyncpg.Record, ket: dict[str, int]) -> bool:
    """Số dư đầu kỳ cho lượt có TRƯỚC mốc bật sổ — một lô mỗi vòng, theo con trỏ
    (giờ tạo lượt giảm dần) cho tới hết rồi đánh dấu xong. Trả True khi xong."""
    clinic_id = moc["clinic_id"]
    den = moc["dau_ky_den"] or moc["bat_dau"]
    den_id = moc["dau_ky_den_id"] or "ffffffff-ffff-ffff-ffff-ffffffffffff"
    async with pool.acquire() as conn:
        lo = await conn.fetch(
            _DAU_KY_LO_SQL, clinic_id, moc["bat_dau"], den, den_id, DAU_KY_MOI_VONG
        )
    for r in lo:
        async with pool.acquire() as conn, conn.transaction():
            # Đã có dòng trong sổ (sự kiện mới chạm vào lượt cũ) thì thôi.
            co = await conn.fetchval(
                "SELECT 1 FROM public.so_no WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid LIMIT 1",
                clinic_id,
                r["visit_id"],
            )
            if co is None:
                rows = await ghi_chenh_lech(
                    conn,
                    clinic_id=clinic_id,
                    visit_id=r["visit_id"],
                    loai="DAU_KY",
                    luc=moc["bat_dau"],
                )
                ket["dong"] += len(rows)
            ket["dau_ky"] += 1
    async with pool.acquire() as conn:
        if lo:
            cuoi = lo[-1]
            await conn.execute(
                "UPDATE public.so_no_moc SET dau_ky_den = $2,"
                " dau_ky_den_id = $3::uuid WHERE clinic_id = $1::uuid",
                clinic_id,
                cuoi["created_at"],
                cuoi["visit_id"],
            )
        if len(lo) < DAU_KY_MOI_VONG:
            await conn.execute(
                "UPDATE public.so_no_moc SET dau_ky_xong = true"
                " WHERE clinic_id = $1::uuid",
                clinic_id,
            )
            logger.info("so_no_dau_ky_xong", clinic_id=clinic_id)
            return True
    return False


__all__ = [
    "CHIEU",
    "LOAI_THEO_SU_KIEN",
    "PHAI_THU",
    "PHAI_TRA",
    "SoDu",
    "chenh_lech",
    "dau_ky_mot_vong",
    "doi_chieu_mot_vong",
    "ghi_chenh_lech",
    "so_du_hien_tai",
]
