"""Quầy thuốc BÁN THEO ĐƠN CŨ (09/10/2026).

Chọn khách cũ ở quầy (chưa mở lượt) là thấy **lịch sử đơn thuốc**: mỗi lượt KHÁM
có thuốc bác sĩ kê là một đơn, mới → cũ, theo trang — ngày khám, bác sĩ, hẹn tái
khám, từng thuốc kê / đã mua / còn lại. "Bán theo đơn này" (đơn nào cũng được)
nối lượt bán lẻ về lượt gốc ấy (``visit.don_goc_visit_id``, mig 20261010100000)
rồi thêm dòng QUAY bằng đúng ``QuayThuocService.luu_dong_them``, số = còn lại.

Đếm theo THUỐC KHO, không cộng theo ``prescription`` (dòng QUAY lượt sau và dòng
đơn gốc là hai dòng của cùng một thuốc — cộng dòng là đếm đôi):
* Kê — dòng ``BAC_SI`` của lượt gốc: ``so_luong_ke_goc`` nếu quầy đã sửa/điền số
  (C14/C19), không thì ``quantity_num``; bác sĩ để trống → không có số kê.
* Đã mua — ``payment_bill_line`` của lần thu thuốc PAID ở lượt gốc + mọi lượt bán
  lẻ nối về nó, trừ phần hoàn xong — cùng nguồn với báo cáo thuốc.
* Đang định bán — dòng của lượt bán lẻ đang mở, chưa thu.

CHỈ NHẮC, KHÔNG CHẶN: quá 2 tháng lịch từ lần khám gần nhất; tổng mua vượt số kê.
Hoàn tác: gỡ nối khi chưa thu — dòng đã thêm giữ nguyên (quầy không xoá dòng).
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.hen_tai_kham_service import doc_hen_luot
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.quay_thuoc_service import QuayThuocService

#: Nối đơn + thêm dòng = đúng quyền của lệnh "lấy thêm thuốc" được dùng lại.
QUYEN = "payment.medicine.collect"
SO_THANG_NHAC_KHAM = 2
_0 = Decimal(0)


# ── Hàm thuần — test không cần database ───────────────────────────────────
def doc_ngay(v: Any) -> date | None:
    """date / datetime / "YYYY-MM-DD…" → ngày. Rác, rỗng → None, không ném."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(v.strip()[:10]) if isinstance(v, str) else None
    except ValueError:
        return None


def cong_thang(d: date, so_thang: int) -> date:
    """Cộng tháng LỊCH; tháng đích ngắn hơn thì lấy ngày cuối (31/12 + 2 = 28/02)."""
    t = d.month - 1 + so_thang
    nam, thang = d.year + t // 12, t % 12 + 1
    return date(nam, thang, min(d.day, calendar.monthrange(nam, thang)[1]))


def qua_han_kham(ngay_kham: Any, hom_nay: Any) -> bool:
    """Hôm nay đã QUA mốc "lần khám gần nhất + 2 tháng lịch". Ngày rác → False."""
    kham, nay = doc_ngay(ngay_kham), doc_ngay(hom_nay)
    if kham is None or nay is None:
        return False
    try:
        return nay > cong_thang(kham, SO_THANG_NHAC_KHAM)
    except (ValueError, OverflowError):
        return False


def chuoi_so(d: Decimal | None) -> str | None:
    if d is None:
        return None
    return format(d.normalize(), "f") if d != 0 else "0"


def gom_dong(
    dong_ke: Iterable[Mapping[str, Any]],
    da_mua: Mapping[str, Decimal],
    dang_ban: Mapping[str, Decimal],
) -> list[dict[str, Any]]:
    """Dòng kê → mỗi THUỐC một dòng: kê / đã mua / đang bán / còn lại / vượt.
    Cùng thuốc kho thì gộp (một dòng không số → cả thuốc không có số kê). Chưa
    xác định thuốc kho thì không khớp được lần mua nào → đã mua 0."""
    gom: dict[str, dict[str, Any]] = {}
    for r in dong_ke:
        thuoc = r.get("drug_catalog_id")
        ke = None if r.get("so_ke") is None else Decimal(str(r["so_ke"]))
        khoa = str(thuoc) if thuoc else f"rx:{r['id']}"
        if khoa in gom:
            cu = gom[khoa]["so_ke"]
            gom[khoa]["so_ke"] = None if cu is None or ke is None else cu + ke
            continue
        ten_kho, ten_bs = r.get("ten_kho"), r.get("drug_name_raw")
        gom[khoa] = {
            "drug_catalog_id": str(thuoc) if thuoc else None,
            "ten": ten_kho or ten_bs or "—",
            "ten_bac_si": ten_bs if ten_kho and ten_bs and ten_bs != ten_kho else None,
            "don_vi": r.get("don_vi"),
            "cach_dung": r.get("dosage_instructions"),
            "luu_y": r.get("caution"),
            "so_ke": ke,
        }
    ra = []
    for d in gom.values():
        mua = da_mua.get(d["drug_catalog_id"] or "", _0)
        ban = dang_ban.get(d["drug_catalog_id"] or "", _0)
        ke = d["so_ke"]
        con = None if ke is None else max(ke - mua, _0)
        vuot = ke is not None and mua + ban > ke
        ra.append({**d, "da_mua": mua, "dang_ban": ban, "con_lai": con, "vuot": vuot})
    return ra


def loi_nhac(
    kham_moi_nhat: Any, hom_nay: Any, dong: Iterable[Mapping[str, Any]]
) -> list[str]:
    """Các câu nhắc (KHÔNG chặn) — nhân viên đọc rồi tự quyết."""
    nhac = []
    ngay = doc_ngay(kham_moi_nhat)
    if ngay is not None and qua_han_kham(ngay, hom_nay):
        nhac.append(
            f"Lần khám gần nhất {ngay:%d/%m/%Y} đã quá {SO_THANG_NHAC_KHAM} tháng"
            " — nên mời khách khám lại. Vẫn bán được nếu khách cần."
        )
    for d in dong:
        if d["vuot"]:
            dv = f" {d['don_vi']}" if d.get("don_vi") else ""
            nhac.append(
                f"“{d['ten']}”: tổng mua {chuoi_so(d['da_mua'] + d['dang_ban'])}{dv}"
                f" vượt số bác sĩ kê {chuoi_so(d['so_ke'])}{dv}."
            )
    return nhac


def dong_can_them(
    dong: Iterable[Mapping[str, Any]], co_san: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Dòng QUAY cần thêm (số = còn lại) + câu cho thuốc không thêm được. Thuốc
    đã có trong lượt thì để nguyên — quầy sửa ở "Lấy thêm thuốc"."""
    them: list[dict[str, Any]] = []
    bo_qua: list[str] = []
    for d in dong:
        thuoc, con, ten = d["drug_catalog_id"], d["con_lai"], d["ten"]
        if not thuoc:
            bo_qua.append(f"“{ten}”: chưa xác định thuốc kho — thêm tay.")
        elif thuoc in co_san:
            continue
        elif con is None:
            bo_qua.append(f"“{ten}”: bác sĩ chưa ghi số lượng — thêm tay.")
        elif con <= 0:
            bo_qua.append(f"“{ten}”: đã mua đủ số bác sĩ kê.")
        else:
            so = f"{chuoi_so(con)} {d.get('don_vi') or ''}".strip()
            them.append(
                {
                    "drug_catalog_id": thuoc,
                    "quantity": so,
                    "dosage": d.get("cach_dung"),
                    "caution": d.get("luu_y"),
                }
            )
    return them, bo_qua


# ── Đọc ────────────────────────────────────────────────────────────────────
async def _goc(
    conn: asyncpg.Connection, cid: str, pid: str, chi_luot: str | None = None
) -> str | None:
    """Lượt KHÁM gần nhất của khách có thuốc bác sĩ kê (``chi_luot``: chỉ xét
    đúng lượt đó — kiểm đơn gốc hợp lệ)."""
    goc: str | None = await conn.fetchval(
        """
        SELECT v.visit_id::text FROM visit v
         WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
           AND NOT v.ban_le AND ($3::uuid IS NULL OR v.visit_id = $3::uuid)
           AND EXISTS (SELECT 1 FROM prescription r
                        WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
                          AND r.nguon = 'BAC_SI' AND r.removed_at IS NULL)
         ORDER BY coalesce(v.checked_in_at, v.created_at) DESC, v.visit_id DESC
         LIMIT 1
        """,
        cid,
        pid,
        chi_luot,
    )
    return goc


_DAU_DON = """
SELECT (coalesce(v.checked_in_at, v.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           AS ngay_kham,
       coalesce(d.full_name, (
           SELECT s.full_name FROM consultation c
             JOIN staff s ON s.id = c.doctor_staff_id
            WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
              AND c.kind = 'PRIMARY' ORDER BY c.round_no LIMIT 1)) AS bac_si
  FROM visit v LEFT JOIN staff d ON d.id = v.attending_doctor_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""

_DONG_KE = """
SELECT r.id::text AS id, r.drug_catalog_id::text AS drug_catalog_id,
       coalesce(c.name_base, c.name_raw) AS ten_kho, r.drug_name_raw,
       coalesce(nullif(btrim(r.unit), ''), nullif(btrim(c.don_vi_ban), '')) AS don_vi,
       CASE WHEN r.so_luong_dien_boi IS NULL THEN r.quantity_num
            ELSE public.so_luong_tu_van_ban(r.so_luong_ke_goc) END AS so_ke,
       r.dosage_instructions, r.caution
  FROM prescription r
  LEFT JOIN drug_catalog c ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
 WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
   AND r.nguon = 'BAC_SI' AND r.removed_at IS NULL
 ORDER BY r.created_at, r.id
"""

#: Đã mua theo thuốc kho: lần thu PAID ở lượt gốc + lượt bán lẻ nối về nó − hoàn.
_DA_MUA = """
SELECT bl.drug_catalog_id::text AS thuoc,
       sum(bl.quantity - coalesce((
           SELECT sum(rl.quantity) FROM payment_refund_line rl
             JOIN payment_refund rf
               ON rf.refund_id = rl.refund_id AND rf.clinic_id = rl.clinic_id
            WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
              AND rf.status = 'COMPLETED'), 0)) AS so
  FROM payment_bill_line bl
  JOIN payment_cycle pc
    ON pc.payment_cycle_id = bl.payment_cycle_id AND pc.clinic_id = bl.clinic_id
 WHERE bl.clinic_id = $1::uuid AND bl.drug_catalog_id IS NOT NULL
   AND bl.source_type = 'prescription' AND pc.kind = 'thuoc' AND pc.status = 'PAID'
   AND bl.visit_id IN (SELECT $2::uuid UNION ALL
                       SELECT k.visit_id FROM visit k
                        WHERE k.clinic_id = $1::uuid AND k.don_goc_visit_id = $2::uuid)
 GROUP BY bl.drug_catalog_id
"""

#: Đang định bán: dòng của lượt bán lẻ khi CHƯA thu (đã thu thì nằm ở "đã mua").
_DANG_BAN = """
SELECT r.drug_catalog_id::text AS thuoc,
       sum(coalesce(r.purchased_qty, r.quantity_num)) AS so
  FROM prescription r
 WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid AND r.removed_at IS NULL
   AND r.refusal_reason IS NULL AND r.drug_catalog_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM payment_cycle pc
                    WHERE pc.clinic_id = r.clinic_id AND pc.visit_id = r.visit_id
                      AND pc.kind = 'thuoc' AND pc.status = 'PAID')
 GROUP BY r.drug_catalog_id
"""


#: Các lượt KHÁM có thuốc bác sĩ kê, mới → cũ, theo trang ($3 dòng từ $4).
_CAC_GOC = """
SELECT v.visit_id::text AS id FROM visit v
 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid AND NOT v.ban_le
   AND EXISTS (SELECT 1 FROM prescription r
                WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
                  AND r.nguon = 'BAC_SI' AND r.removed_at IS NULL)
 ORDER BY coalesce(v.checked_in_at, v.created_at) DESC, v.visit_id DESC
 LIMIT $3 OFFSET $4
"""

#: Mỗi trang lịch sử đơn bao nhiêu đơn; quá ``TRAN_DON`` đơn thì dừng (log kêu).
DON_MOI_TRANG = 10
TRAN_DON = 200


def so_trang(v: Any) -> int:
    """Trang người dùng gửi: số 0…(trần), rác → 0. Không ném."""
    try:
        n = int(str(v).strip()) if not isinstance(v, bool) else 0
    except (TypeError, ValueError):
        return 0
    return min(max(n, 0), TRAN_DON // DON_MOI_TRANG - 1)


async def _theo_thuoc(
    conn: asyncpg.Connection, sql: str, cid: str, luot: str
) -> dict[str, Decimal]:
    rows = await conn.fetch(sql, cid, luot)
    return {r["thuoc"]: Decimal(str(r["so"])) for r in rows if r["so"] is not None}


async def _doc_goc(
    conn: asyncpg.Connection,
    cid: str,
    *,
    goc: str,
    dang_ban: Mapping[str, Decimal],
) -> dict[str, Any]:
    """Một đơn: đầu đơn + dòng kê / đã mua / còn lại + nhắc vượt CỦA ĐƠN NÀY."""
    v = await conn.fetchrow(_DAU_DON, cid, goc)
    dong = gom_dong(
        [dict(r) for r in await conn.fetch(_DONG_KE, cid, goc)],
        await _theo_thuoc(conn, _DA_MUA, cid, goc),
        dang_ban,
    )
    hen = (await doc_hen_luot(conn, cid, goc))["ngay_hen"]
    return {
        "visit_id": goc,
        "ngay_kham": v["ngay_kham"].isoformat() if v and v["ngay_kham"] else None,
        "bac_si": v["bac_si"] if v else None,
        "ngay_hen": hen.isoformat() if hen else None,
        "dong": dong,
        "nhac": loi_nhac(None, None, dong),
    }


async def lich_su_don(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    clinic_patient_id: str,
    trang: Any = 0,
    hom_nay: date | None = None,
) -> dict[str, Any]:
    """LỊCH SỬ ĐƠN THUỐC của khách, mới → cũ, theo trang — hiện ngay khi chọn
    khách ở quầy (chưa mở lượt) và trong lượt bán lẻ.

    Số đang bán (dòng của lượt bán lẻ đang mở, chưa thu) tính vào ĐÚNG đơn lượt
    ấy đã nối; lượt chưa nối đơn nào thì tính vào mọi đơn ("nếu bán theo đơn
    này thì…"). Nhắc 2 tháng là của KHÁCH (lần khám gần nhất), không của đơn.
    ``ban_duoc``: lượt đang mở chưa nối, hoặc nối đúng đơn này."""
    cid, pid, trang = identity.clinic_id, clinic_patient_id, so_trang(trang)
    mo = await conn.fetchrow(
        "SELECT visit_id::text AS id, don_goc_visit_id::text AS goc FROM visit"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
        "   AND ban_le AND closed_at IS NULL",
        cid,
        pid,
    )
    noi = mo["goc"] if mo else None
    dang_ban = await _theo_thuoc(conn, _DANG_BAN, cid, mo["id"]) if mo else {}
    ids = [
        r["id"]
        for r in await conn.fetch(
            _CAC_GOC, cid, pid, DON_MOI_TRANG + 1, trang * DON_MOI_TRANG
        )
    ]
    canh_bao_neu_day(
        "ban_theo_don.lich_su_don", trang * DON_MOI_TRANG + len(ids), TRAN_DON
    )
    don = []
    for goc in ids[:DON_MOI_TRANG]:
        ban = dang_ban if noi in (None, goc) else {}
        d = await _doc_goc(conn, cid, goc=goc, dang_ban=ban)
        so = ("so_ke", "da_mua", "dang_ban", "con_lai")
        d["dong"] = [{**x, **{k: chuoi_so(x[k]) for k in so}} for x in d["dong"]]
        don.append({**d, "da_noi": noi == goc, "ban_duoc": noi in (None, goc)})
    kham = await conn.fetchval(
        "SELECT max((coalesce(checked_in_at, created_at)"
        "            AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)"
        "  FROM visit WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
        "   AND NOT ban_le",
        cid,
        pid,
    )
    return {
        "don": don,
        "nhac_chung": loi_nhac(kham, hom_nay or hom_nay_vn(), []),
        "trang": trang,
        "co_them": len(ids) > DON_MOI_TRANG and (trang + 1) * DON_MOI_TRANG < TRAN_DON,
        "luot_mo": mo["id"] if mo else None,
    }


# ── Ghi ────────────────────────────────────────────────────────────────────
async def _khoa_luot_chua_thu(
    conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str, viec: str
) -> asyncpg.Record:
    """Khoá lượt bán lẻ (visit trước — cùng thứ tự khoá mọi thao tác hoá đơn
    thuốc); từ chối nếu tiền thuốc đã thu / đang chờ xác minh."""
    await doi_quyen(conn, identity, QUYEN, cau="Bạn chưa được thu tiền thuốc.")
    luot = await conn.fetchrow(
        "SELECT clinic_patient_id::text AS pid, ban_le, closed_at,"
        "       don_goc_visit_id::text AS goc"
        "  FROM visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
        identity.clinic_id,
        visit_id,
    )
    if luot is None or not luot["ban_le"]:
        raise NotFoundError("Không tìm thấy lượt bán lẻ này.")
    if luot["closed_at"] is not None or await PharmacyService._da_thu_tien_thuoc(
        conn, identity, visit_id
    ):
        raise ConflictError(
            f"Tiền thuốc của lượt này đã thu — hoàn tác lần thu trước rồi mới {viec}."
        )
    return luot


async def _doi_noi(
    conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str, goc: str | None
) -> dict[str, Any]:
    await conn.execute(
        "UPDATE visit SET don_goc_visit_id = $3::uuid, updated_at = now()"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        identity.clinic_id,
        visit_id,
        goc,
    )
    return {
        "aggregate_type": "visit",
        "aggregate_id": visit_id,
        "identity": identity,
        "origin": "api:pharmacy-ban-le",
        "correlation_id": visit_id,
    }


async def noi_don(
    pool: asyncpg.Pool, identity: StaffIdentity, *, visit_id: str, don_goc_visit_id: str
) -> dict[str, Any]:
    """ "Bán theo đơn này" trên lượt bán lẻ đã mở."""
    async with pool.acquire() as conn, conn.transaction():
        return await noi_don_conn(
            conn, pool, identity, visit_id=visit_id, don_goc_visit_id=don_goc_visit_id
        )


async def noi_don_conn(
    conn: asyncpg.Connection,
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    *,
    visit_id: str,
    don_goc_visit_id: str,
) -> dict[str, Any]:
    """Nối + thêm dòng số còn lại cho thuốc chưa có trong lượt, trong giao dịch
    của người gọi. Giữ khoá lượt (FOR UPDATE): bấm hai lần (hay hai người cùng
    bấm) không thêm dòng hai lần."""
    cid, goc = identity.clinic_id, don_goc_visit_id
    luot = await _khoa_luot_chua_thu(conn, identity, visit_id, "bán theo đơn")
    if luot["goc"] not in (None, goc):
        raise ConflictError(
            "Lượt này đang bán theo một đơn khác — bấm “Gỡ nối đơn” trước."
        )
    if await _goc(conn, cid, luot["pid"], chi_luot=goc) != goc:
        raise ValidationError("Đơn này không phải đơn khám của khách.")
    if luot["goc"] is None:
        vet = await _doi_noi(conn, identity, visit_id, goc)
        await record_event(
            conn,
            event_type="visit.ban_le_noi_don",
            payload={"don_goc_visit_id": goc},
            **vet,
        )
    don = await _doc_goc(conn, cid, goc=goc, dang_ban={})
    co_san = await conn.fetch(
        "SELECT drug_catalog_id::text AS t FROM prescription"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND removed_at IS NULL AND drug_catalog_id IS NOT NULL",
        cid,
        visit_id,
    )
    them, bo_qua = dong_can_them(don["dong"], {r["t"] for r in co_san})
    if them:
        await QuayThuocService(pool).luu_dong_them(
            visit_id=visit_id, dong=them, identity=identity, conn=conn
        )
    return {"ok": True, "so_dong_them": len(them), "bo_qua": bo_qua}


async def go_noi_don(
    pool: asyncpg.Pool, identity: StaffIdentity, *, visit_id: str
) -> dict[str, Any]:
    """HOÀN TÁC "Bán theo đơn này" khi chưa thu. Dòng đã thêm giữ nguyên (bỏ tick
    nếu khách không lấy). Chưa nối → không làm gì."""
    async with pool.acquire() as conn, conn.transaction():
        luot = await _khoa_luot_chua_thu(conn, identity, visit_id, "gỡ nối đơn")
        if luot["goc"] is None:
            return {"ok": True, "da_go": False}
        vet = await _doi_noi(conn, identity, visit_id, None)
        await record_event(
            conn,
            event_type="visit.ban_le_go_don",
            payload={"don_goc_visit_id": luot["goc"]},
            **vet,
        )
    return {"ok": True, "da_go": True}
