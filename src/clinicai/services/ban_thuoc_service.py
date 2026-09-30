"""Màn Nhà thuốc (contract tiền–thuốc CP4, 19/09/2026) — đọc, và quyết định
thao tác nào được phép cho từng lượt / từng dòng đơn.

Giao diện KHÔNG tự suy luật từ các cột: nó nhận `giai_doan` của lượt và
`thao_tac` của từng dòng / từng phân lô rồi vẽ đúng các nút ấy. Máy chủ vẫn
kiểm lại từng lệnh ghi — đây chỉ là để màn hình không mời bấm một nút chắc
chắn bị từ chối.

GIAI ĐOẠN CỦA LƯỢT (tiền thuốc):
  CHUA_SAN_SANG  bác sĩ chưa bấm Khám xong (`moc_kham_xong`) — chỉ xem. Chọn
                 lô sớm sẽ khoá dòng đơn trong khi bác sĩ còn sửa bệnh án.
  SAN_SANG       đã khám xong, chưa có lần thu thuốc — xác định thuốc kho,
                 khai số mua, chọn / bỏ lô.
  CHO_XAC_MINH   chuyển khoản/QR đang chờ — lô đang GIỮ; chỉ đổi lô.
  DA_THU         đã thu (lần thu mới) — giao từ đúng lô đã bán.
  CAN_DOI_SOAT   đã thu nhưng có phân lô chưa ghi bán được — không giao.
  DA_THU_CU      lần thu trước CP3 (legacy) — giao theo luồng cũ.

Ba con số lô trả kèm — `ton_vat_ly` (trên kệ) và `co_the_phan_lo` (số hệ thống
dùng để chống bán trùng). Tên hiển thị chính thức của con số thứ hai chưa chốt
(HOLD J6): màn hình KHÔNG gọi nó là "tồn khả dụng".
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.can import can
from clinicai.services.ban_le_service import QUYEN_THU_THUOC, co_quyen_mo
from clinicai.services.moc_kham_xong import kham_xong_sql
from clinicai.services.phan_lo_service import ban_chua_giao

CHUA_SAN_SANG = "CHUA_SAN_SANG"
SAN_SANG = "SAN_SANG"
CHO_XAC_MINH = "CHO_XAC_MINH"
DA_THU = "DA_THU"
CAN_DOI_SOAT = "CAN_DOI_SOAT"
DA_THU_CU = "DA_THU_CU"

#: Vai được GHI ở nhà thuốc — router dùng đúng tập này cho mọi lệnh ghi, và màn
#: đọc AND nó vào mọi nút (review CP4 P2): người chỉ đọc (thu ngân thuốc,
#: trưởng ca) thấy dữ liệu nhưng không thấy nút sẽ bị 403.
VAI_GHI_NHA_THUOC: frozenset[ClinicRole] = frozenset(
    {ClinicRole.RECEPTION, ClinicRole.PHARMACIST, ClinicRole.MANAGEMENT}
)


def _don_vi(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


def _so(v: Any) -> Decimal:
    return Decimal(str(v if v is not None else 0))


@dataclass(frozen=True)
class LanThu:
    payment_cycle_id: str
    status: str
    method: str | None
    legacy: bool
    can_doi_soat: bool


def giai_doan(
    *, kham_xong: bool, lan_thu: LanThu | None, co_phan_lo_chua_ban: bool
) -> str:
    """Giai đoạn tiền thuốc của một lượt — hàm thuần, test không cần DB."""
    if lan_thu is not None and lan_thu.status == "PENDING_VERIFICATION":
        return CHO_XAC_MINH
    if lan_thu is not None and lan_thu.status == "PAID":
        if lan_thu.legacy:
            return DA_THU_CU
        return CAN_DOI_SOAT if co_phan_lo_chua_ban else DA_THU
    # Tiền thuốc không cần Khám xong (Tuyền 24/09/2026): chưa thu thì luôn làm
    # được. CHUA_SAN_SANG giữ lại (OFF) — không đường nào trả về nữa.
    _ = kham_xong
    return SAN_SANG


def thao_tac_dong(
    *,
    gd: str,
    dong_da_chot: bool,
    da_giao: Decimal,
    co_thuoc_kho: bool,
    co_don_vi: bool,
    co_so_ke: bool,
    can_lo: Decimal,
    da_chon: Decimal,
    co_phan_lo: bool,
    so_ban: Decimal | None,
    co_quyen_ghi: bool = True,
    chua_giao: Decimal = Decimal(0),
    can_hoan: Decimal = Decimal(0),
    lich_su: bool = False,
    lo_da_ban: bool = False,
) -> dict[str, bool]:
    """Nút nào được hiện cho một dòng đơn — cùng luật với lệnh ghi ở
    pharmacy_service (Khám xong, chốt không bỏ lại thuốc đã bán chưa giao)."""
    mo = not dong_da_chot
    san_sang = gd == SAN_SANG and mo
    nut = {
        "xac_dinh_thuoc": san_sang and da_giao == 0 and not co_phan_lo,
        "khai_so_mua": san_sang and co_so_ke,
        "chon_lo": san_sang
        and co_thuoc_kho
        and co_don_vi
        and co_so_ke
        and da_chon < can_lo,
        "giao_luong_cu": gd == DA_THU_CU and mo,
        # 28/09/2026 — GIAO KHÔNG CẦN LÔ ("chưa cần quan tâm lô nào … gán sau"):
        # đã thu, dòng không có lô nào, còn phần bán chưa giao. Kho trừ khi gán
        # lô ở Kho thuốc (`pharmacy_service.gan_lo_da_giao`).
        "giao_khong_lo": gd == DA_THU
        and mo
        and not lo_da_ban
        and so_ban is not None
        and da_giao < so_ban,
        # Khách không lấy: sau Khám xong, trước khi có lần thu (sau đó phải
        # huỷ phiếu). Chốt / từ chối trước Khám xong cũng khoá dòng khỏi nút
        # Lưu bệnh án — đúng thứ màn này không được làm khi bác sĩ còn sửa đơn.
        "tu_choi": san_sang and chua_giao == 0,
        # Chờ xác minh / cần đối soát: không bao giờ. Đã thu (luồng mới): chỉ
        # khi đã giao đủ số bán — trước CP5 không có đường xử lý phần còn lại.
        "chot": mo
        and chua_giao == 0
        and (
            gd in (SAN_SANG, DA_THU_CU)
            or (gd == DA_THU and so_ban is not None and da_giao >= so_ban)
        ),
        # CP5: nhả phần đã bán chưa giao — chỉ khi đã có căn cứ tài chính
        # (huỷ phiếu / hoàn tiền xong đủ). Thiếu căn cứ: màn nói còn cần hoàn.
        "huy_chua_giao": chua_giao > 0 and can_hoan == 0,
    }
    if lich_su:
        # CP6 Q3: dòng bác sĩ đã đính chính không nhận thao tác mới — chỉ còn
        # đối soát phần đã bán (khách trả nằm ở từng lần giao).
        nut = {k: (k == "huy_chua_giao" and v) for k, v in nut.items()}
    return {k: v and co_quyen_ghi for k, v in nut.items()}


def thao_tac_phan_lo(
    *,
    gd: str,
    dong_da_chot: bool,
    gan_lan_thu: bool,
    da_ban: bool,
    con_giao: Decimal,
    co_quyen_ghi: bool = True,
    lich_su: bool = False,
) -> dict[str, bool]:
    """Nút nào được hiện cho một phân lô (một lô đã chọn của dòng đơn).
    Dòng đã đính chính (lịch sử): không nút nào — không bỏ, đổi hay giao."""
    nut = {
        "bo": gd == SAN_SANG and not gan_lan_thu and not dong_da_chot,
        "doi": gd == CHO_XAC_MINH and gan_lan_thu,
        "giao": gd == DA_THU
        and gan_lan_thu
        and da_ban
        and con_giao > 0
        and not dong_da_chot,
    }
    if lich_su:
        return dict.fromkeys(nut, False)
    return {k: v and co_quyen_ghi for k, v in nut.items()}


async def man_nha_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> dict[str, Any]:
    hom_nay = now_vn().date()
    dau_ngay = datetime.combine(hom_nay, time.min, tzinfo=CLINIC_TZ)
    async with pool.acquire() as conn:
        # Nút ghi hiện theo QUYỀN "Nhà thuốc" (24/09), cùng câu hỏi với router.
        co_quyen_ghi = await can(conn, identity, "pharmacy.dispense")
        dong = await conn.fetch(
            f"""
            SELECT r.id::text, r.visit_id::text, r.drug_name_raw, r.quantity,
                   r.quantity_num, r.unit, r.purchased_qty, r.dispensed_qty,
                   r.dispense_status, r.closed_at, r.refusal_reason,
                   r.dosage_instructions, r.drug_catalog_id::text,
                   c.name_base AS ten_thuoc_kho, r.created_at,
                   p.full_name AS ten_khach, p.patient_code, p.phone_primary,
                   ap.so_booking, ap.so_tiep_don,
                   {kham_xong_sql("v")} AS kham_xong,
                   r.removed_at, r.removal_reason,
                   r.superseded_by_id::text AS thay_boi_id, v.ban_le
              FROM public.prescription r
              JOIN public.visit v
                ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
              LEFT JOIN public.patient p
                ON p.clinic_patient_id = r.clinic_patient_id
               AND p.clinic_id = r.clinic_id
              LEFT JOIN public.drug_catalog c
                ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
              LEFT JOIN public.appointment ap
                ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
             WHERE r.clinic_id = $1::uuid
               AND ((r.removed_at IS NULL
                     AND (r.closed_at IS NULL OR r.closed_at >= $2))
                    -- CP6: dòng bác sĩ đã đính chính (lịch sử) chỉ hiện khi
                    -- còn việc đối soát ở quầy: đính chính hôm nay, còn phần
                    -- đã bán chưa giao, hoặc lô còn gắn lần thu đang chờ.
                    OR (r.removed_at IS NOT NULL
                        AND (r.removed_at >= $2
                             OR EXISTS (
                                 SELECT 1 FROM public.prescription_allocation a
                                   JOIN public.inventory_txn s
                                     ON s.allocation_id = a.id
                                    AND s.clinic_id = a.clinic_id
                                    AND s.txn_type = 'SALE'
                                  WHERE a.clinic_id = r.clinic_id
                                    AND a.prescription_id = r.id
                                    AND NOT EXISTS (
                                        SELECT 1 FROM public.inventory_txn x
                                         WHERE x.txn_type = 'SALE_REVERSAL'
                                           AND x.reverses_txn_id = s.id)
                                    AND -s.quantity > coalesce((
                                        SELECT -sum(d.quantity)
                                          FROM public.inventory_txn d
                                         WHERE d.txn_type = 'DISPENSE'
                                           AND d.allocation_id = a.id), 0))
                             OR EXISTS (
                                 SELECT 1 FROM public.prescription_allocation a
                                   JOIN public.payment_cycle c
                                     ON c.payment_cycle_id = a.payment_cycle_id
                                    AND c.clinic_id = a.clinic_id
                                  WHERE a.clinic_id = r.clinic_id
                                    AND a.prescription_id = r.id
                                    AND a.released_at IS NULL
                                    AND c.status = 'PENDING_VERIFICATION'))))
             ORDER BY r.created_at DESC, r.id
             LIMIT 300
            """,
            identity.clinic_id,
            dau_ngay,
        )
        # Trần 300 đơn/ngày. Chạm trần là quầy thuốc đang nhìn một bảng THIẾU
        # đơn — phải nói ra, không để im.
        don_bi_cat = canh_bao_neu_day("nha_thuoc.don_hom_nay", len(dong), 300)
        luot_ids = sorted({r["visit_id"] for r in dong})
        rx_ids = [r["id"] for r in dong]
        lan_thu_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (visit_id)
                   visit_id::text, payment_cycle_id::text, status,
                   hinh_thuc_hieu_luc(clinic_id, payment_cycle_id, method) AS method,
                   legacy, can_doi_soat
              FROM public.payment_cycle
             WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])
               AND kind = 'thuoc'
               AND status IN ('PENDING_VERIFICATION', 'PAID')
             ORDER BY visit_id, created_at DESC
            """,
            identity.clinic_id,
            luot_ids,
        )
        phan_lo = await conn.fetch(
            """
            SELECT a.id::text, a.prescription_id::text, a.drug_batch_id::text,
                   a.quantity, a.handed_over_qty, a.payment_cycle_id::text,
                   b.batch_code, b.expiry_date,
                   -- Đã TỪNG ghi bán (kể cả phần sau đó bị huỷ-chưa-giao). Không
                   -- có SALE nào = "chưa ghi bán được" (cần đối soát).
                   EXISTS (SELECT 1 FROM public.inventory_txn s0
                            WHERE s0.clinic_id = a.clinic_id
                              AND s0.txn_type = 'SALE' AND s0.allocation_id = a.id
                              AND s0.payment_cycle_id = a.payment_cycle_id)
                       AS co_sale,
                   EXISTS (SELECT 1 FROM public.inventory_txn s
                            WHERE s.clinic_id = a.clinic_id
                              AND s.txn_type = 'SALE' AND s.allocation_id = a.id
                              AND s.payment_cycle_id = a.payment_cycle_id
                              AND NOT EXISTS (
                                  SELECT 1 FROM public.inventory_txn r
                                   WHERE r.txn_type = 'SALE_REVERSAL'
                                     AND r.reverses_txn_id = s.id)) AS da_ban
              FROM public.prescription_allocation a
              JOIN public.drug_batch b
                ON b.id = a.drug_batch_id AND b.clinic_id = a.clinic_id
             WHERE a.clinic_id = $1::uuid AND a.prescription_id = ANY($2::uuid[])
               AND a.released_at IS NULL
             ORDER BY a.created_at, a.id
            """,
            identity.clinic_id,
            rx_ids,
        )
        thuoc_ids = sorted({r["drug_catalog_id"] for r in dong if r["drug_catalog_id"]})
        lo_rows = await conn.fetch(
            """
            SELECT id::text, drug_catalog_id::text, batch_code, expiry_date, unit,
                   quantity_on_hand,
                   public.drug_batch_kha_dung($1::uuid, id) AS co_the_phan_lo
              FROM public.drug_batch
             WHERE clinic_id = $1::uuid AND drug_catalog_id = ANY($2::uuid[])
               AND expiry_date >= $3
             ORDER BY expiry_date, batch_code
            """,
            identity.clinic_id,
            thuoc_ids,
            hom_nay,
        )
        # Lượt thu trước CP3 mà dòng đơn chưa từng được xác định thuốc kho:
        # luồng cũ gợi ý lô theo TÊN (đúng như màn cũ) — dược sĩ vẫn là người
        # chọn. Chỉ đọc khi thật sự có lượt như vậy.
        lo_cu: list[asyncpg.Record] = []
        if any(r["legacy"] for r in lan_thu_rows):
            lo_cu = await conn.fetch(
                """
                SELECT b.id::text, b.drug_catalog_id::text, b.batch_code,
                       b.expiry_date, b.unit, b.quantity_on_hand,
                       b.quantity_on_hand AS co_the_phan_lo,
                       lower(coalesce(c.name_base, '')) AS ten_a,
                       lower(coalesce(c.name_raw, '')) AS ten_b
                  FROM public.drug_batch b
                  JOIN public.drug_catalog c
                    ON c.id = b.drug_catalog_id AND c.clinic_id = b.clinic_id
                 WHERE b.clinic_id = $1::uuid AND b.quantity_on_hand > 0
                   AND b.expiry_date >= $2
                 ORDER BY b.expiry_date, b.batch_code
                """,
                identity.clinic_id,
                hom_nay,
            )
        # CP5: các lần GIAO (DISPENSE) của từng dòng — khách trả thuốc phải
        # chọn đúng lần giao gốc — kèm số đã trả; phần đã bán chưa giao; phần
        # đã huỷ-chưa-giao của lần thu đang sống (để "số bán" là số ròng).
        xuat_rows = await conn.fetch(
            """
            SELECT t.id::text, t.ref_id::text AS prescription_id, b.batch_code,
                   -t.quantity AS so_luong, t.performed_at,
                   coalesce((SELECT sum(r.returned_qty) FROM public.drug_return r
                              WHERE r.clinic_id = t.clinic_id
                                AND r.original_dispense_txn_id = t.id), 0) AS da_tra
              FROM public.inventory_txn t
              JOIN public.drug_batch b
                ON b.id = t.drug_batch_id AND b.clinic_id = t.clinic_id
             WHERE t.clinic_id = $1::uuid AND t.txn_type = 'DISPENSE'
               AND t.ref_type = 'prescription' AND t.ref_id = ANY($2::uuid[])
             ORDER BY t.performed_at, t.id
            """,
            identity.clinic_id,
            rx_ids,
        )
        chua_giao = await ban_chua_giao(conn, identity.clinic_id, rx_ids)
        dao_rows = await conn.fetch(
            """
            SELECT a.prescription_id::text, t.payment_cycle_id::text,
                   sum(t.quantity) AS da_dao
              FROM public.inventory_txn t
              JOIN public.prescription_allocation a
                ON a.id = t.allocation_id AND a.clinic_id = t.clinic_id
             WHERE t.clinic_id = $1::uuid AND t.txn_type = 'SALE_REVERSAL'
               AND a.prescription_id = ANY($2::uuid[])
             GROUP BY a.prescription_id, t.payment_cycle_id
            """,
            identity.clinic_id,
            rx_ids,
        )
        # V8 (30/09/2026): lượt BÁN LẺ trong ngày — quầy thấy ngay khi vừa mở,
        # CHƯA có dòng đơn nào (khách chỉ đến mua thuốc).
        ban_le_rows = await conn.fetch(
            """
            SELECT v.visit_id::text, p.full_name AS ten_khach, p.patient_code,
                   p.phone_primary
              FROM public.visit v
              LEFT JOIN public.patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
             WHERE v.clinic_id = $1::uuid AND v.ban_le
               AND (v.created_at >= $2 OR v.updated_at >= $2)
             ORDER BY v.created_at DESC
             LIMIT 100
            """,
            identity.clinic_id,
            dau_ngay,
        )
        duoc_mo_ban_le = await co_quyen_mo(conn, identity)
        duoc_thu_thuoc = await can(conn, identity, QUYEN_THU_THUOC)
        danh_muc = await conn.fetch(
            """
            SELECT id::text, name_base, variant FROM public.drug_catalog
             WHERE clinic_id = $1::uuid AND is_active
             ORDER BY name_base, variant NULLS FIRST
            """,
            identity.clinic_id,
        )

    lan_thu = {
        r["visit_id"]: LanThu(
            payment_cycle_id=r["payment_cycle_id"],
            status=r["status"],
            method=r["method"],
            legacy=bool(r["legacy"]),
            can_doi_soat=bool(r["can_doi_soat"]),
        )
        for r in lan_thu_rows
    }
    xuat_theo_dong: dict[str, list[dict[str, Any]]] = {}
    for x in xuat_rows:
        con_tra = _so(x["so_luong"]) - _so(x["da_tra"])
        xuat_theo_dong.setdefault(x["prescription_id"], []).append(
            {
                "dispense_txn_id": x["id"],
                "batch_code": x["batch_code"],
                "so_luong": _so(x["so_luong"]),
                "luc": x["performed_at"],
                "da_tra": _so(x["da_tra"]),
                "con_tra": con_tra,
                # Chỉ là "thuốc đã quay lại quầy" — không quyết xử lý (HOLD J1/J2).
                "thao_tac": {"tra": co_quyen_ghi and con_tra > 0},
            }
        )
    dao: dict[tuple[str, str], Decimal] = {
        (r["prescription_id"], r["payment_cycle_id"]): _so(r["da_dao"])
        for r in dao_rows
    }
    pl_theo_dong: dict[str, list[asyncpg.Record]] = {}
    for p in phan_lo:
        pl_theo_dong.setdefault(p["prescription_id"], []).append(p)
    lo_theo_thuoc: dict[str, list[asyncpg.Record]] = {}
    for b in lo_rows:
        lo_theo_thuoc.setdefault(b["drug_catalog_id"], []).append(b)

    luot: dict[str, dict[str, Any]] = {}
    for r in dong:
        vid = r["visit_id"]
        lt = lan_thu.get(vid)
        if vid not in luot:
            luot[vid] = {
                "visit_id": vid,
                "ten_khach": r["ten_khach"],
                "patient_code": r["patient_code"],
                "phone": r["phone_primary"],
                "so_booking": r["so_booking"],
                "so_tiep_don": r["so_tiep_don"],
                "kham_xong": bool(r["kham_xong"]),
                "ban_le": bool(r["ban_le"]),
                "lan_thu": (
                    {
                        "payment_cycle_id": lt.payment_cycle_id,
                        "status": lt.status,
                        "method": lt.method,
                        "can_doi_soat": lt.can_doi_soat,
                    }
                    if lt
                    else None
                ),
                "dong": [],
                "_rows": [],
            }
        luot[vid]["_rows"].append(r)

    for vid, g in luot.items():
        lt = lan_thu.get(vid)
        bound = [
            p
            for r in g["_rows"]
            for p in pl_theo_dong.get(r["id"], [])
            if lt is not None and p["payment_cycle_id"] == lt.payment_cycle_id
        ]
        gd = giai_doan(
            kham_xong=g["kham_xong"],
            lan_thu=lt,
            co_phan_lo_chua_ban=any(not p["co_sale"] for p in bound),
        )
        g["giai_doan"] = gd
        for r in g.pop("_rows"):
            cg = chua_giao.get(r["id"], {})
            them = {
                "xuat": xuat_theo_dong.get(r["id"], []),
                "chua_giao": cg.get("chua_giao", Decimal(0)),
                "can_hoan": cg.get("can_hoan", Decimal(0)),
                "da_dao_song": (
                    dao.get((r["id"], lt.payment_cycle_id), Decimal(0))
                    if lt
                    else Decimal(0)
                ),
            }
            g["dong"].append(
                _dong(r, gd, lt, pl_theo_dong, lo_theo_thuoc, lo_cu, co_quyen_ghi, them)
            )
    # Lượt bán lẻ chưa có dòng đơn: vẫn hiện (giai đoạn "chờ thu"), lên đầu.
    ban_le_trong = [
        {
            "visit_id": b["visit_id"],
            "ten_khach": b["ten_khach"],
            "patient_code": b["patient_code"],
            "phone": b["phone_primary"],
            "so_booking": None,
            "so_tiep_don": None,
            "kham_xong": False,
            "ban_le": True,
            "lan_thu": None,
            "dong": [],
            "giai_doan": SAN_SANG,
        }
        for b in ban_le_rows
        if b["visit_id"] not in luot
    ]
    return {
        "luot": ban_le_trong + list(luot.values()),
        "danh_muc": [dict(d) for d in danh_muc],
        "hom_nay": hom_nay.isoformat(),
        "co_quyen_ghi": co_quyen_ghi,
        # V8: nút "Khách mua thuốc" + khối kê / thu tại quầy — máy chủ quyết.
        "duoc_mo_ban_le": duoc_mo_ban_le,
        "duoc_thu_thuoc": duoc_thu_thuoc,
        "bi_cat": don_bi_cat,
        "tran": 300,
    }


def _dong(
    r: asyncpg.Record,
    gd: str,
    lt: LanThu | None,
    pl_theo_dong: dict[str, list[asyncpg.Record]],
    lo_theo_thuoc: dict[str, list[asyncpg.Record]],
    lo_cu: list[asyncpg.Record],
    co_quyen_ghi: bool,
    them: dict[str, Any],
) -> dict[str, Any]:
    ke = r["quantity_num"]
    ban = r["purchased_qty"] if r["purchased_qty"] is not None else ke
    da_giao = _so(r["dispensed_qty"])
    # Phần phải có lô = số bán − phần đã cấp theo luồng cũ (xem
    # phan_lo_service.can_theo_hoa_don). Chỉ có nghĩa trước khi thu.
    can_lo = max(_so(ban) - da_giao, Decimal(0)) if ban is not None else Decimal(0)
    cac_pl = pl_theo_dong.get(r["id"], [])
    da_chon = sum((_so(p["quantity"]) for p in cac_pl), Decimal(0))
    da_chot = r["closed_at"] is not None
    lich_su = r["removed_at"] is not None
    if lich_su:
        can_lo = Decimal(0)
    ds_pl = []
    for p in cac_pl:
        gan = p["payment_cycle_id"] is not None
        con = _so(p["quantity"]) - _so(p["handed_over_qty"])
        ds_pl.append(
            {
                "allocation_id": p["id"],
                "drug_batch_id": p["drug_batch_id"],
                "batch_code": p["batch_code"],
                "expiry_date": p["expiry_date"],
                "quantity": _so(p["quantity"]),
                "handed_over_qty": _so(p["handed_over_qty"]),
                "con_giao": con,
                "dang_giu": gan and gd == CHO_XAC_MINH,
                "da_ban": bool(p["da_ban"]),
                # Đã TỪNG ghi bán — kể cả khi phần chưa giao sau đó đã huỷ (CP5).
                "co_sale": bool(p["co_sale"]),
                "thao_tac": thao_tac_phan_lo(
                    gd=gd,
                    dong_da_chot=da_chot,
                    gan_lan_thu=gan
                    and lt is not None
                    and p["payment_cycle_id"] == lt.payment_cycle_id,
                    da_ban=bool(p["da_ban"]),
                    con_giao=con,
                    co_quyen_ghi=co_quyen_ghi,
                    lich_su=lich_su,
                ),
            }
        )
    lo_goi_y = []
    ung_vien: list[asyncpg.Record] = []
    if r["drug_catalog_id"]:
        ung_vien = lo_theo_thuoc.get(r["drug_catalog_id"], [])
    elif gd == DA_THU_CU:
        ten = (r["drug_name_raw"] or "").strip().lower()
        ung_vien = [
            b
            for b in lo_cu
            if ten
            and any(x and (x in ten or ten in x) for x in (b["ten_a"], b["ten_b"]))
        ]
    if ung_vien and not lich_su:
        dv = _don_vi(r["unit"])
        for b in ung_vien:
            # Luồng mới: chỉ lô cùng đơn vị kê. Luồng cũ (legacy) giữ luật cũ:
            # đơn thiếu đơn vị thì hiểu theo đơn vị lô.
            if dv and _don_vi(b["unit"]) != dv:
                continue
            lo_goi_y.append(
                {
                    "drug_batch_id": b["id"],
                    "batch_code": b["batch_code"],
                    "expiry_date": b["expiry_date"],
                    "unit": b["unit"],
                    "ton_vat_ly": _so(b["quantity_on_hand"]),
                    "co_the_phan_lo": _so(b["co_the_phan_lo"]),
                }
            )
    return {
        "id": r["id"],
        "drug_name_raw": r["drug_name_raw"],
        "quantity_text": r["quantity"],
        "quantity_num": ke,
        "unit": r["unit"],
        "purchased_qty": r["purchased_qty"],
        "dispensed_qty": da_giao,
        "dispense_status": r["dispense_status"],
        "closed": da_chot,
        "refusal_reason": r["refusal_reason"],
        "dosage_instructions": r["dosage_instructions"],
        "drug_catalog_id": r["drug_catalog_id"],
        "ten_thuoc_kho": r["ten_thuoc_kho"],
        "can_lo": can_lo,
        "da_chon": da_chon,
        "phan_lo": ds_pl,
        "lo_goi_y": lo_goi_y,
        "xuat": them["xuat"],
        "chua_giao": them["chua_giao"],
        "can_hoan": them["can_hoan"],
        # CP6: dòng đã được bác sĩ đính chính (lịch sử) — chỉ còn đối soát.
        "lich_su": lich_su,
        "thay_boi_id": r["thay_boi_id"],
        "ly_do_dinh_chinh": r["removal_reason"],
        "dinh_chinh_luc": r["removed_at"],
        "thao_tac": thao_tac_dong(
            gd=gd,
            dong_da_chot=da_chot,
            da_giao=da_giao,
            co_thuoc_kho=r["drug_catalog_id"] is not None,
            co_don_vi=bool(_don_vi(r["unit"])),
            co_so_ke=ke is not None,
            can_lo=can_lo,
            da_chon=da_chon,
            co_phan_lo=bool(cac_pl),
            # Số bán RÒNG: trừ phần đã "huỷ phần chưa giao" của lần thu đang sống.
            so_ban=_so(ban) - them["da_dao_song"] if ban is not None else None,
            co_quyen_ghi=co_quyen_ghi,
            chua_giao=them["chua_giao"],
            can_hoan=them["can_hoan"],
            lich_su=lich_su,
            # Dòng có lô ĐÃ BÁN trong lần thu đang sống → giao đúng lô ấy;
            # không có → giao không lô được (28/09/2026).
            lo_da_ban=any(
                p["payment_cycle_id"] is not None
                and lt is not None
                and p["payment_cycle_id"] == lt.payment_cycle_id
                for p in cac_pl
            ),
        ),
    }


__all__ = ["man_nha_thuoc", "giai_doan", "thao_tac_dong", "thao_tac_phan_lo"]
