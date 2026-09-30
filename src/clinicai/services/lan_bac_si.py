"""CHỌN BÁC SĨ TRONG PHÒNG NHIỀU BÁC SĨ (Tuyền chốt 30/09/2026).

"Phòng siêu âm 2 máy — nếu có đủ 2 bác sĩ ở hai máy thì lúc chọn dịch vụ ở node
thanh toán, chọn phòng siêu âm 2 máy rồi thì thêm cả lựa chọn các bác sĩ ở ngày
đó nữa, rất open, để không tách nhỏ phòng ra nữa."

LÀN (migration 20261001250000): mỗi vị trí BAC_SI của phòng là một lựa chọn;
`vi_tri_lam_viec.lan` ghép vị trí bác sĩ với điều dưỡng / thư ký cùng số (một
cặp làm việc). Ghép bằng DỮ LIỆU — không đoán theo tên hay hậu tố mã vị trí.

Lớp này lọc TIẾP trên tập phòng `eligible_rooms` (luật "phòng làm được" ở hàm
Postgres `phong_lam_duoc`) — không tự tính lại phòng nào làm được.

"Bác sĩ đang trực" = dòng lịch (`work_roster`) hôm nay ở vị trí bác sĩ của
phòng, trừ REJECTED, mà CA đang diễn ra theo giờ VN (giờ ca của phòng khám,
`core.shifts`). Không ai đang trong ca (sáng sớm, nghỉ trưa, sau giờ) → cả ngày,
để quầy không mất ô chọn chỉ vì bấm lúc 13:30.

Luật "mở": lựa chọn bác sĩ KHÔNG khoá ai bắt đầu làm. Nó chỉ trả lời "khách này
định đi máy / bác sĩ nào" — in trên phiếu, hiện ở Hành trình, lọc mặc định ở
hàng chờ của người đang trực làn ấy (tắt được).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg

from clinicai.core.clock import now_vn
from clinicai.core.shifts import Window, ca_tu_settings, covers, shift_windows

#: Tối thiểu bao nhiêu bác sĩ trực thì quầy mới hiện ô chọn bác sĩ.
SO_BAC_SI_DE_CHON = 2


@dataclass(frozen=True)
class DongLich:
    """Một dòng lịch của một vị trí trong phòng hôm nay."""

    room_id: str
    vi_tri: str
    lan: int | None
    sort: int
    staff_id: str
    ten: str
    ca: str
    trang_thai: str
    bac_si: bool = True


def ten_bac_si(ten: Any) -> str:
    """ "BS X" — tên đã có chữ "BS" / "Bác sĩ" thì không lặp. Thuần, rác → "BS"."""
    t = " ".join(str(ten).split()) if isinstance(ten, str) else ""
    if not t:
        return "BS"
    return t if t.upper().startswith(("BS", "BÁC SĨ")) else f"BS {t}"


def noi_lam(phong: Any, bac_si: Any) -> str | None:
    """ "Phòng siêu âm 2 máy · BS X" — tên phòng kèm bác sĩ quầy đã chọn (nếu
    có). Thuần; không phòng → None (người gọi tự đặt chữ giữ chỗ)."""
    p = " ".join(str(phong).split()) if isinstance(phong, str) else ""
    if not p:
        return None
    return f"{p} · {ten_bac_si(bac_si)}" if isinstance(bac_si, str) and bac_si else p


def dang_trong_ca(
    dong: Sequence[DongLich], phut: int | None, ca: Mapping[str, Window]
) -> list[DongLich]:
    """Thuần: dòng ĐANG trong ca lúc `phut`; không dòng nào → mọi dòng (cả
    ngày). `phut` None (xem ngày khác hôm nay) → cả ngày. REJECTED luôn bỏ."""
    song = [d for d in dong if d.trang_thai != "REJECTED"]
    if phut is None:
        return song
    dang = [d for d in song if covers(shift_windows(d.ca, 0, 24 * 60, ca), phut)]
    return dang or song


def bac_si_cua_phong(
    dong: Sequence[DongLich], phut: int | None, ca: Mapping[str, Window]
) -> list[dict[str, Any]]:
    """Thuần: các LỰA CHỌN bác sĩ của MỘT phòng — mỗi bác sĩ một lần, theo làn
    (làn nhỏ trước, vị trí không ghi làn sau), rồi thứ tự vị trí."""
    ra: list[dict[str, Any]] = []
    da: set[str] = set()
    for d in sorted(
        (x for x in dang_trong_ca(dong, phut, ca) if x.bac_si),
        key=lambda x: (x.lan is None, x.lan or 0, x.sort, x.vi_tri, x.ten),
    ):
        if d.staff_id in da:
            continue
        da.add(d.staff_id)
        ra.append(
            {
                "staff_id": d.staff_id,
                "ten": ten_bac_si(d.ten),
                "lan": d.lan,
                "vi_tri": d.vi_tri,
            }
        )
    return ra


def can_chon_bac_si(lua_chon: Sequence[Mapping[str, Any]]) -> bool:
    """Thuần: phòng có ≥2 bác sĩ trực → quầy hiện ô chọn bác sĩ."""
    return len({str(x.get("staff_id")) for x in lua_chon}) >= SO_BAC_SI_DE_CHON


def bac_si_tu_gan(lua_chon: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Thuần: phòng có ĐÚNG MỘT bác sĩ trực → tự gán làn ấy (không hỏi ai)."""
    ds = {str(x.get("staff_id")): x for x in lua_chon}
    return next(iter(ds.values())) if len(ds) == 1 else None


def lan_cua_nguoi(
    dong_cua_toi: Sequence[DongLich],
    lua_chon: Sequence[Mapping[str, Any]],
    *,
    toi: str,
    phut: int | None,
    ca: Mapping[str, Window],
) -> dict[str, Any]:
    """Thuần: người đang đăng nhập đứng LÀN nào của phòng hôm nay.

    `dong_cua_toi` — dòng lịch của chính người ấy ở các vị trí của phòng (mọi
    nhóm nghề). Làn = `lan` của các vị trí ấy (đang trong ca, không thì cả
    ngày); bác sĩ đứng vị trí không ghi làn → "làn" của chính họ.
    Trả ``{co, lan, bac_si_ids, nhan}`` — `co` False = không lọc được.
    """
    cua_toi = dang_trong_ca(dong_cua_toi, phut, ca)
    lans = sorted({d.lan for d in cua_toi if d.lan is not None})
    bac_si = {
        str(x["staff_id"])
        for x in lua_chon
        if x.get("lan") is not None and x.get("lan") in lans
    }
    if any(d.bac_si and d.lan is None for d in cua_toi):
        bac_si.add(toi)
    if not lans and not bac_si:
        return {"co": False, "lan": [], "bac_si_ids": [], "nhan": None}
    ten = [str(x["ten"]) for x in lua_chon if str(x["staff_id"]) in bac_si]
    nhan = " · ".join([*(f"Làn {n}" for n in lans), *ten]) or "Làn của tôi"
    return {"co": True, "lan": lans, "bac_si_ids": sorted(bac_si), "nhan": nhan}


def la_khach_lan_toi(
    *,
    bac_si_lam_id: str | None,
    lan_lam: int | None,
    lan_toi: Mapping[str, Any],
) -> bool:
    """Thuần: chỉ định thuộc làn của tôi? Chỉ định CHƯA chọn bác sĩ thì thuộc
    mọi làn (ai trong phòng cũng nhận) — lọc chỉ giấu khách của làn KHÁC."""
    if not lan_toi.get("co"):
        return True
    if not bac_si_lam_id:
        return True
    if lan_lam is not None and lan_lam in (lan_toi.get("lan") or []):
        return True
    return str(bac_si_lam_id) in (lan_toi.get("bac_si_ids") or [])


# ── Đọc DB ──────────────────────────────────────────────────────────────────

_LICH_PHONG_SQL = """
SELECT v.room_id::text AS room_id, v.code AS vi_tri, v.lan, v.sort,
       w.staff_id::text AS staff_id, s.full_name AS ten, w.shift, w.status,
       (v.nhom_nghe = 'BAC_SI') AS bac_si
  FROM public.work_roster w
  JOIN public.vi_tri_lam_viec v
    ON v.clinic_id = w.clinic_id AND v.code = w.station AND v.is_active
  JOIN public.staff s ON s.id = w.staff_id
 WHERE w.clinic_id = $1::uuid
   AND w.work_date = $2::date
   AND v.room_id = ANY($3::uuid[])
   AND w.staff_id IS NOT NULL
   AND w.status <> 'REJECTED'
   AND (v.nhom_nghe = 'BAC_SI' OR w.staff_id = $4::uuid)
"""

#: Khách đang chờ / đang làm của từng bác sĩ được chọn — người thật, lượt check-in
#: HÔM NAY, không đếm chính khách đang được xếp (cùng cách đếm tải của phòng).
_CHO_THEO_BAC_SI_SQL = """
SELECT q.room_id::text AS room_id, o.bac_si_lam_id::text AS staff_id,
       count(DISTINCT q.visit_id)::int AS so
  FROM public.queue_entry q
  JOIN public.service_order o
    ON o.id = q.ref_id AND o.clinic_id = q.clinic_id
  JOIN public.visit vq ON vq.visit_id = q.visit_id AND vq.clinic_id = q.clinic_id
 WHERE q.clinic_id = $1::uuid AND q.reason = 'SERVICE'
   AND q.room_id = ANY($2::uuid[])
   AND q.status IN ('blocked', 'waiting', 'called', 'serving')
   AND o.bac_si_lam_id IS NOT NULL
   AND (vq.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $3::date
   AND ($4::uuid IS NULL OR q.visit_id <> $4::uuid)
 GROUP BY 1, 2
"""


def _dong(r: Mapping[str, Any]) -> DongLich:
    return DongLich(
        room_id=str(r["room_id"]),
        vi_tri=str(r["vi_tri"]),
        lan=int(r["lan"]) if r["lan"] is not None else None,
        sort=int(r["sort"] or 0),
        staff_id=str(r["staff_id"]),
        ten=str(r["ten"] or ""),
        ca=str(r["shift"]),
        trang_thai=str(r["status"]),
        bac_si=bool(r["bac_si"]),
    )


async def _ca_cua(conn: asyncpg.Connection, clinic_id: str) -> dict[str, Window]:
    return ca_tu_settings(
        await conn.fetchval(
            "SELECT settings FROM public.clinic WHERE id = $1::uuid", clinic_id
        )
    )


def _moc(luc: datetime | None, ngay: date | None) -> tuple[date, int | None]:
    """Ngày + phút đang xét. Xem ngày KHÁC hôm nay → cả ngày (phút None)."""
    bay_gio = luc or now_vn()
    if ngay is not None and ngay != bay_gio.date():
        return ngay, None
    return bay_gio.date(), bay_gio.hour * 60 + bay_gio.minute


async def lua_chon_bac_si(
    conn: asyncpg.Connection,
    clinic_id: str,
    room_ids: Iterable[str | None],
    *,
    luc: datetime | None = None,
    tru_luot: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """{phòng: [lựa chọn bác sĩ đang trực + số khách đang chờ của bác sĩ ấy]}.

    Mọi phòng hỏi đều có khoá (rỗng = không bác sĩ nào trên lịch). Hai câu SQL
    cho mọi phòng — quầy gọi một lần cho cả bảng."""
    ids = sorted({str(r) for r in room_ids if r})
    ra: dict[str, list[dict[str, Any]]] = {r: [] for r in ids}
    if not ids:
        return ra
    ngay, phut = _moc(luc, None)
    rows = await conn.fetch(_LICH_PHONG_SQL, clinic_id, ngay, ids, None)
    if not rows:
        return ra
    ca = await _ca_cua(conn, clinic_id)
    theo_phong: dict[str, list[DongLich]] = {}
    for r in rows:
        d = _dong(r)
        theo_phong.setdefault(d.room_id, []).append(d)
    cho = {
        (r["room_id"], r["staff_id"]): int(r["so"])
        for r in await conn.fetch(_CHO_THEO_BAC_SI_SQL, clinic_id, ids, ngay, tru_luot)
    }
    for rid, dong in theo_phong.items():
        ra[rid] = [
            {**x, "dang_cho": cho.get((rid, x["staff_id"]), 0)}
            for x in bac_si_cua_phong(dong, phut, ca)
        ]
    return ra


async def lan_cua_toi_trong_phong(
    conn: asyncpg.Connection,
    clinic_id: str,
    room_id: str,
    staff_id: str,
    *,
    ngay: date | None = None,
    luc: datetime | None = None,
) -> dict[str, Any]:
    """Làn người đăng nhập đứng trong phòng này ở ngày đang xem (hàng chờ)."""
    ngay_xet, phut = _moc(luc, ngay)
    rows = await conn.fetch(_LICH_PHONG_SQL, clinic_id, ngay_xet, [room_id], staff_id)
    dong = [_dong(r) for r in rows]
    cua_toi = [d for d in dong if d.staff_id == staff_id]
    if not cua_toi:
        return {"co": False, "lan": [], "bac_si_ids": [], "nhan": None}
    ca = await _ca_cua(conn, clinic_id)
    return lan_cua_nguoi(
        cua_toi,
        bac_si_cua_phong(dong, phut, ca),
        toi=staff_id,
        phut=phut,
        ca=ca,
    )


__all__ = [
    "SO_BAC_SI_DE_CHON",
    "DongLich",
    "bac_si_cua_phong",
    "bac_si_tu_gan",
    "can_chon_bac_si",
    "dang_trong_ca",
    "la_khach_lan_toi",
    "lan_cua_nguoi",
    "lan_cua_toi_trong_phong",
    "lua_chon_bac_si",
    "noi_lam",
    "ten_bac_si",
]
