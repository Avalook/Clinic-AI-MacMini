"""Kho email kết quả (tạm) — xem mọi thư kết quả đối tác gửi về Gmail (Gmail G2b).

Kế hoạch `docs/KE-HOACH-KET-QUA-QUA-GMAIL.md` mục 1.7 + 3 G2. Chỉ người có quyền
`xet_nghiem.kho_email` (khối cấp riêng từng người, không nhóm mẫu nào). Người khác ⇒
**404** — không lộ Kho có hay không, thư có hay không.

Dữ liệu là dòng `drive_tep` nguồn GMAIL (G2a ghi). Trạng thái TÍNH RA từ sự việc ở MỘT
biểu thức SQL (`_TRANG_THAI`) dùng cho cả cột lẫn bộ lọc. Mỗi lần mở PDF phát
`lab.archive_viewed` (vết ai xem dữ liệu sức khoẻ). Chỉ đọc — không Gán / Từ chối ở
đây (G3/G4).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.kho_tep import don_tren_kho
from clinicai.events.catalogue import XetNghiemTepDrive
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can

# `_tim_ban` là hàm DUY NHẤT trả lời "đọc byte ổ VPS rồi CFS" (luật 1); tệp
# tep_ket_qua_service đã quá trần nên không thêm tên công khai ở đó.
from clinicai.services.tep_ket_qua_service import TepMoDoc, _tim_ban
from clinicai.services.xet_nghiem import ghep_khach, ghep_tay

QUYEN: Final = "xet_nghiem.kho_email"
_VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")
TRE_NHIP: Final = timedelta(hours=1)
CO_MAC_DINH: Final = 50
CO_TOI_DA: Final = 100
#: Mã trạng thái → chữ + màu chip trên màn (màn chỉ hiện, không tự suy, không giữ
#: bản nhãn thứ hai — danh sách bộ lọc cũng lấy từ đây).
NHAN: Final = {
    "LUU_TRU": "Lưu trữ",
    "CHO_GHEP": "Chờ ghép tay",
    "DA_GHEP": "Đã ghép",
    "TU_CHOI": "Đã từ chối",
}
MAU: Final = {
    "LUU_TRU": "neutral",
    "CHO_GHEP": "warning",
    "DA_GHEP": "success",
    "TU_CHOI": "danger",
}
LOC: Final = [{"ma": "", "nhan": "Mọi thư"}] + [
    {"ma": ma, "nhan": nhan} for ma, nhan in NHAN.items()
]
_TRANG_THAI: Final = (
    "CASE WHEN t.tu_choi_luc IS NOT NULL THEN 'TU_CHOI'"
    " WHEN t.tep_ket_qua_id IS NOT NULL THEN 'DA_GHEP'"
    " WHEN t.ly_do_cho = 'LUU_TRU' THEN 'LUU_TRU' ELSE 'CHO_GHEP' END"
)


async def cua_kho(conn: asyncpg.Connection, identity: StaffIdentity) -> None:
    """Thiếu quyền ⇒ 404 (không 403): người không được cấp không biết Kho tồn tại."""
    if not await can(conn, identity, QUYEN):
        raise NotFoundError("Không tìm thấy.")


def _ngay(v: object) -> date | None:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v).strip()) if v not in (None, "") else None
    except ValueError:
        return None


def doc_loc(tham: dict[str, Any]) -> dict[str, Any]:
    """HÀM THUẦN: tham số lọc từ người dùng ⇒ bộ lọc sạch. Rác ⇒ bỏ lọc đó, không ném.
    `q` là số (≥ 6 chữ số; cho phép cách / chấm / gạch / +84) ⇒ tìm SĐT (+84 ⇒ 0);
    còn lại ⇒ tìm chữ bỏ dấu, từ cuối khớp tiền tố (gõ dở "nguyen th" vẫn ra)."""
    tt = tham.get("trang_thai")
    q = str(tham.get("q") or "").strip()[:100]
    so = "".join(c for c in q if c.isdigit())
    la_so = len(so) >= 6 and not re.sub(r"[\d\s.\-+()]", "", q)
    if la_so and so.startswith("84") and len(so) == 11:
        so = "0" + so[2:]
    try:
        trang = max(1, int(str(tham.get("trang") or 1)))
    except ValueError:
        trang = 1
    try:
        co = min(CO_TOI_DA, max(1, int(str(tham.get("co") or CO_MAC_DINH))))
    except ValueError:
        co = CO_MAC_DINH
    return {
        "tu_ngay": _ngay(tham.get("tu_ngay")),
        "den_ngay": _ngay(tham.get("den_ngay")),
        "trang_thai": tt if tt in NHAN else None,
        "chu": None if la_so else (ghep_khach.chuan(q) or None),
        "so": so if la_so else None,
        "trang": trang,
        "co": co,
    }


_DS_SQL = f"""
SELECT t.id::text AS id, t.doi_tac_id::text AS doi_tac_id, d.ten AS ten_doi_tac,
       t.ten, t.email_tieu_de AS tieu_de, t.email_nhan_luc AS nhan_luc,
       t.ma_ben_doi_tac_tep AS ma_tep, {_TRANG_THAI} AS trang_thai,
       t.ly_do_cho, t.luu_tru_vi_sao,
       t.goi_y_clinic_patient_id::text AS goi_y_id, p.full_name AS goi_y_ten,
       p.patient_code AS goi_y_ma, count(*) OVER () AS tong
  FROM drive_tep t
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = t.goi_y_clinic_patient_id AND p.clinic_id = t.clinic_id
 WHERE t.clinic_id = $1::uuid AND t.nguon = 'GMAIL'
   AND ($2::date IS NULL
        OR t.email_nhan_luc >= ($2::date::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'))
   AND ($3::date IS NULL
        OR t.email_nhan_luc
           < (($3::date + 1)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'))
   AND ($4::text IS NULL OR {_TRANG_THAI} = $4)
   AND ($5::text IS NULL OR ' ' || trim(regexp_replace(
            public.f_unaccent(lower(replace(replace(
                coalesce(t.email_tieu_de, '') || ' ' || t.ten || ' '
                || coalesce(t.email_than, ''), 'đ', 'd'), 'Đ', 'd'))),
            '[^a-z0-9]+', ' ', 'g')) || ' ' LIKE '% ' || $5 || '%')
   AND ($6::text IS NULL OR regexp_replace(
            coalesce(t.email_tieu_de, '') || coalesce(t.email_than, '') || t.ten,
            '\\D', '', 'g') LIKE '%' || $6 || '%')
 ORDER BY t.email_nhan_luc DESC, t.id
 LIMIT $7 OFFSET $8
"""


def _vi_sao(d: dict[str, Any]) -> None:
    """Thư chưa ghép (Lưu trữ / Chờ ghép tay) ⇒ câu "vì sao" — một nơi tính
    (`ghep_tay.vi_sao_cho`); đã ghép / đã từ chối ⇒ None."""
    ly, luu = d.pop("ly_do_cho", None), d.pop("luu_tru_vi_sao", None)
    cho = d["trang_thai"] in ("LUU_TRU", "CHO_GHEP")
    d["vi_sao"] = (
        ghep_tay.vi_sao_cho(ly, luu, d.get("goi_y_id") is not None) if cho else None
    )


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    d = dict(r)
    d.pop("tong", None)
    d["nhan_trang_thai"] = NHAN[d["trang_thai"]]
    d["mau"] = MAU[d["trang_thai"]]
    _vi_sao(d)
    return d


async def danh_sach(
    conn: asyncpg.Connection, identity: StaffIdentity, tham: dict[str, Any]
) -> dict[str, Any]:
    """Một trang Kho (mới trước) + tổng khớp lọc (màn biết còn trang) + thanh trên."""
    await cua_kho(conn, identity)
    loc = doc_loc(tham)
    rows = await conn.fetch(
        _DS_SQL,
        identity.clinic_id,
        loc["tu_ngay"],
        loc["den_ngay"],
        loc["trang_thai"],
        loc["chu"],
        loc["so"],
        loc["co"],
        (loc["trang"] - 1) * loc["co"],
    )
    return {
        "thu": [_dong(r) for r in rows],
        "tong": int(rows[0]["tong"]) if rows else 0,
        "trang": loc["trang"],
        "co": loc["co"],
        "thanh_tren": await thanh_tren(conn, identity.clinic_id),
        "loc": LOC,
    }


def den_kho(
    da_nap: int,
    con: int,
    ok_cuoi: datetime | None,
    so_loi: int,
    so_doi_tac: int,
    bay_gio: datetime,
) -> dict[str, str]:
    """HÀM THUẦN: chữ + màu thanh trên của Kho (một nơi tính, màn chỉ hiện)."""
    nap = f"Đã nạp {da_nap:,} thư".replace(",", ".")
    if con > 0:
        nap = f"Đã nạp {da_nap:,} / ~{da_nap + con:,} thư".replace(",", ".")
    if so_doi_tac == 0:
        return {"nhan": f"{nap} · chưa nối email đối tác nào", "mau": "neutral"}
    if ok_cuoi is None:
        return {"nhan": f"{nap} · chưa đọc được Gmail lần nào", "mau": "danger"}
    gio = ok_cuoi.astimezone(_VN).strftime("%H:%M %d/%m")
    if so_loi or bay_gio - ok_cuoi > TRE_NHIP:
        return {"nhan": f"{nap} · Email lỗi (lần ổn cuối {gio})", "mau": "danger"}
    return {"nhan": f"{nap} · Email ổn · quét lúc {gio}", "mau": "success"}


_THANH_SQL = """
SELECT (SELECT count(DISTINCT email_message_id) FROM drive_tep
         WHERE clinic_id = $1::uuid AND nguon = 'GMAIL') AS da_nap,
       coalesce(sum(n.so_lich_su_con), 0) AS con,
       -- Đối tác chưa quét lần nào (không dòng nhịp / ok_cuoi NULL) ⇒ NULL ⇒ đèn đỏ;
       -- min() một mình bỏ qua NULL và báo "Email ổn" sai.
       CASE WHEN bool_or(n.ok_cuoi IS NULL) THEN NULL ELSE min(n.ok_cuoi) END
           AS ok_cuoi,
       count(*) FILTER (WHERE n.loi_cuoi IS NOT NULL) AS so_loi,
       (SELECT count(*) FROM doi_tac
         WHERE clinic_id = $1::uuid AND email_gui_ket_qua IS NOT NULL
           AND ngung_luc IS NULL) AS so_doi_tac
  FROM doi_tac d
  LEFT JOIN drive_nhip n
    ON n.clinic_id = d.clinic_id AND n.doi_tac_id = d.id AND n.nguon = 'GMAIL'
 WHERE d.clinic_id = $1::uuid AND d.email_gui_ket_qua IS NOT NULL
   AND d.ngung_luc IS NULL
"""


async def thanh_tren(conn: asyncpg.Connection, cid: str) -> dict[str, str]:
    """`ok_cuoi` = lượt ổn CŨ NHẤT trong các đối tác: một đối tác kẹt là đèn đỏ."""
    r = await conn.fetchrow(_THANH_SQL, cid)
    assert r is not None
    return den_kho(
        int(r["da_nap"] or 0),
        int(r["con"] or 0),
        r["ok_cuoi"],
        int(r["so_loi"] or 0),
        int(r["so_doi_tac"] or 0),
        datetime.now(_VN),
    )


async def _mot_thu(conn: asyncpg.Connection, cid: str, tid: object) -> asyncpg.Record:
    try:
        r = await conn.fetchrow(
            f"SELECT t.id::text AS id, t.doi_tac_id::text AS doi_tac_id,"
            f"       d.ten AS ten_doi_tac, t.ten, t.email_tieu_de AS tieu_de,"
            f"       t.email_than AS than, t.email_nhan_luc AS nhan_luc,"
            f"       t.ma_ben_doi_tac_tep AS ma_tep, {_TRANG_THAI} AS trang_thai,"
            f"       t.ly_do_cho, t.luu_tru_vi_sao, t.khoa, t.vi_tri, t.so_byte,"
            f"       t.goi_y_clinic_patient_id::text AS goi_y_id"
            f"  FROM drive_tep t JOIN doi_tac d"
            f"    ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id"
            f" WHERE t.clinic_id = $1::uuid AND t.id = $2::uuid AND t.nguon = 'GMAIL'",
            cid,
            str(tid),
        )
    except (asyncpg.DataError, ValueError):
        r = None
    if r is None:
        raise NotFoundError("Không tìm thấy.")
    return r


async def chi_tiet(
    conn: asyncpg.Connection, identity: StaffIdentity, tid: object
) -> dict[str, Any]:
    """Tiêu đề + thân thư + tên tệp (dữ liệu sức khoẻ — sau cổng quyền)."""
    await cua_kho(conn, identity)
    r = dict(await _mot_thu(conn, identity.clinic_id, tid))
    for k in ("khoa", "vi_tri", "so_byte"):
        r.pop(k)
    r["nhan_trang_thai"] = NHAN[r["trang_thai"]]
    _vi_sao(r)
    return r


async def mo_pdf(pool: asyncpg.Pool, identity: StaffIdentity, tid: object) -> TepMoDoc:
    """Mở PDF để phát trực tiếp: cổng quyền → mở tệp (ổ VPS trước, rồi CFS) → ghi vết
    `lab.archive_viewed`. Ghi vết lỗi ⇒ đóng tệp, không trả byte (xem phải có vết)."""
    async with pool.acquire() as conn:
        await cua_kho(conn, identity)
        r = await _mot_thu(conn, identity.clinic_id, tid)
    duong, kho, f = await _tim_ban(str(r["khoa"]), str(r["vi_tri"]), mo=True)
    assert f is not None
    try:
        async with pool.acquire() as conn, conn.transaction():
            await emit_event(
                conn,
                ten="lab.archive_viewed",
                clinic_id=identity.clinic_id,
                aggregate_id=r["id"],
                payload=XetNghiemTepDrive(
                    drive_tep_id=r["id"], doi_tac_id=r["doi_tac_id"]
                ),
                boi=nguoi(identity),
            )
    except BaseException:
        # Đóng qua luồng phụ có hạn: tệp trên CFS treo không được chặn vòng sự kiện.
        await don_tren_kho(f.close, viec=f"dong_tep:{duong}", kho=kho)
        raise
    return TepMoDoc(
        f=f,
        kho=kho,
        duong=duong,
        mime="application/pdf",
        so_byte=int(r["so_byte"]),
        ten=str(r["ten"]),
    )
