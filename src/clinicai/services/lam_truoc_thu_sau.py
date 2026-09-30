"""Tick "Làm trước – thu sau" theo LƯỢT (Tuyền 30/09/2026 tối).

V10 cho MỌI lượt làm trước, thu sau. Tuyền đổi ý: mặc định phải THU TRƯỚC
(dây nối ``thu_truoc_khi_lam``, mặc định BẬT); chỉ lượt được tick "Làm trước –
thu sau" mới xếp phòng / bắt đầu làm khi chưa thu. Cửa ấy nằm ở FinanceGate
(``finance_gate.cua_lam``) — file này chỉ GHI tick và trả CỜ cho màn:

    lam_truoc_thu_sau   lượt đang tick
    tick_duoc           người xem bấm tick được (dây bật + có quyền + lượt mở)
    bo_tick_duoc        người xem bỏ tick được (chưa chỉ định nào bắt đầu làm)
    ly_do_khong_bo      câu vì sao không bỏ được (màn hiện nguyên)
    chot_thu_sau_duoc   quầy được "Chốt, thu sau" (dây tắt, hoặc lượt đã tick)

Lệnh ``SetDeferPayment``:
  * Bật: ghi người + giờ; đồng thời CHỐT các chỉ định còn chờ khách quyết (cùng
    phần ghi của ConfirmServiceSelection — ``ap_lua_chon``), để dây H4 xếp phòng
    như cũ. Phát ``visit.defer_payment_set`` (Hành trình xếp phòng, Đối tác nhận
    việc, dòng thời gian lượt).
  * Tắt: chỉ khi CHƯA chỉ định nào bắt đầu làm — đã làm thì khoản nợ ấy đã là
    "làm trước", bỏ tick là nói dối lịch sử. Phát ``visit.defer_payment_cleared``.

Quyền: ai có lego Bàn khám (chỉ định / hoàn tất khám) HOẶC thu tiền dịch vụ —
hỏi ``can()``, không hỏi vai. Tick = khách đồng ý làm, nên chốt lựa chọn đi
theo quyền tick (không đòi thêm quyền "xác nhận lựa chọn").

Tranh chấp: lệnh khoá dòng ``visit`` trước (cùng thứ tự "visit trước" với Bắt
đầu làm / Thu tiền / Xếp phòng), nên "bỏ tick" và "bắt đầu làm" trên cùng lượt
luôn nối tiếp nhau.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import LamTruocThuSauDaBat, LamTruocThuSauDaBo
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.day_noi import doc_day
from clinicai.services.finance_gate import DAY_THU_TRUOC
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.service_selection_service import (
    _ORDERS_SQL,
    NOT_SELECTED,
    SELECTED,
    OrderFacts,
    SelectionInput,
    ap_lua_chon,
    decision_ids,
    validate_input,
)

ORIGIN = "api:lam-truoc-thu-sau"
EVENT_BAT = "visit.defer_payment_set"
EVENT_BO = "visit.defer_payment_cleared"

#: Một trong các quyền này là đủ tick / bỏ tick (lego Bàn khám hoặc thu tiền
#: dịch vụ — sau V3 "mở full lego" là gần như mọi người).
QUYEN_TICK: tuple[str, ...] = (
    "clinical.order.place",
    "clinical.consult.finalize",
    "payment.service.collect",
)

CAU_KHONG_QUYEN = (
    'Bạn không có quyền tick "Làm trước – thu sau" (cần lego Bàn khám hoặc thu'
    " tiền dịch vụ)."
)
CAU_DA_BAT_DAU = (
    "Đã có dịch vụ bắt đầu làm — không bỏ Làm trước – thu sau được nữa (thu tiền"
    " ở quầy như thường)."
)

#: Chỉ định của lượt ĐÃ bắt đầu làm (đang làm / xong / dừng giữa chừng; trục
#: mới hoặc ``exec_status`` cũ). Bắt đầu nhầm rồi huỷ thì về PENDING — không
#: tính.
_DA_BAT_DAU_SQL = """
EXISTS (
    SELECT 1 FROM public.service_order o
     WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
       AND (o.execution_status IN ('IN_PROGRESS', 'COMPLETED', 'INTERRUPTED')
            OR o.exec_status IN ('in_progress', 'performed'))
)
"""

_TRANG_THAI_SQL = f"""
SELECT v.visit_id::text AS visit_id, v.status, v.closed_at,
       v.lam_truoc_thu_sau_luc AS luc, s.full_name AS boi,
       {_DA_BAT_DAU_SQL} AS da_bat_dau
  FROM public.visit v
  LEFT JOIN public.staff s ON s.id = v.lam_truoc_thu_sau_boi
 WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])
"""


# ---------------------------------------------------------------------------
# Phần thuần
# ---------------------------------------------------------------------------


def co_tick(
    *,
    cong_tac_bat: bool,
    co_quyen: bool,
    da_tick: bool,
    da_bat_dau: bool,
    luot_mo: bool,
) -> dict[str, Any]:
    """Cờ cho màn — máy chủ quyết, màn chỉ đọc. Hàm thuần."""
    if da_tick and da_bat_dau:
        ly_do: str | None = CAU_DA_BAT_DAU
    elif da_tick and not co_quyen:
        ly_do = CAU_KHONG_QUYEN
    else:
        ly_do = None
    return {
        "cong_tac_bat": cong_tac_bat,
        "lam_truoc_thu_sau": da_tick,
        # Dây tắt thì tick vô nghĩa (mọi lượt làm trước được) — không mời tick.
        # Lượt đã tick vẫn hiện để bỏ được / thấy ai bật.
        "hien": cong_tac_bat or da_tick,
        "tick_duoc": cong_tac_bat and co_quyen and luot_mo and not da_tick,
        "bo_tick_duoc": da_tick and co_quyen and not da_bat_dau,
        "ly_do_khong_bo": ly_do,
        "chot_thu_sau_duoc": (not cong_tac_bat) or da_tick,
    }


def trang_thai_dich_vu_lam_truoc(execution_status: Any, exec_status: Any) -> str:
    """Nhãn máy của một dịch vụ trong nhóm "Làm trước – thu sau" ở quầy.

    DA_XONG / DANG_LAM / KHONG_LAM / CHUA_LAM. Hàm thuần; giá trị lạ → CHUA_LAM.
    """
    ex = execution_status if isinstance(execution_status, str) else ""
    cu = exec_status if isinstance(exec_status, str) else ""
    if ex == "COMPLETED" or cu == "performed":
        return "DA_XONG"
    if ex == "IN_PROGRESS" or cu == "in_progress":
        return "DANG_LAM"
    if ex == "NOT_PERFORMED" or cu == "not_performed":
        return "KHONG_LAM"
    return "CHUA_LAM"


NHAN_TRANG_THAI = {
    "DA_XONG": "Đã làm xong",
    "DANG_LAM": "Đang làm",
    "CHUA_LAM": "Chưa làm",
    "KHONG_LAM": "Không làm",
}


def da_lam_xong_het(trang_thai: Sequence[str]) -> bool:
    """Mọi dịch vụ khách làm đã xong (bỏ qua dịch vụ "không làm"). Hàm thuần."""
    con = [t for t in trang_thai if t != "KHONG_LAM"]
    return bool(con) and all(t == "DA_XONG" for t in con)


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v is not None else None


# ---------------------------------------------------------------------------
# Đọc
# ---------------------------------------------------------------------------


async def co_quyen_tick(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_TICK:
        if await can(conn, identity, q):
            return True
    return False


async def trang_thai_lam_truoc(
    conn: asyncpg.Connection, identity: StaffIdentity, visit_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Cờ tick của nhiều lượt — MỘT câu cho lượt, một lần hỏi dây + quyền."""
    ids = sorted({str(v) for v in visit_ids})
    if not ids:
        return {}
    cong_tac = bool(await doc_day(conn, identity.clinic_id, DAY_THU_TRUOC))
    quyen = await co_quyen_tick(conn, identity)
    out: dict[str, dict[str, Any]] = {}
    for r in await conn.fetch(_TRANG_THAI_SQL, identity.clinic_id, ids):
        out[r["visit_id"]] = {
            **co_tick(
                cong_tac_bat=cong_tac,
                co_quyen=quyen,
                da_tick=r["luc"] is not None,
                da_bat_dau=bool(r["da_bat_dau"]),
                # INCOMPLETE (khách về giữa chừng) / đã ký / đã check-out: không
                # mời tick nữa (bỏ tick vẫn được — lệnh cho phép lượt INCOMPLETE).
                luot_mo=r["status"] in ("OPEN", "IN_PROGRESS")
                and r["closed_at"] is None,
            ),
            "bat_boi": r["boi"] if r["luc"] is not None else None,
            "bat_luc": _iso(r["luc"]),
        }
    return out


_DICH_VU_SQL = """
SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
       o.execution_status, o.exec_status
  FROM public.service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
   AND o.selection_status = 'SELECTED'
   AND o.exec_status NOT IN ('draft', 'cancelled')
 ORDER BY o.created_at, o.id
"""


async def dich_vu_lam_truoc(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_ids: Sequence[str],
    con_no: Mapping[str, Mapping[str, int | None]],
) -> dict[str, dict[str, Any]]:
    """Quầy thu: từng dịch vụ khách làm của lượt đã tick — Đã làm xong / Đang
    làm / Chưa làm + số tiền còn nợ (``con_no``: lượt → chỉ định → tiền, lấy từ
    hoá đơn còn nợ quầy đã dựng — không tính giá lần hai)."""
    ids = sorted({str(v) for v in visit_ids})
    if not ids:
        return {}
    out: dict[str, dict[str, Any]] = {v: {"dich_vu": []} for v in ids}
    for r in await conn.fetch(_DICH_VU_SQL, clinic_id, ids):
        tt = trang_thai_dich_vu_lam_truoc(r["execution_status"], r["exec_status"])
        out[r["visit_id"]]["dich_vu"].append(
            {
                "id": r["id"],
                "ten": r["service_name"],
                "trang_thai": tt,
                "nhan": NHAN_TRANG_THAI[tt],
                "con_no": (con_no.get(r["visit_id"]) or {}).get(r["id"]),
            }
        )
    for v in out.values():
        v["da_lam_xong_het"] = da_lam_xong_het([d["trang_thai"] for d in v["dich_vu"]])
    return out


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------


async def _chot_cho_quyet(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    chon: Mapping[str, Any] | None,
) -> list[str]:
    """Chốt chỉ định còn chờ khách quyết — trả các chỉ định vừa thành SELECTED.

    ``chon`` (quầy thu gửi đúng lựa chọn đang tick trên màn) → áp nguyên, lỗi
    thì ném (người bấm cần biết). Không có → mọi chỉ định CHỜ QUYẾT tính là
    khách làm (chỉ định đã "không làm" giữ nguyên); lượt có sổ tiền cũ mơ hồ /
    danh sách vừa đổi thì bỏ qua (tick vẫn ghi — quầy chốt sau).
    """
    cid = identity.clinic_id
    if chon is not None:
        # validate_input đòi khoá gửi lại — lệnh này tự chạy lại được (bật hai
        # lần = một), khoá chỉ để qua cửa kiểm dạng.
        inp = validate_input(
            visit_id=visit_id,
            order_ids_seen=chon.get("order_ids_seen"),
            selected_order_ids=chon.get("selected_order_ids"),
            expected_selection_revision=chon.get("expected_selection_revision"),
            idempotency_key=f"lam-truoc:{visit_id}",
        )
        if not inp.order_ids_seen:
            return []
        return _vua_chon(await ap_lua_chon(conn, identity, inp))

    rows = await conn.fetch(_ORDERS_SQL, cid, visit_id)
    facts = [
        OrderFacts(
            id=r["id"],
            exec_status=r["exec_status"],
            selection_status=r["selection_status"],
            routing_status=r["routing_status"],
            execution_status=r["execution_status"],
            version=int(r["version"]),
            financially_committed=bool(r["financially_committed"]),
            bat_buoc=bool(r["bat_buoc"]),
        )
        for r in rows
    ]
    theo_id = {f.id: f for f in facts}
    con_quyet = sorted(decision_ids(facts))
    cho_quyet = [
        i
        for i in con_quyet
        if theo_id[i].selection_status not in (SELECTED, NOT_SELECTED)
    ]
    if not cho_quyet:
        return []
    revision = await conn.fetchval(
        "SELECT revision FROM service_selection_state"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        cid,
        visit_id,
    )
    inp = SelectionInput(
        visit_id,
        tuple(con_quyet),
        tuple(i for i in con_quyet if theo_id[i].selection_status != NOT_SELECTED),
        int(revision or 0),
    )
    try:
        async with conn.transaction():
            kq = await ap_lua_chon(conn, identity, inp)
    except LuotKhamConflictError:
        return []
    return _vua_chon(kq)


def _vua_chon(kq: Mapping[str, Any]) -> list[str]:
    """Chỉ định vừa chuyển sang "khách làm" trong một lần áp lựa chọn."""
    chon = set(kq["selected_order_ids"])
    return [i for i in kq["changed_order_ids"] if i in chon]


class LamTruocThuSauService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: Any, identity: StaffIdentity) -> dict[str, Any]:
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            kq = (await trang_thai_lam_truoc(conn, identity, [vid])).get(vid)
        if kq is None:
            raise NotFoundError("Không tìm thấy lượt khám này.")
        return {"visit_id": vid, **kq}

    async def dat(
        self,
        *,
        visit_id: Any,
        bat: Any,
        identity: StaffIdentity,
        chon: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """SetDeferPayment — bật / bỏ tick "Làm trước – thu sau" của một lượt."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        if not isinstance(bat, bool):
            raise LuotKhamValidationError("BAD_REQUEST", "Thiếu bật / tắt (bat).")
        if chon is not None and not isinstance(chon, Mapping):
            raise LuotKhamValidationError(
                "BAD_REQUEST", "Lựa chọn dịch vụ không hợp lệ."
            )
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            if not await co_quyen_tick(conn, identity):
                raise SafetyGateError(CAU_KHONG_QUYEN)
            # Khoá lượt TRƯỚC (thứ tự "visit trước" như Bắt đầu làm / Thu tiền).
            # Bỏ tick được cả ở lượt khách đã về giữa chừng (dọn dấu); bật thì
            # chỉ lượt đang mở.
            await khoa_luot(conn, cid, vid, cho_phep_ve_giua_chung=not bat)
            luot = await conn.fetchrow(
                "SELECT v.lam_truoc_thu_sau_luc AS luc,"
                f" {_DA_BAT_DAU_SQL} AS da_bat_dau"
                "  FROM public.visit v"
                " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
                cid,
                vid,
            )
            assert luot is not None
            if bat:
                chot = await _chot_cho_quyet(conn, identity, vid, chon)
                if luot["luc"] is None:
                    await conn.execute(
                        "UPDATE public.visit SET lam_truoc_thu_sau_luc = now(),"
                        " lam_truoc_thu_sau_boi = $3::uuid"
                        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                        cid,
                        vid,
                        identity.staff_id,
                    )
                    await record_event(
                        conn,
                        event_type=EVENT_BAT,
                        aggregate_type="visit",
                        aggregate_id=vid,
                        identity=identity,
                        origin=ORIGIN,
                        payload={"so_chi_dinh_chot": len(chot)},
                    )
                    await emit_event(
                        conn,
                        ten="visit.defer_payment_set",
                        clinic_id=cid,
                        aggregate_id=vid,
                        payload=LamTruocThuSauDaBat(
                            visit_id=vid, so_chi_dinh_chot=len(chot)
                        ),
                        boi=nguoi(identity),
                        correlation_id=vid,
                    )
            elif luot["luc"] is not None:
                if luot["da_bat_dau"]:
                    raise LuotKhamConflictError("DEFER_PAYMENT_STARTED", CAU_DA_BAT_DAU)
                await conn.execute(
                    "UPDATE public.visit SET lam_truoc_thu_sau_luc = NULL,"
                    " lam_truoc_thu_sau_boi = NULL"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                    cid,
                    vid,
                )
                await record_event(
                    conn,
                    event_type=EVENT_BO,
                    aggregate_type="visit",
                    aggregate_id=vid,
                    identity=identity,
                    origin=ORIGIN,
                    payload={},
                )
                await emit_event(
                    conn,
                    ten="visit.defer_payment_cleared",
                    clinic_id=cid,
                    aggregate_id=vid,
                    payload=LamTruocThuSauDaBo(visit_id=vid),
                    boi=nguoi(identity),
                    correlation_id=vid,
                )
            kq = (await trang_thai_lam_truoc(conn, identity, [vid]))[vid]
        return {"ok": True, "visit_id": vid, **kq}


__all__ = [
    "CAU_DA_BAT_DAU",
    "CAU_KHONG_QUYEN",
    "LamTruocThuSauService",
    "QUYEN_TICK",
    "co_tick",
    "da_lam_xong_het",
    "dich_vu_lam_truoc",
    "trang_thai_dich_vu_lam_truoc",
    "trang_thai_lam_truoc",
]
