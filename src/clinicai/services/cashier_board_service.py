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

  1. CHỈ hiện bệnh nhân khi BÁC SĨ ĐÃ KHÁM XONG (appointment.status =
     'COMPLETED'). Lọc theo appointment chứ không theo visit.status, vì
     dashboard không tự đặt visit.FINALIZED.
  2. Tên dịch vụ/thuốc phải CHUẨN HOÁ trước khi tra bảng giá — bỏ đường link
     dính trong tên, gộp khoảng trắng, bỏ ngoặc. Không chuẩn hoá thì "Siêu âm
     (https://...)" không khớp dòng giá nào và thu ngân thấy giá trống.
  3. Tiền khám lấy từ dịch vụ của lịch hẹn, đứng đầu danh sách.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ

logger = structlog.get_logger()

CASHIER_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CASHIER,
        ClinicRole.CASHIER_THUOC,
        ClinicRole.CASHIER_DV,
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
_SQL = """
WITH v AS (
    SELECT vi.visit_id,
           vi.clinic_patient_id,
           vi.appointment_id,
           p.full_name,
           p.patient_code,
           p.phone_primary,
           a.status                AS appt_status,
           st.name                 AS exam_service_name
      FROM public.visit vi
      JOIN public.appointment a ON a.id = vi.appointment_id
      LEFT JOIN public.patient p
             ON p.clinic_patient_id = vi.clinic_patient_id
            AND p.clinic_id = vi.clinic_id
      LEFT JOIN public.service_type st ON st.id = a.service_type_id
     WHERE vi.clinic_id = $1::uuid
       AND vi.created_at >= $2 AND vi.created_at < $3
       -- Luật 1: chỉ khi bác sĩ đã khám xong.
       AND a.status = 'COMPLETED'
     ORDER BY vi.created_at DESC
     LIMIT 300
)
SELECT json_build_object(
  'visits', (SELECT coalesce(json_agg(row_to_json(v)), '[]'::json) FROM v),
  -- CỘT KHOÁ CỦA lab_result LÀ `lab_result_id`, KHÔNG PHẢI `id`.
  --
  -- Trang cũ hỏi PostgREST `select=id,appointment_id,test_name` → lỗi 42703
  -- "column lab_result.id does not exist", rồi TSX nuốt lỗi bằng `?? []`. Nghĩa
  -- là XÉT NGHIỆM CHƯA BAO GIỜ vào hoá đơn thu ngân, và không ai thấy gì bất
  -- thường vì màn hình vẫn hiện đủ các mục khác. Thu ngân thu thiếu tiền.
  'labs', (
     SELECT coalesce(json_agg(json_build_object(
              'id', l.lab_result_id, 'appointment_id', l.appointment_id,
              'test_name', l.test_name)), '[]'::json)
       FROM public.lab_result l
      WHERE l.appointment_id IN (SELECT appointment_id FROM v
                                  WHERE appointment_id IS NOT NULL)),
  'services', (
     SELECT coalesce(json_agg(json_build_object(
              'id', s.id, 'clinic_patient_id', s.clinic_patient_id,
              'name', coalesce(t.name, s.service_name_raw))), '[]'::json)
       FROM public.service_log s
       LEFT JOIN public.service_type t ON t.id = s.service_type_id
      WHERE s.clinic_patient_id IN (SELECT clinic_patient_id FROM v)
        AND s.ordered_at >= $2 AND s.ordered_at < $3),
  'drugs', (
     SELECT coalesce(json_agg(json_build_object(
              'id', d.id, 'visit_id', d.visit_id, 'name', d.drug_name_raw,
              'quantity', d.quantity, 'dosage', d.dosage_instructions)),
            '[]'::json)
       FROM public.prescription d
      WHERE d.visit_id IN (SELECT visit_id FROM v)),
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


class CashierBoardService:
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

        return build_rows(raw, want_svc=want_svc, want_rx=want_rx)


def build_rows(raw: dict[str, Any], *, want_svc: bool, want_rx: bool) -> dict[str, Any]:
    """Ghép sáu tập thành các dòng thu ngân đọc được. Thuần, nên kiểm được."""
    price_thuoc: dict[str, float] = {}
    price_dv: dict[str, float] = {}
    for p in raw.get("prices") or []:
        if p.get("unit_price") is None:
            continue
        target = price_thuoc if p.get("group") == "thuoc" else price_dv
        target[norm_name(p.get("name"))] = float(p["unit_price"])

    labs_by_appt: dict[str, list[dict[str, Any]]] = {}
    for lab in raw.get("labs") or []:
        appt = lab.get("appointment_id")
        if appt:
            labs_by_appt.setdefault(appt, []).append(lab)

    svc_by_patient: dict[str, list[dict[str, Any]]] = {}
    for s in raw.get("services") or []:
        name = clean_name(s.get("name"))
        if not name:
            continue
        svc_by_patient.setdefault(s["clinic_patient_id"], []).append(
            {"id": s["id"], "name": name, "price": price_dv.get(norm_name(name))}
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
            for lab in labs_by_appt.get(v.get("appointment_id") or "", []):
                nm = clean_name(lab.get("test_name"))
                if nm:
                    services.append(
                        {
                            "id": lab["id"],
                            "name": nm,
                            "price": price_dv.get(norm_name(nm)),
                        }
                    )
            services.extend(svc_by_patient.get(v["clinic_patient_id"], []))

        items.append(
            {
                "visit_id": v["visit_id"],
                "clinic_patient_id": v["clinic_patient_id"],
                "full_name": v.get("full_name"),
                "patient_code": v.get("patient_code"),
                "phone": v.get("phone_primary"),
                "appt_status": v.get("appt_status"),
                "services": services,
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
