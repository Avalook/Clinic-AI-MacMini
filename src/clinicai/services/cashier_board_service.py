"""Bảng thu ngân — MỘT vòng mạng thay cho hai đợt PostgREST.

VÌ SAO CHUYỂN XUỐNG ĐÂY.

Màn thu ngân trước đây đọc qua PostgREST theo hai đợt NỐI TIẾP: đợt một lấy lượt
khám hôm nay, đợt hai lấy xét nghiệm / dịch vụ / đơn thuốc / bảng giá / thanh
toán *theo id lấy được từ đợt một*. Đo ngày 04/08/2026 từ chính máy Mac mini:

    một truy vấn PostgREST   ~210ms
    một vòng Postgres         ~73ms   (kết nối sẵn trong pool)

Hai đợt PostgREST ≈ 420ms ngồi chờ, mỗi lần thu ngân mở màn hình. Gộp thành một
câu SQL đi qua asyncpg thì còn ~73ms — và thu ngân là người bấm màn này nhiều
lần nhất trong ngày.

LUẬT ĐI THEO, KHÔNG Ở LẠI.

Ba luật vốn nằm trong TSX được chuyển xuống cùng, đúng nguyên tắc của dự án
(logic ở backend, TSX chỉ vẽ):

  1. Khách hiện khi BÁC SĨ ĐÃ KHÁM XONG (`moc_kham_xong`), HOẶC ngay khi có
     chỉ định (ô dịch vụ) / có đơn thuốc (ô thuốc) — Tuyền chốt 24/09/2026:
     khách trả tiền trong lúc phiên bác sĩ còn mở. Cùng luật với lệnh thu
     (`payment_service._kiem_luot_thu(can_kham_xong=False)`).
  2. Tên dịch vụ/thuốc phải CHUẨN HOÁ trước khi tra bảng giá — bỏ đường link
     dính trong tên, gộp khoảng trắng, bỏ ngoặc. Không chuẩn hoá thì "Siêu âm
     (https://...)" không khớp dòng giá nào và thu ngân thấy giá trống.
  3. Tiền khám lấy từ dịch vụ của lịch hẹn, đứng đầu danh sách.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import asyncpg
import structlog

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.permissions.can import can
from clinicai.services.anh_chuyen_khoan_service import anh_cua_cac_lan_thu
from clinicai.services.doi_hinh_thuc_service import trang_thai_doi
from clinicai.services.hoan_tien_service import co_quyen_hoan, hoan_cua_cac_lan_thu
from clinicai.services.moc_kham_xong import kham_xong_sql
from clinicai.services.phan_thu import doc_phan_db

if TYPE_CHECKING:
    from clinicai.services.bill_service import HoaDon

logger = structlog.get_logger()

CASHIER_ROLES: frozenset[ClinicRole] = frozenset(
    {
        # Lễ tân kiêm thu ngân ở Kim Ngưu (Tuyền 16/09/2026).
        ClinicRole.RECEPTION,
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.CASHIER_DV,
        # Dược sĩ đứng quầy thu tiền thuốc (Tuyền chốt 23/09, rà quyền nhóm 6).
        ClinicRole.PHARMACIST,
        ClinicRole.MANAGEMENT,
    }
)

_LINK = re.compile(r"\(https?://[^)]*\)?", re.IGNORECASE)
_LINK_SPACED = re.compile(r"\s*\(https?://[^)]*\)?", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def norm_name(s: str | None) -> str:
    """Khoá tra bảng giá. Bản sao 1-1 của normName() bên TSX.

    Đường link bị dính vào tên dịch vụ khi nhập liệu là chuyện thường xảy ra
    (dán từ Zalo). Không bỏ nó ra thì tên không khớp dòng giá nào, và màn thu
    ngân hiện giá trống — trông như chưa khai giá chứ không như lỗi dữ liệu.
    """
    out = (s or "").lower()
    out = _LINK.sub("", out)
    out = out.replace("(", " ").replace(")", " ")
    return _SPACES.sub(" ", out).strip()


def clean_name(s: str | None) -> str:
    """Tên để HIỆN RA (giữ nguyên hoa/thường), chỉ bỏ link."""
    return _LINK_SPACED.sub("", s or "").strip()


# Một câu, một vòng mạng. Sáu tập dữ liệu gói trong một JSON.
_SQL = (
    """
WITH v AS (
    SELECT vi.visit_id,
           vi.clinic_patient_id,
           vi.appointment_id,
           p.full_name,
           p.patient_code,
           p.phone_primary,
           a.status                AS appt_status,
           a.so_booking,
           a.so_tiep_don,
           st.name                 AS exam_service_name,
           bs.full_name            AS bac_si,
           -- CHỜ Ở QUẦY TỪ LÚC NÀO (27/09/2026): chỉ định còn nợ sớm nhất (lúc
           -- bác sĩ chỉ định); không có chỉ định thì lúc khám xong, rồi check-in.
           coalesce(
               (SELECT min(coalesce(so.authorized_at, so.created_at))
                  FROM public.service_order so
                 WHERE so.clinic_id = vi.clinic_id AND so.visit_id = vi.visit_id
                   AND so.selection_status IN ('PENDING', 'SELECTED')
                   -- V10 làm trước, thu sau: đã xếp / đang làm / làm xong mà
                   -- chưa thu vẫn là khoản chờ ở quầy.
                   AND so.exec_status IN
                       ('authorized', 'assigned', 'in_progress', 'performed')
                   AND coalesce(so.execution_status, 'PENDING')
                       IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')
                   AND NOT EXISTS (
                       SELECT 1 FROM public.payment_bill_line bl
                         JOIN public.payment_cycle c
                           ON c.clinic_id = bl.clinic_id
                          AND c.payment_cycle_id = bl.payment_cycle_id
                        WHERE bl.clinic_id = so.clinic_id
                          AND bl.source_type = 'service_order'
                          AND bl.source_id = so.id::text
                          AND c.status IN ('PENDING_VERIFICATION', 'PAID'))),
               vi.exam_completed_at, vi.checked_in_at, vi.created_at) AS cho_tu,
           """
    + kham_xong_sql("vi")
    + """                    AS kham_xong
      FROM public.visit vi
      LEFT JOIN public.staff bs ON bs.id = vi.attending_doctor_id
      LEFT JOIN public.appointment a
             ON a.id = vi.appointment_id AND a.clinic_id = vi.clinic_id
      LEFT JOIN public.patient p
             ON p.clinic_patient_id = vi.clinic_patient_id
            AND p.clinic_id = vi.clinic_id
      LEFT JOIN public.service_type st
             ON st.id = coalesce(vi.service_type_id, a.service_type_id)
     WHERE vi.clinic_id = $1::uuid
       AND ((vi.created_at >= $2 AND vi.created_at < $3)
            -- THU NỢ (01/10/2026): lượt ngày trước đã GHI NỢ, còn chưa thu —
            -- khách quay lại trả ở quầy theo đúng đường thu có sẵn.
            OR EXISTS (
                SELECT 1 FROM public.cong_no n
                 WHERE n.clinic_id = vi.clinic_id AND n.visit_id = vi.visit_id
                   AND n.trang_thai = 'CHUA_THU'))
       -- Luật 1: đã khám xong (ô thuốc + dịch vụ), HOẶC đã có chỉ định chính
       -- thức (ô dịch vụ — trả tiền trong lúc phiên bác sĩ còn mở).
       AND ("""
    + kham_xong_sql("vi")
    + """
            OR EXISTS (
                SELECT 1 FROM public.service_order so
                 WHERE so.clinic_id = vi.clinic_id AND so.visit_id = vi.visit_id
                   AND so.selection_status IS NOT NULL
                   AND so.exec_status NOT IN ('draft', 'cancelled'))
            -- Ô THUỐC: đã có đơn (nhóm 4, 24/09 — không đợi khám xong).
            OR EXISTS (
                SELECT 1 FROM public.prescription rx
                 WHERE rx.clinic_id = vi.clinic_id AND rx.visit_id = vi.visit_id
                   AND rx.removed_at IS NULL))
     ORDER BY vi.created_at DESC
     LIMIT 300
)
SELECT json_build_object(
  'visits', (SELECT coalesce(json_agg(row_to_json(v)), '[]'::json) FROM v),
  -- MỘT NGUỒN CHỈ ĐỊNH (Tuyền 16/09/2026): `service_order`. Trước đây hoá đơn
  -- ghép từ bảng kết quả xét nghiệm + nhật ký dịch vụ — hai đường cũ; đo trên
  -- final cloud nhật ký dịch vụ có 0 dòng trong khi 8 chỉ định thật nằm ở đây,
  -- tức thu ngân sẽ thu THIẾU mọi dịch vụ bác sĩ chỉ định.
  --
  -- Giá tra theo MÃ dịch vụ, không theo tên: chỉ định mang sẵn service_code.
  -- Nháp, đã huỷ, không làm được → không tính tiền.
  'orders', (
     SELECT coalesce(json_agg(json_build_object(
              'id', o.id, 'visit_id', o.visit_id, 'name', o.service_name,
              'service_code', o.service_code, 'exec_status', o.exec_status,
              'unit_price', gia.unit_price)
              ORDER BY o.created_at, o.id), '[]'::json)
       FROM public.service_order o
       LEFT JOIN LATERAL (
            SELECT pr.unit_price FROM public.service_price pr
             WHERE pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
               AND pr.active
             ORDER BY (pr."group" = 'dich_vu') DESC
             LIMIT 1) gia ON true
      WHERE o.clinic_id = $1::uuid
        AND o.visit_id IN (SELECT visit_id FROM v)
        AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')),
  'drugs', (
     SELECT coalesce(json_agg(json_build_object(
              'id', d.id, 'visit_id', d.visit_id, 'name', d.drug_name_raw,
              'quantity', d.quantity, 'dosage', d.dosage_instructions)),
            '[]'::json)
       FROM public.prescription d
      WHERE d.visit_id IN (SELECT visit_id FROM v)
        AND d.removed_at IS NULL),
  'prices', (
     SELECT coalesce(json_agg(json_build_object(
              'name', pr.name, 'group', pr."group",
              'unit_price', pr.unit_price)), '[]'::json)
       FROM public.service_price pr
      WHERE pr.clinic_id = $1::uuid AND pr.active AND pr.unit_price IS NOT NULL),
  'paid', (
     SELECT coalesce(json_agg(json_build_object(
              'visit_id', pay.visit_id, 'kind', pay.kind)), '[]'::json)
       FROM public.payment pay
      WHERE pay.visit_id IN (SELECT visit_id FROM v)
        AND pay.status = 'PAID'
        -- Phiếu thu đã HUỶ không còn là đã thu. Hôm nay chưa có dòng nào bị
        -- huỷ nên bỏ sót cũng chưa lộ ra — đúng loại lỗi chỉ hiện hình vào
        -- ngày đầu tiên có người huỷ một phiếu thu.
        AND pay.voided_at IS NULL)
) AS data
"""
)


async def quyen_thu_theo_loai(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> dict[str, bool]:
    """Người xem có quyền thu (→ hoàn tác) từng loại tiền không."""
    return {
        "dich_vu": await can(conn, identity, "payment.service.collect"),
        "thuoc": await can(conn, identity, "payment.medicine.collect"),
    }


def hoan_tac_cua(
    status: object,
    kind: object,
    hoan: dict[str, Any] | None,
    quyen: dict[str, bool],
) -> dict[str, Any]:
    """Nút "Hoàn tác lần thu" của một dòng giao dịch: có hiện không + vì sao. Thuần."""
    from clinicai.services.payment_service import ly_do_khong_hoan_tac

    co_hoan = any(
        k.get("status") in ("PENDING", "COMPLETED")
        for k in ((hoan or {}).get("khoan_hoan") or [])
    )
    ly = ly_do_khong_hoan_tac(status, kind, co_hoan)
    if ly is None and not quyen.get(str(kind), False):
        ly = "Bạn không có quyền thu loại tiền này."
    return {"duoc": ly is None, "ly_do_khong": ly}


class CashierBoardService:
    async def giao_dich(
        self, *, identity: StaffIdentity, tu: Any, den: Any
    ) -> dict[str, Any]:
        """Giao dịch đã ghi trong khoảng ngày — CHỈ ĐỌC, kể cả dòng đã huỷ.

        Batch pilot 18/09: "đã thanh toán hôm nay" và "lịch sử giao dịch". Không
        ghi đè lịch sử: dòng huỷ vẫn hiện, kèm ai huỷ, lúc nào, vì sao. Phương
        thức thanh toán CHƯA có cột trong `payment` — trả null, không đoán.
        """
        a, b = doc_khoang_ngay(tu, den)
        # SỔ CÁC LẦN THU (contract tiền–thuốc CP2): một dòng mỗi lần thu, kể cả
        # lần đã huỷ và lần chuyển khoản chờ xác minh/đã huỷ chờ. Bản trước đọc
        # `payment` — dòng hiện tại, bị tái dùng sau khi huỷ → mất lần thu cũ.
        rows = await self._pool.fetch(
            """
            SELECT pc.payment_cycle_id::text AS id, pc.visit_id::text AS visit_id,
                   pc.kind, pc.status, pc.amount,
                   -- Hình thức / mã GD HIỆU LỰC (sau mọi lần đổi — V7).
                   hinh_thuc_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                      pc.method) AS method,
                   ma_gd_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                  pc.reference) AS reference,
                   -- Chia theo hình thức (TM + CK) HIỆU LỰC — 01/10/2026.
                   phan_thu_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                     pc.method, pc.amount) AS phan,
                   pc.legacy, pc.can_doi_soat, pc.created_at, pc.paid_at,
                   pc.closed_at,
                   pc.close_reason,
                   p.full_name, p.patient_code,
                   cb.full_name AS nguoi_tao,
                   xn.full_name AS nguoi_xac_nhan,
                   dg.full_name AS nguoi_huy,
                   (vi.closed_at IS NOT NULL AND pc.closed_at IS NOT NULL
                    AND pc.closed_at > vi.closed_at) AS sau_khi_dong_luot
              FROM payment_cycle pc
              JOIN visit vi
                ON vi.visit_id = pc.visit_id AND vi.clinic_id = pc.clinic_id
              LEFT JOIN patient p
                ON p.clinic_patient_id = vi.clinic_patient_id
               AND p.clinic_id = vi.clinic_id
              LEFT JOIN staff cb ON cb.id = pc.created_by
              LEFT JOIN staff xn ON xn.id = pc.confirmed_by
              LEFT JOIN staff dg ON dg.id = pc.closed_by
             WHERE pc.clinic_id = $1::uuid
               AND (coalesce(pc.paid_at, pc.created_at) AT TIME ZONE
                    'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
             ORDER BY coalesce(pc.paid_at, pc.created_at) DESC
             LIMIT 1000
            """,
            identity.clinic_id,
            a,
            b,
        )
        # CP5: khoản hoàn của từng lần thu đã từng thu (kể cả đã huỷ phiếu) +
        # dòng còn hoàn được. Nút hoàn chỉ cho vai hoàn tiền TẠM THỜI (HOLD J4).
        async with self._pool.acquire() as conn:
            hoan = await hoan_cua_cac_lan_thu(
                conn, identity, [r["id"] for r in rows if r["paid_at"] is not None]
            )
            doi = await trang_thai_doi(
                conn, identity.clinic_id, [r["id"] for r in rows if r["paid_at"]]
            )
            anh = await anh_cua_cac_lan_thu(
                conn, identity.clinic_id, [r["id"] for r in rows]
            )
            quyen = await quyen_thu_theo_loai(conn, identity)
        return {
            "tu": a.isoformat(),
            "den": b.isoformat(),
            "co_quyen_hoan": co_quyen_hoan(identity),
            "giao_dich": [
                {
                    "id": r["id"],
                    "visit_id": r["visit_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "loai": r["kind"],
                    "trang_thai": r["status"],
                    "so_tien": float(r["amount"]) if r["amount"] is not None else None,
                    "luc": (r["paid_at"] or r["created_at"]).isoformat(),
                    "nguoi_thu": r["nguoi_xac_nhan"] or r["nguoi_tao"],
                    # NULL = phiếu thu trước CP2 — không biết phương thức, không đoán.
                    "phuong_thuc": r["method"],
                    "ma_giao_dich": r["reference"],
                    "legacy": r["legacy"],
                    "can_doi_soat": r["can_doi_soat"],
                    "huy_luc": r["closed_at"].isoformat() if r["closed_at"] else None,
                    "nguoi_huy": r["nguoi_huy"],
                    "ly_do_huy": r["close_reason"],
                    "sau_khi_dong_luot": r["sau_khi_dong_luot"],
                    "hoan": hoan.get(r["id"]),
                    # [Đổi hình thức] (V7): cờ đổi được + lịch sử đổi.
                    "doi_hinh_thuc": doi.get(r["id"]),
                    # Chia hình thức + ảnh chuyển khoản + nút Hoàn tác (01/10).
                    "phan": doc_phan_db(r["phan"]),
                    "anh_ck": anh.get(r["id"], []),
                    "hoan_tac": hoan_tac_cua(
                        r["status"], r["kind"], hoan.get(r["id"]), quyen
                    ),
                }
                for r in rows
            ],
        }

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def board(
        self, *, identity: StaffIdentity, modes: list[str]
    ) -> dict[str, Any]:
        want_svc = "dich_vu" in modes
        want_rx = "thuoc" in modes
        start = _vn_midnight_today()
        end = start + timedelta(days=1)

        row = await self._pool.fetchval(_SQL, identity.clinic_id, start, end)
        raw = json.loads(row) if isinstance(row, str) else row

        out = build_rows(raw, want_svc=want_svc, want_rx=want_rx)
        # HOÁ ĐƠN MÁY CHỦ (contract tiền–thuốc C3, 19/09/2026): tổng tiền và
        # dấu hoá đơn mà thu ngân thấy phải là đúng thứ `PaymentService` sẽ tính
        # lại lúc thu — màn không tự cộng nữa (trước: thuốc cộng đơn giá, quên
        # nhân số lượng). Chỉ tính cho khoản CHƯA thu.
        from clinicai.services.bill_service import tinh_hoa_don
        from clinicai.services.quay_thu_service import PhongQuay
        from clinicai.services.service_routing_service import (
            KHOA_NOI_BO,
            da_tra_cho_vao_phong,
        )
        from clinicai.services.service_selection_service import cho_khach_quyet

        da_thu = {(p["visit_id"], p["kind"]) for p in out["paid"]}
        cho_rows = await self._pool.fetch(
            """
            SELECT payment_cycle_id::text AS payment_cycle_id,
                   visit_id::text AS visit_id, kind, amount, method, created_at,
                   phan_thu_hieu_luc(clinic_id, payment_cycle_id, method, amount)
                       AS phan
              FROM payment_cycle
             WHERE clinic_id = $1::uuid AND status = 'PENDING_VERIFICATION'
               AND visit_id = ANY($2::uuid[])
            """,
            identity.clinic_id,
            [i["visit_id"] for i in out["items"]],
        )
        async with self._pool.acquire() as conn:
            anh_cho = await anh_cua_cac_lan_thu(
                conn, identity.clinic_id, [r["payment_cycle_id"] for r in cho_rows]
            )
        out["cho_xac_minh"] = [
            {
                "payment_cycle_id": r["payment_cycle_id"],
                "visit_id": r["visit_id"],
                "kind": r["kind"],
                "so_tien": int(r["amount"]),
                "phuong_thuc": r["method"],
                "luc": r["created_at"].isoformat(),
                # Chia TM + CK của lần chờ (01/10/2026) + ảnh chuyển khoản.
                "phan": doc_phan_db(r["phan"]),
                "anh_ck": anh_cho.get(r["payment_cycle_id"], []),
            }
            for r in cho_rows
        ]
        cho = {(r["visit_id"], r["kind"]) for r in cho_rows}
        loai = [k for k, co in (("dich_vu", want_svc), ("thuoc", want_rx)) if co]
        # Tiền dịch vụ thu được NHIỀU lần (Slice 3): bác sĩ chỉ định thêm sau
        # lần thu đầu thì còn khoản mới. "Đã thu" của ô dịch vụ = hoá đơn CÒN
        # NỢ rỗng, không phải "từng có một phiếu thu" — tính lại ở dưới.
        con_no_dv: set[str] = set()
        vids = [i["visit_id"] for i in out["items"]]
        # Tiền còn nợ của TỪNG chỉ định (từ hoá đơn quầy vừa dựng) — cho nhóm
        # "Làm trước – thu sau" (30/09/2026 tối), không tính giá lần hai.
        no_theo_chi_dinh: dict[str, dict[str, int | None]] = {}
        async with self._pool.acquire() as conn:
            chon: dict[str, dict[str, Any]] = {}
            phong: dict[str, list[dict[str, Any]]] = {}
            pq = PhongQuay(conn, identity.clinic_id)
            if want_svc:
                chon = await cho_khach_quyet(conn, identity.clinic_id, vids)
                # Đã trả, chưa bắt đầu → xếp / đổi phòng SAU khi thu (24/09).
                phong = await da_tra_cho_vao_phong(conn, identity.clinic_id, vids)
            for item in out["items"]:
                hd: dict[str, Any] = {}
                tinh_dv: HoaDon | None = None
                for k in loai:
                    if (item["visit_id"], k) in cho:
                        continue
                    if k == "thuoc" and (item["visit_id"], k) in da_thu:
                        continue
                    tinh = await tinh_hoa_don(
                        conn,
                        clinic_id=identity.clinic_id,
                        visit_id=item["visit_id"],
                        kind=k,
                    )
                    if k == "dich_vu":
                        tinh_dv = tinh
                        no_theo_chi_dinh[item["visit_id"]] = _no_theo_chi_dinh(tinh)
                    if k == "dich_vu" and not tinh.dong and not tinh.dong_doi_tac:
                        continue
                    # Chỉ còn dịch vụ ĐỐI TÁC TỰ THU (27/09/2026): hiện để lễ tân
                    # nói "khách trả trực tiếp cho đối tác", nhưng KHÔNG tính là
                    # còn nợ — lượt không kẹt ở quầy.
                    if k == "dich_vu" and tinh.dong:
                        con_no_dv.add(item["visit_id"])
                    hd[k] = tinh.cho_api()
                item["hoa_don"] = hd
                if want_svc:
                    item["chon_dich_vu"] = chon.get(item["visit_id"])
                    # Ô phòng trên dòng (27/09/2026): phòng chọn được, vắng
                    # nhất lên đầu — cùng tập dây H4.
                    item["xep_phong"] = [
                        {
                            **{k: v for k, v in x.items() if k not in KHOA_NOI_BO},
                            "phong_chon_duoc": await pq.cua(
                                x.get("node_code"),
                                item["visit_id"],
                                x.get("service_code"),
                            ),
                        }
                        for x in phong.get(item["visit_id"], [])
                    ]
                    if (item["visit_id"], "dich_vu") not in cho:
                        item["quay_thu"] = await _quay_thu(
                            conn,
                            identity.clinic_id,
                            item["visit_id"],
                            tinh_dv,
                            chon.get(item["visit_id"]),
                        )
            await _lam_truoc_va_no_khac(
                conn,
                identity,
                out,
                want_svc=want_svc,
                want_rx=want_rx,
                da_thu=da_thu,
                cho=cho,
                no_theo_chi_dinh=no_theo_chi_dinh,
            )
        if want_svc:
            _xep_hang_cho_thu(out, cho={v for v, k in cho if k == "dich_vu"})
            out["dem"] = {
                "cho_thu": len(out["ds_cho_thu"]),
                "da_thu_hom_nay": await _dem_da_thu_hom_nay(
                    self._pool, identity.clinic_id
                ),
            }
        if want_svc:
            khac = [p for p in out["paid"] if p["kind"] != "dich_vu"]
            out["paid"] = khac + [
                {"visit_id": i["visit_id"], "kind": "dich_vu"}
                for i in out["items"]
                if i["visit_id"] not in con_no_dv
                and (i["visit_id"], "dich_vu") not in cho
            ]
        return out


def _no_theo_chi_dinh(hd: HoaDon) -> dict[str, int | None]:
    """Chỉ định → tiền còn nợ, từ các dòng thu của MỘT hoá đơn dịch vụ đã dựng."""
    return {
        d.source_id: (int(d.thanh_tien) if d.thanh_tien is not None else None)
        for d in hd.dong_thu
        if d.source_type == "service_order"
    }


async def _lam_truoc_va_no_khac(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    out: dict[str, Any],
    *,
    want_svc: bool,
    want_rx: bool,
    da_thu: set[tuple[str, str]],
    cho: set[tuple[str, str]],
    no_theo_chi_dinh: dict[str, dict[str, int | None]],
) -> None:
    """Hai phần của đợt "thu trước, trừ khi tick" (30/09/2026 tối):

    * ``lam_truoc`` — tick "Làm trước – thu sau" của lượt + cờ bấm được; lượt đã
      tick kèm từng dịch vụ (Đã làm xong / Đang làm / Chưa làm + còn nợ) và
      ``nhom`` = ``LAM_XONG_THU_TIEN`` khi mọi dịch vụ đã xong mà còn nợ — lượt
      ấy nổi lên ĐẦU danh sách ("Đã làm xong — thu tiền").
    * ``no_khac`` — MỌI QUẦY THU HẾT ĐƯỢC: quầy thuốc thấy hoá đơn dịch vụ còn
      nợ, quầy dịch vụ thấy hoá đơn thuốc còn nợ (cùng hoá đơn máy chủ, thu
      bằng đúng lệnh thu của khoản ấy). Chờ xác minh thì không mời thu lại.
    """
    from clinicai.services.bill_service import tinh_hoa_don
    from clinicai.services.lam_truoc_thu_sau import (
        dich_vu_lam_truoc,
        trang_thai_lam_truoc,
    )

    vids = [i["visit_id"] for i in out["items"]]
    lam_truoc = await trang_thai_lam_truoc(conn, identity, vids)
    da_tick = [v for v, t in lam_truoc.items() if t["lam_truoc_thu_sau"]]
    dich_vu = await dich_vu_lam_truoc(
        conn, identity.clinic_id, da_tick, no_theo_chi_dinh
    )
    khac = [k for k, co in (("dich_vu", not want_svc), ("thuoc", not want_rx)) if co]
    for item in out["items"]:
        vid = item["visit_id"]
        no_khac: dict[str, Any] = {}
        # Tiền còn nợ từng chỉ định: quầy dịch vụ đã dựng sẵn; quầy thuốc lấy từ
        # hoá đơn dịch vụ dựng cho "Còn nợ dịch vụ" dưới đây (bấm thật 30/09:
        # quầy thuốc hiện "—" ở mọi dịch vụ làm trước vì chưa có bảng này).
        no_dv = dict(no_theo_chi_dinh.get(vid) or {})
        # Chỉ lượt đang có mặt ở quầy này (quầy thuốc: có đơn; quầy dịch vụ: có
        # dịch vụ) — không dựng hoá đơn cho mọi lượt trong ngày.
        co_mat = bool(item.get("drugs") if want_rx else item.get("services"))
        for k in khac if co_mat else []:
            if (vid, k) in cho or (k == "thuoc" and (vid, k) in da_thu):
                continue
            hd = await tinh_hoa_don(
                conn, clinic_id=identity.clinic_id, visit_id=vid, kind=k
            )
            if hd.dong_thu and hd.tong > 0:
                no_khac[k] = hd.cho_api()
            if k == "dich_vu":
                no_dv = _no_theo_chi_dinh(hd)
        item["no_khac"] = no_khac
        lt = dict(lam_truoc.get(vid) or {})
        dv = dich_vu.get(vid)
        con_no = sum(x for x in no_dv.values() if x)
        if dv is not None:
            lt["dich_vu"] = [
                {**x, "con_no": no_dv.get(x["id"])} if x["con_no"] is None else x
                for x in dv["dich_vu"]
            ]
            lt["nhom"] = (
                "LAM_XONG_THU_TIEN"
                if dv["da_lam_xong_het"] and con_no > 0
                else "LAM_TRUOC"
            )
        item["lam_truoc"] = lt or None
    # Lượt đã làm xong hết (đã tick) mà còn nợ lên đầu — thứ tự còn lại giữ nguyên.
    out["items"].sort(
        key=lambda i: (i.get("lam_truoc") or {}).get("nhom") != "LAM_XONG_THU_TIEN"
    )


async def _quay_thu(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    tinh_dv: Any,
    chon: dict[str, Any] | None,
) -> dict[str, Any]:
    """Hoá đơn MỘT khách của quầy (27/09/2026): hoá đơn còn nợ DỰ KIẾN — chỉ
    định còn chờ khách quyết tính như khách làm (mặc định của quầy) — ghép với
    danh sách chỉ định chờ quyết. Lệnh thu gộp chốt đúng lựa chọn ấy rồi dựng
    lại hoá đơn thật: cùng dòng, cùng ``revision``."""
    from clinicai.services.bill_service import hoa_don_con_no
    from clinicai.services.quay_thu_service import dung_hoa_don_quay

    cho_quyet = [
        c["id"]
        for c in (chon or {}).get("chi_dinh", [])
        if c.get("selection_status") == "PENDING"
    ]
    if cho_quyet or tinh_dv is None:
        tinh_dv = await hoa_don_con_no(
            conn, clinic_id=clinic_id, visit_id=visit_id, coi_nhu_chon=cho_quyet
        )
    return dung_hoa_don_quay(tinh_dv.cho_api(), chon)


def _xep_hang_cho_thu(out: dict[str, Any], *, cho: set[str]) -> None:
    """Ai đang CHỜ THU ở quầy dịch vụ + thứ tự (chờ lâu nhất lên đầu) + phút chờ.

    Máy chủ quyết (trước đây TSX tự lọc): đang chờ xác minh chuyển khoản/QR;
    còn dòng phòng khám thu (kể cả dòng chưa thu được vì thiếu giá — cần người
    xử lý); hoặc còn chỉ định chờ khách quyết (kể cả chỉ dịch vụ đối tác).
    """
    from clinicai.services.luot_kham_rules import cho_thu_lau, phut_cho

    bay_gio = datetime.now(CLINIC_TZ)
    ds: list[dict[str, Any]] = []
    for item in out["items"]:
        qt = item.get("quay_thu") or {}
        cho_quyet = any(
            c.get("selection_status") == "PENDING"
            for c in (item.get("chon_dich_vu") or {}).get("chi_dinh", [])
        )
        dang_cho = (
            item["visit_id"] in cho
            or any(r.get("chon") for r in qt.get("phong_kham", []))
            or cho_quyet
        )
        cho_tu = _doc_luc(item.pop("cho_tu", None))
        phut = phut_cho(cho_tu, bay_gio)
        item["cho_phut"] = phut
        item["cho_lau"] = cho_thu_lau(phut)
        item["cho_thu"] = dang_cho
        if dang_cho:
            ds.append({"visit_id": item["visit_id"], "cho_tu": cho_tu})
    ds.sort(key=lambda x: (x["cho_tu"] is None, x["cho_tu"] or bay_gio))
    out["ds_cho_thu"] = [x["visit_id"] for x in ds]


def _doc_luc(v: Any) -> datetime | None:
    """Mốc giờ trong JSON của Postgres (chuỗi ISO) → datetime; rác → None."""
    if isinstance(v, datetime):
        return v
    if not isinstance(v, str) or not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return None


async def _dem_da_thu_hom_nay(pool: asyncpg.Pool, clinic_id: str) -> int:
    """Số khách ở tab "Đã thu hôm nay" — cùng tập với sổ gom theo khách
    (``QuayThuService.lich_su`` hôm nay): lần thu đã thu hoặc khoản hoàn hôm nay."""
    return int(
        await pool.fetchval(
            """
            SELECT count(DISTINCT visit_id) FROM (
                SELECT visit_id FROM payment_cycle
                 WHERE clinic_id = $1::uuid AND kind = 'dich_vu'
                   AND paid_at IS NOT NULL
                   AND (paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                UNION ALL
                SELECT visit_id FROM payment_refund
                 WHERE clinic_id = $1::uuid AND kind = 'dich_vu'
                   AND status IN ('PENDING', 'COMPLETED')
                   AND (created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date) x
            """,
            clinic_id,
        )
        or 0
    )


def doc_khoang_ngay(tu: Any, den: Any, *, mac_dinh_ngay: int = 0) -> tuple[date, date]:
    """Khoảng ngày xem giao dịch (giờ VN). Rác/rỗng → mặc định, không ném.

    Mặc định HÔM NAY; ``den`` trước ``tu`` thì đổi chỗ; tối đa 92 ngày.
    """
    hom_nay = datetime.now(CLINIC_TZ).date()

    def _d(v: Any) -> date | None:
        if not isinstance(v, str) or not v.strip():
            return None
        try:
            return date.fromisoformat(v.strip()[:10])
        except ValueError:
            return None

    a = _d(tu) or hom_nay - timedelta(days=mac_dinh_ngay)
    b = _d(den) or hom_nay
    if b < a:
        a, b = b, a
    if (b - a).days > 92:
        a = b - timedelta(days=92)
    return a, b


def build_rows(raw: dict[str, Any], *, want_svc: bool, want_rx: bool) -> dict[str, Any]:
    """Ghép sáu tập thành các dòng thu ngân đọc được. Thuần, nên kiểm được."""
    price_thuoc: dict[str, float] = {}
    price_dv: dict[str, float] = {}
    for p in raw.get("prices") or []:
        if p.get("unit_price") is None:
            continue
        target = price_thuoc if p.get("group") == "thuoc" else price_dv
        target[norm_name(p.get("name"))] = float(p["unit_price"])

    orders_by_visit: dict[str, list[dict[str, Any]]] = {}
    for o in raw.get("orders") or []:
        name = clean_name(o.get("name"))
        if not name:
            continue
        gia = o.get("unit_price")
        orders_by_visit.setdefault(o["visit_id"], []).append(
            {
                "id": o["id"],
                "name": name,
                "price": float(gia)
                if gia is not None
                else price_dv.get(norm_name(name)),
            }
        )

    rx_by_visit: dict[str, list[dict[str, Any]]] = {}
    for d in raw.get("drugs") or []:
        name = (d.get("name") or "").strip()
        if not name:
            continue
        rx_by_visit.setdefault(d["visit_id"], []).append(
            {
                "id": d["id"],
                "name": name,
                "quantity": d.get("quantity"),
                "dosage": d.get("dosage"),
                "price": price_thuoc.get(norm_name(name)),
            }
        )

    items: list[dict[str, Any]] = []
    for v in raw.get("visits") or []:
        services: list[dict[str, Any]] = []
        if want_svc:
            # Luật 3: tiền khám đứng đầu.
            exam = clean_name(v.get("exam_service_name"))
            if exam:
                services.append(
                    {
                        "id": f"exam-{v['visit_id']}",
                        "name": exam,
                        "price": price_dv.get(norm_name(exam)),
                    }
                )
            services.extend(orders_by_visit.get(v["visit_id"], []))

        items.append(
            {
                "visit_id": v["visit_id"],
                "clinic_patient_id": v["clinic_patient_id"],
                "full_name": v.get("full_name"),
                "patient_code": v.get("patient_code"),
                "phone": v.get("phone_primary"),
                "appt_status": v.get("appt_status"),
                # Số booking + số check-in đứng cạnh tên ở MỌI khâu (Tuyền 27/09).
                "so_booking": v.get("so_booking"),
                "so_tiep_don": v.get("so_tiep_don"),
                # Dòng phụ của quầy (27/09/2026): loại khám · bác sĩ · chờ N′.
                "loai_kham": clean_name(v.get("exam_service_name")) or None,
                "bac_si": v.get("bac_si"),
                "cho_tu": v.get("cho_tu"),
                "services": services,
                # Tiền thuốc không đợi khám xong (nhóm 4, 24/09/2026).
                "drugs": rx_by_visit.get(v["visit_id"], []) if want_rx else [],
            }
        )

    paid = [
        {"visit_id": p["visit_id"], "kind": p["kind"]}
        for p in raw.get("paid") or []
        if p.get("kind") in ("thuoc", "dich_vu")
    ]
    return {"items": items, "paid": paid}


def _vn_midnight_today() -> datetime:
    """Nửa đêm HÔM NAY giờ Việt Nam, CÓ múi giờ.

    `visit.created_at` là timestamptz; một datetime trần sẽ được Postgres hiểu
    theo TimeZone của phiên và biên ngày lệch bảy tiếng — thu ngân sẽ thấy bệnh
    nhân của hôm qua nằm lẫn trong danh sách hôm nay.
    """
    return datetime.now(CLINIC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
