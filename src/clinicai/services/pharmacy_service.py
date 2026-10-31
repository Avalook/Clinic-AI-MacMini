"""Đường GHI của nhà thuốc: nhập lô, cấp phát, điều chỉnh, huỷ.

VÌ SAO FILE NÀY ĐƯỢC VIẾT.

Nhà thuốc là một cái kho xây xong vỏ mà chưa có cửa vào. Lược đồ đầy đủ và chặt
— `drug_batch`, `inventory_txn` chỉ-thêm, trigger cộng dồn tồn, CHECK chặn tồn
âm — bốn màn hình chạy được, vai PHARMACIST có tài khoản thật. Nhưng đo trên
production ngày 07/08/2026: **không một dòng Python nào chạm tới ba bảng ấy**,
không router nào tên pharmacy, và RLS chỉ cấp SELECT cho `authenticated`. Kết
quả: dược sĩ mở màn kho thấy một cái bảng rỗng và không có nút nào để nhập
hàng. `drug_batch` 0 dòng, `inventory_txn` 0 dòng — vĩnh viễn.

BA TÌNH HUỐNG QUANG MÔ TẢ, MỘT MÔ HÌNH.

Bệnh nhân mua thuốc, không mua, hoặc mua một phần. Cả ba đi qua cùng một đường:
`cap_phat()` cộng vào `prescription.dispensed_qty` và ghi một dòng DISPENSE vào
sổ kho. "Không mua" là `tu_choi()`. "Lấy 5 rồi thôi" là cấp 5 rồi `chot()`.
Trạng thái không phải một cột ghi tay mà được TÍNH từ hai con số ấy
(`dispense_status`, migration 20260807000004) — nên không có trạng thái nào tồn
tại mà lệch với số liệu.

RANH GIỚI VỚI DATABASE.

Database đã chặn những điều không được phép: tồn không xuống âm
(`drug_batch_qty_non_negative`), sổ không sửa được (`inventory_txn_append_only`),
lô phải cùng phòng khám (trigger `inventory_txn_apply` ném lỗi), dấu của số
lượng phải khớp loại giao dịch. File này KHÔNG dựng lại những chốt ấy — nó nói
trước chúng, bằng tiếng Việt, để dược sĩ đọc được câu từ chối thay vì một lỗi
ràng buộc Postgres.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NamedTuple

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn, now_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import ThuocDaGiao, ThuocKhachTra
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.don_vi_thuoc import (
    SAU_SO_LE,
    BangDonVi,
    QuyDoiDong,
    cau_thieu_quy_doi,
    chuan,
    doc_bang,
    doc_don_vi_gui_len,
    he_so_da_chup,
    kiem_doi_don_vi_goc,
    luu_cac_don_vi,
    quy_doi_cua_dong,
    so_de_doc,
)
from clinicai.services.hoan_tac_giao_service import (
    LanGiao,
    cac_lan_giao,
    ghi_dong_dao,
    giam_da_giao,
    huy_cho_gan_lo,
    phat_hoan_tac_giao,
)
from clinicai.services.moc_kham_xong import kham_xong_sql
from clinicai.services.phan_lo_service import chua_giao_cua_dong, khoa_lo, so
from clinicai.services.vat_tu_trung_ma import thuoc_la_vat_tu

logger = structlog.get_logger()

#: Câu trả về màn sau khi giao hàng trùng mã vật tư.
GIAO_VAT_TU_XONG = "Đã giao cho khách. Hàng này tính ở Kho vật tư — không cần gán lô."

# Loại giao dịch kho, đúng bốn giá trị mà `inventory_txn_type_check` canh.
# Khai lại ở đây để một lỗi gõ bị bắt ở Python, trước khi nó thành một lỗi
# ràng buộc khó đọc từ Postgres.
NHAP = "RECEIVE"
CAP = "DISPENSE"
DIEU_CHINH = "ADJUST"
HUY = "DISCARD"
# CP5: thuốc khách trả đã quay lại quầy — vật lý tăng, CHƯA bán lại được.
TRA_NHAN = "RETURN_RECEIVED"
#: Kết cục TIỀN của một lần khách trả thuốc (G4d · R3, Tuyền chốt E 14/10).
KET_CUC_TIEN = frozenset({"HOAN", "DOI", "GIU_LAI"})


#: Số lớn nhất một ô số lượng / giá nhận. Cột Postgres là numeric(12,3) / (12,0):
#: gõ lố 1e12 thì trước đây rơi vào lỗi tràn số → 500 "chưa lường trước". Trần này
#: nằm dưới giới hạn cột, và lớn hơn mọi lô / giá có thật của một phòng khám.
SO_TOI_DA = Decimal(999_999_999)


def _so(value: Any, *, ten: str, cho_0: bool = False) -> Decimal:
    """Ép về số dương (`cho_0`: được bằng 0 — giá tặng kèm). Câu từ chối nói rõ
    ô nào sai, không nói 'invalid input'."""
    try:
        so = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 — mọi kiểu rác đều về một câu
        raise ValidationError(f"{ten} phải là một con số.") from exc
    if not so.is_finite():
        raise ValidationError(f"{ten} phải là một con số.")
    if so < 0 or (so == 0 and not cho_0):
        raise ValidationError(f"{ten} phải lớn hơn 0.")
    if so > SO_TOI_DA:
        toi_da = f"{SO_TOI_DA:,}".replace(",", ".")
        raise ValidationError(
            f"{ten} quá lớn (tối đa {toi_da}) — kiểm tra lại có gõ thừa số 0 không."
        )
    return so


def _don_vi(value: str | None) -> str:
    """Chỉ chuẩn hoá cách viết; hộp, vỉ, viên luôn là các đơn vị khác nhau."""
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


def _kiem_khong_giao_qua_so_mua(don: Any, luong: Decimal) -> None:
    """Không giao quá số khách mua; số kê chỉ là mức dự phòng cho đơn cũ chưa ghi
    riêng số mua."""
    da_cap = Decimal(str(don["dispensed_qty"] or 0))
    mua = don.get("purchased_qty")
    if mua is None:
        mua = don["quantity_num"]
    if mua is not None and da_cap + luong > Decimal(str(mua)):
        so_mua = Decimal(str(mua))
        dv = f" {don['unit']}" if don.get("unit") else ""
        raise ValidationError(
            f"Khách mua {_so_gon(so_mua)}{dv}, đã giao {_so_gon(da_cap)}{dv}, còn "
            f"{_so_gon(so_mua - da_cap)}{dv} — không giao quá số đã bán."
        )


def _tom_tat_giao(
    lo_da_tru: list[dict[str, Any]],
    chua_tru: Decimal,
    don_vi: str | None,
    can_lam: str | None = None,
    chu_chua_tru: str | None = None,
) -> str | None:
    """Câu cho màn nhà thuốc sau khi giao tự chọn lô: lô nào đã trừ, phần nào
    chưa trừ được. Rỗng khi giao có chỉ định lô (màn đã tự nói)."""
    if not lo_da_tru and chua_tru <= 0:
        return None
    dv = f" {don_vi}" if don_vi else ""
    phan = [
        # Số trừ theo đơn vị CỦA LÔ: bán 1 hộp thì lô trừ 30 gói.
        f"trừ {so(x['so_luong'])}"
        + (f" {x['don_vi']}" if x.get("don_vi") else dv)
        + f" từ lô {x['batch_code']}"
        + (f" (hạn {x['expiry_date']:%d/%m/%Y})" if x["expiry_date"] else "")
        for x in lo_da_tru
    ]
    if chua_tru > 0:
        phan.append(
            f"{chu_chua_tru or so(chua_tru) + dv} quầy không đủ để trừ — đã ghi vào "
            "danh sách "
            "“Đã giao, chưa trừ kho”, gán lô ở kho hoặc quầy sau"
        )
    return "Đã giao: " + "; ".join(phan) + "." + (f" {can_lam}" if can_lam else "")


def _kiem_don_vi_cung_lo(hang: list[Any], *, batch_code: str, unit: str) -> None:
    """Không gộp lô nếu bất kỳ nơi chứa hiện có nào dùng đơn vị khác."""
    khac = next((row for row in hang if _don_vi(row["unit"]) != _don_vi(unit)), None)
    if khac is not None:
        raise ConflictError(
            f"Số lô {batch_code} đang tính theo đơn vị {khac['unit']} — "
            "nhập cùng đơn vị."
        )


def _so_chuan(value: Decimal) -> str:
    """Chuỗi số ổn định cho dấu vân tay; 2, 2.0 và 2.000 là cùng một lượng."""
    return format(value.normalize(), "f")


def _dau_van_tay(payload: dict[str, Any]) -> str:
    data = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _so_chu(v: Any) -> str | None:
    return None if v is None else str(v)


def _ly_do_hoan_tac_giao(raw: object) -> str:
    """Lý do TUỲ CHỌN của hoàn tác giao → câu ghi sổ, không bao giờ rỗng."""
    chu = " ".join(raw.split())[:300] if isinstance(raw, str) else ""
    return f"Hoàn tác giao: {chu}" if chu else "Hoàn tác giao"


#: Không gửi ô ấy = giữ giá trị cũ (khác với gửi rỗng = xoá).
GIU_NGUYEN: Any = object()


#: Luật cũ "nhà thuốc đợi Khám xong" — OFF từ 24/09/2026 (xem `_bat_buoc_kham_xong`).
_CHO_KHAM_XONG = False

#: Kho riêng từng cơ sở (08/10/2026): thao tác gắn LƯỢT chỉ dùng lô của cơ sở
#: của lượt. Trigger `prescription_allocation_dung_co_so` /
#: `inventory_txn_dung_co_so` là chốt cuối; câu này nói trước bằng tiếng Việt.
LO_KHAC_CO_SO = (
    "Lô này thuộc kho cơ sở khác với cơ sở của lượt khám — chọn lô của kho cơ sở này."
)


class PharmacyService:
    """Kho thuốc và cấp phát theo đơn. Mọi ghi đi qua đây."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc ────────────────────────────────────────────────────────────────

    async def hang_doi(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Đơn thuốc CHƯA CHỐT, gom theo lượt khám.

        Lọc theo `closed_at IS NULL` chứ không theo `dispense_status`: một đơn
        đã cấp một phần vẫn còn việc, còn một đơn khách từ chối thì đã xong.
        Trạng thái trả kèm để màn hình vẽ, không dùng để lọc.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text,
                       r.visit_id::text,
                       r.clinic_patient_id::text,
                       p.full_name      AS patient_name,
                       p.patient_code,
                       r.drug_name_raw,
                       r.quantity       AS quantity_text,
                       r.quantity_num,
                       r.unit,
                       r.dispensed_qty,
                       r.dispense_status,
                       r.dosage_instructions,
                       r.caution,
                       r.created_at
                  FROM public.prescription r
                  LEFT JOIN public.patient p
                    ON p.clinic_patient_id = r.clinic_patient_id
                 WHERE r.clinic_id = $1::uuid
                   AND r.closed_at IS NULL
                   AND r.removed_at IS NULL
                   -- Chỉ đơn của cơ sở đang đứng ($2 NULL = không lọc).
                   AND coalesce(public.co_so_cua_luot(r.clinic_id, r.visit_id),
                                $2::uuid)
                       IS NOT DISTINCT FROM
                       coalesce($2::uuid,
                                public.co_so_cua_luot(r.clinic_id, r.visit_id))
                 ORDER BY r.created_at DESC
                 LIMIT 300
                """,
                identity.clinic_id,
                identity.location_id or None,
            )
        # Hàng đợi cấp thuốc mà cắt im lặng là có người đứng đợi mà không ai
        # thấy tên. Trần giữ nguyên; điều đổi là nó kêu lên khi chạm.
        canh_bao_neu_day("nha_thuoc.hang_doi", len(rows), 300)
        return [dict(r) for r in rows]

    async def lich_su_giao(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Dòng thuốc ĐÃ GIAO (mới nhất trước, tối đa 200) — kèm ba con số của
        một dòng: bác sĩ KÊ (`quantity_num`), khách CHỐT MUA (`purchased_qty`,
        trống = như kê) và ĐÃ GIAO (`dispensed_qty`).

        24/09/2026: trang Lịch sử bàn giao từng đọc thẳng `prescription` bằng
        Supabase và chỉ hiện số đã giao — nợ "đơn kê vs khách thực mua".
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text, r.source_ref, r.drug_name_raw,
                       c.name_raw AS ten_thuoc_kho,
                       r.dosage_instructions, r.quantity, r.quantity_note,
                       r.quantity_num, r.purchased_qty, r.dispensed_qty, r.unit,
                       r.dispense_status, r.dispensed_at, r.created_at,
                       p.full_name, p.phone_primary
                  FROM public.prescription r
                  LEFT JOIN public.patient p
                    ON p.clinic_patient_id = r.clinic_patient_id
                   AND p.clinic_id = r.clinic_id
                  -- Thuốc THẬT đã giao = thuốc kho quầy chọn; drug_name_raw là
                  -- chữ bác sĩ gõ (khách báo 08/10/2026: lịch sử hiện thuốc kê).
                  LEFT JOIN public.drug_catalog c
                    ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.dispensed_qty > 0
                   AND coalesce(public.co_so_cua_luot(r.clinic_id, r.visit_id),
                                $2::uuid)
                       IS NOT DISTINCT FROM
                       coalesce($2::uuid,
                                public.co_so_cua_luot(r.clinic_id, r.visit_id))
                 -- rx:gom-ca-lich-su: thuốc ĐÃ GIAO tay khách là sự thật, kể cả
                 -- dòng bác sĩ đính chính sau khi giao — lịch sử phải còn nó.
                 ORDER BY r.dispensed_at DESC NULLS LAST
                 LIMIT 200
                """,
                identity.clinic_id,
                identity.location_id or None,
            )
        canh_bao_neu_day(
            "nha_thuoc.lich_su", len(rows), 200, clinic_id=identity.clinic_id
        )
        return [dict(r) for r in rows]

    async def cho_tu_van(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Dòng thuốc còn việc (chưa chốt, chưa bị đính chính) — màn Tư vấn dùng
        thuốc. Chuyển từ trang đọc thẳng Supabase (24/09/2026)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text, r.source_ref, r.drug_name_raw,
                       r.dosage_instructions, r.quantity, r.quantity_note,
                       r.caution, r.created_at, p.full_name, p.phone_primary
                  FROM public.prescription r
                  LEFT JOIN public.patient p
                    ON p.clinic_patient_id = r.clinic_patient_id
                   AND p.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid
                   AND r.closed_at IS NULL AND r.removed_at IS NULL
                   AND coalesce(public.co_so_cua_luot(r.clinic_id, r.visit_id),
                                $2::uuid)
                       IS NOT DISTINCT FROM
                       coalesce($2::uuid,
                                public.co_so_cua_luot(r.clinic_id, r.visit_id))
                 ORDER BY r.created_at DESC
                 LIMIT 100
                """,
                identity.clinic_id,
                identity.location_id or None,
            )
        canh_bao_neu_day(
            "nha_thuoc.cho_tu_van", len(rows), 100, clinic_id=identity.clinic_id
        )
        return [dict(r) for r in rows]

    async def ton_kho(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Tồn theo lô, kèm hạn dùng. Lô hết sạch vẫn hiện — nó là lịch sử.

        Chỉ kho của cơ sở đang làm (`identity.location_id`) — kho riêng từng
        cơ sở (08/10/2026).
        """
        async with self._pool.acquire() as conn:
            from clinicai.services.lo_thuoc_service import so_ngay_canh_bao

            nguong_han = await so_ngay_canh_bao(conn, identity.clinic_id)
            rows = await conn.fetch(
                """
                SELECT b.id::text,
                       b.drug_catalog_id::text,
                       c.name_base,
                       c.variant,
                       c.group_label,
                       b.batch_code,
                       b.ma_tem,
                       b.noi_chua,
                       b.expiry_date,
                       b.quantity_on_hand,
                       coalesce((SELECT sum(CASE
                              WHEN lower(trim(coalesce(p.unit, ''))) =
                                   lower(trim(coalesce(b.unit, '')))
                              THEN g.so_luong
                              -- Dòng bán đơn vị khác đơn vị lô: đổi qua hệ số;
                              -- không đổi được thì không cộng (NULL).
                              ELSE round(g.so_luong
                                   * public.he_so_don_vi(g.clinic_id,
                                                         g.drug_catalog_id, p.unit)
                                   / public.he_so_don_vi(g.clinic_id,
                                                         g.drug_catalog_id, b.unit), 3)
                              END)
                         FROM public.thuoc_giao_chua_gan_lo g
                         JOIN public.prescription p ON p.id = g.prescription_id
                          AND p.clinic_id = g.clinic_id
                        /* rx:gom-ca-lich-su: đơn đã giao vẫn phải đối chiếu
                           tồn kho dù bác sĩ đã đính chính dòng đơn */
                        WHERE g.clinic_id = b.clinic_id
                          AND g.drug_catalog_id = b.drug_catalog_id
                          AND g.drug_batch_id IS NULL AND g.huy_luc IS NULL
                          AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id),
                                       $4::uuid) = b.location_id), 0)
                         AS da_giao_chua_doi_chieu,
                       coalesce((SELECT sum(x.quantity_on_hand)
                         FROM public.drug_batch x
                        WHERE x.clinic_id = b.clinic_id
                          AND x.location_id = b.location_id
                          AND x.drug_catalog_id = b.drug_catalog_id
                          AND x.noi_chua = 'QUAY'
                          AND lower(trim(coalesce(x.unit, ''))) =
                              lower(trim(coalesce(b.unit, '')))), 0)
                         AS ton_quay_thuoc,
                       coalesce((SELECT sum(
                           public.drug_batch_kha_dung(x.clinic_id, x.id))
                         FROM public.drug_batch x
                        WHERE x.clinic_id = b.clinic_id
                          AND x.location_id = b.location_id
                          AND x.drug_catalog_id = b.drug_catalog_id
                          AND lower(trim(coalesce(x.unit, ''))) =
                              lower(trim(coalesce(b.unit, '')))
                          AND (x.expiry_date IS NULL OR x.expiry_date >= $2::date)), 0)
                         AS kha_dung_truoc_doi_chieu,
                       b.unit,
                       b.cost_price,
                       b.received_at,
                       (SELECT t.id::text FROM public.inventory_txn t
                         WHERE t.drug_batch_id = b.id AND t.clinic_id = b.clinic_id
                           AND t.txn_type = 'DISCARD'
                           AND t.ref_type = 'expired_batch'
                           AND NOT EXISTS (
                               SELECT 1 FROM public.inventory_txn r
                                WHERE r.ref_type = 'discard_undo'
                                  AND r.ref_id = t.id AND r.clinic_id = t.clinic_id)
                         ORDER BY t.performed_at DESC, t.id DESC LIMIT 1
                       ) AS huy_lo_txn_id,
                       coalesce(b.expiry_date < $2::date, false) AS het_han,
                       CASE WHEN b.expiry_date IS NULL THEN 'chua_co_han'
                            WHEN b.expiry_date < $2::date THEN 'het_han'
                            WHEN b.expiry_date <= $2::date + $3::int THEN 'sap_het_han'
                            ELSE 'con_han' END AS trang_thai_han
                  FROM public.drug_batch b
                  LEFT JOIN public.drug_catalog c
                    ON c.id = b.drug_catalog_id
                 WHERE b.clinic_id = $1::uuid AND b.location_id = $4::uuid
                 ORDER BY b.expiry_date NULLS LAST, c.name_base
                """,
                identity.clinic_id,
                hom_nay_vn(),
                nguong_han,
                identity.location_id,
            )
        # Cảnh báo hạn chỉ cho lô CÒN thuốc trên kệ — lô đã hết sạch là lịch sử.
        # Đọc bằng .get: dòng thiếu cột (bản ghi cũ / stub) = không cảnh báo, không 500.
        ds = [dict(r) for r in rows]
        return [
            {
                **d,
                # Pending chưa thuộc lô nào: số tổng theo thuốc/đơn vị/cơ sở,
                # không được cộng lặp theo từng lô ở giao diện.
                "ton_kha_dung_thuoc": Decimal(
                    str(d.get("kha_dung_truoc_doi_chieu") or 0)
                )
                - Decimal(str(d.get("da_giao_chua_doi_chieu") or 0)),
                # Số thật trên kệ quầy khi còn phần đã giao chờ gán lô: sổ chưa trừ
                # phần ấy nên đếm kệ sẽ thấp hơn sổ đúng bằng phần chờ gán.
                "so_tren_ke_quay": max(
                    Decimal(str(d.get("ton_quay_thuoc") or 0))
                    - Decimal(str(d.get("da_giao_chua_doi_chieu") or 0)),
                    Decimal(0),
                ),
                "canh_bao_han": d.get("trang_thai_han") in ("het_han", "sap_het_han")
                and (d.get("quantity_on_hand") or 0) > 0,
            }
            for d in ds
        ]

    async def danh_muc(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Danh mục thuốc kho (cả thuốc đang tắt) kèm tổng tồn — màn Kho thuốc.

        Tuyền 25/09/2026: tên, giá, hướng dẫn nạp sẵn theo KiotViet; lô, hạn,
        nhập/xuất nhà thuốc tự làm ở đây. Danh mục (và giá) CHUNG cả phòng
        khám; tồn / lô chỉ của kho cơ sở đang làm (08/10/2026).
        """
        async with self._pool.acquire() as conn:
            from clinicai.services.lo_thuoc_service import so_ngay_canh_bao

            nguong_han = await so_ngay_canh_bao(conn, identity.clinic_id)
            rows = await conn.fetch(
                """
                SELECT c.id::text, c.name_raw AS ten, c.ma_hang, c.unit_price AS gia,
                       c.don_vi_ban, c.duong_dung, c.cach_dung, c.luu_y, c.biet_duoc,
                       c.is_active AS dang_dung, c.needs_review AS can_soat,
                       c.ton_toi_thieu,
                       coalesce(sum(b.quantity_on_hand), 0) AS ton,
                       count(b.id) FILTER (WHERE b.quantity_on_hand > 0) AS so_lo,
                       -- Sắp hết hàng: thuốc đang dùng có ngưỡng và MỌI đơn
                       -- vị lô đều ≤ ngưỡng. Không cộng hộp với viên (30/09):
                       -- 8 hộp + 5 viên cộng thành 13 > 10 thì lọt cảnh báo;
                       -- còn 20 hộp thì chưa hết dù viên lẻ đã cạn.
                       (c.is_active AND c.ton_toi_thieu IS NOT NULL
                        AND coalesce((
                            SELECT max(dv.ton)
                              FROM (SELECT sum(x.quantity_on_hand) AS ton
                                      FROM public.drug_batch x
                                     WHERE x.clinic_id = c.clinic_id
                                       AND x.location_id = $4::uuid
                                       AND x.drug_catalog_id = c.id
                                     GROUP BY lower(btrim(x.unit))) dv
                        ), 0) <= c.ton_toi_thieu)
                           AS sap_het_hang,
                       count(b.id) FILTER (
                           WHERE b.quantity_on_hand > 0
                             AND b.expiry_date <= $2::date + $3::int
                       ) AS so_lo_can_han,
                       -- Đơn vị các lô đang có (29/09): phiếu nhập điền sẵn
                       -- đơn vị lô, không lấy đơn vị bán — 20 hộp + 50 viên
                       -- không cộng được. Lô còn tồn trước, không có thì mọi lô.
                       coalesce(
                           array_agg(DISTINCT b.unit)
                               FILTER (WHERE b.quantity_on_hand > 0),
                           array_agg(DISTINCT b.unit) FILTER (WHERE b.id IS NOT NULL),
                           '{}'::text[]
                       ) AS don_vi_lo,
                       coalesce((
                           SELECT jsonb_agg(jsonb_build_object('don_vi', dv.don_vi,
                                                               'ton', dv.ton)
                                            ORDER BY dv.don_vi)
                             FROM (SELECT min(x.unit) AS don_vi,
                                          sum(x.quantity_on_hand) AS ton
                                     FROM public.drug_batch x
                                    WHERE x.clinic_id = c.clinic_id
                                      AND x.location_id = $4::uuid
                                      AND x.drug_catalog_id = c.id
                                    GROUP BY lower(btrim(x.unit))
                                    -- Đơn vị đã hết sạch không hiện (30/09):
                                    -- "20 hộp · 0 viên" → "20 hộp".
                                   HAVING sum(x.quantity_on_hand) <> 0) dv
                       ), '[]'::jsonb)::text AS ton_theo_don_vi
                  FROM public.drug_catalog c
                  LEFT JOIN public.drug_batch b
                    ON b.drug_catalog_id = c.id AND b.clinic_id = c.clinic_id
                   AND b.location_id = $4::uuid
                 WHERE c.clinic_id = $1::uuid
                 GROUP BY c.id
                 ORDER BY c.is_active DESC, lower(c.name_raw)
                """,
                identity.clinic_id,
                hom_nay_vn(),
                nguong_han,
                identity.location_id,
            )
            bang = await doc_bang(conn, identity.clinic_id, [r["id"] for r in rows])
        return [_dong_danh_muc(dict(r), bang.get(r["id"], BangDonVi())) for r in rows]

    async def luu_thuoc(
        self,
        *,
        identity: StaffIdentity,
        drug_catalog_id: str | None,
        ten: str,
        gia: Any = None,
        ma_hang: str | None = None,
        don_vi_ban: str | None = None,
        duong_dung: str | None = None,
        cach_dung: str | None = None,
        luu_y: str | None = None,
        biet_duoc: str | None = None,
        dang_dung: bool = True,
        ton_toi_thieu: Any = GIU_NGUYEN,
        cac_don_vi: Any = None,
    ) -> dict[str, Any]:
        """Thêm (không có mã) hoặc sửa MỘT thuốc trong danh mục kho.

        `cac_don_vi` (31/10/2026): đơn vị bán thêm, cùng giao dịch với thuốc; đơn
        vị không gửi thì giữ nguyên (xem `don_vi_thuoc.luu_cac_don_vi`).

        `ton_toi_thieu` (29/09/2026): ngưỡng cảnh báo sắp hết hàng; rỗng = không
        canh; không gửi (`GIU_NGUYEN`) = giữ số cũ.

        Dược sĩ lưu = đã soát: bỏ cờ `needs_review`. Giá ở đây là giá bán duy
        nhất (khép HOLD J5, migration 20260925000014) — quầy thu đọc thẳng.
        """
        ten_sach = " ".join((ten or "").split())
        if not ten_sach:
            raise ValidationError("Nhập tên thuốc.")
        gia_so = None if gia in (None, "") else _so(gia, ten="Giá bán", cho_0=True)
        doi_nguong = ton_toi_thieu is not GIU_NGUYEN
        nguong = (
            None
            if not doi_nguong or ton_toi_thieu in (None, "")
            else _so(ton_toi_thieu, ten="Tồn tối thiểu", cho_0=True)
        )
        don_vi_them = doc_don_vi_gui_len(cac_don_vi, goc=don_vi_ban, gia_goc=gia_so)

        def _chu(v: str | None) -> str | None:
            v = (v or "").strip()
            return v or None

        async with self._pool.acquire() as conn, conn.transaction():
            trung = await conn.fetchval(
                "SELECT id::text FROM public.drug_catalog"
                " WHERE clinic_id = $1::uuid AND lower(name_raw) = lower($2)"
                "   AND ($3::uuid IS NULL OR id <> $3::uuid)",
                identity.clinic_id,
                ten_sach,
                drug_catalog_id,
            )
            if trung is not None:
                raise ConflictError(f"Đã có thuốc tên “{ten_sach}” trong danh mục.")
            if drug_catalog_id is not None:
                await kiem_doi_don_vi_goc(
                    conn, identity, thuoc=drug_catalog_id, goc_moi=don_vi_ban
                )
            gia_tri = (
                identity.clinic_id,
                ten_sach,
                gia_so,
                _chu(ma_hang),
                _chu(don_vi_ban),
                _chu(duong_dung),
                _chu(cach_dung),
                _chu(luu_y),
                _chu(biet_duoc),
                bool(dang_dung),
            )
            if drug_catalog_id is None:
                ma = await conn.fetchval(
                    """
                    INSERT INTO public.drug_catalog
                        (clinic_id, name_raw, name_base, unit_price, ma_hang,
                         don_vi_ban, duong_dung, cach_dung, luu_y, biet_duoc,
                         is_active, needs_review, ton_toi_thieu)
                    VALUES ($1::uuid, $2, $2, $3, $4, $5, $6, $7, $8, $9, $10, false,
                            $11)
                    RETURNING id::text
                    """,
                    *gia_tri,
                    nguong,
                )
            else:
                ma = await conn.fetchval(
                    """
                    UPDATE public.drug_catalog
                       SET name_raw = $2, name_base = $2, unit_price = $3,
                           ma_hang = $4, don_vi_ban = $5, duong_dung = $6,
                           cach_dung = $7, luu_y = $8, biet_duoc = $9,
                           is_active = $10, needs_review = false,
                           ton_toi_thieu = CASE WHEN $12::bool THEN $13
                                                ELSE ton_toi_thieu END
                     WHERE clinic_id = $1::uuid AND id = $11::uuid
                    RETURNING id::text
                    """,
                    *gia_tri,
                    drug_catalog_id,
                    doi_nguong,
                    nguong,
                )
                if ma is None:
                    raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")
            doi = await luu_cac_don_vi(conn, identity, thuoc=ma, ds=don_vi_them)
            if doi:
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.sale_units_changed",
                    aggregate_type="drug_catalog",
                    aggregate_id=ma,
                    payload={"doi": doi},
                )
        return {"ok": True, "id": ma}

    # ── Ghi ────────────────────────────────────────────────────────────────

    async def nhap_lo(
        self,
        *,
        identity: StaffIdentity,
        drug_catalog_id: str,
        so_luong: Any,
        batch_code: str,
        # `date | None` chứ không phải `date`: thân hàm CÓ kiểm None và trả về
        # một câu tiếng Việt. Khai là `date` thì nhánh ấy thành mã chết dưới
        # mắt mypy, và người gọi tiếp theo — một script nhập kho hàng loạt
        # chẳng hạn — vẫn truyền None vào được mà không ai chặn.
        expiry_date: date | None,
        unit: str,
        cost_price: Any = None,
        ly_do: str | None = None,
        idempotency_key: str | None = None,
        he_so: Any = None,
        xac_nhan_he_so: bool = False,
    ) -> dict[str, Any]:
        """Nhập lô theo đơn vị bán, chống ghi lặp khi client gửi lại yêu cầu.

        Nhập khác đơn vị bán thì đổi về đơn vị bán ngay ở đây
        (`quy_doi_dong_nhap`): kho chỉ giữ một đơn vị. Khoá idempotency được tra
        trước bước đổi vì bước đổi có thể lưu hệ số quy đổi đã xác nhận.

        Số lô và đơn vị bắt buộc; hạn dùng được bổ sung sau. Tồn chỉ đổi qua
        dòng sổ kho để trigger giữ số dư khớp với lịch sử.
        """
        gia: Decimal | None = None
        if cost_price is not None:
            try:
                gia = Decimal(str(cost_price))
            except Exception as exc:  # noqa: BLE001 — mọi kiểu rác đều về một câu
                raise ValidationError("Giá nhập phải là một con số hữu hạn.") from exc
            if not gia.is_finite() or gia < 0:
                raise ValidationError("Giá nhập phải là một con số hữu hạn không âm.")
            if gia > SO_TOI_DA:
                toi_da = f"{SO_TOI_DA:,}".replace(",", ".")
                raise ValidationError(
                    f"Giá nhập quá lớn (tối đa {toi_da}) — "
                    "kiểm tra lại có gõ thừa số 0 không."
                )

        luong, ma_lo, don_vi, han = kiem_dong_nhap(
            so_luong=so_luong, batch_code=batch_code, expiry_date=expiry_date, unit=unit
        )
        dau_van_tay = _dau_van_tay(
            {
                "drug_catalog_id": str(drug_catalog_id),
                "location_id": identity.location_id,
                "batch_code": ma_lo,
                "expiry_date": han.isoformat() if han else None,
                # Dấu vân tay dùng dữ liệu GỐC trước khi đổi số lượng/giá về
                # đơn vị bán; đổi hệ số cùng key phải bị nhận là payload khác.
                "unit": _don_vi(don_vi),
                "quantity": _so_chuan(luong),
                "cost_price": _so_chuan(gia) if gia is not None else None,
                "reason": (ly_do or "").strip() or None,
                "he_so": None if he_so is None else str(he_so).strip(),
                "xac_nhan_he_so": xac_nhan_he_so,
            }
        )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                replay = await self._tim_yeu_cau_gui_lai(
                    conn,
                    identity=identity,
                    operation="receive",
                    idempotency_key=idempotency_key,
                    payload_sha256=dau_van_tay,
                )
                if replay is not None:
                    return replay

                # Chạy sau khi tra replay: quy_doi_dong_nhap có thể ghi hệ số đã
                # nhớ, nên request gửi lại không được lặp lại hiệu ứng ấy.
                qd = await quy_doi_dong_nhap(
                    conn,
                    identity=identity,
                    drug_catalog_id=drug_catalog_id,
                    so_luong=luong,
                    unit=don_vi,
                    cost_price=gia,
                    he_so=he_so,
                    xac_nhan_he_so=xac_nhan_he_so,
                )
                lo_id, txn_id = await nhap_vao_lo(
                    conn,
                    identity=identity,
                    drug_catalog_id=drug_catalog_id,
                    so_luong=qd.so_luong,
                    batch_code=ma_lo,
                    expiry_date=han,
                    unit=qd.don_vi,
                    cost_price=qd.cost_price,
                    ly_do=" · ".join(x for x in (ly_do, qd.ghi_chu) if x) or None,
                    ref_type="manual",
                    ref_id=None,
                )
                ton = await self._ton_cua_lo(conn, identity, lo_id)
                ket_qua: dict[str, Any] = {
                    "ok": True,
                    "drug_batch_id": str(lo_id),
                    "quantity_on_hand": ton,
                }
                if qd.goc is not None:
                    ket_qua["quy_doi"] = {
                        "so_luong": str(qd.so_luong),
                        "don_vi": qd.don_vi,
                        "ghi_chu": qd.ghi_chu,
                    }
                await self._luu_yeu_cau_gui_lai(
                    conn,
                    identity=identity,
                    operation="receive",
                    idempotency_key=idempotency_key,
                    payload_sha256=dau_van_tay,
                    inventory_txn_id=txn_id,
                    drug_batch_id=str(lo_id),
                    response=ket_qua,
                )

        logger.info(
            "pharmacy_batch_received",
            batch_id=str(lo_id),
            quantity=str(qd.so_luong),
            by_staff_id=identity.staff_id,
        )
        return ket_qua

    async def cap_phat(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_batch_id: str | None,
        so_luong: Any,
        don_vi_giao: str | None = None,
    ) -> dict[str, Any]:
        """GIAO thuốc cho một dòng đơn (bàn giao vật lý). Giao một phần là bình thường.

        `so_luong` tính theo đơn vị đã bán của dòng; `don_vi_giao` (31/10/2026) cho
        gõ theo đơn vị khác: khách mua 1 hộp, giao trước 15 gói.

        `drug_batch_id` rỗng = GIAO KHÔNG CẦN LÔ (Tuyền 28/09/2026: "chưa cần quan
        tâm lô nào … lô nhập và gán sau"): chỉ cho lần thu không gắn lô; ghi sổ
        `thuoc_giao_chua_gan_lo`, kho trừ khi gán lô sau (`gan_lo_da_giao`).

        Contract tiền–thuốc CP3: thuốc đã BÁN lúc thu tiền thành công. Giao chỉ
        là thuốc thật rời quầy — ghi DISPENSE (tồn vật lý giảm) gắn đúng phân lô
        và lần thu, nên lượng khả dụng không giảm lần hai.

          * Chưa thu tiền thuốc → không giao.
          * Lần thu cũ (`payment_cycle.legacy`, trước CP3, không có phân lô) →
            giữ nguyên luồng cũ `_cap_phat_cu`.
          * Lần thu mới ĐÃ gắn lô → chỉ giao từ đúng lô đã phân, không vượt phần
            chưa giao.
          * Lần thu mới KHÔNG gắn lô (thu không chờ kho) → giao thẳng như lần
            thu cũ.

        Một thao tác, hai sổ, MỘT GIAO DỊCH: kho và số đã cấp của đơn.
        """
        luong = _so(so_luong, ten="Số lượng cấp")
        tu_chon_lo = False

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # visit → dòng đơn (cùng thứ tự với lần thu / huỷ phiếu).
                don = await self._khoa_theo_luot(conn, identity, prescription_id)
                if don["closed_at"] is not None:
                    raise ConflictError(
                        "Dòng thuốc này đã chốt — không cấp thêm được nữa."
                    )
                luong = await _so_giao_theo_don_vi_ban(
                    conn, identity, don, prescription_id, luong, don_vi_giao
                )
                lan = await conn.fetchrow(
                    """
                    SELECT payment_cycle_id::text, legacy FROM public.payment_cycle
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND kind = 'thuoc' AND status = 'PAID'
                    """,
                    identity.clinic_id,
                    don["visit_id"],
                )
                if lan is None:
                    raise ConflictError(
                        "Tiền thuốc của lượt này chưa thu — thu tiền thuốc trước "
                        "rồi mới giao thuốc."
                    )
                # Lần thu KHÔNG gắn lô nào (thu không chờ kho — công tắc
                # CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY tắt, Tuyền chốt
                # 20/09/2026) đi đường giao thẳng từ lô như lần thu cũ. Trước
                # 24/09 nó rơi vào nhánh "giao đúng lô đã bán" và KHÔNG giao
                # được gì (bộ mô phỏng 20 khách bắt được). Quyết theo DỮ LIỆU,
                # không đọc công tắc: lần thu nào đã bán lô thì vẫn phải giao
                # đúng lô ấy, dù công tắc sau đó đổi.
                giao_thang = bool(lan["legacy"]) or not await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM public.prescription_allocation"
                    " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid"
                    " AND released_at IS NULL)",
                    identity.clinic_id,
                    lan["payment_cycle_id"],
                )
                # Giao không lô: xét THEO DÒNG — dòng này không có lô nào đã bán
                # trong lần thu (cùng luật nút `giao_khong_lo` ở ban_thuoc_service).
                if drug_batch_id is None and await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM public.prescription_allocation"
                    " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid"
                    " AND prescription_id = $3::uuid AND released_at IS NULL)",
                    identity.clinic_id,
                    lan["payment_cycle_id"],
                    prescription_id,
                ):
                    raise ValidationError(
                        "Dòng này đã bán theo lô — giao từ đúng lô đã bán."
                    )
                lo_da_tru: list[dict[str, Any]] = []
                chua_tru = Decimal(0)
                can_lam: str | None = None
                chu_chua_tru: str | None = None
                la_vat_tu = bool(
                    await thuoc_la_vat_tu(
                        conn, identity.clinic_id, [don.get("drug_catalog_id")]
                    )
                )
                if la_vat_tu and drug_batch_id is not None:
                    raise ValidationError(
                        "Hàng này theo dõi ở Kho vật tư — bấm Giao, không chọn lô."
                    )
                if la_vat_tu:
                    moi = await self._giao_vat_tu(
                        conn,
                        identity=identity,
                        don=don,
                        prescription_id=prescription_id,
                        luong=luong,
                    )
                elif drug_batch_id is None:
                    tu_chon_lo = True
                    moi, lo_da_tru, chua_tru = await self._giao_tu_chon_lo(
                        conn,
                        identity=identity,
                        don=don,
                        prescription_id=prescription_id,
                        luong=luong,
                    )
                    if chua_tru > 0:
                        can_lam = await _viec_de_tru_duoc(
                            conn, identity, don, prescription_id
                        )
                        doi = await quy_doi_cua_dong(
                            conn,
                            identity.clinic_id,
                            thuoc=don.get("drug_catalog_id"),
                            don_vi=don.get("unit"),
                            prescription_id=prescription_id,
                        )
                        chu_chua_tru = so_de_doc(
                            chua_tru, doi.he_so_dong, doi.bang.goc, don.get("unit")
                        )
                elif giao_thang:
                    moi = await self._cap_phat_cu(
                        conn,
                        identity=identity,
                        don=don,
                        prescription_id=prescription_id,
                        drug_batch_id=drug_batch_id,
                        luong=luong,
                    )
                else:
                    moi = await self._giao_theo_phan_lo(
                        conn,
                        identity=identity,
                        prescription_id=prescription_id,
                        drug_batch_id=drug_batch_id,
                        cycle_id=lan["payment_cycle_id"],
                        luong=luong,
                    )
                # Dòng thời gian: kê ↔ khách mua ↔ đã giao (hai bản đơn). Số kê
                # và số mua đọc từ dòng đã khoá ở trên — giao không đổi hai số ấy.
                await emit_event(
                    conn,
                    ten="medicine.dispensed",
                    clinic_id=identity.clinic_id,
                    aggregate_id=prescription_id,
                    payload=ThuocDaGiao(
                        visit_id=str(don["visit_id"]),
                        prescription_id=prescription_id,
                        so_ke=_so_chu(don.get("quantity_num")),
                        so_mua=_so_chu(don.get("purchased_qty")),
                        so_da_giao=str(moi["dispensed_qty"]),
                    ),
                    boi=nguoi(identity),
                    correlation_id=str(don["visit_id"]),
                )

        logger.info(
            "pharmacy_dispensed",
            prescription_id=prescription_id,
            quantity=str(luong),
            by_staff_id=identity.staff_id,
        )
        ket_qua: dict[str, Any] = {
            "ok": True,
            "dispensed_qty": moi["dispensed_qty"],
            "dispense_status": moi["dispense_status"],
        }
        if la_vat_tu:
            ket_qua["tom_tat"] = GIAO_VAT_TU_XONG
        if tu_chon_lo:
            # Giao không chỉ định lô: máy tự chọn — màn đọc các khoá này để nói
            # lô nào đã trừ và phần nào còn chờ gán lô (không tự suy ở TSX).
            ket_qua["lo_da_tru"] = lo_da_tru
            ket_qua["chua_tru_kho"] = chua_tru
            ket_qua["tom_tat"] = _tom_tat_giao(
                lo_da_tru, chua_tru, don.get("unit"), can_lam, chu_chua_tru
            )
        return ket_qua

    async def _giao_vat_tu(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        don: asyncpg.Record,
        prescription_id: str,
        luong: Decimal,
    ) -> asyncpg.Record:
        """Giao hàng trùng mã vật tư (đầu dò Bio bán ở quầy thuốc, 31/10/2026): chỉ
        tăng số đã giao. Không lô thuốc, không vào hàng chờ gán lô — tồn đã trừ ở
        Kho vật tư lúc thu tiền (`vat_tu_ban_service`)."""
        _kiem_khong_giao_qua_so_mua(don, luong)
        moi = await conn.fetchrow(
            """
            UPDATE public.prescription
               SET dispensed_qty = dispensed_qty + $3,
                   dispensed_at = now(),
                   dispensed_by_staff_id = $4::uuid,
                   updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            RETURNING dispensed_qty, dispense_status
            """,
            prescription_id,
            identity.clinic_id,
            luong,
            identity.staff_id,
        )
        await _log(
            conn,
            identity=identity,
            event_type="pharmacy.dispensed",
            aggregate_type="prescription",
            aggregate_id=prescription_id,
            payload={
                "drug_batch_id": None,
                "vat_tu": True,
                "quantity": str(luong),
                "dispensed_qty": str(moi["dispensed_qty"]),
                "dispense_status": moi["dispense_status"],
            },
        )
        return moi

    async def _giao_theo_phan_lo(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_batch_id: str,
        cycle_id: str,
        luong: Decimal,
    ) -> asyncpg.Record:
        pl = await conn.fetchrow(
            """
            SELECT id::text, quantity, handed_over_qty
              FROM public.prescription_allocation
             WHERE clinic_id = $1::uuid AND prescription_id = $2::uuid
               AND drug_batch_id = $3::uuid AND payment_cycle_id = $4::uuid
               AND released_at IS NULL
             FOR UPDATE
            """,
            identity.clinic_id,
            prescription_id,
            drug_batch_id,
            cycle_id,
        )
        if pl is None:
            raise ValidationError(
                "Lô này không nằm trong các lô đã bán cho dòng thuốc này — "
                "giao đúng lô đã chọn lúc thu tiền."
            )
        con = Decimal(str(pl["quantity"])) - Decimal(str(pl["handed_over_qty"]))
        if luong > con:
            raise ValidationError(
                f"Lô này đã bán {so(Decimal(str(pl['quantity'])))}, còn {so(con)} "
                "chưa giao — "
                "không giao quá số đã bán."
            )
        await khoa_lo(conn, clinic_id=identity.clinic_id, lo_ids=[drug_batch_id])
        lo = await conn.fetchrow(
            "SELECT quantity_on_hand, expiry_date, noi_chua FROM public.drug_batch"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            drug_batch_id,
            identity.clinic_id,
        )
        if lo["noi_chua"] != "QUAY":
            raise ConflictError(NOI_KHO_DANG_O)
        if lo["expiry_date"] is not None and lo["expiry_date"] < now_vn().date():
            raise ConflictError(
                f"Lô này hết hạn ngày {lo['expiry_date']:%d/%m/%Y} — không giao "
                "được. Đổi lô hoặc hoàn phần chưa giao."
            )
        if Decimal(str(lo["quantity_on_hand"] or 0)) < luong:
            raise ConflictError(
                f"Trên kệ lô này chỉ còn "
                f"{so(Decimal(str(lo['quantity_on_hand'] or 0)))} — không khớp số "
                "đã bán. Cần kiểm kê trước khi giao."
            )
        da_ban = await conn.fetchval(
            """
            SELECT EXISTS (SELECT 1 FROM public.inventory_txn s
                            WHERE s.clinic_id = $1::uuid AND s.txn_type = 'SALE'
                              AND s.allocation_id = $2::uuid
                              AND s.payment_cycle_id = $3::uuid
                              AND NOT EXISTS (
                                  SELECT 1 FROM public.inventory_txn r
                                   WHERE r.txn_type = 'SALE_REVERSAL'
                                     AND r.reverses_txn_id = s.id))
            """,
            identity.clinic_id,
            pl["id"],
            cycle_id,
        )
        if not da_ban:
            da_huy = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM public.inventory_txn"
                " WHERE clinic_id = $1::uuid AND txn_type = 'SALE_REVERSAL'"
                " AND allocation_id = $2::uuid)",
                identity.clinic_id,
                pl["id"],
            )
            raise ConflictError(
                "Phần chưa giao của lô này đã huỷ — không giao thêm."
                if da_huy
                else "Lần thu này chưa ghi bán được cho lô này (đang cần đối soát) "
                "— chưa giao được."
            )
        await self._ghi_so(
            conn,
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=CAP,
            quantity=-luong,
            reason=None,
            ref_type="prescription",
            ref_id=prescription_id,
            payment_cycle_id=cycle_id,
            allocation_id=pl["id"],
        )
        await conn.execute(
            "UPDATE public.prescription_allocation"
            " SET handed_over_qty = handed_over_qty + $3"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            pl["id"],
            identity.clinic_id,
            luong,
        )
        moi = await conn.fetchrow(
            """
            UPDATE public.prescription
               SET dispensed_qty = dispensed_qty + $3,
                   dispensed_at = now(),
                   dispensed_by_staff_id = $4::uuid,
                   updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            RETURNING dispensed_qty, dispense_status
            """,
            prescription_id,
            identity.clinic_id,
            luong,
            identity.staff_id,
        )
        await _log(
            conn,
            identity=identity,
            event_type="pharmacy.dispensed",
            aggregate_type="prescription",
            aggregate_id=prescription_id,
            payload={
                "drug_batch_id": drug_batch_id,
                "allocation_id": pl["id"],
                "payment_cycle_id": cycle_id,
                "quantity": str(luong),
                "dispensed_qty": str(moi["dispensed_qty"]),
                "dispense_status": moi["dispense_status"],
            },
        )
        return moi

    async def _giao_tu_chon_lo(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        don: asyncpg.Record,
        prescription_id: str,
        luong: Decimal,
    ) -> tuple[asyncpg.Record, list[dict[str, Any]], Decimal]:
        """Giao không chỉ định lô: máy TỰ CHỌN lô hết hạn sớm nhất và trừ kho ngay
        (Tuyền 27/10/2026 — "trừ kho lúc giao, máy tự gợi ý lô, không bắt gõ tay").

        Trả (dòng đơn sau khi cập nhật, các lô đã trừ, số CHƯA trừ được).

        Lô được xét: đúng thuốc, đúng cơ sở của lượt, nằm ở QUẦY, còn tồn, còn
        hạn (lô không hạn xếp cuối), CÙNG ĐƠN VỊ với dòng đơn hoặc đổi được qua
        hệ số đã khai (`don_vi_thuoc.QuyDoiDong`: bán 1 hộp thì lô trừ 30 gói, lô
        đổi không chẵn thì bỏ qua). Số lượng lấy tối đa theo `drug_batch_kha_dung`
        (đã trừ phần giữ cho chuyển khoản chờ) và trừ thêm các lần giao CHƯA gán
        lô của cùng thuốc, cơ sở: thuốc ấy đã rời kệ mà sổ chưa biết.

        Thiếu lô / thiếu tồn / dòng đơn chưa rõ thuốc hoặc đơn vị thì phần còn
        lại VẪN GIAO, ghi vào sổ chờ gán lô như trước (`_giao_khong_lo`) — giai
        đoạn chưa nạp tồn thật không được làm kẹt quầy.
        """
        _kiem_khong_giao_qua_so_mua(don, luong)
        thuoc = don.get("drug_catalog_id")
        don_vi = _don_vi(don.get("unit"))
        if thuoc and not don_vi:
            don_vi = _don_vi(
                await conn.fetchval(
                    "SELECT don_vi_ban FROM public.drug_catalog"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    thuoc,
                    identity.clinic_id,
                )
            )
        lo_da_tru: list[dict[str, Any]] = []
        con = luong
        if thuoc and don_vi:
            co_so = (
                await conn.fetchval(
                    "SELECT public.co_so_cua_luot($1::uuid, $2::uuid)",
                    identity.clinic_id,
                    don["visit_id"],
                )
                or identity.location_id
            )
            # Khoá TRƯỚC khi đọc tồn (theo id tăng dần, như `khoa_lo`): hai lần
            # giao cùng lúc xếp hàng ở đây thay vì cùng thấy một số tồn.
            ung_vien = await conn.fetch(
                "SELECT id::text AS id FROM public.drug_batch"
                " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid"
                " AND location_id = $3::uuid AND noi_chua = 'QUAY'"
                " AND quantity_on_hand > 0",
                identity.clinic_id,
                thuoc,
                co_so,
            )
            await khoa_lo(
                conn,
                clinic_id=identity.clinic_id,
                lo_ids=[r["id"] for r in ung_vien],
            )
            # Câu lệnh MỚI sau khoá: thấy số tồn người giao trước vừa ghi.
            lo = await conn.fetch(
                "SELECT id::text AS id, batch_code, expiry_date, unit,"
                " public.drug_batch_kha_dung(clinic_id, id) AS kha_dung"
                " FROM public.drug_batch"
                " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])"
                " AND quantity_on_hand > 0"
                " AND (expiry_date IS NULL OR expiry_date >= $3::date)"
                " ORDER BY expiry_date NULLS LAST, batch_code, id",
                identity.clinic_id,
                [r["id"] for r in ung_vien],
                now_vn().date(),
            )
            doi = await quy_doi_cua_dong(
                conn,
                identity.clinic_id,
                thuoc=thuoc,
                don_vi=don_vi,
                prescription_id=prescription_id,
            )
            # Tính theo đơn vị của DÒNG; chỉ dòng ghi sổ mới đổi ra đơn vị lô.
            lo = [
                {**b, "san": Decimal(str(b["kha_dung"] or 0)) / ty_le}
                for b in lo
                if (ty_le := doi.ty_le(b["unit"]))
            ]
            cho_gan = sum(
                (
                    doi.so_dong(Decimal(str(r["so"])), r["unit"]) or Decimal(0)
                    for r in await conn.fetch(
                        "SELECT p.unit, sum(g.so_luong) AS so"
                        "  FROM public.thuoc_giao_chua_gan_lo g"
                        "  JOIN public.prescription p ON p.id = g.prescription_id"
                        " /* rx:gom-ca-lich-su: thuốc đã rời kệ vẫn trừ khỏi số có"
                        " thể trừ dù dòng đơn sau đó bị bác sĩ đính chính */"
                        " WHERE g.clinic_id = $1::uuid"
                        "   AND g.drug_catalog_id = $2::uuid"
                        "   AND g.drug_batch_id IS NULL AND g.huy_luc IS NULL"
                        "   AND coalesce(public.co_so_cua_luot(g.clinic_id,"
                        "                p.visit_id), $3::uuid) = $3::uuid"
                        " GROUP BY p.unit",
                        identity.clinic_id,
                        thuoc,
                        co_so,
                    )
                ),
                Decimal(0),
            )
            san = sum((b["san"] for b in lo), Decimal(0))
            san = max(san - cho_gan, Decimal(0))
            for b in lo:
                if con <= 0 or san <= 0:
                    break
                lay = min(con, san, b["san"])
                tru_lo = doi.so_lo(lay, b["unit"]) if lay > 0 else None
                if not tru_lo:
                    continue
                await self._ghi_so(
                    conn,
                    identity=identity,
                    drug_batch_id=b["id"],
                    txn_type=CAP,
                    quantity=-tru_lo,
                    reason=None,
                    ref_type="prescription",
                    ref_id=prescription_id,
                )
                lo_da_tru.append(
                    {
                        "drug_batch_id": b["id"],
                        "batch_code": b["batch_code"],
                        "expiry_date": b["expiry_date"],
                        "so_luong": tru_lo,
                        "don_vi": b["unit"],
                    }
                )
                con -= lay
                san -= lay
            if lo_da_tru:
                # 5/30 hộp còn lại = 0,166667: đủ đổi lại đúng 5 gói lúc gán lô.
                con = con.quantize(SAU_SO_LE)
        tru = luong - con
        moi: asyncpg.Record | None = None
        if tru > 0:
            moi = await conn.fetchrow(
                """
                UPDATE public.prescription
                   SET dispensed_qty = dispensed_qty + $3,
                       dispensed_at = now(),
                       dispensed_by_staff_id = $4::uuid,
                       updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                RETURNING dispensed_qty, dispense_status
                """,
                prescription_id,
                identity.clinic_id,
                tru,
                identity.staff_id,
            )
            for x in lo_da_tru:
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.dispensed",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "drug_batch_id": x["drug_batch_id"],
                        "tu_chon_lo": True,
                        "quantity": str(x["so_luong"]),
                        "dispensed_qty": str(moi["dispensed_qty"]),
                        "dispense_status": moi["dispense_status"],
                    },
                )
        if con > 0:
            moi = await self._giao_khong_lo(
                conn,
                identity=identity,
                don=don,
                prescription_id=prescription_id,
                luong=con,
            )
        assert moi is not None
        return moi, lo_da_tru, con

    async def _giao_khong_lo(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        don: asyncpg.Record,
        prescription_id: str,
        luong: Decimal,
    ) -> asyncpg.Record:
        """Giao KHÔNG chọn lô (28/09/2026): tăng số đã giao + ghi sổ chờ gán lô.

        Không ghi `inventory_txn` (bắt lô NOT NULL, tồn lô ≥ 0) — kho trừ lúc
        gán lô. Không giao quá số khách mua; số kê chỉ dùng làm mức dự phòng
        cho đơn cũ chưa ghi riêng số mua.

        Từ 27/10/2026 đây chỉ còn là ĐƯỜNG DỰ PHÒNG của `_giao_tu_chon_lo`
        (kho chưa đủ lô để trừ).
        """
        _kiem_khong_giao_qua_so_mua(don, luong)
        await conn.execute(
            "INSERT INTO thuoc_giao_chua_gan_lo"
            " (clinic_id, prescription_id, drug_catalog_id, so_luong, giao_boi)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::uuid)",
            identity.clinic_id,
            prescription_id,
            don.get("drug_catalog_id"),
            luong,
            identity.staff_id,
        )
        moi = await conn.fetchrow(
            """
            UPDATE public.prescription
               SET dispensed_qty = dispensed_qty + $3,
                   dispensed_at = now(),
                   dispensed_by_staff_id = $4::uuid,
                   updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            RETURNING dispensed_qty, dispense_status
            """,
            prescription_id,
            identity.clinic_id,
            luong,
            identity.staff_id,
        )
        await _log(
            conn,
            identity=identity,
            event_type="pharmacy.dispensed",
            aggregate_type="prescription",
            aggregate_id=prescription_id,
            payload={
                "drug_batch_id": None,
                "chua_gan_lo": True,
                "quantity": str(luong),
                "dispensed_qty": str(moi["dispensed_qty"]),
                "dispense_status": moi["dispense_status"],
            },
        )
        return moi

    async def cho_gan_lo(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Thuốc ĐÃ GIAO mà chưa gán lô + lô gán được cho từng dòng (28/09/2026).

        Lô gợi ý: cùng thuốc kho, cùng đơn vị kê (nếu có), còn hạn, đủ tồn,
        thuộc kho cơ sở của LƯỢT (lượt không rõ cơ sở → cơ sở đang làm).
        Tổng chưa gán = phần tồn vật lý kho đang báo cao hơn thực tế.
        """
        async with self._pool.acquire() as conn:
            dong = await conn.fetch(
                """
                SELECT g.id::text AS id, g.so_luong, g.giao_luc,
                       g.prescription_id::text AS prescription_id,
                       g.drug_catalog_id::text AS drug_catalog_id,
                       p.drug_name_raw, p.unit, c.name_base AS ten_thuoc_kho,
                       s.full_name AS nguoi_giao, pt.full_name AS ten_khach,
                       pt.patient_code,
                       public.co_so_cua_luot(g.clinic_id, p.visit_id)::text
                           AS co_so_id
                  FROM thuoc_giao_chua_gan_lo g
                  JOIN prescription p ON p.id = g.prescription_id
                  /* rx:gom-ca-lich-su: thuốc ĐÃ giao phải gán lô dù dòng đơn
                     sau đó bị bác sĩ đính chính */
                  LEFT JOIN drug_catalog c ON c.id = g.drug_catalog_id
                  LEFT JOIN staff s ON s.id = g.giao_boi
                  LEFT JOIN visit v ON v.visit_id = p.visit_id
                  LEFT JOIN patient pt
                    ON pt.clinic_patient_id = v.clinic_patient_id
                   AND pt.clinic_id = v.clinic_id
                 WHERE g.clinic_id = $1::uuid AND g.drug_batch_id IS NULL
                   AND g.huy_luc IS NULL
                   -- Chỉ dòng của cơ sở đang đứng ($2 NULL = không lọc).
                   AND coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id),
                                $2::uuid)
                       IS NOT DISTINCT FROM
                       coalesce($2::uuid,
                                public.co_so_cua_luot(g.clinic_id, p.visit_id))
                 ORDER BY g.giao_luc
                """,
                identity.clinic_id,
                identity.location_id or None,
            )
            thuoc = sorted({r["drug_catalog_id"] for r in dong if r["drug_catalog_id"]})
            lo = await conn.fetch(
                """
                SELECT b.id::text AS id, b.drug_catalog_id::text AS drug_catalog_id,
                       b.batch_code, b.expiry_date, b.unit, b.quantity_on_hand,
                       b.location_id::text AS co_so_id, b.noi_chua,
                       public.drug_batch_kha_dung(b.clinic_id, b.id) AS co_the_gan
                  FROM drug_batch b
                 WHERE b.clinic_id = $1::uuid
                   AND b.drug_catalog_id = ANY($2::uuid[])
                   AND b.quantity_on_hand > 0 AND b.noi_chua IN ('KHO', 'QUAY')
                   AND (b.expiry_date IS NULL OR b.expiry_date >=
                        (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
                 ORDER BY b.expiry_date NULLS LAST, b.batch_code
                """,
                identity.clinic_id,
                thuoc,
            )
            bang = await doc_bang(conn, identity.clinic_id, thuoc)
            chup = await he_so_da_chup(
                conn, identity.clinic_id, [r["prescription_id"] for r in dong]
            )
        ra = []
        for r in dong:
            b_thuoc = bang.get(r["drug_catalog_id"] or "", BangDonVi())
            # Dòng không ghi đơn vị: hiểu theo đơn vị gốc đã khai (như lúc giao).
            don_vi = (r["unit"] or "").strip() or b_thuoc.goc
            dv = _don_vi(don_vi)
            co_so = r["co_so_id"] or identity.location_id
            giao = Decimal(str(r["so_luong"]))
            doi = QuyDoiDong(
                don_vi=don_vi,
                he_so_dong=chup.get(r["prescription_id"]) or b_thuoc.he_so(don_vi),
                bang=b_thuoc,
            )
            cua_thuoc = [
                b
                for b in lo
                if b["drug_catalog_id"] == r["drug_catalog_id"]
                and b["co_so_id"] == co_so
            ]
            tru_o: dict[str, Decimal | None] = {
                # Đơn cũ không ghi đơn vị: hiểu theo đơn vị lô (như trước).
                b["id"]: doi.so_lo(giao, b["unit"]) if dv else giao
                for b in cua_thuoc
            }
            ra.append(
                {
                    "id": r["id"],
                    "prescription_id": r["prescription_id"],
                    "so_luong": Decimal(str(r["so_luong"])),
                    "giao_luc": r["giao_luc"],
                    "thuoc": r["ten_thuoc_kho"] or r["drug_name_raw"],
                    "unit": r["unit"],
                    "hien": so_de_doc(giao, doi.he_so_dong, doi.bang.goc, don_vi),
                    "nguoi_giao": r["nguoi_giao"],
                    "khach": r["ten_khach"],
                    "ma_bn": r["patient_code"],
                    "lo_gan_duoc": [
                        {
                            "drug_batch_id": b["id"],
                            "batch_code": b["batch_code"],
                            "expiry_date": b["expiry_date"],
                            "noi_chua": b["noi_chua"],
                            "ton": Decimal(str(b["co_the_gan"])),
                            "unit": b["unit"],
                            # Gán thì trừ ở lô này bao nhiêu (theo đơn vị lô).
                            "so_tru": tru_o[b["id"]],
                        }
                        for b in cua_thuoc
                        if (t := tru_o[b["id"]]) is not None
                        and Decimal(str(b["co_the_gan"])) >= t
                    ],
                    # Lô của thuốc ở QUẦY nhưng tính theo đơn vị KHÁC mà chưa đổi
                    # được (lô "hộp", giao "gói", chưa có hệ số hoặc đổi không
                    # chẵn) — nói ra thay vì chỉ "chưa có lô gán được".
                    "lo_khac_don_vi": [
                        {
                            "drug_batch_id": b["id"],
                            "batch_code": b["batch_code"],
                            "unit": b["unit"],
                            "ton": Decimal(str(b["co_the_gan"])),
                        }
                        for b in cua_thuoc
                        if tru_o[b["id"]] is None
                    ],
                    "can_lam": cau_thieu_quy_doi(doi, [b["unit"] for b in cua_thuoc]),
                }
            )
        return {"dong": ra, "so_dong": len(ra)}

    async def gan_lo_da_giao(
        self, *, identity: StaffIdentity, dong_id: str, drug_batch_id: str
    ) -> dict[str, Any]:
        """Gán một lần giao KHÔNG LÔ vào một lô thật → ghi DISPENSE lúc này.

        Kiểm như một lần giao thường: cùng thuốc kho, cùng đơn vị, còn hạn, đủ
        tồn (CHECK tồn lô ≥ 0 là chốt cuối). Mỗi dòng gán đúng một lần.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            g = await conn.fetchrow(
                """
                SELECT g.id::text AS id, g.so_luong, g.prescription_id::text AS rx,
                       g.drug_catalog_id::text AS drug_catalog_id,
                       g.drug_batch_id, g.huy_luc, p.unit, p.visit_id
                  FROM thuoc_giao_chua_gan_lo g
                  JOIN prescription p ON p.id = g.prescription_id
                  /* rx:gom-ca-lich-su: gán lô cho thuốc đã giao, kể cả dòng
                     đã đính chính */
                 WHERE g.clinic_id = $1::uuid AND g.id = $2::uuid
                 FOR UPDATE OF g
                """,
                identity.clinic_id,
                dong_id,
            )
            if g is None:
                raise NotFoundError("Không tìm thấy lần giao này.")
            if g["drug_batch_id"] is not None:
                raise ConflictError("Lần giao này đã gán lô rồi — tải lại.")
            if g["huy_luc"] is not None:
                raise ConflictError("Lần giao này đã hoàn tác — không gán lô được.")
            lo = await conn.fetchrow(
                """
                SELECT id::text AS id, drug_catalog_id::text AS drug_catalog_id,
                       unit, expiry_date, quantity_on_hand, noi_chua,
                       public.drug_batch_kha_dung(clinic_id, id) AS co_the_gan,
                       public.lo_dung_co_so_luot($1::uuid, $3::uuid, id) AS dung_co_so
                  FROM drug_batch
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                 FOR UPDATE
                """,
                identity.clinic_id,
                drug_batch_id,
                g["visit_id"],
            )
            if lo is None:
                raise NotFoundError("Không tìm thấy lô thuốc này trong kho.")
            if g["drug_catalog_id"] and lo["drug_catalog_id"] != g["drug_catalog_id"]:
                raise ValidationError("Lô này không phải của thuốc đã giao.")
            if not lo["dung_co_so"]:
                raise ValidationError(LO_KHAC_CO_SO)
            # Đã giao rồi: đối chiếu trực tiếp lô ở kho hoặc quầy, không buộc
            # tạo một phiếu chuyển giả sau khi thuốc đã đến tay khách.
            luong_ban = Decimal(str(g["so_luong"]))
            doi = await quy_doi_cua_dong(
                conn,
                identity.clinic_id,
                thuoc=g["drug_catalog_id"],
                don_vi=g["unit"],
                prescription_id=g["rx"],
            )
            if not chuan(g["unit"]) and doi.bang.co_goc:
                doi = replace(doi, don_vi=doi.bang.goc, he_so_dong=Decimal(1))
            dv = _don_vi(doi.don_vi)
            quy_ra = doi.so_lo(luong_ban, lo["unit"]) if dv else luong_ban
            if quy_ra is None:
                raise ValidationError(
                    f"Thuốc giao theo đơn vị {g['unit']}, lô theo đơn vị "
                    f"{lo['unit'] or 'chưa xác định'} — "
                    + (
                        cau_thieu_quy_doi(doi, [lo["unit"]])
                        or "số giao không đổi chẵn ra đơn vị lô, chọn lô cùng đơn vị."
                    )
                )
            if lo["expiry_date"] is not None and lo["expiry_date"] < now_vn().date():
                raise ConflictError(
                    "Lô này đã hết hạn — đổi lô hoặc hoàn phần chưa giao."
                )
            luong = quy_ra
            if Decimal(str(lo["co_the_gan"] or 0)) < luong:
                raise ValidationError(
                    f"Lô này chỉ còn {so(Decimal(str(lo['co_the_gan'] or 0)))} "
                    f"được dùng — không đủ {so(luong)}."
                )
            # Cùng dòng sổ như `_ghi_so` (DISPENSE, dấu âm, trỏ về dòng đơn),
            # cần id để gắn vào sổ chờ gán lô.
            txn = await conn.fetchval(
                """
                INSERT INTO public.inventory_txn
                    (clinic_id, drug_batch_id, txn_type, quantity, reason,
                     ref_type, ref_id, performed_by_staff_id, performed_at)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, 'prescription',
                        $6::uuid, $7::uuid, now())
                RETURNING id::text
                """,
                identity.clinic_id,
                drug_batch_id,
                CAP,
                -luong,
                "Gán lô cho lần giao chưa gán lô",
                g["rx"],
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE thuoc_giao_chua_gan_lo SET drug_batch_id = $2::uuid,"
                " inventory_txn_id = $3::uuid, gan_boi = $4::uuid, gan_luc = now()"
                " WHERE id = $1::uuid",
                dong_id,
                drug_batch_id,
                txn,
                identity.staff_id,
            )
            await _log(
                conn,
                identity=identity,
                event_type="pharmacy.lot_assigned",
                aggregate_type="prescription",
                aggregate_id=g["rx"],
                payload={
                    "dong_id": dong_id,
                    "drug_batch_id": drug_batch_id,
                    "quantity": str(luong),
                },
            )
        return {"ok": True, "dong_id": dong_id, "drug_batch_id": drug_batch_id}

    async def _cap_phat_cu(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        don: asyncpg.Record,
        prescription_id: str,
        drug_batch_id: str,
        luong: Decimal,
    ) -> asyncpg.Record:
        """Giao thẳng từ lô: lần thu cũ (`legacy`, trước CP3) và lần thu KHÔNG gắn
        lô (thu không chờ kho, 24/09/2026).

        Đơn có đơn vị cấp từ lô cùng đơn vị, hoặc lô đổi được qua hệ số đã khai;
        không có hệ số thì không đoán số viên/hộp. Đơn cũ thiếu đơn vị giữ hành vi cũ:
        số lượng cấp được hiểu theo đơn vị lô. Đây là giới hạn dữ liệu cũ,
        không xác nhận rằng số kê và số tồn đã có cùng đơn vị.
        """
        da_cap = Decimal(str(don["dispensed_qty"] or 0))
        mua = don.get("purchased_qty")
        if mua is None:
            mua = don["quantity_num"]
        if mua is not None and da_cap + luong > Decimal(str(mua)):
            raise ValidationError(
                f"Khách mua {mua}, đã giao {da_cap}, còn {Decimal(str(mua)) - da_cap} "
                "— không giao quá số đã bán."
            )

        lo = await conn.fetchrow(
            """
            SELECT b.id, b.quantity_on_hand, b.unit, b.expiry_date,
                   c.name_base, b.noi_chua
              FROM public.drug_batch b
              LEFT JOIN public.drug_catalog c ON c.id = b.drug_catalog_id
             WHERE b.id = $1::uuid AND b.clinic_id = $2::uuid
             FOR UPDATE OF b
            """,
            drug_batch_id,
            identity.clinic_id,
        )
        if lo is None:
            raise NotFoundError("Không tìm thấy lô thuốc này trong kho.")
        # Trigger `inventory_txn_dung_co_so` là chốt cuối; nói tiếng Việt trước.
        if not await conn.fetchval(
            "SELECT public.lo_dung_co_so_luot($1::uuid, $2::uuid, $3::uuid)",
            identity.clinic_id,
            don["visit_id"],
            drug_batch_id,
        ):
            raise ValidationError(LO_KHAC_CO_SO)
        if lo["noi_chua"] != "QUAY":
            raise ConflictError(NOI_KHO_DANG_O)

        don_vi_ke = _don_vi(don.get("unit"))
        don_vi_lo = _don_vi(lo.get("unit"))
        tru_lo = luong
        if don_vi_ke and don_vi_ke != don_vi_lo:
            doi = await quy_doi_cua_dong(
                conn,
                identity.clinic_id,
                thuoc=don.get("drug_catalog_id"),
                don_vi=don.get("unit"),
                prescription_id=prescription_id,
            )
            quy_ra = doi.so_lo(luong, lo.get("unit"))
            if quy_ra is None:
                raise ValidationError(
                    f"Đơn kê theo đơn vị {don['unit']}, nhưng lô thuốc theo "
                    f"đơn vị {lo.get('unit') or 'chưa xác định'}. "
                    "Chọn lô cùng đơn vị hoặc xác nhận lại đơn thuốc; "
                    "không tự quy đổi hộp, vỉ, viên khi chưa có hệ số."
                )
            tru_lo = quy_ra

        ton = Decimal(str(lo["quantity_on_hand"] or 0))
        if ton < tru_lo:
            # Nói TRƯỚC ràng buộc `drug_batch_qty_non_negative`. Để
            # Postgres từ chối thì dược sĩ đọc được một câu tiếng Anh
            # về CHECK constraint và không biết còn bao nhiêu.
            raise ValidationError(
                f"Lô này chỉ còn {ton} {lo['name_base'] or ''}".rstrip()
                + f" — không đủ để cấp {tru_lo}. Chọn lô khác hoặc nhập thêm."
            )
        if lo["expiry_date"] is not None and lo["expiry_date"] < now_vn().date():
            raise ConflictError(
                f"Lô này hết hạn ngày {lo['expiry_date']:%d/%m/%Y} — "
                "không cấp được. Huỷ lô rồi chọn lô khác."
            )

        await self._ghi_so(
            conn,
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=CAP,
            # DISPENSE mang dấu ÂM (inventory_txn_qty_sign_check).
            quantity=-tru_lo,
            reason=None,
            ref_type="prescription",
            ref_id=prescription_id,
        )

        moi = await conn.fetchrow(
            """
            UPDATE public.prescription
               SET dispensed_qty = dispensed_qty + $3,
                   dispensed_at = now(),
                   dispensed_by_staff_id = $4::uuid,
                   updated_at = now()
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            RETURNING dispensed_qty, dispense_status
            """,
            prescription_id,
            identity.clinic_id,
            luong,
            identity.staff_id,
        )
        await _log(
            conn,
            identity=identity,
            event_type="pharmacy.dispensed",
            aggregate_type="prescription",
            aggregate_id=prescription_id,
            payload={
                "drug_batch_id": drug_batch_id,
                "quantity": str(luong),
                "dispensed_qty": str(moi["dispensed_qty"]),
                "dispense_status": moi["dispense_status"],
            },
        )
        return moi

    async def xac_dinh_thuoc(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_catalog_id: str,
    ) -> dict[str, Any]:
        """Gắn dòng đơn với ĐÚNG một thuốc trong danh mục kho (contract C1).

        Bác sĩ kê bằng tên gõ tay; tên không phải bằng chứng thuốc nào trong kho.
        Chưa gắn thì dòng ấy chưa vào hoá đơn và chưa cấp được — người có quyền
        nhà thuốc chọn thuốc, hệ thống không đoán theo tên.

        Không đổi được sau khi đã thu tiền thuốc (hoá đơn đã chụp theo thuốc
        này) hoặc đã cấp (lô đã chọn theo thuốc này).
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                don = await self._khoa_dong_chua_thu(conn, identity, prescription_id)
                await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
                if Decimal(str(don["dispensed_qty"] or 0)) > 0:
                    raise ConflictError(
                        "Dòng này đã cấp thuốc — không đổi thuốc kho được nữa."
                    )
                if str(don["drug_catalog_id"] or "") != str(
                    drug_catalog_id
                ) and await self._da_phan_lo(conn, identity, prescription_id):
                    raise ConflictError(
                        "Dòng này đã chọn lô — bỏ các lô đã chọn trước khi "
                        "đổi thuốc kho."
                    )
                thuoc = await conn.fetchrow(
                    """
                    SELECT id, name_base FROM public.drug_catalog
                     WHERE id = $1::uuid AND clinic_id = $2::uuid AND is_active
                    """,
                    drug_catalog_id,
                    identity.clinic_id,
                )
                if thuoc is None:
                    raise NotFoundError("Không tìm thấy thuốc này trong danh mục kho.")
                await conn.execute(
                    """
                    UPDATE public.prescription
                       SET drug_catalog_id = $3::uuid, drug_mapped_by = $4::uuid,
                           drug_mapped_at = now(), updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    prescription_id,
                    identity.clinic_id,
                    drug_catalog_id,
                    identity.staff_id,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.drug_mapped",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "drug_catalog_id": drug_catalog_id,
                        "truoc_do": (
                            str(don["drug_catalog_id"])
                            if don["drug_catalog_id"]
                            else None
                        ),
                    },
                )
        return {"ok": True, "drug_catalog_id": drug_catalog_id}

    async def khai_so_luong_mua(
        self, *, identity: StaffIdentity, prescription_id: str, so_luong: Any
    ) -> dict[str, Any]:
        """Số khách đồng ý mua (contract C2) — khác số kê và số đã giao.

        Số mua không âm và không nhỏ hơn số đã giao/đã phân lô. Vượt số kê
        chỉ nhắc để nhân viên quyết định. Không đổi sau khi đã thu tiền thuốc.
        """
        mua = _so(so_luong, ten="Số lượng mua", cho_0=True)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                don = await self._khoa_dong_chua_thu(conn, identity, prescription_id)
                await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
                ke = don["quantity_num"]
                if ke is None:
                    # Không biết số kê thì không có căn cứ cho một số mua bất kỳ
                    # (review CP1 #1; DB cũng chặn: prescription_purchased_qty_check).
                    raise ValidationError(
                        "Dòng này chưa có số lượng (bác sĩ để trống) — "
                        "thu ngân thuốc điền ở màn Thu tiền thuốc, không chờ bác sĩ."
                    )
                da_giao = Decimal(str(don["dispensed_qty"] or 0))
                if mua < da_giao:
                    raise ValidationError(
                        f"Đã giao {da_giao} — số mua không nhỏ hơn số đã giao."
                    )
                da_phan = await self._da_phan_lo(conn, identity, prescription_id)
                if mua < da_phan:
                    raise ValidationError(
                        f"Đã chọn lô cho {so(da_phan)} — bỏ bớt lô trước khi "
                        "giảm số mua."
                    )
                await conn.execute(
                    """
                    UPDATE public.prescription
                       SET purchased_qty = $3, updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    prescription_id,
                    identity.clinic_id,
                    mua,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.purchase_qty_set",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "purchased_qty": str(mua),
                        "truoc_do": (
                            str(don["purchased_qty"])
                            if don["purchased_qty"] is not None
                            else None
                        ),
                    },
                )
        return {
            "ok": True,
            "purchased_qty": mua,
            "canh_bao": (
                f"Số mua {mua} vượt số bác sĩ kê {ke}."
                if mua > Decimal(str(ke))
                else None
            ),
        }

    @staticmethod
    async def _bat_buoc_kham_xong(
        conn: asyncpg.Connection, identity: StaffIdentity, visit_id: Any
    ) -> None:
        """OFF từ 24/09/2026 — nhà thuốc KHÔNG còn đợi bác sĩ bấm Khám xong.

        Tuyền chốt: "tiền thuốc không cần khám xong"; Khám xong là mốc thời gian,
        không phải cửa khoá (luồng chuẩn bước 9–10). Đơn đổi SAU khi nhà thuốc đã
        đụng dòng thì đi đường ĐÍNH CHÍNH (dinh_chinh_don: dòng cũ giữ lịch sử,
        dòng mới thay) — không cần chặn nhà thuốc để giữ đơn đứng yên.

        Giữ hàm (không xoá, Tuyền bấm thật xong mới dọn): bật lại luật cũ =
        đổi `_CHO_KHAM_XONG` thành True.
        """
        if not _CHO_KHAM_XONG:
            return
        # Mốc chung của Nhà thuốc / Thu ngân / Payment (moc_kham_xong): trạng
        # thái của LƯỢT, không phụ thuộc lượt có lịch hẹn hay không.
        if not await conn.fetchval(
            f"""
            SELECT {kham_xong_sql("v")}
              FROM public.visit v
             WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
            """,  # noqa: S608 — chỉ chèn biểu thức cố định
            visit_id,
            identity.clinic_id,
        ):
            raise ConflictError(
                "Bác sĩ chưa bấm Khám xong lượt này — nhà thuốc chỉ xem, chưa "
                "thao tác được (đơn còn có thể thay đổi)."
            )

    @staticmethod
    async def _chot_duoc_khong(
        conn: asyncpg.Connection, identity: StaffIdentity, don: asyncpg.Record
    ) -> None:
        """Chốt "không giao thêm" không được bỏ lại thuốc đã bán chưa giao.

        Review CP4 P1 #2 — trước CP5 (hoàn / trả / đảo) chưa có đường nào xử lý
        phần đã bán mà không giao, nên:
          * lần chờ xác minh → không chốt;
          * đã thu nhưng có phân lô chưa ghi bán được (cần đối soát) → không;
          * đã thu (luồng mới) → chỉ chốt khi đã giao đủ số bán.
        Chưa có lần thu, hoặc lần thu cũ (legacy): giữ nghĩa cũ.
        """
        lan = await conn.fetchrow(
            """
            SELECT payment_cycle_id, status, legacy FROM public.payment_cycle
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND kind = 'thuoc'
               AND status IN ('PENDING_VERIFICATION', 'PAID')
            """,
            identity.clinic_id,
            don["visit_id"],
        )
        if lan is None or lan["legacy"]:
            return
        if lan["status"] == "PENDING_VERIFICATION":
            raise ConflictError(
                "Tiền thuốc đang chờ xác minh chuyển khoản — chưa chốt dòng được."
            )
        if await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM public.prescription_allocation a
                 WHERE a.clinic_id = $1::uuid AND a.payment_cycle_id = $2::uuid
                   AND a.released_at IS NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM public.inventory_txn s
                        WHERE s.txn_type = 'SALE' AND s.allocation_id = a.id
                          AND s.payment_cycle_id = a.payment_cycle_id))
            """,
            identity.clinic_id,
            lan["payment_cycle_id"],
        ):
            raise ConflictError(
                "Lượt này đang cần đối soát (đã nhận tiền, chưa ghi bán được) — "
                "không chốt dòng; báo quản lý đối soát."
            )
        ban = (
            don["purchased_qty"]
            if don["purchased_qty"] is not None
            else (don["quantity_num"])
        )
        # CP5: phần đã "huỷ phần chưa giao" (SALE_REVERSAL) không còn là bán.
        da_dao = Decimal(
            str(
                await conn.fetchval(
                    """
                    SELECT coalesce(sum(t.quantity), 0)
                      FROM public.inventory_txn t
                      JOIN public.prescription_allocation a
                        ON a.id = t.allocation_id AND a.clinic_id = t.clinic_id
                     WHERE t.clinic_id = $1::uuid AND t.txn_type = 'SALE_REVERSAL'
                       AND t.payment_cycle_id = $2::uuid
                       AND a.prescription_id = $3::uuid
                    """,
                    identity.clinic_id,
                    lan["payment_cycle_id"],
                    don["id"],
                )
            )
        )
        ban_rong = Decimal(str(ban)) - da_dao if ban is not None else None
        da_giao = Decimal(str(don["dispensed_qty"] or 0))
        if ban_rong is None or da_giao < ban_rong:
            raise ConflictError(
                f"Đã bán {so(ban_rong or Decimal(0))}, mới giao {so(da_giao)} — "
                "chưa chốt được: phần đã bán chưa giao phải hoàn tiền rồi "
                "“Huỷ phần chưa giao” trước, không đóng dòng để bỏ lại."
            )

    @staticmethod
    async def _khoa_theo_luot(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        prescription_id: str,
        *,
        cho_lich_su: bool = False,
    ) -> asyncpg.Record:
        """Khoá LƯỢT KHÁM rồi mới khoá dòng đơn — cùng thứ tự với lần thu.

        Review CP1 #3 (TOCTOU): lần thu khoá `visit` rồi tính hoá đơn; nếu lệnh
        đổi dòng thuốc chỉ khoá `prescription` thì hai giao dịch không chặn nhau
        và có thể commit hai sự thật (đơn = thuốc B, ảnh chụp hoá đơn = thuốc A).
        Thứ tự khoá DUY NHẤT cho mọi thao tác chạm hoá đơn thuốc (CP3 thêm
        phân lô và lô vào giữa — xem phan_lo_service):
            visit → prescription → prescription_allocation → drug_batch
                  → payment_cycle / payment
        Không bao giờ khoá ngược (prescription trước visit) — sẽ tắc lẫn nhau.
        """
        vid = await conn.fetchval(
            "SELECT visit_id FROM public.prescription"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid"
            " /* rx:gom-ca-lich-su: tìm lượt theo id để khoá; removed_at kiểm"
            " ngay dưới, sau khi đã khoá */",
            prescription_id,
            identity.clinic_id,
        )
        if vid is None:
            raise NotFoundError("Không tìm thấy dòng thuốc này trong đơn.")
        await conn.execute(
            "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            identity.clinic_id,
            vid,
        )
        don = await conn.fetchrow(
            """
            SELECT id, visit_id, quantity_num, purchased_qty, dispensed_qty,
                   drug_catalog_id, closed_at, drug_name_raw, unit, removed_at
              FROM public.prescription
             WHERE id = $1::uuid AND clinic_id = $2::uuid
             /* rx:gom-ca-lich-su: khoá theo id; dòng lịch sử bị từ chối ngay
                dưới trừ lệnh đối soát (cho_lich_su) */
             FOR UPDATE
            """,
            prescription_id,
            identity.clinic_id,
        )
        if don is None or don["visit_id"] != vid:
            raise ConflictError("Dòng thuốc vừa thay đổi — tải lại rồi thử lại.")
        if don["removed_at"] is not None and not cho_lich_su:
            # CP6 Q3: dòng lịch sử không nhận tác động mới (thuốc kho, số mua,
            # lô, giao, chốt). Chỉ còn đối soát: huỷ phần chưa giao, khách trả.
            raise ConflictError(
                "Dòng thuốc này đã được bác sĩ đính chính — không thao tác mới "
                "được. Chỉ còn đối soát: huỷ phần chưa giao, khách trả thuốc."
            )
        return don

    @staticmethod
    async def _da_thu_tien_thuoc(
        conn: asyncpg.Connection, identity: StaffIdentity, visit_id: Any
    ) -> bool:
        return bool(
            await conn.fetchval(
                """
                -- Đã thu, HOẶC đang chờ xác minh chuyển khoản/QR (CP2): hoá
                -- đơn thuốc đã chốt theo lần thu ấy.
                SELECT EXISTS (SELECT 1 FROM public.payment
                                WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                                  AND kind = 'thuoc' AND status = 'PAID')
                    OR EXISTS (SELECT 1 FROM public.payment_cycle
                                WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                                  AND kind = 'thuoc'
                                  AND status IN ('PENDING_VERIFICATION', 'PAID'))
                """,
                identity.clinic_id,
                visit_id,
            )
        )

    @classmethod
    async def _khoa_dong_chua_thu(
        cls, conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
    ) -> asyncpg.Record:
        """Khoá (lượt → dòng); từ chối nếu dòng đã chốt hoặc tiền thuốc đã thu."""
        don = await cls._khoa_theo_luot(conn, identity, prescription_id)
        if don["closed_at"] is not None:
            raise ConflictError("Dòng thuốc này đã chốt — không sửa được nữa.")
        if await cls._da_thu_tien_thuoc(conn, identity, don["visit_id"]):
            raise ConflictError(
                "Tiền thuốc của lượt này đã thu theo hoá đơn cũ — huỷ phiếu thu "
                "trước rồi mới sửa dòng thuốc."
            )
        return don

    async def tu_choi(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Khách không mua. Lý do BẮT BUỘC — CSKH còn gọi lại để hỏi."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError(
                "Ghi rõ vì sao khách không lấy thuốc — hết tiền, đã có thuốc ở "
                "nhà, hay đổi ý sau khi nghe tư vấn."
            )
        return await self._chot_dong(
            identity=identity,
            prescription_id=prescription_id,
            refusal_reason=ly,
            event_type="pharmacy.refused",
        )

    async def chot(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: str | None = None
    ) -> dict[str, Any]:
        """Không giao thêm dòng này nữa.

        Trước khi thu: đóng dòng (khách thôi lấy phần còn lại). Đã thu theo luồng
        mới: CHỈ khi đã giao đủ số bán — "đã thu 10, giao 5 rồi chốt" bị từ chối
        vì 5 viên đã bán sẽ không còn đường giao (chờ CP5 hoàn / trả). Lần thu
        cũ (legacy) giữ nghĩa cũ. Xem `_chot_duoc_khong`.
        """
        return await self._chot_dong(
            identity=identity,
            prescription_id=prescription_id,
            refusal_reason=None,
            ly_do=(ly_do or "").strip() or None,
            event_type="pharmacy.line_closed",
        )

    async def dieu_chinh(
        self,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        so_luong: Any,
        ly_do: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Kiểm kê lệch. `so_luong` mang dấu: âm là bớt, dương là thêm."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Điều chỉnh tồn kho thì phải ghi lý do.")
        try:
            lech = Decimal(str(so_luong))
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("Số lượng điều chỉnh phải là một con số.") from exc
        if not lech.is_finite():
            raise ValidationError("Số lượng điều chỉnh phải là một con số hữu hạn.")
        if lech == 0:
            raise ValidationError("Điều chỉnh 0 thì không phải một điều chỉnh.")
        return await self._ghi_kho_don_gian(
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=DIEU_CHINH,
            quantity=lech,
            ly_do=ly,
            event_type="pharmacy.adjusted",
            idempotency_key=idempotency_key,
        )

    async def huy(
        self,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        so_luong: Any,
        ly_do: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Huỷ thuốc hỏng / hết hạn. Ra khỏi kho nhưng không ra khỏi sổ."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Huỷ thuốc thì phải ghi lý do.")
        return await self._ghi_kho_don_gian(
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=HUY,
            quantity=-_so(so_luong, ten="Số lượng huỷ"),
            ly_do=ly,
            event_type="pharmacy.discarded",
            idempotency_key=idempotency_key,
        )

    # ── Huỷ phần chưa giao / khách trả thuốc (contract tiền–thuốc CP5) ────

    async def huy_phan_chua_giao(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Nhả PHẦN ĐÃ BÁN MÀ CHƯA GIAO của dòng đơn — lệnh KHO, không phải tiền.

        Đảo đúng `bán − đã xuất` của từng phân lô còn bán (không nhận số tuỳ ý),
        mỗi dòng bán một lần. Phải có căn cứ tài chính — lần thu đã huỷ phiếu,
        hoặc đã hoàn tiền xong cho đủ phần ấy; DB kiểm lại (trigger
        `inventory_txn_ban_hop_le`). Sau đó phân lô không giao thêm được.
        """
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Huỷ phần chưa giao thì ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await self._khoa_theo_luot(
                    conn, identity, prescription_id, cho_lich_su=True
                )
                ban = await conn.fetch(
                    """
                    SELECT s.id::text AS sale_id, s.payment_cycle_id::text,
                           a.id::text AS allocation_id, a.drug_batch_id::text,
                           -s.quantity AS da_ban,
                           coalesce((SELECT -sum(d.quantity) FROM public.inventory_txn d
                                      WHERE d.txn_type IN
                                            ('DISPENSE', 'DISPENSE_REVERSAL')
                                        AND d.allocation_id = a.id
                                        AND d.clinic_id = a.clinic_id), 0) AS da_xuat
                      FROM public.prescription_allocation a
                      JOIN public.inventory_txn s
                        ON s.allocation_id = a.id AND s.clinic_id = a.clinic_id
                       AND s.txn_type = 'SALE'
                     WHERE a.clinic_id = $1::uuid AND a.prescription_id = $2::uuid
                       AND NOT EXISTS (SELECT 1 FROM public.inventory_txn r
                                        WHERE r.txn_type = 'SALE_REVERSAL'
                                          AND r.reverses_txn_id = s.id)
                     ORDER BY a.id
                       FOR UPDATE OF a
                    """,
                    identity.clinic_id,
                    prescription_id,
                )
                dao = [
                    b
                    for b in ban
                    if Decimal(str(b["da_ban"])) > Decimal(str(b["da_xuat"]))
                ]
                if not dao:
                    raise ConflictError("Dòng này không còn phần đã bán mà chưa giao.")
                await khoa_lo(
                    conn,
                    clinic_id=identity.clinic_id,
                    lo_ids=[b["drug_batch_id"] for b in dao],
                )
                tong = Decimal(0)
                try:
                    for b in dao:
                        con = Decimal(str(b["da_ban"])) - Decimal(str(b["da_xuat"]))
                        tong += con
                        await conn.execute(
                            """
                            INSERT INTO public.inventory_txn
                                (clinic_id, drug_batch_id, txn_type, quantity, reason,
                                 ref_type, ref_id, performed_by_staff_id, performed_at,
                                 payment_cycle_id, allocation_id, reverses_txn_id)
                            VALUES ($1::uuid, $2::uuid, 'SALE_REVERSAL', $3, $4,
                                    'payment_cycle', $5::uuid, $6::uuid, now(),
                                    $5::uuid, $7::uuid, $8::uuid)
                            """,
                            identity.clinic_id,
                            b["drug_batch_id"],
                            con,
                            f"Huỷ phần chưa giao: {ly}",
                            b["payment_cycle_id"],
                            identity.staff_id,
                            b["allocation_id"],
                            b["sale_id"],
                        )
                except asyncpg.CheckViolationError as exc:
                    if "căn cứ" in str(exc):
                        raise ConflictError(
                            "Chưa có căn cứ để huỷ phần chưa giao: cần huỷ phiếu thu, "
                            "hoặc Quản lý hoàn tiền xong cho đủ phần chưa giao trước."
                        ) from exc
                    raise
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.undelivered_cancelled",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "quantity": str(tong),
                        "allocations": [b["allocation_id"] for b in dao],
                        "reason": ly,
                    },
                )
        return {"ok": True, "da_huy": so(tong)}

    async def khach_tra_thuoc(
        self,
        *,
        identity: StaffIdentity,
        dispense_txn_id: str,
        so_luong: Any,
        ly_do: str,
        ket_cuc_tien: object = None,
        hinh_thuc: object = None,
        ly_do_tien: object = None,
    ) -> dict[str, Any]:
        """Ghi nhận thuốc KHÁCH ĐÃ NHẬN rồi mang trả lại quầy.

        Thuốc: "thuốc vật lý đã quay lại" — KHÔNG phải quyết định bán lại / huỷ /
        cách ly (HOLD J1/J2). Trỏ đúng DISPENSE gốc; lô trả = lô đã xuất; tổng
        trả không vượt số đã xuất (DB kiểm). Tồn vật lý tăng (`RETURN_RECEIVED`),
        nhưng phần trả chưa có quyết định xử lý không vào lượng có thể bán.

        TIỀN (G4d · R3 — Tuyền chốt E 14/10): BẮT chọn ``ket_cuc_tien``:
          * ``HOAN`` — tạo khoản hoàn đúng phần trả (lệnh hoàn hiện có: máy tính
            tiền = số lượng × đơn giá ảnh chụp), mặc định theo hình thức HIỆU LỰC
            của lần thu gốc, ``hinh_thuc`` đổi được;
          * ``DOI`` — đổi thuốc khác: tiền phần trả cũng hoàn ra (lý do "Đổi
            thuốc"); đơn mới thu như thường — chênh lệch ra ở quầy;
          * ``GIU_LAI`` — khách để lại tiền, bắt ghi ``ly_do_tien``: vẫn là nợ
            khách (sổ PHAI_TRA) tới khi hoàn / dùng.
        Trước đây lệnh không đụng tiền — hàng về kho, tiền không ra, không màn
        nào báo. Cùng một giao dịch với lần trả: hoàn không được thì không trả.
        """
        luong = _so(so_luong, ten="Số lượng trả")
        ly = (ly_do or "").strip()
        if len(ly) < 3:
            raise ValidationError("Ghi lý do khách trả thuốc (tối thiểu 3 ký tự).")
        if ket_cuc_tien not in KET_CUC_TIEN:
            raise ValidationError(
                "Chọn tiền của phần trả: hoàn tiền, đổi thuốc khác, hoặc giữ lại."
            )
        ly_tien = ly_do_tien.strip() if isinstance(ly_do_tien, str) else ""
        if ket_cuc_tien == "GIU_LAI" and len(ly_tien) < 3:
            raise ValidationError("Giữ lại tiền thì ghi lý do (tối thiểu 3 ký tự).")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                xuat = await conn.fetchrow(
                    """
                    SELECT id::text, ref_id::text AS prescription_id,
                           drug_batch_id::text, allocation_id::text,
                           -quantity AS da_xuat
                      FROM public.inventory_txn
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND txn_type = 'DISPENSE' AND ref_type = 'prescription'
                    """,
                    dispense_txn_id,
                    identity.clinic_id,
                )
                if xuat is None:
                    raise NotFoundError("Không tìm thấy lần giao thuốc gốc này.")
                don = await self._khoa_theo_luot(
                    conn, identity, xuat["prescription_id"], cho_lich_su=True
                )
                await khoa_lo(
                    conn, clinic_id=identity.clinic_id, lo_ids=[xuat["drug_batch_id"]]
                )
                if await conn.fetchval(
                    "SELECT 1 FROM public.inventory_txn WHERE clinic_id = $1::uuid"
                    " AND txn_type = 'DISPENSE_REVERSAL'"
                    " AND reverses_txn_id = $2::uuid",
                    identity.clinic_id,
                    dispense_txn_id,
                ):
                    raise ConflictError(
                        "Lần giao này đã hoàn tác — thuốc đã về quầy, không ghi "
                        "khách trả được."
                    )
                da_tra = Decimal(
                    str(
                        await conn.fetchval(
                            "SELECT coalesce(sum(returned_qty), 0)"
                            " FROM public.drug_return WHERE clinic_id = $1::uuid"
                            " AND original_dispense_txn_id = $2::uuid",
                            identity.clinic_id,
                            dispense_txn_id,
                        )
                    )
                )
                con = Decimal(str(xuat["da_xuat"])) - da_tra
                if luong > con:
                    raise ValidationError(
                        f"Lần giao này xuất {so(Decimal(str(xuat['da_xuat'])))}, "
                        f"đã trả {so(da_tra)} — chỉ còn trả được {so(con)}."
                    )
                # Trả theo đơn vị LÔ, tiền và sổ nợ theo đơn vị ĐÃ BÁN.
                don_vi_lo = await conn.fetchval(
                    "SELECT unit FROM public.drug_batch"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    xuat["drug_batch_id"],
                    identity.clinic_id,
                )
                so_ban = await _phan_tra_theo_don_vi_ban(
                    conn, identity, don, xuat["prescription_id"], luong, don_vi_lo
                )
                hoan = (
                    await _hoan_phan_tra(
                        conn,
                        identity=identity,
                        prescription_id=xuat["prescription_id"],
                        so_luong=so_ban if so_ban is not None else luong,
                        hinh_thuc=hinh_thuc,
                        ly_do=(
                            f"Đổi thuốc: {ly}"
                            if ket_cuc_tien == "DOI"
                            else f"Khách trả thuốc: {ly}"
                        ),
                    )
                    if ket_cuc_tien in ("HOAN", "DOI")
                    else None
                )
                tra_id = await conn.fetchval(
                    """
                    INSERT INTO public.drug_return
                        (clinic_id, visit_id, prescription_id,
                         original_dispense_txn_id, allocation_id, drug_batch_id,
                         returned_qty, reason, returned_by,
                         ket_cuc_tien, ly_do_tien, refund_id, so_luong_ban)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6::uuid,
                            $7, $8, $9::uuid, $10, $11, $12::uuid, $13)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    don["visit_id"],
                    xuat["prescription_id"],
                    dispense_txn_id,
                    xuat["allocation_id"],
                    xuat["drug_batch_id"],
                    luong,
                    ly,
                    identity.staff_id,
                    ket_cuc_tien,
                    ly_tien if ket_cuc_tien == "GIU_LAI" else None,
                    hoan["refund_id"] if hoan else None,
                    so_ban,
                )
                await self._ghi_so(
                    conn,
                    identity=identity,
                    drug_batch_id=xuat["drug_batch_id"],
                    txn_type=TRA_NHAN,
                    quantity=luong,
                    reason=ly,
                    ref_type="drug_return",
                    ref_id=tra_id,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.drug_returned",
                    aggregate_type="prescription",
                    aggregate_id=xuat["prescription_id"],
                    payload={
                        "drug_return_id": tra_id,
                        "original_dispense_txn_id": dispense_txn_id,
                        "drug_batch_id": xuat["drug_batch_id"],
                        "quantity": str(luong),
                        "ket_cuc_tien": ket_cuc_tien,
                        "refund_id": hoan["refund_id"] if hoan else None,
                    },
                )
                # Sổ nợ + dòng thời gian nghe (G4d · R3): khách thường trả SAU
                # check-out — sổ đã ghi xong lần về, vòng đối chiếu chỉ quét 48
                # giờ. Không có sự kiện này thì "Giữ lại" không bao giờ vào sổ.
                await emit_event(
                    conn,
                    ten="medicine.returned",
                    clinic_id=identity.clinic_id,
                    aggregate_id=xuat["prescription_id"],
                    payload=ThuocKhachTra(
                        visit_id=str(don["visit_id"]),
                        prescription_id=xuat["prescription_id"],
                        drug_return_id=str(tra_id),
                        so_luong=str(luong),
                        ket_cuc_tien=str(ket_cuc_tien),
                        refund_id=str(hoan["refund_id"]) if hoan else None,
                    ),
                    boi=nguoi(identity),
                    correlation_id=str(don["visit_id"]),
                )
        ket_qua: dict[str, Any] = {
            "ok": True,
            "drug_return_id": tra_id,
            "ket_cuc_tien": ket_cuc_tien,
            "hoan": hoan,
        }
        if so_ban is not None:
            ket_qua["tom_tat"] = (
                f"Khách trả {so(luong)} {don_vi_lo} (≈ {_so_gon(so_ban)} "
                f"{don['unit']} đã bán)"
                + (f" — hoàn {_tien_viet(hoan['amount'])}." if hoan else ".")
            )
        return ket_qua

    async def hoan_tac_giao(
        self, *, identity: StaffIdentity, dispense_txn_id: str, ly_do: object = None
    ) -> dict[str, Any]:
        """Hoàn tác MỘT lần giao: thuốc về đúng lô, tiền giữ nguyên, giao lại được.
        Phần khách đã trả không đảo lại. Dòng bác sĩ đã đính chính không giao lại
        được nên không hoàn tác ở đây (thuốc về quầy qua hoàn tác lần thu)."""
        ly = _ly_do_hoan_tac_giao(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            goc = await conn.fetchrow(
                "SELECT ref_id::text AS rx, allocation_id::text, drug_batch_id::text"
                " FROM public.inventory_txn WHERE id = $1::uuid"
                " AND clinic_id = $2::uuid AND txn_type = 'DISPENSE'"
                " AND ref_type = 'prescription'",
                dispense_txn_id,
                identity.clinic_id,
            )
            if goc is None:
                raise NotFoundError("Không tìm thấy lần giao thuốc này.")
            don = await self._khoa_theo_luot(conn, identity, goc["rx"])
            if goc["allocation_id"]:
                await conn.execute(
                    "SELECT 1 FROM public.prescription_allocation"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                    goc["allocation_id"],
                    identity.clinic_id,
                )
            await khoa_lo(
                conn, clinic_id=identity.clinic_id, lo_ids=[goc["drug_batch_id"]]
            )
            lan = next(
                (
                    x
                    for x in await cac_lan_giao(conn, identity.clinic_id, [goc["rx"]])
                    if x.id == dispense_txn_id
                ),
                None,
            )
            if lan is None:
                raise ConflictError("Lần giao này đã hoàn tác rồi — tải lại.")
            if lan.con <= 0:
                raise ConflictError(
                    "Khách đã trả hết thuốc của lần giao này — không còn gì để "
                    "hoàn tác."
                )
            if goc["allocation_id"] and await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM public.inventory_txn s
                      JOIN public.payment_cycle c
                        ON c.payment_cycle_id = s.payment_cycle_id
                       AND c.clinic_id = s.clinic_id AND c.status = 'PAID'
                     WHERE s.clinic_id = $1::uuid AND s.allocation_id = $2::uuid
                       AND s.txn_type = 'SALE_REVERSAL')
                """,
                identity.clinic_id,
                goc["allocation_id"],
            ):
                raise ConflictError(
                    "Lô này đã “Huỷ phần chưa giao” nên không giao lại được — khách "
                    "mang thuốc trả thì dùng “Khách trả thuốc”."
                )
            await ghi_dong_dao(
                conn,
                clinic_id=identity.clinic_id,
                staff_id=identity.staff_id,
                lan=lan,
                ly_do=ly,
            )
            if goc["allocation_id"]:
                await conn.execute(
                    "UPDATE public.prescription_allocation"
                    " SET handed_over_qty = handed_over_qty - $3"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    goc["allocation_id"],
                    identity.clinic_id,
                    lan.con,
                )
            # Sổ tính theo đơn vị lô, `dispensed_qty` theo đơn vị đã bán.
            moi = await giam_da_giao(
                conn,
                clinic_id=identity.clinic_id,
                prescription_id=goc["rx"],
                so=await _so_dong_cua_lan_giao(conn, identity, don, lan),
            )
            await _log(
                conn,
                identity=identity,
                event_type="pharmacy.dispense_undone",
                aggregate_type="prescription",
                aggregate_id=goc["rx"],
                payload={
                    "dispense_txn_id": dispense_txn_id,
                    "drug_batch_id": goc["drug_batch_id"],
                    "quantity": str(lan.con),
                    "dispensed_qty": str(moi["dispensed_qty"]),
                    "reason": ly,
                },
            )
            await phat_hoan_tac_giao(
                conn,
                identity=identity,
                visit_id=str(don["visit_id"]),
                prescription_id=goc["rx"],
                so_luong=lan.con,
                so_da_giao=so(Decimal(str(moi["dispensed_qty"]))),
                ly_do=ly,
            )
        return {
            "ok": True,
            "so_luong": lan.con,
            "dispensed_qty": moi["dispensed_qty"],
            "dispense_status": moi["dispense_status"],
        }

    async def hoan_tac_giao_vat_tu(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: object = None
    ) -> dict[str, Any]:
        """Hoàn tác giao hàng trùng mã vật tư: chỉ đưa số đã giao về 0, tiền và số
        trừ ở Kho vật tư giữ nguyên (tồn theo lần thu, không theo lần giao)."""
        ly = _ly_do_hoan_tac_giao(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            don = await self._khoa_theo_luot(conn, identity, prescription_id)
            if not await thuoc_la_vat_tu(
                conn, identity.clinic_id, [don.get("drug_catalog_id")]
            ):
                raise ValidationError("Dòng này không phải hàng vật tư.")
            da_giao = Decimal(str(don.get("dispensed_qty") or 0))
            if da_giao <= 0:
                raise ConflictError("Dòng này chưa giao — không có gì để hoàn tác.")
            moi = await giam_da_giao(
                conn,
                clinic_id=identity.clinic_id,
                prescription_id=prescription_id,
                so=da_giao,
            )
            await _log(
                conn,
                identity=identity,
                event_type="pharmacy.dispense_undone",
                aggregate_type="prescription",
                aggregate_id=prescription_id,
                payload={"quantity": str(da_giao), "vat_tu": True, "reason": ly},
            )
            await phat_hoan_tac_giao(
                conn,
                identity=identity,
                visit_id=str(don["visit_id"]),
                prescription_id=prescription_id,
                so_luong=da_giao,
                so_da_giao=moi["dispensed_qty"],
                ly_do=ly,
            )
        return {"ok": True, "dispensed_qty": moi["dispensed_qty"]}

    async def huy_dong_cho_gan_lo(
        self, *, identity: StaffIdentity, dong_id: str, ly_do: object = None
    ) -> dict[str, Any]:
        """Hoàn tác một lần giao CHƯA gán lô: dòng chờ huỷ có vết, số đã giao giảm,
        giao lại được. Sổ kho không đổi — lần giao ấy chưa từng trừ kho."""
        ly = _ly_do_hoan_tac_giao(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            rx = await conn.fetchval(
                "SELECT prescription_id::text FROM public.thuoc_giao_chua_gan_lo"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                dong_id,
                identity.clinic_id,
            )
            if rx is None:
                raise NotFoundError("Không tìm thấy lần giao này.")
            don = await self._khoa_theo_luot(conn, identity, rx, cho_lich_su=True)
            huy = await huy_cho_gan_lo(
                conn,
                clinic_id=identity.clinic_id,
                staff_id=identity.staff_id,
                ly_do=ly,
                dong_id=dong_id,
            )
            so_huy = huy.get(rx)
            if so_huy is None:
                raise ConflictError(
                    "Lần giao này đã gán lô hoặc đã hoàn tác rồi — tải lại."
                )
            moi = await giam_da_giao(
                conn, clinic_id=identity.clinic_id, prescription_id=rx, so=so_huy
            )
            await _log(
                conn,
                identity=identity,
                event_type="pharmacy.dispense_undone",
                aggregate_type="prescription",
                aggregate_id=rx,
                payload={
                    "dong_id": dong_id,
                    "chua_gan_lo": True,
                    "quantity": str(so_huy),
                    "dispensed_qty": str(moi["dispensed_qty"]),
                    "reason": ly,
                },
            )
            await phat_hoan_tac_giao(
                conn,
                identity=identity,
                visit_id=str(don["visit_id"]),
                prescription_id=rx,
                so_luong=so_huy,
                so_da_giao=so(Decimal(str(moi["dispensed_qty"]))),
                ly_do=ly,
            )
        return {
            "ok": True,
            "so_luong": so_huy,
            "dispensed_qty": moi["dispensed_qty"],
            "dispense_status": moi["dispense_status"],
        }

    async def thuoc_tra_cho_kiem(
        self, *, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Thuốc khách đã trả mà CHƯA quyết xử lý (`drug_return.disposition` rỗng),
        của kho cơ sở đang làm. Phần này đã nằm trong tồn vật lý nhưng bị trừ khỏi
        lượng bán được (`drug_batch_kha_dung`) cho tới khi có quyết định."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text AS id, r.returned_qty, r.reason, r.returned_at,
                       r.drug_batch_id::text AS drug_batch_id,
                       b.batch_code, b.unit, b.cost_price, b.expiry_date,
                       coalesce(c.name_base, p.drug_name_raw) AS thuoc,
                       s.full_name AS nguoi_tra, pt.full_name AS ten_khach,
                       pt.patient_code
                  FROM public.drug_return r
                  JOIN public.drug_batch b
                    ON b.id = r.drug_batch_id AND b.clinic_id = r.clinic_id
                  /* rx:gom-ca-lich-su: thuốc đã trả vẫn phải hiện dù dòng đơn
                     sau đó bị bác sĩ đính chính */
                  JOIN public.prescription p
                    ON p.id = r.prescription_id AND p.clinic_id = r.clinic_id
                  LEFT JOIN public.drug_catalog c ON c.id = b.drug_catalog_id
                  LEFT JOIN public.staff s ON s.id = r.returned_by
                  LEFT JOIN public.visit v
                    ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
                  LEFT JOIN public.patient pt
                    ON pt.clinic_patient_id = v.clinic_patient_id
                   AND pt.clinic_id = v.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.disposition IS NULL
                   AND b.location_id = $2::uuid
                 ORDER BY r.returned_at, r.id
                """,
                identity.clinic_id,
                identity.location_id,
            )
        return [
            {
                "id": r["id"],
                "thuoc": r["thuoc"],
                "batch_code": r["batch_code"],
                "unit": r["unit"],
                "so_luong": Decimal(str(r["returned_qty"])),
                "gia_von": r["cost_price"],
                "ly_do_tra": r["reason"],
                "tra_luc": r["returned_at"],
                "nguoi_tra": r["nguoi_tra"],
                "khach": r["ten_khach"],
                "ma_bn": r["patient_code"],
            }
            for r in rows
        ]

    async def xu_ly_thuoc_tra(
        self,
        *,
        identity: StaffIdentity,
        drug_return_id: str,
        quyet_dinh: object,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        """Quyết định MỘT LẦN cho thuốc khách trả đang chờ kiểm (HOLD J1/J2 gỡ).

          * ``BAN_LAI`` — nhập lại bán được: chỉ đặt quyết định; lượng bán được
            (`drug_batch_kha_dung`) tự thôi trừ phần này. Lý do tuỳ chọn.
          * ``HUY`` — huỷ (hỏng, hết hạn, đã mở…): BẮT lý do, ghi một dòng sổ
            ``DISCARD`` (tồn vật lý giảm, ref `drug_return`) CÙNG giao dịch với
            quyết định — huỷ mà tồn không giảm là sai sổ (DB ép bằng CHECK).

        Quyết định không sửa lại (trigger `drug_return_guard`); gửi lần hai →
        câu báo đã xử lý. Không đụng tiền: tiền của lần trả đã chốt lúc trả.
        """
        if quyet_dinh not in ("BAN_LAI", "HUY"):
            raise ValidationError("Chọn nhập lại bán được, hoặc huỷ.")
        ly = (ly_do or "").strip()
        if quyet_dinh == "HUY" and len(ly) < 3:
            raise ValidationError(
                "Huỷ thuốc khách trả thì ghi lý do (tối thiểu 3 ký tự)."
            )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                tra = await conn.fetchrow(
                    """
                    SELECT r.id::text AS id, r.returned_qty, r.disposition,
                           r.drug_batch_id::text AS drug_batch_id,
                           r.prescription_id::text AS prescription_id
                      FROM public.drug_return r
                      JOIN public.drug_batch b
                        ON b.id = r.drug_batch_id AND b.clinic_id = r.clinic_id
                     WHERE r.id = $1::uuid AND r.clinic_id = $2::uuid
                       AND b.location_id = $3::uuid
                       FOR UPDATE OF r
                    """,
                    drug_return_id,
                    identity.clinic_id,
                    identity.location_id,
                )
                if tra is None:
                    raise NotFoundError("Không tìm thấy lần khách trả thuốc này.")
                if tra["disposition"] is not None:
                    raise ConflictError("Lần trả này đã được xử lý rồi.")
                luong = Decimal(str(tra["returned_qty"]))
                await khoa_lo(
                    conn, clinic_id=identity.clinic_id, lo_ids=[tra["drug_batch_id"]]
                )
                txn_id: str | None = None
                if quyet_dinh == "HUY":
                    ton = Decimal(
                        str(
                            await self._ton_cua_lo(conn, identity, tra["drug_batch_id"])
                        )
                    )
                    if ton < luong:
                        raise ConflictError(
                            f"Lô chỉ còn {so(ton)} trên sổ, ít hơn {so(luong)} khách "
                            "trả — kiểm kho trước khi huỷ."
                        )
                    txn_id = await self._ghi_so_trong(
                        conn,
                        identity=identity,
                        drug_batch_id=tra["drug_batch_id"],
                        txn_type=HUY,
                        quantity=-luong,
                        reason=f"Huỷ thuốc khách trả: {ly}",
                        ref_type="drug_return",
                        ref_id=tra["id"],
                    )
                await conn.execute(
                    """
                    UPDATE public.drug_return
                       SET disposition = $3, disposition_by = $4::uuid,
                           disposition_at = now(), disposition_reason = $5,
                           disposition_txn_id = $6::uuid
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND disposition IS NULL
                    """,
                    tra["id"],
                    identity.clinic_id,
                    quyet_dinh,
                    identity.staff_id,
                    ly or None,
                    txn_id,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.drug_return_decided",
                    aggregate_type="prescription",
                    aggregate_id=tra["prescription_id"],
                    payload={
                        "drug_return_id": tra["id"],
                        "drug_batch_id": tra["drug_batch_id"],
                        "quyet_dinh": quyet_dinh,
                        "quantity": str(luong),
                        "discard_txn_id": txn_id,
                    },
                )
        return {
            "ok": True,
            "drug_return_id": drug_return_id,
            "quyet_dinh": quyet_dinh,
            "discard_txn_id": txn_id,
        }

    # ── Phân lô (contract tiền–thuốc CP3) ─────────────────────────────────

    async def phan_lo(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_batch_id: str,
        so_luong: Any,
    ) -> dict[str, Any]:
        """Chọn lô cho dòng đơn TRƯỚC khi thu tiền thuốc. Chưa giữ chỗ.

        Thu tiền thuốc đòi mọi dòng có đủ lô; thu xong là bán đúng các lô này.
        Hai khách có thể cùng chọn một lô — người thu sau được kiểm lại.
        """
        luong = _so(so_luong, ten="Số lượng chọn lô")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                don = await self._khoa_dong_chua_thu(conn, identity, prescription_id)
                await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
                if don["drug_catalog_id"] is None:
                    raise ValidationError(
                        "Chưa xác định thuốc trong kho cho dòng này — xác định "
                        "thuốc trước khi chọn lô."
                    )
                if don["quantity_num"] is None:
                    raise ValidationError(
                        "Dòng này chưa có số lượng (bác sĩ để trống) — thu ngân "
                        "thuốc điền ở màn Thu tiền thuốc trước, chưa chọn lô được."
                    )
                if not _don_vi(don["unit"]):
                    raise ValidationError(
                        "Chưa xác định đơn vị thuốc được kê; cần xác nhận/chỉnh "
                        "đơn trước khi chọn lô."
                    )
                ban = Decimal(
                    str(
                        don["purchased_qty"]
                        if don["purchased_qty"] is not None
                        else don["quantity_num"]
                    )
                )
                can = ban - Decimal(str(don["dispensed_qty"] or 0))
                da_phan = await self._da_phan_lo(conn, identity, prescription_id)
                if da_phan + luong > can:
                    raise ValidationError(
                        f"Dòng này cần lô cho {so(can)}, đã chọn {so(da_phan)} — "
                        "không chọn quá số bán."
                    )
                await khoa_lo(
                    conn, clinic_id=identity.clinic_id, lo_ids=[drug_batch_id]
                )
                lo = await self._kiem_lo(
                    conn, identity, don, drug_batch_id, luong, them_giu=Decimal(0)
                )
                try:
                    pl_id = await conn.fetchval(
                        """
                        INSERT INTO public.prescription_allocation
                            (clinic_id, visit_id, prescription_id, drug_catalog_id,
                             drug_batch_id, quantity, created_by)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7::uuid)
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        don["visit_id"],
                        prescription_id,
                        don["drug_catalog_id"],
                        drug_batch_id,
                        luong,
                        identity.staff_id,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ConflictError(
                        f"Dòng này đã chọn lô {lo['batch_code']} — bỏ lô ấy rồi "
                        "chọn lại với số lượng mới."
                    ) from exc
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.allocated",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "allocation_id": pl_id,
                        "drug_batch_id": drug_batch_id,
                        "quantity": str(luong),
                    },
                )
        return {"ok": True, "allocation_id": pl_id}

    async def bo_phan_lo(
        self, *, identity: StaffIdentity, allocation_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Bỏ một lô đã chọn (chưa gắn lần thu). Dòng giữ lại làm lịch sử."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Bỏ lô đã chọn thì ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                pl = await self._khoa_phan_lo(conn, identity, allocation_id)
                if pl["released_at"] is not None:
                    return {"ok": True, "da_bo_tu_truoc": True}
                if pl["payment_cycle_id"] is not None:
                    raise ConflictError(
                        "Lô này đã gắn vào một lần thu — huỷ lần chờ / huỷ phiếu "
                        "thu, hoặc đổi lô khi đang chờ xác minh."
                    )
                await conn.execute(
                    "UPDATE public.prescription_allocation"
                    " SET released_at = now(), released_by = $3::uuid,"
                    " release_reason = $4"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    allocation_id,
                    identity.clinic_id,
                    identity.staff_id,
                    ly,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.allocation_released",
                    aggregate_type="prescription",
                    aggregate_id=str(pl["prescription_id"]),
                    payload={"allocation_id": allocation_id, "reason": ly},
                )
        return {"ok": True}

    async def doi_lo_khi_cho(
        self,
        *,
        identity: StaffIdentity,
        allocation_id: str,
        drug_batch_id: str,
        ly_do: str,
    ) -> dict[str, Any]:
        """Đổi lô ĐANG GIỮ cho một lần chuyển khoản/QR chờ xác minh.

        Chuyển phần giữ sang lô mới trong MỘT giao dịch: cùng thuốc, cùng số
        lượng, cùng lần thu — hoá đơn tiền không đổi. Lô mới phải còn hạn và đủ
        khả dụng; không được thì không đổi gì.
        """
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Đổi lô thì ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                pl = await self._khoa_phan_lo(conn, identity, allocation_id)
                if pl["released_at"] is not None:
                    raise ConflictError("Lô này đã được bỏ/đổi — tải lại.")
                if str(pl["drug_batch_id"]) == str(drug_batch_id):
                    return {"ok": True, "allocation_id": allocation_id}
                await khoa_lo(
                    conn,
                    clinic_id=identity.clinic_id,
                    lo_ids=[str(pl["drug_batch_id"]), drug_batch_id],
                )
                trang_thai = await conn.fetchval(
                    "SELECT status FROM public.payment_cycle"
                    " WHERE payment_cycle_id = $1::uuid AND clinic_id = $2::uuid",
                    pl["payment_cycle_id"],
                    identity.clinic_id,
                )
                if (
                    pl["payment_cycle_id"] is None
                    or trang_thai != "PENDING_VERIFICATION"
                ):
                    raise ConflictError(
                        "Chỉ đổi lô đang giữ cho lần chuyển khoản/QR chờ xác minh."
                    )
                don = await conn.fetchrow(
                    "SELECT id, visit_id, drug_catalog_id, unit"
                    " FROM public.prescription"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    " /* rx:gom-ca-lich-su: dòng của phân lô vừa khoá qua"
                    " _khoa_phan_lo (đã chặn dòng lịch sử) */",
                    pl["prescription_id"],
                    identity.clinic_id,
                )
                luong = Decimal(str(pl["quantity"]))
                await self._kiem_lo(
                    conn, identity, don, drug_batch_id, luong, them_giu=Decimal(0)
                )
                await conn.execute(
                    "UPDATE public.prescription_allocation"
                    " SET released_at = now(), released_by = $3::uuid,"
                    " release_reason = $4"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    allocation_id,
                    identity.clinic_id,
                    identity.staff_id,
                    f"Đổi lô khi chờ xác minh: {ly}",
                )
                try:
                    moi = await conn.fetchval(
                        """
                        INSERT INTO public.prescription_allocation
                            (clinic_id, visit_id, prescription_id, drug_catalog_id,
                             drug_batch_id, quantity, created_by, payment_cycle_id)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7::uuid, $8::uuid)
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        pl["visit_id"],
                        pl["prescription_id"],
                        pl["drug_catalog_id"],
                        drug_batch_id,
                        luong,
                        identity.staff_id,
                        pl["payment_cycle_id"],
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ConflictError(
                        "Dòng này đã có lô ấy trong lần thu — chưa hỗ trợ gộp lô."
                    ) from exc
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.allocation_moved",
                    aggregate_type="prescription",
                    aggregate_id=str(pl["prescription_id"]),
                    payload={
                        "from_allocation_id": allocation_id,
                        "to_allocation_id": moi,
                        "drug_batch_id": drug_batch_id,
                        "payment_cycle_id": str(pl["payment_cycle_id"]),
                        "reason": ly,
                    },
                )
        return {"ok": True, "allocation_id": moi}

    async def _khoa_phan_lo(
        self, conn: asyncpg.Connection, identity: StaffIdentity, allocation_id: str
    ) -> asyncpg.Record:
        """visit → dòng đơn → phân lô (đúng thứ tự khoá chung)."""
        rx = await conn.fetchval(
            "SELECT prescription_id::text FROM public.prescription_allocation"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            allocation_id,
            identity.clinic_id,
        )
        if rx is None:
            raise NotFoundError("Không tìm thấy lô đã chọn này.")
        await self._khoa_theo_luot(conn, identity, rx)
        pl = await conn.fetchrow(
            """
            SELECT id, visit_id, prescription_id, drug_catalog_id, drug_batch_id,
                   quantity, payment_cycle_id, released_at
              FROM public.prescription_allocation
             WHERE id = $1::uuid AND clinic_id = $2::uuid
             FOR UPDATE
            """,
            allocation_id,
            identity.clinic_id,
        )
        assert pl is not None
        return pl

    @staticmethod
    async def _da_phan_lo(
        conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
    ) -> Decimal:
        return Decimal(
            str(
                await conn.fetchval(
                    "SELECT coalesce(sum(quantity), 0)"
                    " FROM public.prescription_allocation"
                    " WHERE clinic_id = $1::uuid AND prescription_id = $2::uuid"
                    " AND released_at IS NULL",
                    identity.clinic_id,
                    prescription_id,
                )
            )
        )

    @staticmethod
    async def _kiem_lo(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        don: asyncpg.Record,
        drug_batch_id: str,
        luong: Decimal,
        *,
        them_giu: Decimal,
    ) -> asyncpg.Record:
        """Lô đúng thuốc, đúng cơ sở của lượt, đúng đơn vị, còn hạn, đủ khả dụng
        — nói bằng tiếng Việt trước khi trigger của DB từ chối."""
        lo = await conn.fetchrow(
            """
            SELECT batch_code, drug_catalog_id, unit, expiry_date, noi_chua,
                   public.drug_batch_kha_dung($2::uuid, id) AS kha_dung,
                   public.lo_dung_co_so_luot($2::uuid, $3::uuid, id) AS dung_co_so
              FROM public.drug_batch
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            """,
            drug_batch_id,
            identity.clinic_id,
            don["visit_id"],
        )
        if lo is None:
            raise NotFoundError("Không tìm thấy lô thuốc này trong kho.")
        if str(lo["drug_catalog_id"]) != str(don["drug_catalog_id"]):
            raise ValidationError("Lô này không phải thuốc của dòng đơn.")
        if not lo["dung_co_so"]:
            raise ValidationError(LO_KHAC_CO_SO)
        if lo["noi_chua"] != "QUAY":
            raise ConflictError(NOI_KHO_DANG_O)
        if _don_vi(lo["unit"]) != _don_vi(don["unit"]):
            raise ValidationError(
                f"Đơn kê theo đơn vị {don['unit']}, lô theo đơn vị {lo['unit']} — "
                "không chọn lô trước được; thu tiền rồi bấm Giao, máy tự đổi và "
                "trừ lô nếu đơn vị đã khai ở Danh mục kho."
            )
        if lo["expiry_date"] is not None and lo["expiry_date"] < now_vn().date():
            raise ConflictError(
                f"Lô {lo['batch_code']} hết hạn ngày {lo['expiry_date']:%d/%m/%Y}."
            )
        kd = Decimal(str(lo["kha_dung"] or 0)) + them_giu
        if kd < luong:
            raise ValidationError(
                f"Lô {lo['batch_code']} chỉ còn {so(max(kd, Decimal(0)))} có thể "
                f"phân lô lúc này — không đủ {so(luong)}."
            )
        return lo

    # ── Bên trong ──────────────────────────────────────────────────────────

    async def _chot_dong(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        refusal_reason: str | None,
        event_type: str,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Từ chối làm đổi hoá đơn thuốc → cùng thứ tự khoá với lần thu
                # (review CP1 #3), và không từ chối dòng đã thu tiền: phải huỷ
                # phiếu / hoàn tiền trước (contract D).
                don = await self._khoa_theo_luot(conn, identity, prescription_id)
                if don["closed_at"] is None:
                    await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
                    # CP5: còn phần ĐÃ BÁN mà chưa giao (ở bất kỳ lần thu nào,
                    # kể cả lần đã huỷ phiếu) thì không đóng dòng — chốt hay
                    # "khách không lấy" đều bỏ lại số thuốc ấy không ai xử lý.
                    chua_giao = await chua_giao_cua_dong(
                        conn, identity.clinic_id, prescription_id
                    )
                    if chua_giao > 0:
                        raise ConflictError(
                            f"Còn {so(chua_giao)} đã bán mà chưa giao — “Huỷ phần "
                            "chưa giao” (sau khi hoàn tiền hoặc huỷ phiếu) trước "
                            "khi đóng dòng."
                        )
                    if refusal_reason is None:
                        await self._chot_duoc_khong(conn, identity, don)
                    elif (da_giao := Decimal(str(don.get("dispensed_qty") or 0))) > 0:
                        # Xảy ra sau khi hoàn tác lần thu của dòng đã giao: thuốc đã
                        # rời quầy thì không thể ghi là khách không lấy.
                        raise ConflictError(
                            f"Dòng này đã giao {so(da_giao)} — thuốc đã rời quầy, "
                            "không ghi được là khách không lấy."
                        )
                if (
                    refusal_reason is not None
                    and don["closed_at"] is None
                    and await self._da_thu_tien_thuoc(conn, identity, don["visit_id"])
                ):
                    raise ConflictError(
                        "Tiền thuốc của lượt này đã thu — khách đổi ý thì huỷ "
                        "phiếu thu / hoàn tiền trước, rồi mới ghi không lấy thuốc."
                    )
                row = await conn.fetchrow(
                    """
                    UPDATE public.prescription
                       SET closed_at = coalesce(closed_at, now()),
                           refusal_reason = coalesce($3, refusal_reason),
                           updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND closed_at IS NULL
                    RETURNING dispensed_qty, dispense_status
                    """,
                    prescription_id,
                    identity.clinic_id,
                    refusal_reason,
                )
                if row is not None:
                    # Dòng đã chốt không bán nữa → bỏ các lô CHƯA gắn lần thu
                    # (chỉ là kế hoạch, không giữ chỗ). Lô đã bán thì giữ nguyên.
                    await conn.execute(
                        "UPDATE public.prescription_allocation"
                        " SET released_at = now(), released_by = $3::uuid,"
                        " release_reason = 'Dòng đơn đã chốt'"
                        " WHERE clinic_id = $1::uuid AND prescription_id = $2::uuid"
                        " AND released_at IS NULL AND payment_cycle_id IS NULL",
                        identity.clinic_id,
                        prescription_id,
                        identity.staff_id,
                    )
                if row is None:
                    # Hai người cùng bấm, hoặc bấm lại sau khi mạng lag. Không
                    # phải lỗi — nhưng phải nói rõ là KHÔNG CÓ GÌ ĐỔI, chứ không
                    # trả "ok" trống khiến người dùng tưởng vừa ghi được.
                    ton_tai = await conn.fetchval(
                        "SELECT 1 FROM public.prescription "
                        "WHERE id = $1::uuid AND clinic_id = $2::uuid"
                        " /* rx:gom-ca-lich-su: chỉ phân biệt 'không có' với"
                        " 'đã chốt từ trước' */",
                        prescription_id,
                        identity.clinic_id,
                    )
                    if not ton_tai:
                        raise NotFoundError("Không tìm thấy dòng thuốc này.")
                    return {"ok": True, "da_chot_tu_truoc": True}

                await _log(
                    conn,
                    identity=identity,
                    event_type=event_type,
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "refusal_reason": refusal_reason,
                        "note": ly_do,
                        "dispensed_qty": str(row["dispensed_qty"]),
                        "dispense_status": row["dispense_status"],
                    },
                )
        return {
            "ok": True,
            "dispensed_qty": row["dispensed_qty"],
            "dispense_status": row["dispense_status"],
        }

    @staticmethod
    async def _tim_yeu_cau_gui_lai(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        operation: str,
        idempotency_key: str | None,
        payload_sha256: str,
    ) -> dict[str, Any] | None:
        """Khoá theo key và đọc kết quả cũ bên trong cùng transaction ghi sổ."""
        if idempotency_key is None:
            return None
        khoa_day_du = (
            f"{identity.clinic_id}:{identity.staff_id}:{operation}:{idempotency_key}"
        )
        await conn.fetchval(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", khoa_day_du
        )
        row = await conn.fetchrow(
            """
            SELECT payload_sha256, response::text AS response
              FROM app_private.pharmacy_inventory_request
             WHERE clinic_id = $1::uuid AND staff_id = $2::uuid
               AND operation = $3 AND idempotency_key = $4::uuid
            """,
            identity.clinic_id,
            identity.staff_id,
            operation,
            idempotency_key,
        )
        if row is None:
            return None
        if row["payload_sha256"] != payload_sha256:
            raise ConflictError(
                "Mã gửi lại này đã dùng cho nội dung khác. Hãy tải lại kho và "
                "tạo thao tác mới."
            )
        response: dict[str, Any] = json.loads(row["response"])
        if isinstance(response.get("quantity_on_hand"), str):
            response["quantity_on_hand"] = Decimal(response["quantity_on_hand"])
        return response

    @staticmethod
    async def _luu_yeu_cau_gui_lai(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        operation: str,
        idempotency_key: str | None,
        payload_sha256: str,
        inventory_txn_id: str,
        drug_batch_id: str,
        response: dict[str, Any],
    ) -> None:
        """Lưu key + kết quả sau ledger insert, trước khi transaction commit."""
        if idempotency_key is None:
            return
        await conn.execute(
            """
            INSERT INTO app_private.pharmacy_inventory_request
                (clinic_id, staff_id, operation, idempotency_key,
                 payload_sha256, inventory_txn_id, drug_batch_id, response)
            VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5, $6::uuid, $7::uuid,
                    $8::jsonb)
            """,
            identity.clinic_id,
            identity.staff_id,
            operation,
            idempotency_key,
            payload_sha256,
            inventory_txn_id,
            drug_batch_id,
            json.dumps(response, ensure_ascii=False, default=str),
        )

    async def _ghi_kho_don_gian(
        self,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        txn_type: str,
        quantity: Decimal,
        ly_do: str,
        event_type: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        operation = txn_type.lower()
        dau_van_tay = _dau_van_tay(
            {
                "drug_batch_id": str(drug_batch_id),
                "location_id": identity.location_id,
                "quantity": _so_chuan(quantity),
                "reason": ly_do,
            }
        )
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                replay = await self._tim_yeu_cau_gui_lai(
                    conn,
                    identity=identity,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    payload_sha256=dau_van_tay,
                )
                if replay is not None:
                    return replay

                # Điều chỉnh / huỷ tay ở màn Kho: chỉ lô của kho cơ sở đang làm.
                lo = await conn.fetchrow(
                    """
                    SELECT id, quantity_on_hand FROM public.drug_batch
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND location_id = $3::uuid
                     FOR UPDATE
                    """,
                    drug_batch_id,
                    identity.clinic_id,
                    identity.location_id,
                )
                if lo is None:
                    raise NotFoundError(
                        "Không tìm thấy lô thuốc này trong kho của cơ sở đang làm."
                    )

                ton = Decimal(str(lo["quantity_on_hand"] or 0))
                if quantity < 0 and ton < -quantity:
                    raise ValidationError(
                        f"Lô này chỉ còn {so(ton)} — không bớt được {so(-quantity)}."
                    )
                if txn_type == HUY:
                    # Huỷ là QUYẾT ĐỊNH bỏ thuốc: không được bỏ vào phần đã bán chưa
                    # giao / đang giữ cho đơn / thuốc trả chờ kiểm — khách quay lại
                    # lấy sẽ không còn thuốc. Điều chỉnh thì KHÔNG chặn: nó ghi số
                    # đếm thật (kệ đã thiếu thì chặn chỉ làm sổ sai; CP3 giữ phần đã
                    # phân lô dù khả dụng âm). Đọc SAU khoá lô ở trên — luồng bán
                    # cũng khoá lô (`phan_lo_service.khoa_lo`) trước khi so.
                    kha_dung = Decimal(
                        str(
                            await conn.fetchval(
                                "SELECT public.drug_batch_kha_dung($1::uuid, $2::uuid)",
                                identity.clinic_id,
                                drug_batch_id,
                            )
                            or 0
                        )
                    )
                    if kha_dung < -quantity:
                        raise ValidationError(
                            f"Lô này còn {_so_chuan(ton)} trên kệ nhưng "
                            f"{_so_chuan(ton - max(kha_dung, Decimal(0)))} đã bán/"
                            "giữ cho khách hoặc là thuốc trả chờ kiểm — chỉ huỷ "
                            f"được tối đa {_so_chuan(max(kha_dung, Decimal(0)))}. "
                            "Nếu kệ thật thiếu, dùng Điều chỉnh theo số đếm."
                        )

                txn_id = await self._ghi_so_trong(
                    conn,
                    identity=identity,
                    drug_batch_id=drug_batch_id,
                    txn_type=txn_type,
                    quantity=quantity,
                    reason=ly_do,
                    ref_type="manual",
                    ref_id=None,
                )
                con = await self._ton_cua_lo(conn, identity, drug_batch_id)
                ket_qua = {"ok": True, "quantity_on_hand": con}
                await self._luu_yeu_cau_gui_lai(
                    conn,
                    identity=identity,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    payload_sha256=dau_van_tay,
                    inventory_txn_id=txn_id,
                    drug_batch_id=drug_batch_id,
                    response=ket_qua,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type=event_type,
                    aggregate_type="drug_batch",
                    aggregate_id=drug_batch_id,
                    payload={
                        "quantity": str(quantity),
                        "reason": ly_do,
                        "quantity_on_hand": str(con),
                    },
                )
        return ket_qua

    async def _ghi_so(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        txn_type: str,
        quantity: Decimal,
        reason: str | None,
        ref_type: str | None,
        ref_id: str | None,
        payment_cycle_id: str | None = None,
        allocation_id: str | None = None,
    ) -> None:
        if not quantity.is_finite():
            raise ValidationError("Số lượng biến động kho phải là số hữu hạn.")
        # `execute`, không RETURNING: các đường cũ (giao, huỷ, điều chỉnh…)
        # không cần id dòng sổ — giữ đúng một lời gọi ghi như trước 29/09.
        await conn.execute(
            _SQL_GHI_SO,
            identity.clinic_id,
            drug_batch_id,
            txn_type,
            quantity,
            reason,
            ref_type,
            ref_id,
            identity.staff_id,
            payment_cycle_id,
            allocation_id,
        )

    @staticmethod
    async def _ghi_so_trong(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        txn_type: str,
        quantity: Decimal,
        reason: str | None,
        ref_type: str | None,
        ref_id: str | None,
        payment_cycle_id: str | None = None,
        allocation_id: str | None = None,
    ) -> str:
        """Một dòng vào sổ kho. Trigger tự cộng vào tồn của lô. Trả id dòng sổ.

        `performed_by_staff_id` luôn đặt: `inventory_txn_manual_needs_actor`
        chỉ đòi nó khi `ref_type` là 'manual' hoặc trống, nhưng một dòng sổ
        không biết ai làm thì về sau không đối soát được với ai cả.
        """
        if not quantity.is_finite():
            raise ValidationError("Số lượng biến động kho phải là số hữu hạn.")
        ma: str = await conn.fetchval(
            _SQL_GHI_SO + " RETURNING id::text",
            identity.clinic_id,
            drug_batch_id,
            txn_type,
            quantity,
            reason,
            ref_type,
            ref_id,
            identity.staff_id,
            payment_cycle_id,
            allocation_id,
        )
        return ma

    @staticmethod
    async def _ton_cua_lo(
        conn: asyncpg.Connection, identity: StaffIdentity, drug_batch_id: str
    ) -> Any:
        return await conn.fetchval(
            "SELECT quantity_on_hand FROM public.drug_batch "
            "WHERE id = $1::uuid AND clinic_id = $2::uuid",
            drug_batch_id,
            identity.clinic_id,
        )


#: Một dòng vào sổ kho — dùng chung cho `_ghi_so` (không cần id) và
#: `_ghi_so_trong` (phiếu kho cần id dòng sổ, thêm RETURNING).
_SQL_GHI_SO = """
    INSERT INTO public.inventory_txn
        (clinic_id, drug_batch_id, txn_type, quantity, reason,
         ref_type, ref_id, performed_by_staff_id, performed_at,
         payment_cycle_id, allocation_id)
    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, $8::uuid, now(),
            $9::uuid, $10::uuid)
"""


NOI_KHO_DANG_O = "Lô này đang ở KHO — chuyển sang quầy rồi mới bán / giao."


async def tach_kho_quay_bat(conn: Any, identity: StaffIdentity) -> bool:
    """Cơ sở đang đứng đã BẬT tách kho / quầy chưa (G7). Mặc định tắt: một kho,
    mọi lô là hàng QUẦY như trước."""
    return bool(
        await conn.fetchval(
            "SELECT tach_kho_quay FROM public.clinic_location"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            identity.location_id,
            identity.clinic_id,
        )
    )


def kiem_dong_nhap(
    *, so_luong: Any, batch_code: str | None, expiry_date: date | None, unit: str | None
) -> tuple[Decimal, str, str, date | None]:
    """Luật một dòng nhập kho (số lô, đơn vị bắt buộc; số lượng > 0) —
    dùng chung cho `receive` và phiếu nhập nhiều dòng."""
    ma_lo = (batch_code or "").strip()
    don_vi = (unit or "").strip()
    if not ma_lo:
        raise ValidationError("Nhập số lô — không có số lô thì không thu hồi được.")
    if not don_vi:
        raise ValidationError("Nhập đơn vị (viên, vỉ, hộp, ống…).")
    han = expiry_date if isinstance(expiry_date, date) else None
    return _so(so_luong, ten="Số lượng nhập"), ma_lo, don_vi, han


#: Hệ số quy đổi tối đa (khớp CHECK `thuoc_quy_doi.he_so`).
HE_SO_TOI_DA = Decimal(10_000)
#: Hệ số lần này lệch quá ngần ấy lần so với hệ số đã nhớ thì bắt xác nhận —
#: gõ thừa/thiếu một số 0 là lỗi hay gặp nhất và làm lệch tồn cả chục lần.
NGUONG_HE_SO_LA = Decimal(10)
_BA_SO_LE = Decimal("0.001")
#: Trần của `inventory_txn.quantity` numeric(12,3), chừa chỗ cho số lẻ.
_LUONG_TOI_DA_SAU_DOI = Decimal(999_999_999)


class DongQuyDoi(NamedTuple):
    """Một dòng nhập SAU khi đổi về đơn vị bán (hoặc nguyên trạng nếu không đổi)."""

    so_luong: Decimal
    don_vi: str
    cost_price: Any
    #: (số gốc, đơn vị gốc, hệ số) — None = dòng không phải quy đổi.
    goc: tuple[Decimal, str, Decimal] | None = None

    @property
    def ghi_chu(self) -> str | None:
        if self.goc is None:
            return None
        so_goc, dv_goc, hs = self.goc
        return (
            f"Quy đổi {_so_dep(so_goc)} {dv_goc} × {_so_dep(hs)} = "
            f"{_so_dep(self.so_luong)} {self.don_vi}"
        )


def _so_dep(x: Decimal) -> str:
    return format(x.normalize(), "f")


async def xet_quy_doi(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    unit: str,
    he_so: Any = None,
) -> dict[str, Any]:
    """Nhập theo `unit` thì có phải đổi về đơn vị bán không, và hệ số nào.

    Trả `{can_doi, don_vi_ban, he_so_da_nho, he_so, la}`: `he_so` là hệ số sẽ dùng
    (gõ vào, không thì đã nhớ; None = còn thiếu), `la` = hệ số gõ lệch hơn
    `NGUONG_HE_SO_LA` lần so với hệ số đã nhớ. Hệ số gõ rác → ValidationError."""
    ban = (
        await conn.fetchval(
            "SELECT don_vi_ban FROM public.drug_catalog"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            drug_catalog_id,
            identity.clinic_id,
        )
        or ""
    ).strip()
    if not ban or not _don_vi(unit) or _don_vi(unit) == _don_vi(ban):
        return {
            "can_doi": False,
            "don_vi_ban": ban or None,
            "he_so_da_nho": None,
            "he_so": None,
            "la": False,
        }
    nho = await conn.fetchval(
        "SELECT he_so FROM public.thuoc_quy_doi"
        " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid AND don_vi = $3",
        identity.clinic_id,
        drug_catalog_id,
        _don_vi(unit),
    )
    if he_so is None or str(he_so).strip() == "":
        return {
            "can_doi": True,
            "don_vi_ban": ban,
            "he_so_da_nho": nho,
            "he_so": nho,
            "la": False,
        }
    hs = _so(he_so, ten="Hệ số quy đổi")
    if hs > HE_SO_TOI_DA:
        raise ValidationError(
            f"Hệ số quy đổi quá lớn (tối đa {HE_SO_TOI_DA:,.0f}) — "
            "kiểm tra lại có gõ thừa số 0 không."
        )
    hs = hs.quantize(_BA_SO_LE, rounding=ROUND_HALF_UP)
    if hs <= 0:
        raise ValidationError("Hệ số quy đổi phải lớn hơn 0 (tối đa 3 số lẻ).")
    la = nho is not None and max(hs / nho, nho / hs) > NGUONG_HE_SO_LA
    return {
        "can_doi": True,
        "don_vi_ban": ban,
        "he_so_da_nho": nho,
        "he_so": hs,
        "la": la,
    }


async def quy_doi_dong_nhap(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    so_luong: Decimal,
    unit: str,
    cost_price: Any,
    he_so: Any = None,
    xac_nhan_he_so: bool = False,
) -> DongQuyDoi:
    """Đổi một dòng nhập về ĐƠN VỊ BÁN của thuốc, ĐỨNG TRƯỚC `nhap_vao_lo`.

    Kho chỉ giữ một đơn vị = `drug_catalog.don_vi_ban`; nhập khác đơn vị thì kho
    ghi số đã đổi (6 hộp × 10 = 60 gói, giá 450.000đ/hộp → 45.000đ/gói), nếu
    không giao thuốc ghi tiền mà không trừ được kho. Không đoán: thiếu hệ số thì
    từ chối bằng một câu nói rõ cần gõ gì. Thuốc chưa khai đơn vị bán, hoặc nhập
    đúng đơn vị bán → nguyên trạng."""
    x = await xet_quy_doi(
        conn, identity=identity, drug_catalog_id=drug_catalog_id, unit=unit, he_so=he_so
    )
    if not x["can_doi"]:
        # Gõ "Viên" mà thuốc bán theo "viên": lưu đúng chữ của danh mục, kẻo màn
        # hiện hai cách viết của cùng một đơn vị.
        ban = x["don_vi_ban"]
        trung = bool(ban) and _don_vi(unit) == _don_vi(ban)
        return DongQuyDoi(so_luong, ban if trung else unit, cost_price)
    ban = x["don_vi_ban"]
    hs = x["he_so"]
    if hs is None:
        raise ValidationError(
            f"Thuốc này bán theo “{ban}”, bạn nhập theo “{unit}”: "
            f"nhập hệ số — 1 {unit} = ? {ban}."
        )
    if x["la"] and not xac_nhan_he_so:
        raise ValidationError(
            f"Hệ số lần này (1 {unit} = {_so_dep(hs)} {ban}) lệch hơn "
            f"{NGUONG_HE_SO_LA:.0f} lần so với lần trước "
            f"(1 {unit} = {_so_dep(x['he_so_da_nho'])} {ban}). "
            "Nếu đúng, tích “Đúng, hệ số này” rồi lưu lại."
        )
    luong = (so_luong * hs).quantize(_BA_SO_LE, rounding=ROUND_HALF_UP)
    if luong <= 0 or luong > _LUONG_TOI_DA_SAU_DOI:
        raise ValidationError(
            f"Sau khi đổi ra “{ban}” số lượng là {_so_dep(luong)} — "
            "kiểm tra lại số lượng và hệ số."
        )
    gia = None
    if cost_price is not None:
        # numeric(12,0): giá vốn mỗi đơn vị bán làm tròn đồng.
        gia = (Decimal(str(cost_price)) / hs).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    if x["he_so_da_nho"] != hs:
        await conn.execute(
            """
            INSERT INTO public.thuoc_quy_doi
                (clinic_id, drug_catalog_id, don_vi, he_so, cap_nhat_boi)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)
            ON CONFLICT (clinic_id, drug_catalog_id, don_vi)
            DO UPDATE SET he_so = EXCLUDED.he_so,
                          cap_nhat_boi = EXCLUDED.cap_nhat_boi,
                          cap_nhat_luc = now()
            """,
            identity.clinic_id,
            drug_catalog_id,
            _don_vi(unit),
            hs,
            identity.staff_id,
        )
    return DongQuyDoi(luong, ban, gia, (so_luong, unit, hs))


async def nhap_vao_lo(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    so_luong: Decimal,
    batch_code: str,
    expiry_date: date | None,
    unit: str,
    cost_price: Any,
    ly_do: str | None,
    ref_type: str,
    ref_id: str | None,
) -> tuple[str, str]:
    """Nhập vào một lô TRONG giao dịch của người gọi: tạo lô nếu chưa có, rồi
    ghi một dòng RECEIVE. Trả (id lô, id dòng sổ). Xem `PharmacyService.nhap_lo`.

    Lô thuộc kho của cơ sở NGƯỜI NHẬP (`identity.location_id`)."""
    thuoc = await conn.fetchrow(
        """
        SELECT id, name_base FROM public.drug_catalog
         WHERE id = $1::uuid AND clinic_id = $2::uuid
        """,
        drug_catalog_id,
        identity.clinic_id,
    )
    if thuoc is None:
        raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")

    # SỐ LÔ LÀ DUY NHẤT THEO (KHO CƠ SỞ, NƠI CHỨA), không theo từng thuốc:
    # `uq_drug_batch_clinic_location_code UNIQUE (clinic_id, location_id,
    # noi_chua, batch_code)` — cùng số lô ở hai cơ sở là hai lô; ở một cơ sở một
    # lô có tối đa hai hàng (KHO, QUẦY). Tra theo (thuốc, lô, hạn) sẽ không tìm
    # thấy dòng đã có rồi đâm vào ràng buộc duy nhất — và dược sĩ nhận một lỗi
    # Postgres thay vì một câu tiếng Việt.
    # G7: nhập đi vào KHO khi cơ sở đã bật tách kho / quầy, ngược lại vào QUẦY.
    noi = "KHO" if await tach_kho_quay_bat(conn, identity) else "QUAY"
    hang = await conn.fetch(
        """
        SELECT id, drug_catalog_id, expiry_date, noi_chua, ma_tem, unit, cost_price
          FROM public.drug_batch
         WHERE clinic_id = $1::uuid AND location_id = $3::uuid AND batch_code = $2
         ORDER BY noi_chua
        """,
        identity.clinic_id,
        batch_code,
        identity.location_id,
    )
    lo = next((h for h in hang if h["noi_chua"] == noi), None)
    if hang:
        # Cùng số lô mà khác thuốc hoặc khác hạn thì KHÔNG phải một lô — đó là
        # gõ nhầm số lô. Nhập tiếp vào đấy là trộn hai thứ thuốc vào một dòng tồn.
        goc = hang[0]
        if str(goc["drug_catalog_id"]) != str(drug_catalog_id):
            raise ConflictError(
                f"Số lô {batch_code} đã dùng cho một thuốc khác. "
                "Kiểm tra lại số lô trên vỏ hộp."
            )
        if goc["expiry_date"] != expiry_date:
            han_cu = (
                goc["expiry_date"].strftime("%d/%m/%Y")
                if goc["expiry_date"]
                else "chưa có hạn"
            )
            raise ConflictError(
                f"Số lô {batch_code} đã có trong kho với hạn dùng "
                f"{han_cu}, "
                "khác hạn vừa nhập. Kiểm tra lại."
            )
        _kiem_don_vi_cung_lo(hang, batch_code=batch_code, unit=unit)
    if lo is not None:
        lo_id = lo["id"]
        # Cộng "60 gói" vào lô đang tính "hộp" là trộn hai đơn vị vào một số dư.
        if lo["unit"] and _don_vi(lo["unit"]) != _don_vi(unit):
            raise ConflictError(
                f"Số lô {batch_code} đang tính theo đơn vị {lo['unit']} — "
                "nhập cùng đơn vị."
            )
        if (
            cost_price is not None
            and lo["cost_price"] is not None
            and Decimal(str(cost_price)) != Decimal(str(lo["cost_price"]))
        ):
            raise ValidationError(
                f"Số lô {batch_code} đã có giá nhập {lo['cost_price']}, "
                f"khác giá nhập mới {cost_price}. Hãy nhập thành lô riêng "
                "để giữ đúng giá vốn từng lần nhập."
            )
        if cost_price is not None:
            # Lô cũ chưa có giá nhập → lấy giá của lần nhập này (không ghi đè giá cũ).
            await conn.execute(
                "UPDATE public.drug_batch SET cost_price = $3"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid AND cost_price IS NULL",
                lo_id,
                identity.clinic_id,
                cost_price,
            )
    else:
        # Hàng thứ hai của cùng lô (đã có ở nơi kia): dùng chung mã tem, đơn vị.
        lo_id = await conn.fetchval(
            """
            INSERT INTO public.drug_batch
                (clinic_id, location_id, drug_catalog_id, batch_code, expiry_date,
                 quantity_on_hand, unit, cost_price, received_at, noi_chua, ma_tem)
            VALUES ($1::uuid, $7::uuid, $2::uuid, $3, $4::date, 0, $5, $6, now(),
                    $8, coalesce($9, 'LT' || lpad(
                        nextval('public.drug_batch_tem_seq')::text, 8, '0')))
            RETURNING id
            """,
            identity.clinic_id,
            drug_catalog_id,
            batch_code,
            expiry_date,
            unit,
            cost_price,
            identity.location_id,
            noi,
            hang[0]["ma_tem"] if hang else None,
        )

    txn_id = await PharmacyService._ghi_so_trong(
        conn,
        identity=identity,
        drug_batch_id=str(lo_id),
        txn_type=NHAP,
        quantity=so_luong,
        reason=ly_do,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    return str(lo_id), txn_id


def _dong_danh_muc(r: dict[str, Any], bang: BangDonVi) -> dict[str, Any]:
    """Một dòng danh mục + các đơn vị bán, câu quy đổi tồn. Máy chủ soạn sẵn chữ để
    màn chỉ vẽ."""
    ton_don_vi = json.loads(r["ton_theo_don_vi"])
    lo_lech = sorted(
        {
            str(x["don_vi"]).strip()
            for x in ton_don_vi
            if chuan(x["don_vi"]) and bang.he_so(x["don_vi"]) is None
        }
    )
    return {
        **r,
        "ton_theo_don_vi": ton_don_vi,
        "cac_don_vi": bang.cac_dong(),
        "gia_theo_don_vi": bang.nhan_gia(),
        "ton_quy_doi": bang.chu_ton(ton_don_vi),
        "chua_khai_don_vi": not bang.co_goc,
        # Có tồn theo đơn vị máy chưa đổi được về đơn vị gốc.
        "lo_chua_quy_doi": lo_lech if bang.co_goc else [],
    }


def _tien_viet(v: Any) -> str:
    return f"{int(v):,}đ".replace(",", ".")


def _so_gon(x: Decimal) -> str:
    """Số lẻ cho người đọc: 0,166666667 hộp đọc là 0,167."""
    return so(x.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)).replace(".", ",")


async def _viec_de_tru_duoc(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    don: Any,
    prescription_id: str,
) -> str | None:
    """Giao xong còn phần chưa trừ kho: có phải vì đơn vị không, phải làm gì."""
    thuoc = don.get("drug_catalog_id")
    if not thuoc:
        return None
    doi = await quy_doi_cua_dong(
        conn,
        identity.clinic_id,
        thuoc=str(thuoc),
        don_vi=don.get("unit"),
        prescription_id=prescription_id,
    )
    don_vi_lo = await conn.fetch(
        "SELECT DISTINCT unit FROM public.drug_batch"
        " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid"
        "   AND quantity_on_hand > 0",
        identity.clinic_id,
        str(thuoc),
    )
    return cau_thieu_quy_doi(doi, [r["unit"] for r in don_vi_lo])


async def _so_giao_theo_don_vi_ban(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    don: Any,
    prescription_id: str,
    luong: Decimal,
    don_vi_giao: str | None,
) -> Decimal:
    """Số gõ theo `don_vi_giao` đổi ra đơn vị đã bán của dòng: 15 gói của dòng 1 hộp
    (30 gói) = 0,5. Giao lẻ tới hết thì lấy đúng phần còn lại — ba lần 10 gói phải
    ra đúng 1 hộp, không kẹt "giao một phần" vì số lẻ."""
    if not chuan(don_vi_giao) or chuan(don_vi_giao) == chuan(don.get("unit")):
        return luong
    doi = await quy_doi_cua_dong(
        conn,
        identity.clinic_id,
        thuoc=don.get("drug_catalog_id"),
        don_vi=don.get("unit"),
        prescription_id=prescription_id,
    )
    doi_ra = doi.so_dong(luong, don_vi_giao)
    if doi_ra is None:
        raise ValidationError(
            f"Dòng này bán theo “{don.get('unit') or 'chưa ghi đơn vị'}”, chưa đổi "
            f"được từ “{don_vi_giao}” — thêm đơn vị ở Danh mục kho."
        )
    mua = don.get("purchased_qty")
    mua = don["quantity_num"] if mua is None else mua
    if mua is not None and doi.he_so_dong is not None:
        con = Decimal(str(mua)) - Decimal(str(don["dispensed_qty"] or 0))
        if abs(con - doi_ra) * doi.he_so_dong < Decimal("0.001"):
            return con
    return doi_ra.quantize(SAU_SO_LE, rounding=ROUND_HALF_UP)


async def _phan_tra_theo_don_vi_ban(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    don: Any,
    prescription_id: str,
    luong: Decimal,
    don_vi_lo: str | None,
) -> Decimal | None:
    """`luong` theo đơn vị lô đổi ra đơn vị đã bán của dòng. None = cùng đơn vị,
    không cần đổi (dòng đơn cũ không ghi đơn vị cũng vậy).

    Hoàn nốt phần cuối thì lấy đúng số còn lại: 30 lần trả 1 gói của dòng 1 hộp
    cộng lại phải đúng 1 hộp, không dư một số lẻ không ai hoàn được."""
    dv = _don_vi(don.get("unit"))
    if not dv or dv == _don_vi(don_vi_lo):
        return None
    doi = await quy_doi_cua_dong(
        conn,
        identity.clinic_id,
        thuoc=don.get("drug_catalog_id"),
        don_vi=don.get("unit"),
        prescription_id=prescription_id,
    )
    ty_le = doi.ty_le(don_vi_lo)
    if not ty_le:
        raise ConflictError(
            f"Dòng này bán theo “{don['unit']}”, lô theo “{don_vi_lo}” mà chưa có hệ "
            "số đổi — thêm đơn vị ở Danh mục kho rồi ghi nhận khách trả."
        )
    so_ban = (luong / ty_le).quantize(Decimal("0.000000001"), rounding=ROUND_HALF_UP)
    con = await conn.fetchval(
        """
        SELECT sum(bl.quantity - coalesce((
                   SELECT sum(l.quantity) FROM public.payment_refund_line l
                     JOIN public.payment_refund r
                       ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
                    WHERE l.clinic_id = bl.clinic_id AND l.payment_bill_line_id = bl.id
                      AND r.status IN ('PENDING', 'COMPLETED')), 0))
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = $1::uuid AND bl.source_type = 'prescription'
           AND bl.source_id = $2 AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PAID', 'PENDING_VERIFICATION')
        """,
        identity.clinic_id,
        prescription_id,
    )
    if con is not None and abs(Decimal(str(con)) - so_ban) * ty_le < Decimal("0.001"):
        return Decimal(str(con))
    return so_ban


async def _so_dong_cua_lan_giao(
    conn: asyncpg.Connection, identity: StaffIdentity, don: Any, lan: LanGiao
) -> Decimal:
    """Phần còn lại của một lần giao, đổi từ đơn vị lô về đơn vị đã bán của dòng.

    Bán 1 hộp (30 gói) giao 1 gói thì hoàn tác giảm 1/30 hộp, không phải 1 hộp. Lô
    tính hộp bán lẻ viên: sổ làm tròn 3 số lẻ nên đổi ngược ra 8,01 viên; lệch dưới
    0,05 là do làm tròn, lấy số nguyên để dòng đơn về đúng."""
    don_vi_lo = await conn.fetchval(
        "SELECT unit FROM public.drug_batch"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid",
        lan.drug_batch_id,
        identity.clinic_id,
    )
    qd = await quy_doi_cua_dong(
        conn,
        identity.clinic_id,
        thuoc=don.get("drug_catalog_id"),
        don_vi=don.get("unit"),
        prescription_id=lan.prescription_id,
    )
    ty_le = qd.ty_le(don_vi_lo)
    if not ty_le:
        return lan.con
    so_dong = lan.con / ty_le
    # Chỉ lô đơn vị LỚN hơn dòng mới có sai số làm tròn của sổ.
    if ty_le < 1:
        nguyen = so_dong.to_integral_value()
        if abs(so_dong - nguyen) <= Decimal("0.05"):
            return nguyen
    return so_dong.quantize(SAU_SO_LE)


async def _hoan_phan_tra(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    prescription_id: str,
    so_luong: Decimal,
    hinh_thuc: object,
    ly_do: str,
) -> dict[str, Any]:
    """Khoản hoàn cho phần thuốc khách trả (G4d · R3), TRONG giao dịch của lần
    trả. Dòng hoá đơn = dòng đơn này ở lần thu đã từng thu gần nhất; tiền do
    lệnh hoàn hiện có tính (số lượng × đơn giá ảnh chụp, DB kiểm không vượt số
    đã thu). Hình thức mặc định = hình thức HIỆU LỰC của lần thu ấy."""
    from clinicai.services.hoan_tien_service import (
        PHUONG_THUC,
        _tao_trong,
        co_quyen_hoan,
    )

    dong = await conn.fetchrow(
        """
        SELECT bl.id::text AS line_id, c.payment_cycle_id::text AS cycle_id,
               c.visit_id::text AS visit_id, c.paid_at,
               hinh_thuc_hieu_luc(c.clinic_id, c.payment_cycle_id, c.method)
                   AS hinh_thuc
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = $1::uuid AND bl.source_type = 'prescription'
           AND bl.source_id = $2 AND bl.billing_owner = 'CLINIC'
           AND c.status IN ('PAID', 'PENDING_VERIFICATION')
         ORDER BY (c.paid_at IS NULL), c.paid_at DESC
         LIMIT 1
        """,
        identity.clinic_id,
        prescription_id,
    )
    if dong is None:
        raise ConflictError(
            "Không tìm thấy lần thu của dòng thuốc này — không hoàn được; chọn "
            '"Giữ lại" (ghi lý do) rồi xử lý ở quầy thu.'
        )
    if dong["paid_at"] is None:
        raise ConflictError(
            "Tiền thuốc của dòng này còn CHỜ XÁC MINH chuyển khoản — xác minh xong"
            ' mới hoàn được, hoặc chọn "Giữ lại" (ghi lý do).'
        )
    ht = hinh_thuc if hinh_thuc else dong["hinh_thuc"] or "CASH"
    if ht not in PHUONG_THUC:
        raise ValidationError(f"Hình thức hoàn không hợp lệ: {ht!r}")
    if not await co_quyen_hoan(conn, identity, "thuoc", dong["visit_id"]):
        raise ConflictError(
            "Bạn chưa có lego Thu tiền thuốc nên không hoàn được — chọn"
            ' "Giữ lại" (ghi lý do) hoặc nhờ thu ngân thuốc.'
        )
    return await _tao_trong(
        conn,
        identity=identity,
        payment_cycle_id=dong["cycle_id"],
        visit_id=dong["visit_id"],
        kind="thuoc",
        yeu_cau={dong["line_id"]: so_luong},
        method=str(ht),
        ly_do=ly_do,
    )


async def _log(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
) -> None:
    await conn.execute(
        """
        INSERT INTO public.event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, $3, $4::uuid, $5::jsonb, $6::jsonb,
                'api:pharmacy', FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_type,
        aggregate_id,
        json.dumps(payload, ensure_ascii=False),
        json.dumps(
            {
                "actor_auth_user_id": identity.auth_user_id,
                "clinic_staff_id": identity.staff_id,
                "clinic_role": identity.role.value,
                # Vai tài khoản gốc (vai dùng có thể khác).
                "vai_tai_khoan": identity.vai_goc.value,
            }
        ),
    )


#: Cho service kho khác (phiếu nhập / kiểm kho) ghi cùng nhật ký.
ghi_nhat_ky = _log
