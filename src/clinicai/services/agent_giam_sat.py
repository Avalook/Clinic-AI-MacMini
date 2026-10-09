"""AGENT GIÁM SÁT — Layer 1, giai đoạn shadow (09/10/2026).

Anh Quang chốt: Phase 1 theo dõi + giám sát → sau mới đề xuất → người thực thi.
Hợp đồng: `docs/ai/HOP-DONG-AGENT.md`. Bộ nguyên tắc: §3 hiến pháp agent.

LEGO CẮM THÊM. Chạy trong vòng su-kien cạnh bộ canh gác (`canh_gac.py`), mỗi
phút một lượt. Chỉ ĐỌC hiện trạng; chỉ GHI bảng của chính nó
(`agent_nhan_dinh`). Không gọi lệnh của lego nào, không réo chuông ai — giai
đoạn shadow chỉ quản lý thấy ở /ops và chấm đúng/sai. Rút file này ra thì hệ
chạy y nguyên.

CÙNG NGUỒN VỚI MÀN TRƯỞNG CA. Khách chờ / phòng tải đọc qua `DispatchService`,
không viết SQL riêng: hai màn đọc hai nơi là cách chắc nhất để chúng nói hai
điều khác nhau — và agent mà nói khác màn thì không ai chấm được nó đúng hay sai.

RULE, CHƯA CÓ LLM. Hiến pháp §20: rule đủ thì dùng rule. LLM về sau chỉ đọc
bảng nhận định (đã không tên khách) để viết tóm tắt.

Không bao giờ ném: một bộ phát hiện hỏng không được làm chết vòng giao tin, và
KHÔNG được đóng nhầm nhận định của loại đó (chỉ loại xét xong mới được đóng).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.dispatch_service import DispatchService

logger = structlog.get_logger()

#: Ghi vào từng nhận định — đổi luật / ngưỡng là tăng số, để truy được bản nào
#: nói gì (hiến pháp §13, hợp đồng mục A).
PHIEN_BAN = "giam-sat-rule-1"
NHIP_GIAY = 60
#: Lượt còn mở, không ở hàng chờ nào, không sự kiện mới chừng này phút → nghi
#: bị quên (hoặc về mà chưa check-out).
LANG_IM_PHUT = 30
#: Việc quá hạn chừng này giờ → critical.
QUA_HAN_NANG_GIO = 4
#: Trần mỗi bộ phát hiện SQL — chạm trần thì log kêu (core/tran.py), không cắt im.
TRAN = 200

#: Mọi loại nhận định và tên đọc được. Thêm loại = thêm một dòng ở đây + một
#: bộ phát hiện bên dưới.
LOAI: dict[str, str] = {
    "khach_cho_qua_nguong": "Khách đang chờ quá ngưỡng phòng",
    "phong_qua_tai": "Phòng quá tải",
    "khach_chua_xep_buoc": "Khách đã check-in chưa có bước nào",
    "khach_lang_im": "Khách lặng im (không hàng chờ, không sự kiện)",
    "luot_khong_ro_co_so": "Lượt không rõ cơ sở",
    "viec_qua_han": "Việc trách nhiệm quá hạn",
}

#: Nhãn hàng chờ mà khách KHÔNG còn "chờ": đang được làm / đã được gọi / đã về /
#: chờ kết quả đối tác. Màn Trưởng ca báo "chờ lâu" cả những khách này; agent
#: thì không — đó là một chỗ shadow sẽ đo xem ai đúng.
_KHONG_PHAI_CHO = frozenset({"DANG_LAM", "DA_GOI", "KHACH_VE", "CHO_KQ_DOI_TAC"})


@dataclass(frozen=True)
class NhanDinh:
    loai: str
    khoa: str
    muc: str  # warning | critical
    noi_dung: str
    muc_bang_chung: str  # quan_sat | suy_ra
    bang_chung: dict[str, Any] = field(default_factory=dict)
    location_id: str | None = None


# ── Hàm thuần ────────────────────────────────────────────────────────────────


def _so(x: Any) -> int | None:
    """Số nguyên hoặc None — dữ liệu rác không được làm vỡ vòng."""
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x)
    return None


def _so_luot(p: dict[str, Any]) -> str:
    """Tên gọi một lượt KHÔNG lộ khách: số tiếp đón → số thứ tự → 'không số'."""
    for k in ("so_tiep_don", "queue_number", "so_booking"):
        v = p.get(k)
        if v not in (None, ""):
            return f"số {v}"
    return "không số"


def tu_dieu_phoi(
    patients: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
    *,
    location_id: str | None = None,
) -> list[NhanDinh]:
    """Từ hai danh sách của `DispatchService` (overview / stations) → nhận định.

    Không ném với dòng thiếu khoá / sai kiểu: bỏ dòng đó.
    """
    ra: list[NhanDinh] = []
    for p in patients:
        if not isinstance(p, dict):
            continue
        vid = p.get("visit_id")
        if not vid:
            continue
        noi = p.get("current_node_name") or p.get("room_name") or "chưa xếp trạm"
        nhan = p.get("trang_thai") if isinstance(p.get("trang_thai"), dict) else {}
        ma_nhan = nhan.get("ma") if isinstance(nhan, dict) else None
        cho = _so(p.get("wait_minutes"))
        nguong = _so(p.get("threshold_minutes")) or 20
        if (
            cho is not None
            and nguong > 0
            and cho > nguong
            and ma_nhan not in _KHONG_PHAI_CHO
        ):
            ra.append(
                NhanDinh(
                    loai="khach_cho_qua_nguong",
                    khoa=str(vid),
                    muc="critical" if cho > nguong * 2 else "warning",
                    noi_dung=(
                        f"Khách {_so_luot(p)} chờ {cho} phút tại {noi}"
                        f" (ngưỡng {nguong} phút)."
                    ),
                    muc_bang_chung="quan_sat",
                    bang_chung={
                        "visit_id": str(vid),
                        "cho_phut": cho,
                        "nguong_phut": nguong,
                        "buoc": p.get("current_node_code"),
                        "phong": p.get("room_code"),
                        "nhan_hang_cho": ma_nhan,
                    },
                    location_id=location_id,
                )
            )
        if not p.get("current_node_code") and ma_nhan != "KHACH_VE":
            ra.append(
                NhanDinh(
                    loai="khach_chua_xep_buoc",
                    khoa=str(vid),
                    muc="warning",
                    noi_dung=f"Khách {_so_luot(p)} đã check-in nhưng chưa có bước nào.",
                    muc_bang_chung="quan_sat",
                    bang_chung={
                        "visit_id": str(vid),
                        "tong_phut": _so(p.get("total_minutes")),
                        "nhan_hang_cho": ma_nhan,
                    },
                    location_id=location_id,
                )
            )
    for r in rooms:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        state = r.get("state")
        if state not in ("warning", "critical"):
            continue
        ra.append(
            NhanDinh(
                loai="phong_qua_tai",
                khoa=str(r["id"]),
                muc=state,
                noi_dung=(
                    f"{r.get('name') or r.get('code') or 'Phòng'}: "
                    f"{_so(r.get('waiting')) or 0} người chờ, lâu nhất "
                    f"{_so(r.get('max_wait')) or 0} phút (ngưỡng "
                    f"{_so(r.get('threshold_waiting'))} người / "
                    f"{_so(r.get('threshold_minutes'))} phút)."
                ),
                muc_bang_chung="quan_sat",
                bang_chung={
                    "room_id": str(r["id"]),
                    "phong": r.get("code"),
                    "dang_cho": _so(r.get("waiting")),
                    "dang_lam": _so(r.get("serving")),
                    "cho_lau_nhat_phut": _so(r.get("max_wait")),
                },
                location_id=location_id,
            )
        )
    return ra


def che_do_hieu_luc(cau_hinh: dict[str, str], loai: str) -> str:
    """'*' = 'tat' tắt HẾT (công tắc khẩn thắng mọi dòng riêng); không thì dòng
    riêng của loại; không có gì thì 'shadow'."""
    if cau_hinh.get("*") == "tat":
        return "tat"
    return cau_hinh.get(loai) or cau_hinh.get("*") or "shadow"


# ── Đọc (chỉ SELECT) ─────────────────────────────────────────────────────────

# Chỉ lượt OPEN / IN_PROGRESS là "đang ở phòng khám". INCOMPLETE (khách về giữa
# chừng, `visit.left_early`, có lý do) cố ý KHÔNG xét: khách đã đi, lượt đã khép
# có chủ đích — báo "lặng im" cho họ là báo sai. Cùng tập trạng thái với màn
# Trưởng ca (`dispatch_service.LIVE_VISIT_STATUSES`).
_DAU_NGAY = (
    "(date_trunc('day', $2::timestamptz AT TIME ZONE 'Asia/Ho_Chi_Minh')"
    " AT TIME ZONE 'Asia/Ho_Chi_Minh')"
)

_LANG_IM_SQL = f"""
SELECT v.visit_id::text                        AS visit_id,
       coalesce(v.location_id, a.location_id)::text AS location_id,
       a.so_tiep_don, a.queue_number,
       coalesce(e.occurred_at, v.checked_in_at) AS lan_cuoi,
       e.event_type                            AS su_kien_cuoi
  FROM public.visit v
  LEFT JOIN public.appointment a ON a.id = v.appointment_id
  LEFT JOIN LATERAL (
      SELECT d.occurred_at, d.event_type
        FROM public.domain_event d
       WHERE d.clinic_id = v.clinic_id AND d.correlation_id = v.visit_id
       ORDER BY d.occurred_at DESC
       LIMIT 1
  ) e ON TRUE
 WHERE v.clinic_id = $1::uuid
   AND v.status IN ('OPEN', 'IN_PROGRESS')
   AND v.closed_at IS NULL
   AND NOT v.ban_le
   AND v.checked_in_at IS NOT NULL
   AND v.current_node_code IS DISTINCT FROM 'LUOTKHAM-15'
   AND v.checked_in_at >= {_DAU_NGAY}
   AND NOT EXISTS (
       SELECT 1 FROM public.queue_entry q
        WHERE q.clinic_id = v.clinic_id AND q.visit_id = v.visit_id
          AND q.status IN ('blocked', 'waiting', 'called', 'serving'))
   AND coalesce(e.occurred_at, v.checked_in_at)
       < $2::timestamptz - make_interval(mins => $3)
 LIMIT {TRAN}
"""

_KHONG_RO_CO_SO_SQL = f"""
SELECT v.visit_id::text AS visit_id, a.so_tiep_don, a.queue_number
  FROM public.visit v
  LEFT JOIN public.appointment a ON a.id = v.appointment_id
 WHERE v.clinic_id = $1::uuid
   AND v.status IN ('OPEN', 'IN_PROGRESS')
   AND v.closed_at IS NULL
   AND coalesce(v.checked_in_at, v.created_at) >= {_DAU_NGAY}
   AND coalesce(v.location_id, a.location_id) IS NULL
   AND (SELECT count(*) FROM public.clinic_location l
         WHERE l.clinic_id = $1::uuid AND l.is_active) >= 2
 LIMIT {TRAN}
"""

_QUA_HAN_SQL = f"""
SELECT w.id::text AS id, w.node_code, w.due_at, w.visit_id::text AS visit_id,
       coalesce(v.location_id, a.location_id)::text AS location_id,
       n.name AS ten_viec
  FROM public.work_item w
  LEFT JOIN public.visit v ON v.visit_id = w.visit_id
  LEFT JOIN public.appointment a ON a.id = v.appointment_id
  LEFT JOIN public.node_definition n
         ON n.clinic_id = w.clinic_id AND n.code = w.node_code
 WHERE w.clinic_id = $1::uuid
   AND w.status IN ('PENDING', 'IN_PROGRESS')
   AND w.due_at IS NOT NULL
   AND w.due_at < $2::timestamptz
 LIMIT {TRAN}
"""


def _phut(tu: Any, den: datetime) -> int | None:
    if not isinstance(tu, datetime):
        return None
    return max(0, int((den - tu).total_seconds() // 60))


async def phat_hien_sql(
    conn: asyncpg.Connection, clinic_id: str, luc: datetime
) -> dict[str, list[NhanDinh]]:
    """Ba bộ phát hiện đọc thẳng SQL. Trả theo loại — loại nào có khoá ở đây là
    đã XÉT XONG (kể cả danh sách rỗng)."""
    ra: dict[str, list[NhanDinh]] = {}

    rows = await conn.fetch(_LANG_IM_SQL, clinic_id, luc, LANG_IM_PHUT)
    canh_bao_neu_day("agent.khach_lang_im", len(rows), TRAN, clinic_id=clinic_id)
    ra["khach_lang_im"] = [
        NhanDinh(
            loai="khach_lang_im",
            khoa=r["visit_id"],
            muc="warning",
            noi_dung=(
                f"Khách {_so_luot(dict(r))} không ở hàng chờ nào và "
                f"{_phut(r['lan_cuoi'], luc)} phút chưa có sự kiện mới"
                f" (cuối: {r['su_kien_cuoi'] or 'check-in'}) — có thể bị quên,"
                " hoặc đã về mà chưa check-out."
            ),
            # Đoán từ chỗ VẮNG sự kiện — không phải điều quan sát được (§8).
            muc_bang_chung="suy_ra",
            bang_chung={
                "visit_id": r["visit_id"],
                "su_kien_cuoi": r["su_kien_cuoi"],
                "lan_cuoi": r["lan_cuoi"].isoformat() if r["lan_cuoi"] else None,
            },
            location_id=r["location_id"],
        )
        for r in rows
    ]

    rows = await conn.fetch(_KHONG_RO_CO_SO_SQL, clinic_id, luc)
    canh_bao_neu_day("agent.luot_khong_ro_co_so", len(rows), TRAN, clinic_id=clinic_id)
    ra["luot_khong_ro_co_so"] = [
        NhanDinh(
            loai="luot_khong_ro_co_so",
            khoa=r["visit_id"],
            muc="warning",
            noi_dung=(
                f"Lượt của khách {_so_luot(dict(r))} không gắn cơ sở nào trong khi"
                " phòng khám đang mở nhiều cơ sở — màn của cơ sở nào cũng có thể"
                " thấy hoặc bỏ sót lượt này."
            ),
            muc_bang_chung="quan_sat",
            bang_chung={"visit_id": r["visit_id"]},
        )
        for r in rows
    ]

    rows = await conn.fetch(_QUA_HAN_SQL, clinic_id, luc)
    canh_bao_neu_day("agent.viec_qua_han", len(rows), TRAN, clinic_id=clinic_id)
    ra["viec_qua_han"] = [
        NhanDinh(
            loai="viec_qua_han",
            khoa=r["id"],
            muc=(
                "critical"
                if r["due_at"] < luc - timedelta(hours=QUA_HAN_NANG_GIO)
                else "warning"
            ),
            noi_dung=(
                f"Việc '{r['ten_viec'] or r['node_code']}' quá hạn "
                f"{_phut(r['due_at'], luc)} phút, vẫn chưa xong."
            ),
            muc_bang_chung="quan_sat",
            bang_chung={
                "work_item_id": r["id"],
                "node_code": r["node_code"],
                "visit_id": r["visit_id"],
                "han": r["due_at"].isoformat(),
            },
            location_id=r["location_id"],
        )
        for r in rows
    ]
    return ra


async def _co_so_dang_mo(conn: asyncpg.Connection, clinic_id: str) -> list[str | None]:
    rows = await conn.fetch(
        "SELECT id::text FROM clinic_location"
        " WHERE clinic_id = $1::uuid AND is_active ORDER BY id",
        clinic_id,
    )
    return [r["id"] for r in rows] or [None]


async def phat_hien_dieu_phoi(
    pool: asyncpg.Pool, clinic_id: str, co_so: list[str | None]
) -> dict[str, list[NhanDinh]]:
    """Ba loại đọc qua màn Trưởng ca, xét theo TỪNG cơ sở (ngưỡng/tải là của cơ
    sở). Lượt không rõ cơ sở hiện ở mọi cơ sở → khoá trùng chỉ giữ lần đầu."""
    dv = DispatchService(pool)
    ra: dict[str, list[NhanDinh]] = {
        "khach_cho_qua_nguong": [],
        "khach_chua_xep_buoc": [],
        "phong_qua_tai": [],
    }
    da_co: set[tuple[str, str]] = set()
    for loc in co_so:
        patients = await dv.overview(clinic_id=clinic_id, location_id=loc)
        rooms = await dv.stations(clinic_id=clinic_id, location_id=loc)
        for n in tu_dieu_phoi(patients, rooms, location_id=loc):
            if (n.loai, n.khoa) in da_co:
                continue
            da_co.add((n.loai, n.khoa))
            ra[n.loai].append(n)
    return ra


async def doc_cau_hinh(conn: asyncpg.Connection, clinic_id: str) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT loai, che_do FROM agent_cau_hinh WHERE clinic_id = $1::uuid",
        clinic_id,
    )
    return {r["loai"]: r["che_do"] for r in rows}


# ── Ghi (chỉ bảng của agent) ─────────────────────────────────────────────────


async def ap_dung(
    conn: asyncpg.Connection,
    clinic_id: str,
    theo_loai: dict[str, list[NhanDinh]],
    tat: set[str],
) -> dict[str, int]:
    """Mở / cộng dồn nhận định của các loại ĐÃ XÉT; đóng 'HET' cái không còn;
    đóng 'TAT' mọi cái đang mở của loại bị tắt. Một giao dịch."""
    mo_moi = dong = 0
    async with conn.transaction():
        for loai, ds in theo_loai.items():
            for n in ds:
                moi = await conn.fetchval(
                    """
                    INSERT INTO agent_nhan_dinh
                        (clinic_id, location_id, loai, khoa, muc, noi_dung,
                         muc_bang_chung, bang_chung, agent_version)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8::jsonb, $9)
                    ON CONFLICT (clinic_id, loai, khoa) WHERE dong_luc IS NULL
                    DO UPDATE SET so_lan = agent_nhan_dinh.so_lan + 1,
                                  lan_cuoi = now(),
                                  muc = EXCLUDED.muc,
                                  noi_dung = EXCLUDED.noi_dung,
                                  bang_chung = EXCLUDED.bang_chung,
                                  agent_version = EXCLUDED.agent_version
                    RETURNING (xmax = 0)
                    """,
                    clinic_id,
                    n.location_id,
                    n.loai,
                    n.khoa,
                    n.muc,
                    n.noi_dung,
                    n.muc_bang_chung,
                    json.dumps(n.bang_chung, ensure_ascii=False, default=str),
                    PHIEN_BAN,
                )
                mo_moi += 1 if moi else 0
            kq = await conn.execute(
                """
                UPDATE agent_nhan_dinh SET dong_luc = now(), ly_do_dong = 'HET'
                 WHERE clinic_id = $1::uuid AND loai = $2 AND dong_luc IS NULL
                   AND NOT (khoa = ANY($3::text[]))
                """,
                clinic_id,
                loai,
                [n.khoa for n in ds],
            )
            dong += int(str(kq).split()[-1])
        if tat:
            kq = await conn.execute(
                """
                UPDATE agent_nhan_dinh SET dong_luc = now(), ly_do_dong = 'TAT'
                 WHERE clinic_id = $1::uuid AND loai = ANY($2::text[])
                   AND dong_luc IS NULL
                """,
                clinic_id,
                sorted(tat),
            )
            dong += int(str(kq).split()[-1])
    return {"mo_moi": mo_moi, "dong": dong}


async def mot_vong_phong_kham(
    pool: asyncpg.Pool, clinic_id: str, luc: datetime | None = None
) -> dict[str, int]:
    """Một lượt cho một phòng khám. Bộ phát hiện hỏng → loại của nó KHÔNG được
    xét (không đóng nhầm), các loại khác vẫn chạy."""
    async with pool.acquire() as conn:
        cau_hinh = await doc_cau_hinh(conn, clinic_id)
        luc = luc or await conn.fetchval("SELECT now()")
        co_so = await _co_so_dang_mo(conn, clinic_id)
    tat = {loai for loai in LOAI if che_do_hieu_luc(cau_hinh, loai) == "tat"}
    if tat == set(LOAI):
        # TẮT HẲN: không đọc gì, không phát hiện gì — chỉ đóng phần còn mở.
        async with pool.acquire() as conn:
            return await ap_dung(conn, clinic_id, {}, tat)

    theo_loai: dict[str, list[NhanDinh]] = {}
    try:
        theo_loai.update(await phat_hien_dieu_phoi(pool, clinic_id, co_so))
    except Exception:  # noqa: BLE001 — một bộ hỏng không được kéo cả vòng
        logger.exception("agent_giam_sat_dieu_phoi_hong", clinic_id=clinic_id)
    try:
        async with pool.acquire() as conn:
            theo_loai.update(await phat_hien_sql(conn, clinic_id, luc))
    except Exception:  # noqa: BLE001
        logger.exception("agent_giam_sat_sql_hong", clinic_id=clinic_id)

    theo_loai = {k: v for k, v in theo_loai.items() if k not in tat}
    async with pool.acquire() as conn:
        return await ap_dung(conn, clinic_id, theo_loai, tat)


async def mot_vong(pool: asyncpg.Pool, luc: datetime | None = None) -> None:
    """Một lượt agent cho mọi phòng khám. Không bao giờ ném."""
    try:
        clinics = [str(r["id"]) for r in await pool.fetch("SELECT id FROM clinic")]
    except Exception:  # noqa: BLE001
        logger.exception("agent_giam_sat_hong")
        return
    for cid in clinics:
        try:
            kq = await mot_vong_phong_kham(pool, cid, luc)
            if kq["mo_moi"] or kq["dong"]:
                logger.info("agent_giam_sat", clinic_id=cid, **kq)
        except Exception:  # noqa: BLE001
            logger.exception("agent_giam_sat_hong", clinic_id=cid)


# ── Cho màn /ops ─────────────────────────────────────────────────────────────


def _json_dong(r: asyncpg.Record) -> dict[str, Any]:
    d = dict(r)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    if isinstance(d.get("bang_chung"), str):
        d["bang_chung"] = json.loads(d["bang_chung"])
    d["ten_loai"] = LOAI.get(d.get("loai") or "", d.get("loai"))
    return d


async def danh_sach(
    pool: asyncpg.Pool, *, clinic_id: str, chi_dang_mo: bool, gioi_han: int = 200
) -> dict[str, Any]:
    """Nhận định (đang mở trước), thống kê độ đúng 14 ngày theo loại, công tắc."""
    gioi_han = max(1, min(int(gioi_han), 500))
    rows = await pool.fetch(
        """
        SELECT id::text, location_id::text, loai, khoa, muc, noi_dung,
               muc_bang_chung, bang_chung, agent_version, so_lan, mo_luc,
               lan_cuoi, dong_luc, ly_do_dong, danh_gia, danh_gia_ghi_chu,
               danh_gia_luc
          FROM agent_nhan_dinh
         WHERE clinic_id = $1::uuid AND ($2::boolean IS FALSE OR dong_luc IS NULL)
         ORDER BY (dong_luc IS NULL) DESC,
                  CASE muc WHEN 'critical' THEN 0 ELSE 1 END, lan_cuoi DESC
         LIMIT $3
        """,
        clinic_id,
        chi_dang_mo,
        gioi_han,
    )
    bi_cat = canh_bao_neu_day(
        "agent.nhan_dinh", len(rows), gioi_han, clinic_id=clinic_id
    )
    tk = await pool.fetch(
        """
        SELECT loai,
               count(*) FILTER (WHERE dong_luc IS NULL)      AS dang_mo,
               count(*)                                      AS tong,
               count(*) FILTER (WHERE danh_gia = 'dung')     AS dung,
               count(*) FILTER (WHERE danh_gia = 'sai')      AS sai,
               count(*) FILTER (WHERE danh_gia = 'khong_ro') AS khong_ro
          FROM agent_nhan_dinh
         WHERE clinic_id = $1::uuid AND mo_luc > now() - interval '14 days'
         GROUP BY loai
        """,
        clinic_id,
    )
    async with pool.acquire() as conn:
        cau_hinh = await doc_cau_hinh(conn, clinic_id)
    theo = {r["loai"]: dict(r) for r in tk}
    thong_ke = []
    for loai, ten in LOAI.items():
        t = theo.get(loai, {})
        dung, sai = int(t.get("dung", 0)), int(t.get("sai", 0))
        thong_ke.append(
            {
                "loai": loai,
                "ten": ten,
                "che_do": che_do_hieu_luc(cau_hinh, loai),
                "dang_mo": int(t.get("dang_mo", 0)),
                "tong_14_ngay": int(t.get("tong", 0)),
                "dung": dung,
                "sai": sai,
                "khong_ro": int(t.get("khong_ro", 0)),
                # Độ đúng chỉ tính trên số đã chấm đúng/sai; chưa chấm → None.
                "do_dung": round(dung / (dung + sai), 2) if dung + sai else None,
            }
        )
    return {
        "phien_ban": PHIEN_BAN,
        "tat_het": cau_hinh.get("*") == "tat",
        "thong_ke": thong_ke,
        "nhan_dinh": [_json_dong(r) for r in rows],
        # Chạm trần → màn phải nói "đang hiện N cái mới nhất", không im.
        "bi_cat": bi_cat,
        "tran": gioi_han,
    }


DANH_GIA = ("dung", "sai", "khong_ro")


async def danh_gia(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    nhan_dinh_id: str,
    gia_tri: str | None,
    ghi_chu: str | None,
    staff_id: str,
) -> bool:
    """Người quản lý chấm một nhận định. `gia_tri=None` = bỏ chấm (hoàn tác
    được, luật 'mọi thao tác hoàn tác được'). Trả False nếu không thấy."""
    if gia_tri is not None and gia_tri not in DANH_GIA:
        raise ValueError(f"Đánh giá không hợp lệ: {gia_tri!r}")
    kq = await pool.execute(
        """
        UPDATE agent_nhan_dinh
           SET danh_gia = $3,
               danh_gia_ghi_chu = CASE WHEN $3::text IS NULL THEN NULL
                                       ELSE nullif(trim($4), '') END,
               danh_gia_boi = CASE WHEN $3::text IS NULL THEN NULL
                                   ELSE $5::uuid END,
               danh_gia_luc = CASE WHEN $3::text IS NULL THEN NULL ELSE now() END
         WHERE clinic_id = $1::uuid AND id = $2::uuid
        """,
        clinic_id,
        nhan_dinh_id,
        gia_tri,
        (ghi_chu or "")[:500],
        staff_id,
    )
    return str(kq).endswith(" 1")


CHE_DO = ("tat", "shadow")


async def dat_che_do(
    pool: asyncpg.Pool, *, clinic_id: str, loai: str, che_do: str, staff_id: str
) -> None:
    """Bật/tắt một loại (hoặc '*' = mọi loại). Có hiệu lực ở vòng kế (≤ 1 phút).
    Tắt → vòng kế đóng các nhận định đang mở của loại đó ('TAT')."""
    if loai != "*" and loai not in LOAI:
        raise ValueError(f"Loại nhận định không có: {loai!r}")
    if che_do not in CHE_DO:
        raise ValueError(f"Chế độ không hợp lệ: {che_do!r}")
    await pool.execute(
        """
        INSERT INTO agent_cau_hinh (clinic_id, loai, che_do, cap_nhat_boi)
        VALUES ($1::uuid, $2, $3, $4::uuid)
        ON CONFLICT (clinic_id, loai) DO UPDATE
           SET che_do = EXCLUDED.che_do, cap_nhat_luc = now(),
               cap_nhat_boi = EXCLUDED.cap_nhat_boi
        """,
        clinic_id,
        loai,
        che_do,
        staff_id,
    )
    if che_do == "tat":
        # Đóng NGAY trong lệnh bấm — chờ vòng quét sau (tới 1 phút) thì người
        # bấm thấy như công tắc không ăn.
        await pool.execute(
            """
            UPDATE agent_nhan_dinh SET dong_luc = now(), ly_do_dong = 'TAT'
             WHERE clinic_id = $1::uuid AND dong_luc IS NULL
               AND ($2 = '*' OR loai = $2)
            """,
            clinic_id,
            loai,
        )


async def tat_het(conn: asyncpg.Connection, clinic_id: str) -> bool:
    """Công tắc '*' đang tắt? Tắt hết = dừng cả tóm tắt AI (không tốn tiền)."""
    return che_do_hieu_luc(await doc_cau_hinh(conn, clinic_id), "*") == "tat"
