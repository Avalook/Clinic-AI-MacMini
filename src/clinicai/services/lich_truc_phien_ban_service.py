"""Lịch trực có lịch sử thay đổi — kiểu lịch sử Google Docs (Khối 3, Tuyền 06/10/2026).

Trưởng ca cần xem lại lịch của một tuần ở từng thời điểm: lịch gốc lúc áp dụng
tuần, rồi mỗi lần đổi người / xoá ca / thêm người vào ca trống là một phiên bản,
ô đổi được tô màu so với bản ngay trước.

GHI ở tầng Postgres (migration `20261006300000_lich_truc_phien_ban.sql`):
trigger trên `work_roster` ghi sổ `lich_truc_thay_doi`, trigger trên
`roster_week` chụp ảnh tuần `lich_truc_anh`. Ở đây chỉ còn hai việc:

  * ``dat_nguoi_bam`` / ``giao_dich_lich_truc`` — mọi lối ghi lịch trực đặt
    người bấm vào giao dịch (`app.staff_id`) để trigger biết ai sửa. Quên đặt
    thì sổ vẫn ghi, chỉ thiếu tên — không bao giờ chặn thao tác.
  * ``LichTrucPhienBanService.xem`` — dựng danh sách phiên bản + bảng lịch tại
    một phiên bản + phần khác so với bản trước.

MỘT PHIÊN BẢN = MỘT GIAO DỊCH (txid). Dựng lại = ảnh gần nhất ≤ phiên bản + các
thay đổi sau ảnh theo thứ tự (txid, id). Phần khác tính bằng SO HAI TRẠNG THÁI
(không đọc thẳng dòng sổ) nên ảnh áp dụng lại, nhiều thay đổi trong một giao
dịch, ca chuyển chỗ… đều ra cùng ba loại người xem cần: THÊM / XOÁ / ĐỔI NGƯỜI.

Chỉ ca ĐÃ DUYỆT (`APPROVED`) có mặt trên bảng — cùng luật với "Lịch làm việc
chính thức" — nên một ca chuyển sang APPROVED hiện là THÊM.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.nhan_vai import nhan_vai

#: Phần khác giữa hai bản: {"them": [...], "xoa": [...], "doi_nguoi": [...]}.
KhacNhau = dict[str, list[dict[str, Any]]]

#: Loại phiên bản trả cho giao diện. Ba loại đầu là ẢNH (cả tuần), loại cuối là
#: một giao dịch sửa ô.
LOAI_ANH = ("GOC", "AP_DUNG_LAI", "LEN_BAN")
LOAI_THAY_DOI = "THAY_DOI"


# ── Người bấm ────────────────────────────────────────────────────────────────
async def dat_nguoi_bam(conn: asyncpg.Connection, staff_id: str | None) -> None:
    """Đặt người bấm cho trigger lịch trực, CHỈ trong giao dịch đang mở.

    `set_config(..., true)` = SET LOCAL: hết giao dịch là hết, nên kết nối trả
    về hồ không mang tên người này sang lượt của người khác. Gọi ngoài giao dịch
    thì nó mất ngay sau câu lệnh — lỗi lập trình, ném luôn cho lộ ở test.
    """
    if not conn.is_in_transaction():
        raise RuntimeError(
            "dat_nguoi_bam phải gọi trong conn.transaction() — SET LOCAL ngoài "
            "giao dịch mất ngay sau câu lệnh, sổ lịch trực sẽ thiếu người bấm."
        )
    await conn.execute(
        "SELECT set_config('app.staff_id', $1, true)", str(staff_id or "")
    )


@asynccontextmanager
async def giao_dich_lich_truc(
    conn: asyncpg.Connection, staff_id: str | None
) -> AsyncIterator[None]:
    """Mở giao dịch (hoặc savepoint nếu đã ở trong một giao dịch) và đặt người
    bấm — bọc quanh câu ghi `work_roster` / `roster_week` của lối chưa có giao
    dịch riêng."""
    async with conn.transaction():
        await dat_nguoi_bam(conn, staff_id)
        yield


# ── Đọc đầu vào người dùng: rác → None, không ném ────────────────────────────
def doc_tuan(raw: object) -> date | None:
    """Ngày bất kỳ trong tuần (`YYYY-MM-DD` hoặc `date`) → thứ Hai. Rác → None."""
    if isinstance(raw, datetime):
        raw = raw.date()
    if isinstance(raw, date):
        d: date | None = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            d = date.fromisoformat(raw.strip()[:10])
        except ValueError:
            d = None
    else:
        d = None
    if d is None:
        return None
    try:
        return d - timedelta(days=d.weekday())
    except OverflowError:
        return None


def doc_ban(raw: object) -> int | None:
    """Mã phiên bản (txid) từ URL. Rác / âm / rỗng → None (= bản mới nhất)."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s.isdigit() or len(s) > 19:
        return None
    n = int(s)
    return n if n > 0 else None


# ── Dựng phiên bản (thuần, test được không cần DB) ───────────────────────────
@dataclass
class PhienBan:
    txid: int
    loai: str
    luc: datetime | None
    boi_staff_id: str | None
    #: roster_id → ô (mọi trạng thái); lọc APPROVED khi so / trình bày.
    trang_thai: dict[str, dict[str, Any]] = field(default_factory=dict)


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


def dung_phien_ban(
    anh: list[dict[str, Any]], thay_doi: list[dict[str, Any]]
) -> list[PhienBan]:
    """Ảnh + sổ → các phiên bản theo thứ tự thời gian (cũ trước).

    Lịch sử bắt đầu ở ẢNH ĐẦU TIÊN; thay đổi trước đó là lúc xếp nháp, không phải
    phiên bản. Một giao dịch vừa có ảnh vừa có thay đổi → ảnh thắng (ảnh đã là
    trạng thái cả tuần lúc ấy)."""
    anh = sorted(anh, key=lambda a: (int(a["txid"]), int(a["id"])))
    if not anh:
        return []
    moc = int(anh[0]["txid"])
    txid_anh = {int(a["txid"]) for a in anh}
    nhom: dict[int, list[dict[str, Any]]] = {}
    for t in sorted(thay_doi, key=lambda t: (int(t["txid"]), int(t["id"]))):
        tx = int(t["txid"])
        if tx <= moc or tx in txid_anh:
            continue
        nhom.setdefault(tx, []).append(t)

    muc: list[tuple[int, str, Any]] = [(int(a["txid"]), "ANH", a) for a in anh]
    muc += [(tx, "DOI", ds) for tx, ds in nhom.items()]
    muc.sort(key=lambda m: m[0])

    ket: list[PhienBan] = []
    trang_thai: dict[str, dict[str, Any]] = {}
    for tx, kieu, du_lieu in muc:
        if kieu == "ANH":
            a = du_lieu
            trang_thai = {
                str(o["id"]): dict(o) for o in (_json(a["ca"]) or []) if o.get("id")
            }
            ket.append(
                PhienBan(
                    txid=tx,
                    loai=str(a["loai"]),
                    luc=a.get("luc"),
                    boi_staff_id=_str(a.get("boi_staff_id")),
                    trang_thai=dict(trang_thai),
                )
            )
            continue
        ds = du_lieu
        for t in ds:
            rid = str(t["roster_id"])
            if t["hanh_dong"] == "XOA":
                trang_thai.pop(rid, None)
            else:
                sau = _json(t.get("sau"))
                if sau:
                    trang_thai[rid] = dict(sau)
        cuoi = ds[-1]
        ket.append(
            PhienBan(
                txid=tx,
                loai=LOAI_THAY_DOI,
                luc=cuoi.get("luc"),
                boi_staff_id=_str(cuoi.get("boi_staff_id")),
                trang_thai=dict(trang_thai),
            )
        )
    return ket


def _str(v: Any) -> str | None:
    return str(v) if v else None


def _hien(trang_thai: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Ô có mặt trên bảng chính thức: chỉ ca ĐÃ DUYỆT."""
    return {k: o for k, o in trang_thai.items() if o.get("status") == "APPROVED"}


def _cho(o: dict[str, Any]) -> tuple[str, str, str]:
    return (str(o.get("work_date")), str(o.get("shift")), str(o.get("station")))


def so_sanh(
    truoc: dict[str, dict[str, Any]], sau: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Phần khác giữa hai trạng thái (chỉ ca đã duyệt), theo id dòng lịch.

    * có ở sau, không ở trước → THÊM;  có ở trước, không ở sau → XOÁ;
    * cùng id, đổi CHỖ (ngày / ca / vị trí) → XOÁ chỗ cũ + THÊM chỗ mới;
    * cùng id, cùng chỗ, đổi người → ĐỔI NGƯỜI (kèm người trước).
    """
    a, b = _hien(truoc), _hien(sau)
    them: list[dict[str, Any]] = []
    xoa: list[dict[str, Any]] = []
    doi: list[dict[str, Any]] = []
    for k, o in b.items():
        cu = a.get(k)
        if cu is None:
            them.append(o)
        elif _cho(cu) != _cho(o):
            xoa.append(cu)
            them.append(o)
        elif (cu.get("staff_id"), cu.get("staff_name")) != (
            o.get("staff_id"),
            o.get("staff_name"),
        ):
            doi.append({"o": o, "truoc": cu})
    for k, cu in a.items():
        if k not in b:
            xoa.append(cu)
    return {"them": them, "xoa": xoa, "doi_nguoi": doi}


def _rong(d: dict[str, list[dict[str, Any]]]) -> bool:
    return not (d["them"] or d["xoa"] or d["doi_nguoi"])


def loc_phien_ban(
    phien_ban: list[PhienBan],
) -> list[tuple[PhienBan, dict[str, list[dict[str, Any]]] | None]]:
    """Kèm phần khác so với bản trước; bỏ giao dịch không đổi gì trên bảng
    (vd. sửa ca chờ duyệt). Ảnh luôn giữ — "áp dụng lại" là một mốc có thật."""
    ket: list[tuple[PhienBan, dict[str, list[dict[str, Any]]] | None]] = []
    truoc: PhienBan | None = None
    for p in phien_ban:
        khac = so_sanh(truoc.trang_thai, p.trang_thai) if truoc else None
        if p.loai == LOAI_THAY_DOI and (khac is None or _rong(khac)):
            continue
        ket.append((p, khac))
        truoc = p
    return ket


# ── Service ──────────────────────────────────────────────────────────────────
_ANH_SQL = """
SELECT id, loai, txid, luc, boi_staff_id::text AS boi_staff_id, ca
  FROM public.lich_truc_anh
 WHERE clinic_id = $1::uuid AND week_start = $2
 ORDER BY txid, id
"""

_THAY_DOI_SQL = """
SELECT id, roster_id::text AS roster_id, hanh_dong, truoc, sau, txid, luc,
       boi_staff_id::text AS boi_staff_id
  FROM public.lich_truc_thay_doi
 WHERE clinic_id = $1::uuid AND week_start = $2
   AND txid > (SELECT min(txid) FROM public.lich_truc_anh
                WHERE clinic_id = $1::uuid AND week_start = $2)
 ORDER BY txid, id
"""

_NHAN_SU_SQL = """
SELECT s.id::text AS id, s.full_name,
       (SELECT m.role FROM public.clinic_membership m
         WHERE m.staff_id = s.id AND m.clinic_id = $1::uuid AND m.is_active
         ORDER BY m.created_at, m.id LIMIT 1) AS vai_ma
  FROM public.staff s
 WHERE s.id = ANY($2::uuid[])
"""


class LichTrucPhienBanService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def xem(
        self, *, identity: StaffIdentity, tuan: object, ban: object = None
    ) -> dict[str, Any]:
        """Danh sách phiên bản (mới nhất trước) + bảng lịch tại phiên bản `ban`
        (rỗng / rác / không có → mới nhất) + phần khác so với bản trước.

        Tuần rác → `tuan: None`, không ném. Tuần chưa có ảnh (chưa áp dụng từ
        ngày lên bản) → `co_lich_su: False` kèm `lich_su_tu` = mốc bắt đầu ghi
        của phòng khám, để màn nói rõ "chưa có lịch sử trước ngày …"."""
        dau = doc_tuan(tuan)
        if dau is None:
            return _khong_co(None, None, False)
        async with self._pool.acquire() as conn:
            anh = [dict(r) for r in await conn.fetch(_ANH_SQL, identity.clinic_id, dau)]
            da_ap_dung = bool(
                await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM public.roster_week"
                    " WHERE clinic_id = $1::uuid AND week_start = $2)",
                    identity.clinic_id,
                    dau,
                )
            )
            if not anh:
                moc = await conn.fetchval(
                    "SELECT min(luc) FROM public.lich_truc_anh"
                    " WHERE clinic_id = $1::uuid",
                    identity.clinic_id,
                )
                return _khong_co(dau, moc, da_ap_dung)
            thay_doi = [
                dict(r)
                for r in await conn.fetch(_THAY_DOI_SQL, identity.clinic_id, dau)
            ]
            ds = loc_phien_ban(dung_phien_ban(anh, thay_doi))
            muon = doc_ban(ban)
            chon_i = next(
                (i for i, (p, _) in enumerate(ds) if p.txid == muon), len(ds) - 1
            )
            chon, khac = ds[chon_i]
            truoc = ds[chon_i - 1][0] if chon_i > 0 else None

            ma_nv: set[str] = {p.boi_staff_id for p, _ in ds if p.boi_staff_id}
            for o in _hien(chon.trang_thai).values():
                if o.get("staff_id"):
                    ma_nv.add(str(o["staff_id"]))
            nv = {
                r["id"]: dict(r)
                for r in await conn.fetch(
                    _NHAN_SU_SQL, identity.clinic_id, sorted(ma_nv)
                )
            }

        def ten(sid: str | None) -> str | None:
            return nv[sid]["full_name"] if sid and sid in nv else None

        def meta(p: PhienBan, k: KhacNhau | None) -> dict[str, Any]:
            return {
                "ma": str(p.txid),
                "loai": p.loai,
                "luc": p.luc.isoformat() if p.luc else None,
                "boi_ten": ten(p.boi_staff_id),
                "so": {
                    "them": len(k["them"]) if k else 0,
                    "xoa": len(k["xoa"]) if k else 0,
                    "doi_nguoi": len(k["doi_nguoi"]) if k else 0,
                },
            }

        def o_ra(o: dict[str, Any], **them: Any) -> dict[str, Any]:
            sid = str(o["staff_id"]) if o.get("staff_id") else None
            day_du, ngan = nhan_vai(nv.get(sid or "", {}).get("vai_ma"))
            return {
                "id": str(o.get("id")),
                "work_date": str(o.get("work_date")),
                "shift": o.get("shift"),
                "station": o.get("station"),
                "staff_id": sid,
                "staff_name": o.get("staff_name"),
                "ten_chuan": ten(sid),
                "vai": day_du,
                "vai_ngan": ngan,
                **them,
            }

        moi = {str(o["id"]) for o in (khac or {}).get("them", [])}
        doi = {str(d["o"]["id"]): d["truoc"] for d in (khac or {}).get("doi_nguoi", [])}
        dong = []
        for o in sorted(
            _hien(chon.trang_thai).values(),
            key=lambda o: (_cho(o), str(o.get("staff_name"))),
        ):
            rid = str(o["id"])
            if rid in doi:
                dong.append(
                    o_ra(o, thay_doi="DOI_NGUOI", truoc_ten=doi[rid].get("staff_name"))
                )
            elif rid in moi:
                dong.append(o_ra(o, thay_doi="THEM", truoc_ten=None))
            else:
                dong.append(o_ra(o, thay_doi=None, truoc_ten=None))
        da_xoa = [
            o_ra(o, thay_doi="XOA", truoc_ten=None)
            for o in sorted((khac or {}).get("xoa", []), key=_cho)
        ]

        return {
            "tuan": dau.isoformat(),
            "co_lich_su": True,
            "da_ap_dung": da_ap_dung,
            "lich_su_tu": ds[0][0].luc.isoformat() if ds[0][0].luc else None,
            # Mới nhất trước — như ô lịch sử phiên bản của Google Docs.
            "phien_ban": [meta(p, k) for p, k in reversed(ds)],
            "dang_xem": {
                **meta(chon, khac),
                "moi_nhat": chon_i == len(ds) - 1,
                "truoc_ma": str(truoc.txid) if truoc else None,
                "dong": dong,
                "da_xoa": da_xoa,
            },
        }


def _khong_co(
    dau: date | None, moc: datetime | None, da_ap_dung: bool
) -> dict[str, Any]:
    return {
        "tuan": dau.isoformat() if dau else None,
        "co_lich_su": False,
        "da_ap_dung": da_ap_dung,
        "lich_su_tu": moc.isoformat() if moc else None,
        "phien_ban": [],
        "dang_xem": None,
    }
