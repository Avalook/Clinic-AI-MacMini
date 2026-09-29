"""Hành trình của MỘT lượt khám — dải mốc ở đầu phiếu khám (lát 5, 26/09/2026).

Bản giao diện mẫu Tuyền duyệt: "timeline hành trình ở trên cùng — mốc tiếp đón,
sinh hiệu, tư vấn, khám, gửi chỉ định, thu tiền, vào phòng, có kết quả…; khoảng
chờ ghi trên đoạn nối giữa hai mốc; 'đang ở đâu'; nhiều chỉ định gửi cùng lúc =
MỘT mốc".

CHỈ ĐỌC, KHÔNG LUẬT MỚI. Mốc thời gian đọc projection `luot_dong_thoi_gian` (dựng
từ sổ sự kiện); "đã thu / đã có kết quả" đọc hiện trạng chỉ định; "đang ở đâu"
dùng lại đúng hàm của Bảng hành trình chung (`dang_o`) để hai màn không nói hai
câu khác nhau. Không nội dung lâm sàng.

`dung_moc` là hàm THUẦN — test không cần DB. Giao diện chỉ vẽ và tính khoảng chờ
theo đồng hồ (thứ phải chạy theo giây ở trình duyệt).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bang_hanh_trinh_service import dang_o

XONG, DANG, CHUA = "xong", "dang", "chua"

#: Sự kiện có mặt trong dải mốc. Còn lại (định tuyến, tệp, sửa kết quả…) là chi
#: tiết của màn Xem lượt, không phải mốc khách đi qua.
_SU_KIEN = (
    "vitals.started",
    "vitals.recorded",
    "consultation.started",
    "consultation.handed_over",
    "consultation.completed",
    "payment.service_collected",
    "service.started",
    "service.completed",
    "result.ready",
    "result_file.uploaded",
    "prescription.saved",
    "payment.medicine_collected",
    "medicine.dispensed",
)

SuKien = tuple[str, datetime, dict[str, Any]]


def _dau(ds: list[datetime]) -> datetime | None:
    return min(ds) if ds else None


def _cuoi(ds: list[datetime]) -> datetime | None:
    return max(ds) if ds else None


def _tt(bat: datetime | None, ket: datetime | None) -> str:
    return XONG if ket is not None else DANG if bat is not None else CHUA


def _moc(
    ma: str,
    ten: str,
    noi: str,
    bat: datetime | None,
    ket: datetime | None,
    trang_thai: str,
    **them: Any,
) -> dict[str, Any]:
    return {
        "ma": ma,
        "ten": ten,
        "noi": noi,
        "bat": bat,
        "ket": ket,
        "trang_thai": trang_thai,
        **them,
    }


def dung_moc(
    *,
    dat_lich_luc: datetime | None,
    check_in_luc: datetime | None,
    ve_luc: datetime | None,
    su_kien: list[SuKien],
    chi_dinh: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Các mốc theo thứ tự khách đi qua.

    `chi_dinh`: mỗi dòng {lan, tao_luc, chon (False = khách bỏ ở quầy),
    da_tra, xong, phong, ngoai}. Chỉ định chưa gửi (nháp) / đã huỷ không vào đây.
    """

    def luc(ten_su_kien: str, **khop: Any) -> list[datetime]:
        return [
            t
            for (e, t, ct) in su_kien
            if e == ten_su_kien and all(ct.get(k) == v for k, v in khop.items())
        ]

    moc: list[dict[str, Any]] = []
    if dat_lich_luc is not None:
        hom_truoc = check_in_luc is not None and (
            dat_lich_luc.astimezone(CLINIC_TZ).date()
            < check_in_luc.astimezone(CLINIC_TZ).date()
        )
        moc.append(
            _moc(
                "DAT_LICH",
                "Đặt lịch",
                "",
                dat_lich_luc,
                dat_lich_luc,
                XONG,
                hom_truoc=hom_truoc,
            )
        )
    moc.append(
        _moc(
            "CHECK_IN",
            "Check-in",
            "Lễ tân",
            check_in_luc,
            check_in_luc,
            XONG if check_in_luc else CHUA,
        )
    )

    bat = _dau(luc("vitals.started") + luc("vitals.recorded"))
    ket = _cuoi(luc("vitals.recorded"))
    moc.append(_moc("SINH_HIEU", "Đo sinh hiệu", "Điều dưỡng", bat, ket, _tt(bat, ket)))

    tv = luc("consultation.started", loai="TU_VAN")
    if tv:
        bat = min(tv)
        het = [
            t
            for t in luc("consultation.handed_over")
            + luc("consultation.completed", loai="TU_VAN")
            if t >= bat
        ]
        ket = _dau(het)
        moc.append(_moc("TU_VAN", "Tư vấn", "Bàn tư vấn", bat, ket, _tt(bat, ket)))

    bat = _dau(luc("consultation.started", loai="PRIMARY"))
    ket = _cuoi(luc("consultation.completed", loai="PRIMARY")) if bat else None
    moc.append(_moc("KHAM", "Khám bác sĩ chính", "Bàn khám", bat, ket, _tt(bat, ket)))

    if chi_dinh:
        # NHIỀU CHỈ ĐỊNH GỬI CÙNG LÚC = MỘT MỐC: gom theo lần chỉ định.
        theo_lan: dict[int | None, list[datetime]] = {}
        for o in chi_dinh:
            theo_lan.setdefault(o["lan"], []).append(o["tao_luc"])
        gui = sorted(
            ((min(ts), lan, len(ts)) for lan, ts in theo_lan.items()),
            key=lambda g: g[0],
        )
        cac_lan: list[dict[str, Any]] = [
            {"lan": lan, "luc": t, "so": so} for (t, lan, so) in gui
        ]
        moc.append(
            _moc(
                "CHI_DINH",
                "Gửi chỉ định",
                "Bác sĩ",
                gui[0][0],
                gui[-1][0],
                XONG,
                cac_lan=cac_lan,
            )
        )

        lam = [o for o in chi_dinh if o["chon"]]
        if lam:
            # Khách trả TRỰC TIẾP cho đối tác (27/09/2026): không phải khoản
            # quầy thu — không làm mốc "Thu tiền" treo "còn chờ".
            cho_thu = [o for o in lam if not o["da_tra"] and not o.get("doi_tac_thu")]
            thu = luc("payment.service_collected")
            bat = _dau(thu)
            ket = _cuoi(thu) if not cho_thu else None
            moc.append(
                _moc(
                    "THU_TIEN",
                    "Thu tiền dịch vụ",
                    "Quầy thu ngân",
                    bat,
                    ket,
                    XONG if not cho_thu else DANG,
                    con_cho=len(cho_thu),
                )
            )
            so_xong = sum(1 for o in lam if o["xong"])
            bat = _dau(luc("service.started"))
            ket = (
                _cuoi(
                    luc("result.ready")
                    + luc("service.completed")
                    + luc("result_file.uploaded")
                )
                if so_xong == len(lam)
                else None
            )
            noi = list(
                dict.fromkeys(
                    "Đối tác" if o["ngoai"] else (o["phong"] or "Phòng dịch vụ")
                    for o in lam
                )
            )
            moc.append(
                _moc(
                    "LAM_DV",
                    f"Làm dịch vụ ({so_xong}/{len(lam)} xong)",
                    " · ".join(noi),
                    bat,
                    ket,
                    XONG
                    if so_xong == len(lam)
                    else DANG
                    if bat is not None or any(o["da_tra"] for o in lam)
                    else CHUA,
                )
            )

    doc = luc("consultation.started", loai="REVIEW")
    if doc:
        bat = min(doc)
        ket = _cuoi(luc("consultation.completed", loai="REVIEW"))
        moc.append(_moc("DOC_KQ", "Đọc kết quả", "Bàn khám", bat, ket, _tt(bat, ket)))

    if luc("prescription.saved"):
        bat = _dau(luc("payment.medicine_collected"))
        ket = _cuoi(luc("medicine.dispensed"))
        moc.append(_moc("THUOC", "Nhận thuốc", "Quầy thuốc", bat, ket, _tt(bat, ket)))

    moc.append(_moc("VE", "Về", "Check-out", ve_luc, ve_luc, XONG if ve_luc else CHUA))
    return moc


#: Trạng thái MỘT trục của từng chỉ định — cùng trục chip khối 2 của phiếu khám
#: (Chờ thu → Đã thu, chờ làm → Đang làm → Xong); khách bỏ ở quầy thì ra khỏi trục.
BO, CHO_THU, CHO_LAM, DANG_LAM, DA_XONG = "BO", "CHO_THU", "CHO_LAM", "DANG_LAM", "XONG"


def dung_tung_dich_vu(chi_dinh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bảng "Từng dịch vụ" dưới dải mốc (27/09/2026, bản giao diện mẫu).

    Mỗi chỉ định một dòng: gửi → thu → bắt đầu → xong, theo đúng thứ tự gửi.
    CHỈ trả thời điểm; số phút chờ / làm do giao diện tính theo đồng hồ (dòng
    đang chạy phải nhích theo phút, như nhãn trên dải mốc).

    `chi_dinh`: như `dung_moc`, thêm {id, ten, tra_luc, bat_dau_luc, xong_luc,
    dang_lam}. `dang_lam` thiếu thì suy từ `bat_dau_luc`.
    """
    ra: list[dict[str, Any]] = []
    for o in sorted(chi_dinh, key=lambda x: x["tao_luc"]):
        if not o["chon"]:
            tt = BO
        elif o["xong"]:
            tt = DA_XONG
        elif o.get("dang_lam", o.get("bat_dau_luc") is not None):
            tt = DANG_LAM
        elif o["da_tra"] or o.get("doi_tac_thu"):
            tt = CHO_LAM
        else:
            tt = CHO_THU
        ra.append(
            {
                "id": o.get("id"),
                "ten": o.get("ten") or "",
                "lan": o["lan"],
                "noi": "Đối tác" if o["ngoai"] else (o["phong"] or "Phòng dịch vụ"),
                "trang_thai": tt,
                "gui": o["tao_luc"],
                "thu": o.get("tra_luc") if o["da_tra"] else None,
                "bat_dau": o.get("bat_dau_luc"),
                "xong": o.get("xong_luc") if o["xong"] else None,
                # Khách trả TRỰC TIẾP cho đối tác (27/09/2026): "DA_THU" /
                # "CHUA_THU" theo sổ của khối Đối tác; None = phòng khám thu.
                "doi_tac_thu_tien": (
                    ("DA_THU" if o.get("doi_tac_da_thu") else "CHUA_THU")
                    if o.get("doi_tac_thu")
                    else None
                ),
            }
        )
    return ra


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


# Chỉ định của NHIỀU lượt một lần — phiếu khám (một lượt) và Hành trình khách
# (cả ngày, 29/09/2026) dùng chung câu này để hai nơi không lệch nhau.
_SQL_CHI_DINH = """
        SELECT o.visit_id::text AS visit_id, o.id, o.service_name,
               o.lan_chi_dinh, o.created_at,
               o.selection_status, o.execution_status, o.ket_qua_luc,
               o.started_at, o.finished_at, r.name AS phong,
               coalesce(n.lam_ben_ngoai, false) AS ngoai,
               EXISTS (
                   SELECT 1 FROM payment_bill_line bl
                     JOIN payment_cycle c
                       ON c.clinic_id = bl.clinic_id
                      AND c.payment_cycle_id = bl.payment_cycle_id
                    WHERE bl.clinic_id = o.clinic_id
                      AND bl.source_type = 'service_order'
                      AND bl.source_id = o.id::text
                      AND c.status = 'PAID') AS da_tra,
               (SELECT min(c.paid_at) FROM payment_bill_line bl
                  JOIN payment_cycle c
                    ON c.clinic_id = bl.clinic_id
                   AND c.payment_cycle_id = bl.payment_cycle_id
                 WHERE bl.clinic_id = o.clinic_id
                   AND bl.source_type = 'service_order'
                   AND bl.source_id = o.id::text
                   AND c.status = 'PAID') AS tra_luc,
               EXISTS (SELECT 1 FROM service_price sp
                        WHERE sp.clinic_id = o.clinic_id
                          AND sp.service_code = o.service_code
                          AND sp.active AND sp."group" = 'dich_vu'
                          AND sp.billing_owner = 'EXTERNAL_PARTNER')
                 AS doi_tac_thu,
               EXISTS (SELECT 1 FROM doi_tac_thanh_toan tt
                        WHERE tt.clinic_id = o.clinic_id
                          AND tt.service_order_id = o.id
                          AND tt.huy_luc IS NULL) AS doi_tac_da_thu
          FROM service_order o
          LEFT JOIN clinic_room r ON r.id = o.room_id
          LEFT JOIN node_definition n
            ON n.clinic_id = o.clinic_id AND n.code = o.node_code
         WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
           AND o.exec_status NOT IN ('draft', 'cancelled')
           AND coalesce(o.execution_status, '') <> 'CANCELLED'
         ORDER BY o.created_at
"""


def _chi_dinh(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "ten": r["service_name"],
        "lan": r["lan_chi_dinh"],
        "tao_luc": r["created_at"],
        "chon": r["selection_status"] != "NOT_SELECTED",
        "da_tra": bool(r["da_tra"]),
        "xong": r["ket_qua_luc"] is not None
        or (r["execution_status"] == "COMPLETED" and not r["ngoai"]),
        "phong": r["phong"],
        "ngoai": bool(r["ngoai"]),
        "tra_luc": r["tra_luc"],
        "bat_dau_luc": r["started_at"],
        # Đang làm ở phòng; việc đối tác: phòng khám lấy mẫu xong là mẫu
        # đang ở đối tác (chưa có kết quả thì chưa xong).
        "dang_lam": r["execution_status"] == "IN_PROGRESS"
        or (bool(r["ngoai"]) and r["execution_status"] == "COMPLETED"),
        # Có kết quả là "xong" với bác sĩ; chưa có (dịch vụ không có phiếu
        # kết quả) thì giờ làm xong.
        "xong_luc": r["ket_qua_luc"] or r["finished_at"],
        "doi_tac_thu": bool(r["doi_tac_thu"]),
        "doi_tac_da_thu": bool(r["doi_tac_da_thu"]),
        # Hai trường thô cho khung Hành trình khách (29/09/2026): việc đối tác
        # "đã lấy mẫu, chờ kết quả" = COMPLETED mà chưa có kết quả; giờ làm xong
        # ở phòng khám = giờ lấy mẫu.
        "execution_status": r["execution_status"],
        "lam_xong_luc": r["finished_at"],
    }


async def _doc_su_kien_chi_dinh(
    conn: asyncpg.Connection, *, clinic_id: str, visit_ids: list[str]
) -> tuple[dict[str, list[SuKien]], dict[str, list[dict[str, Any]]]]:
    """Sự kiện dòng thời gian + chỉ định, gom theo lượt — 2 câu cho mọi lượt."""
    # Khoá theo chữ thường — Postgres trả uuid dạng thường, người gọi có thể không.
    su_kien: dict[str, list[SuKien]] = {v.lower(): [] for v in visit_ids}
    for r in await conn.fetch(
        "SELECT visit_id::text AS visit_id, event_type, occurred_at, chi_tiet"
        "  FROM luot_dong_thoi_gian"
        " WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])"
        "   AND event_type = ANY($3::text[])"
        " ORDER BY occurred_at, thu_tu",
        clinic_id,
        visit_ids,
        list(_SU_KIEN),
    ):
        ct = r["chi_tiet"]
        if isinstance(ct, str):
            ct = json.loads(ct)
        su_kien.setdefault(r["visit_id"], []).append(
            (r["event_type"], r["occurred_at"], ct or {})
        )
    chi_dinh: dict[str, list[dict[str, Any]]] = {v.lower(): [] for v in visit_ids}
    for r in await conn.fetch(_SQL_CHI_DINH, clinic_id, visit_ids):
        chi_dinh.setdefault(r["visit_id"], []).append(_chi_dinh(r))
    return su_kien, chi_dinh


def _moc_iso(moc: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for m in moc:
        for k in ("bat", "ket"):
            m[k] = _iso(m[k])
        for x in m.get("cac_lan", []):
            x["luc"] = _iso(x["luc"])
    return moc


async def doc_hanh_trinh(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> dict[str, Any] | None:
    """Mốc + "đang ở đâu" của một lượt. None = lượt không thuộc phòng khám này."""
    luot = await conn.fetchrow(
        "SELECT v.status, v.closed_at, v.checked_in_at, a.created_at AS dat_luc"
        "  FROM visit v"
        "  LEFT JOIN appointment a"
        "    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )
    if luot is None:
        return None
    hang = [
        dict(r)
        for r in await conn.fetch(
            "SELECT q.lane, q.status, r.name AS phong, d.full_name AS bac_si"
            "  FROM queue_entry q"
            "  LEFT JOIN clinic_room r ON r.id = q.room_id"
            "  LEFT JOIN staff d ON d.id = q.doctor_staff_id"
            " WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid"
            "   AND q.status IN ('blocked', 'waiting', 'called', 'serving')"
            " ORDER BY q.eligible_at NULLS LAST, q.created_at",
            clinic_id,
            visit_id,
        )
    ]
    su_kien, chi_dinh_theo = await _doc_su_kien_chi_dinh(
        conn, clinic_id=clinic_id, visit_ids=[visit_id]
    )
    chi_dinh = chi_dinh_theo[visit_id.lower()]
    moc = _moc_iso(
        dung_moc(
            dat_lich_luc=luot["dat_luc"],
            check_in_luc=luot["checked_in_at"],
            ve_luc=luot["closed_at"],
            su_kien=su_kien[visit_id.lower()],
            chi_dinh=chi_dinh,
        )
    )
    tung = dung_tung_dich_vu(chi_dinh)
    for d in tung:
        for k in ("gui", "thu", "bat_dau", "xong"):
            d[k] = _iso(d[k])
    return {
        "dang_o": dang_o(
            {"status": luot["status"], "closed_at": luot["closed_at"]}, hang
        ),
        "moc": moc,
        "ngoai_cho": sum(
            1 for o in chi_dinh if o["ngoai"] and o["chon"] and not o["xong"]
        ),
        "tung_dich_vu": tung,
    }


__all__ = ["doc_hanh_trinh", "dung_moc", "dung_tung_dich_vu"]
