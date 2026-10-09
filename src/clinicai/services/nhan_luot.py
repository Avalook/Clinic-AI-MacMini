"""Nhãn đếm LƯỢT của khách — một luật cho mọi màn (Tuyền chốt 08/10/2026).

Luật đếm: mỗi lần CHECK-IN đến khám rồi về = MỘT LƯỢT KHÁM, đếm theo thời gian
trên TOÀN BỘ lượt của khách — không đếm theo dịch vụ hay chuỗi lịch nối nhau
(``lich_truoc_id``). Điều trị đếm theo BUỔI, không ăn số lượt khám.

    lượt nhóm KHÁM / KHÁC (hoặc chưa rõ loại) đã check-in → "Lượt khám n"
    lượt ĐIỀU TRỊ có chỉ định gắn liệu trình               → "Buổi k/N"
    lượt ĐIỀU TRỊ không gắn liệu trình                     → "Điều trị · buổi lẻ"
    lượt MUA THUỐC                                         → "Mua thuốc"
    lịch chưa check-in                                     → "Lịch hẹn"
    lịch huỷ / bác sĩ từ chối                              → "Đã huỷ"
    lịch khách không đến                                   → "Không đến"

Trước 08/10 mỗi màn tự đếm bằng chỉ số mảng trong TSX ("Lần đầu", "Tái khám n",
"Lần n") — mỗi màn một kiểu, và gom theo chuỗi lịch nên hai lượt cùng ngày của
hai dịch vụ đều là "Lần đầu". Nay máy chủ tính MỘT lần (``doc_nhan_luot``), màn
chỉ vẽ trường ``nhan_luot``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import asyncpg

#: Lịch đã check-in (lượt có thật). Lịch có lượt mà đã hoàn tác check-in (lượt
#: còn dòng — booking_service giữ visit) thì KHÔNG đếm.
DA_CHECK_IN = frozenset({"CHECKED_IN", "COMPLETED"})
NHAN_LICH_DONG: dict[str, str] = {
    "CANCELLED": "Đã huỷ",
    "DOCTOR_DECLINED": "Đã huỷ",
    "NO_SHOW": "Không đến",
}
_SOM_NHAT = datetime.min.replace(tzinfo=UTC)


def _moc(v: Any) -> datetime:
    if not isinstance(v, datetime):
        return _SOM_NHAT
    return v if v.tzinfo else v.replace(tzinfo=UTC)


def chu_buoi(so: Any, tong: Any, da_lam: Any) -> str:
    """ "Buổi k/N · đã làm" / "Buổi k/N · chưa làm" — MỘT câu chữ cho mọi màn
    (Tuyền 09/10: số buổi phải nói rõ đã làm hay chưa). Số = thứ tự làm xong
    (``v_lieu_trinh_buoi``). Rác → chuỗi rỗng, không ném. Thuần."""
    try:
        k, n = int(so), int(tong)
    except (TypeError, ValueError):
        return ""
    return f"Buổi {k}/{n} · {'đã làm' if da_lam else 'chưa làm'}"


def gan_nhan(cac_muc: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Nhãn cho mọi lượt / lịch của MỘT khách. Thuần.

    Mỗi mục: ``khoa`` (chuỗi bất kỳ, duy nhất), ``moc`` (giờ check-in, hoặc giờ
    hẹn khi chưa check-in), ``da_check_in``, ``trang_thai_lich`` (status lịch
    hẹn, None nếu lượt không có lịch), ``nhom`` (nhóm loại khám), ``buoi``
    (``(buoi_so, so_buoi, da_lam)`` của chỉ định gắn liệu trình đầu tiên, hoặc
    None; số = thứ tự làm xong, chữ ghi rõ đã làm / chưa làm).

    Trả ``khoa → {nhan, loai, so, buoi}``: ``loai`` ∈ KHAM / DIEU_TRI / THUOC /
    LICH / HUY; ``so`` = thứ tự lượt khám (chỉ loại KHAM); ``buoi`` = "Buổi k/N"
    khi lượt có buổi liệu trình (kể cả lượt khám làm buổi 1 — chip phụ)."""
    ra: dict[str, dict[str, Any]] = {}
    kham: list[tuple[datetime, str]] = []
    for m in cac_muc:
        khoa = str(m.get("khoa") or "")
        if not khoa:
            continue
        b = m.get("buoi")
        buoi = (chu_buoi(*b) or None) if b else None
        nhom = m.get("nhom")
        if not m.get("da_check_in"):
            st = m.get("trang_thai_lich")
            dong = NHAN_LICH_DONG.get(str(st or ""))
            ra[khoa] = {
                "nhan": dong or "Lịch hẹn",
                "loai": "HUY" if dong else "LICH",
                "so": None,
                "buoi": None,
            }
        elif nhom == "DIEU_TRI":
            ra[khoa] = {
                "nhan": buoi or "Điều trị · buổi lẻ",
                "loai": "DIEU_TRI",
                "so": None,
                "buoi": buoi,
            }
        elif nhom == "THUOC":
            ra[khoa] = {"nhan": "Mua thuốc", "loai": "THUOC", "so": None, "buoi": buoi}
        else:
            ra[khoa] = {"nhan": "", "loai": "KHAM", "so": None, "buoi": buoi}
            kham.append((_moc(m.get("moc")), khoa))
    for n, (_luc, khoa) in enumerate(sorted(kham), start=1):
        ra[khoa]["so"] = n
        ra[khoa]["nhan"] = f"Lượt khám {n}"
    return ra


#: MỘT câu (màn khách hàng giữ số câu trên một kết nối): dòng ``v`` = mỗi lượt
#: (+ buổi liệu trình còn sống của chỉ định tạo SỚM NHẤT), dòng ``a`` = lịch chưa
#: có lượt.
_SQL = """
SELECT 'v' AS kieu, v.visit_id::text AS visit_id, v.appointment_id::text AS appt_id,
       v.clinic_patient_id::text AS khach,
       coalesce(v.checked_in_at, v.created_at) AS moc, v.created_at,
       a.status AS trang_thai_lich, st.nhom, bu.buoi_so, bu.so_buoi, bu.da_lam
  FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN public.service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
  LEFT JOIN LATERAL (
       SELECT b.buoi_so, lt.so_buoi, b.da_lam
         FROM public.service_order o
         JOIN public.v_lieu_trinh_buoi b
           ON b.clinic_id = o.clinic_id AND b.service_order_id = o.id
          AND b.go_luc IS NULL
         JOIN public.lieu_trinh lt
           ON lt.clinic_id = b.clinic_id AND lt.id = b.lieu_trinh_id
        WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
        ORDER BY o.created_at, o.id
        LIMIT 1) bu ON true
 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = ANY($2::uuid[])
UNION ALL
SELECT 'a', NULL, a.id::text, a.clinic_patient_id::text, a.slot_start, a.created_at,
       a.status, st.nhom, NULL, NULL, NULL
  FROM public.appointment a
  LEFT JOIN public.service_type st ON st.id = a.service_type_id
 WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = ANY($2::uuid[])
   AND NOT EXISTS (SELECT 1 FROM public.visit v
                    WHERE v.clinic_id = a.clinic_id AND v.appointment_id = a.id)
"""


def _dung_muc(
    luot: Sequence[dict[str, Any]],
    lich: Sequence[dict[str, Any]],
    buoi: dict[str, tuple[int, int, bool]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Gom theo khách thành các mục cho ``gan_nhan``. Một lịch có nhiều lượt
    (check-in lại sau hoàn tác) → MỘT mục, lượt mới nhất; mọi khoá (``a:`` lịch,
    ``v:`` từng lượt) trỏ về mục ấy. Thuần."""
    theo_khach: dict[str, list[dict[str, Any]]] = {}
    tro: dict[str, str] = {}
    dai_dien: dict[str, dict[str, Any]] = {}
    for r in luot:
        goc = f"a:{r['appt_id']}" if r.get("appt_id") else f"v:{r['visit_id']}"
        tro[f"v:{r['visit_id']}"] = goc
        cu = dai_dien.get(goc)
        if cu is None or _moc(r.get("created_at")) > _moc(cu.get("created_at")):
            dai_dien[goc] = dict(r)
    for goc, r in dai_dien.items():
        if r.get("appt_id"):
            tro[goc] = goc
            da = r.get("trang_thai_lich") in DA_CHECK_IN
        else:
            da = True
        theo_khach.setdefault(str(r["khach"]), []).append(
            {
                "khoa": goc,
                "moc": r.get("moc"),
                "da_check_in": da,
                "trang_thai_lich": r.get("trang_thai_lich"),
                "nhom": r.get("nhom"),
                "buoi": buoi.get(str(r["visit_id"])),
            }
        )
    for r in lich:
        goc = f"a:{r['appt_id']}"
        tro[goc] = goc
        theo_khach.setdefault(str(r["khach"]), []).append(
            {
                "khoa": goc,
                "moc": r.get("moc"),
                "da_check_in": False,
                "trang_thai_lich": r.get("trang_thai_lich"),
                "nhom": r.get("nhom"),
                "buoi": None,
            }
        )
    return theo_khach, tro


async def doc_nhan_luot(
    conn: asyncpg.Connection, clinic_id: str, khach_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Nhãn lượt cho mọi lượt + lịch của các khách. Khoá: ``"v:<visit_id>"`` và
    ``"a:<appointment_id>"`` (màn theo lịch hay theo lượt đều tra được)."""
    ids = [str(x) for x in dict.fromkeys(khach_ids) if x]
    if not ids:
        return {}
    rows = [dict(r) for r in await conn.fetch(_SQL, clinic_id, ids)]
    luot = [r for r in rows if r.get("kieu") == "v"]
    lich = [r for r in rows if r.get("kieu") == "a"]
    buoi = {
        str(r["visit_id"]): (int(r["buoi_so"]), int(r["so_buoi"]), bool(r["da_lam"]))
        for r in luot
        if r.get("buoi_so") is not None and r.get("so_buoi") is not None
    }
    theo_khach, tro = _dung_muc(luot, lich, buoi)
    nhan: dict[str, dict[str, Any]] = {}
    for muc in theo_khach.values():
        nhan.update(gan_nhan(muc))
    return {khoa: nhan[goc] for khoa, goc in tro.items() if goc in nhan}


def tra_nhan(
    nhan: dict[str, dict[str, Any]],
    *,
    visit_id: Any = None,
    appointment_id: Any = None,
) -> dict[str, Any] | None:
    """Nhãn của một dòng màn — theo lượt trước, không thì theo lịch."""
    if visit_id and f"v:{visit_id}" in nhan:
        return nhan[f"v:{visit_id}"]
    if appointment_id and f"a:{appointment_id}" in nhan:
        return nhan[f"a:{appointment_id}"]
    return None


__all__ = ["DA_CHECK_IN", "doc_nhan_luot", "gan_nhan", "tra_nhan"]
