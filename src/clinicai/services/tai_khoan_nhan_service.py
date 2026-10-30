"""TÀI KHOẢN NGÂN HÀNG NHẬN CHUYỂN KHOẢN (31/10/2026).

Thu ngân phân loại tiền chuyển khoản theo TÀI KHOẢN nhận — báo cáo cuối ngày,
chốt ca, danh sách hoá đơn tách số chuyển khoản theo từng tài khoản để kế toán
đối chiếu sao kê từng ngân hàng.

* Danh mục ``tai_khoan_nhan`` (mig 20261031120000): Quản lý (quyền
  ``config.clinic.manage`` — lego Cài đặt phòng khám) thêm / sửa / tắt. Không
  xoá: tắt là hoàn tác được, lần thu cũ vẫn trỏ vào.
* Một tài khoản thuộc MỘT cơ sở, hoặc dùng chung (``location_id`` NULL). Mỗi cơ
  sở tối đa một mặc định (Postgres ép); mặc định phải đang dùng.
* Lúc thu có phần chuyển khoản, tài khoản nhận được chọn theo
  ``chon_mac_dinh``: tài khoản thu ngân chọn > mặc định của cơ sở > mặc định
  dùng chung > tài khoản DUY NHẤT dùng được > không (= "Chưa phân loại"). Máy chủ
  không từ chối khi không chọn được (màn bắt chọn khi có ≥ 2 mà không mặc định):
  phòng khám chưa cài tài khoản nào vẫn thu chuyển khoản như cũ.
* Sửa tài khoản của một phiếu đã thu (chọn nhầm) — ``doi_cho_lan_thu``, có vết ở
  ``event_log`` (``payment.receiving_account_changed``: từ → sang, ai, lý do).

Hàm thuần có test không cần DB: ``tests/unit/test_tai_khoan_nhan.py``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.payment_access_service import head_money_grant
from clinicai.services.phan_thu import doc_phan_db, so_tien_chuyen_khoan

logger = structlog.get_logger()

#: Ai sửa danh mục: lego Cài đặt phòng khám.
QUYEN_QUAN_LY = "config.clinic.manage"
#: Ai sửa tài khoản của phiếu đã thu: cùng người đổi được hình thức thu.
QUYEN_DOI = ("payment.service.collect", "payment.medicine.collect")
#: Nhãn của phần chuyển khoản không gắn tài khoản nào.
CHUA_PHAN_LOAI = "Chưa phân loại"


def doc_id(raw: object, *, cau: str = "Tài khoản nhận không hợp lệ.") -> str | None:
    """Mã tài khoản trình duyệt gửi: rỗng → None; UUID → dạng chuẩn; rác → 422."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return str(uuid.UUID(s))
    except ValueError:
        raise ValidationError(cau) from None


def chuan_so_tai_khoan(raw: object) -> str:
    """Bỏ khoảng trắng / dấu chấm / gạch ("0123 456.789" → "0123456789"). Rác → 422."""
    s = re.sub(r"[\s.\-]", "", raw) if isinstance(raw, str) else ""
    if not re.fullmatch(r"[0-9A-Za-z]{4,30}", s):
        raise ValidationError("Số tài khoản 4–30 chữ số (chữ cái nếu có), không dấu.")
    return s


def _chu(raw: object, ten: str, toi_da: int) -> str:
    s = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not 1 <= len(s) <= toi_da:
        raise ValidationError(f"{ten}: bắt buộc, tối đa {toi_da} ký tự.")
    return s


def doc_form(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Ô của màn quản trị → giá trị sẽ ghi. Thiếu / rác → 422 câu dễ hiểu. Thuần."""
    dang_dung = raw.get("dang_dung", True) is not False
    return {
        "ten_goi": _chu(raw.get("ten_goi"), "Tên gọi", 60),
        "ngan_hang": _chu(raw.get("ngan_hang"), "Ngân hàng", 100),
        "so_tai_khoan": chuan_so_tai_khoan(raw.get("so_tai_khoan")),
        "chu_tai_khoan": _chu(raw.get("chu_tai_khoan"), "Chủ tài khoản", 120),
        "location_id": doc_id(raw.get("location_id"), cau="Cơ sở không hợp lệ."),
        # Mặc định thì phải đang dùng (Postgres cũng ép).
        "mac_dinh": bool(raw.get("mac_dinh")) and dang_dung,
        "dang_dung": dang_dung,
    }


def dung_duoc(tk: Mapping[str, Any], co_so: str | None) -> bool:
    """Tài khoản dùng được cho lần thu ở cơ sở ``co_so``: đang dùng, và thuộc
    đúng cơ sở ấy hoặc dùng chung. Lượt không rõ cơ sở: mọi tài khoản đang dùng."""
    if not tk.get("dang_dung"):
        return False
    loc = tk.get("location_id")
    return loc is None or co_so is None or str(loc) == str(co_so)


def chon_mac_dinh(ds: Iterable[Mapping[str, Any]], co_so: str | None) -> str | None:
    """Tài khoản tự chọn sẵn cho cơ sở ``co_so``. Thuần.

    Mặc định của cơ sở > mặc định dùng chung > tài khoản DUY NHẤT dùng được >
    ``None`` (thu ngân phải chọn; không chọn thì "Chưa phân loại")."""
    dung = [t for t in ds if dung_duoc(t, co_so)]
    for t in dung:
        if (
            t.get("mac_dinh")
            and co_so is not None
            and str(t.get("location_id")) == co_so
        ):
            return str(t["id"])
    for t in dung:
        if t.get("mac_dinh") and t.get("location_id") is None:
            return str(t["id"])
    return str(dung[0]["id"]) if len(dung) == 1 else None


def nhan_tai_khoan(tk: Mapping[str, Any] | None) -> str:
    """ "VCB Hào Nam · 0123456789" — dòng báo cáo / phiếu. ``None`` → Chưa phân loại."""
    if not tk:
        return CHUA_PHAN_LOAI
    return f"{tk.get('ten_goi')} · {tk.get('so_tai_khoan')}"


def _iso(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None


def _ra(r: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "ten_goi": r["ten_goi"],
        "ngan_hang": r["ngan_hang"],
        "so_tai_khoan": r["so_tai_khoan"],
        "chu_tai_khoan": r["chu_tai_khoan"],
        "location_id": str(r["location_id"]) if r["location_id"] else None,
        "ten_co_so": r.get("ten_co_so"),
        "mac_dinh": bool(r["mac_dinh"]),
        "dang_dung": bool(r["dang_dung"]),
        "so_lan_thu": int(r.get("so_lan_thu") or 0),
        "sua_luc": _iso(r.get("sua_luc")),
        "sua_boi": r.get("sua_boi_ten"),
    }


_DS_SQL = """
SELECT t.id, t.ten_goi, t.ngan_hang, t.so_tai_khoan, t.chu_tai_khoan,
       t.location_id, l.name AS ten_co_so, t.mac_dinh, t.dang_dung, t.sua_luc,
       s.full_name AS sua_boi_ten,
       (SELECT count(*) FROM public.payment_cycle pc
         WHERE pc.clinic_id = t.clinic_id AND pc.tai_khoan_nhan_id = t.id) AS so_lan_thu
  FROM public.tai_khoan_nhan t
  LEFT JOIN public.clinic_location l ON l.id = t.location_id
  LEFT JOIN public.staff s ON s.id = t.sua_boi
 WHERE t.clinic_id = $1::uuid
 ORDER BY t.dang_dung DESC, l.name NULLS FIRST, t.ten_goi
"""

_CO_SO_LUOT_SQL = """
SELECT coalesce(v.location_id, a.location_id)::text
  FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""


async def doc_ds(
    conn: asyncpg.Connection | asyncpg.Pool, clinic_id: str
) -> list[dict[str, Any]]:
    """Cả danh mục (kể cả đã tắt) của phòng khám."""
    return [_ra(r) for r in await conn.fetch(_DS_SQL, clinic_id)]


async def ten_cac_tai_khoan(
    conn: asyncpg.Connection | asyncpg.Pool, clinic_id: str
) -> dict[str, str]:
    """id → "Tên gọi · số" — cho báo cáo (cả tài khoản đã tắt)."""
    rows = await conn.fetch(
        "SELECT id::text AS id, ten_goi, so_tai_khoan FROM public.tai_khoan_nhan"
        " WHERE clinic_id = $1::uuid",
        clinic_id,
    )
    return {r["id"]: nhan_tai_khoan(dict(r)) for r in rows}


async def co_so_cua_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> str | None:
    v = await conn.fetchval(_CO_SO_LUOT_SQL, clinic_id, visit_id)
    return str(v) if v else None


async def chon_cho_lan_thu(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    chon: str | None,
) -> str | None:
    """Tài khoản nhận sẽ ghi cho phần chuyển khoản của một lần thu (trong giao
    dịch thu). Thu ngân có chọn → phải đang dùng + dùng được ở cơ sở của lượt,
    không thì 422; không chọn → ``chon_mac_dinh``."""
    ds = await doc_ds(conn, clinic_id)
    co_so = await co_so_cua_luot(conn, clinic_id, visit_id)
    if chon is None:
        return chon_mac_dinh(ds, co_so)
    tk = next((t for t in ds if t["id"] == chon), None)
    if tk is None:
        raise ValidationError("Không tìm thấy tài khoản nhận này — tải lại rồi chọn.")
    if not dung_duoc(tk, co_so):
        raise ValidationError(
            f"Tài khoản “{tk['ten_goi']}” "
            + ("đã tắt" if not tk["dang_dung"] else "thuộc cơ sở khác")
            + " — chọn tài khoản khác."
        )
    return chon


class TaiKhoanNhanService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def danh_sach(
        self, *, identity: StaffIdentity, visit_id: str | None = None
    ) -> dict[str, Any]:
        """Danh mục cho màn quản trị (Quản lý: cả tài khoản đã tắt) và cho khối
        thu (mọi người: tài khoản dùng được ở cơ sở của lượt + mặc định)."""
        vid = doc_id(visit_id, cau="Lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            quan_ly = await can(conn, identity, QUYEN_QUAN_LY)
            ds = await doc_ds(conn, identity.clinic_id)
            co_so = (
                await co_so_cua_luot(conn, identity.clinic_id, vid)
                if vid
                else identity.location_id
            )
        return {
            "tai_khoan": ds if quan_ly else [t for t in ds if t["dang_dung"]],
            "dung_duoc": [t["id"] for t in ds if dung_duoc(t, co_so)],
            "mac_dinh": chon_mac_dinh(ds, co_so),
            "co_so": co_so,
            "quan_ly": quan_ly,
        }

    async def _ghi(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        tk_id: str | None,
        f: dict[str, Any],
    ) -> str:
        if f["location_id"] is not None and not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.clinic_location"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid)",
            f["location_id"],
            identity.clinic_id,
        ):
            raise ValidationError("Cơ sở không thuộc phòng khám này.")
        if f["mac_dinh"]:
            # Mỗi cơ sở một mặc định: bỏ mặc định cũ của cùng nhóm cơ sở trước.
            await conn.execute(
                """
                UPDATE public.tai_khoan_nhan
                   SET mac_dinh = false, sua_luc = now(), sua_boi = $3::uuid
                 WHERE clinic_id = $1::uuid AND mac_dinh
                   AND location_id IS NOT DISTINCT FROM $2::uuid
                   AND ($4::uuid IS NULL OR id <> $4::uuid)
                """,
                identity.clinic_id,
                f["location_id"],
                identity.staff_id,
                tk_id,
            )
        try:
            if tk_id is None:
                v = await conn.fetchval(
                    """
                    INSERT INTO public.tai_khoan_nhan
                        (clinic_id, location_id, ten_goi, ngan_hang, so_tai_khoan,
                         chu_tai_khoan, mac_dinh, dang_dung, tao_boi, sua_boi)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8,
                            $9::uuid, $9::uuid)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    f["location_id"],
                    f["ten_goi"],
                    f["ngan_hang"],
                    f["so_tai_khoan"],
                    f["chu_tai_khoan"],
                    f["mac_dinh"],
                    f["dang_dung"],
                    identity.staff_id,
                )
            else:
                v = await conn.fetchval(
                    """
                    UPDATE public.tai_khoan_nhan
                       SET location_id = $3::uuid, ten_goi = $4, ngan_hang = $5,
                           so_tai_khoan = $6, chu_tai_khoan = $7, mac_dinh = $8,
                           dang_dung = $9, sua_luc = now(), sua_boi = $10::uuid
                     WHERE clinic_id = $1::uuid AND id = $2::uuid
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    tk_id,
                    f["location_id"],
                    f["ten_goi"],
                    f["ngan_hang"],
                    f["so_tai_khoan"],
                    f["chu_tai_khoan"],
                    f["mac_dinh"],
                    f["dang_dung"],
                    identity.staff_id,
                )
        except asyncpg.UniqueViolationError as exc:
            if "ux_tai_khoan_nhan_so" in str(exc):
                raise ConflictError(
                    "Số tài khoản này đã có trong danh mục — sửa dòng cũ (bật lại"
                    " nếu đã tắt) thay vì thêm mới."
                ) from None
            raise ConflictError(
                "Cơ sở này vừa có tài khoản mặc định khác — tải lại rồi lưu."
            ) from None
        if v is None:
            raise NotFoundError("Không tìm thấy tài khoản nhận này.")
        await record_event(
            conn,
            event_type="config.receiving_account_saved",
            aggregate_type="tai_khoan_nhan",
            aggregate_id=str(v),
            identity=identity,
            origin="api:tai-khoan-nhan",
            payload={
                "moi": tk_id is None,
                "location_id": f["location_id"],
                "mac_dinh": f["mac_dinh"],
                "dang_dung": f["dang_dung"],
            },
        )
        return str(v)

    async def luu(
        self,
        *,
        identity: StaffIdentity,
        data: Mapping[str, Any],
        tai_khoan_id: str | None = None,
    ) -> dict[str, Any]:
        """Thêm (``tai_khoan_id`` None) hoặc sửa một tài khoản — cả bật / tắt và
        đặt mặc định. Tắt tài khoản đang mặc định = bỏ mặc định luôn."""
        tk_id = doc_id(tai_khoan_id)
        f = doc_form(data)
        async with self._pool.acquire() as conn:
            if not await can(conn, identity, QUYEN_QUAN_LY):
                raise SafetyGateError(
                    "Chỉ người có quyền Cài đặt phòng khám sửa được tài khoản nhận."
                )
            async with conn.transaction():
                v = await self._ghi(conn, identity, tk_id, f)
            ds = await doc_ds(conn, identity.clinic_id)
        return {"ok": True, "id": v, "tai_khoan": next(t for t in ds if t["id"] == v)}

    async def doi_cho_lan_thu(
        self,
        *,
        identity: StaffIdentity,
        payment_cycle_id: str,
        tai_khoan_id: object,
        tai_khoan_cu: object = None,
        ly_do: object = None,
    ) -> dict[str, Any]:
        """Sửa tài khoản nhận của một phiếu (đã thu hoặc đang chờ xác minh) — hoàn
        tác chọn nhầm. Vết ở event_log. ``tai_khoan_cu`` (màn đang thấy) khác
        hiện tại → 409, không đè người vừa sửa."""
        moi = doc_id(tai_khoan_id)
        if moi is None:
            raise ValidationError("Chọn tài khoản nhận.")
        cu_man = doc_id(tai_khoan_cu) if tai_khoan_cu not in (None, "") else None
        ly = ly_do.strip()[:500] if isinstance(ly_do, str) and ly_do.strip() else None
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            if not identity.cashier_head_scope and not any(
                [await can(conn, identity, q) for q in QUYEN_DOI]
            ):
                raise SafetyGateError(
                    "Bạn không có quyền thu tiền nên không sửa được tài khoản nhận."
                )
            async with conn.transaction():
                lan = await conn.fetchrow(
                    """
                    SELECT pc.visit_id::text AS visit_id, pc.kind, pc.status,
                           pc.amount, pc.method, pc.tai_khoan_nhan_id::text AS tk,
                           phan_thu_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                             pc.method, pc.amount) AS phan
                      FROM public.payment_cycle pc
                     WHERE pc.clinic_id = $1::uuid AND pc.payment_cycle_id = $2::uuid
                     FOR UPDATE
                    """,
                    cid,
                    payment_cycle_id,
                )
                if lan is None:
                    raise NotFoundError("Không tìm thấy phiếu thu này.")
                if identity.cashier_head_scope and not head_money_grant(
                    identity, str(lan["kind"]), str(lan["visit_id"])
                ):
                    raise SafetyGateError(
                        "Phiếu không thuộc loại tiền được phép xử lý."
                    )
                if lan["status"] not in ("PAID", "PENDING_VERIFICATION"):
                    raise ConflictError(
                        "Phiếu đã huỷ — không sửa tài khoản nhận."
                        if lan["status"] == "VOIDED"
                        else "Lần chờ đã huỷ — không sửa tài khoản nhận."
                    )
                ck = so_tien_chuyen_khoan(
                    doc_phan_db(lan["phan"]), lan["method"], int(lan["amount"])
                )
                if ck <= 0:
                    raise ConflictError(
                        "Phiếu này không có phần chuyển khoản — không cần tài"
                        " khoản nhận."
                    )
                if lan["tk"] == moi:
                    return {
                        "ok": True,
                        "payment_cycle_id": payment_cycle_id,
                        "da_la": True,
                    }
                if cu_man is not None and cu_man != lan["tk"]:
                    raise ConflictError(
                        "Tài khoản nhận của phiếu vừa được người khác sửa — tải lại."
                    )
                await chon_cho_lan_thu(
                    conn, clinic_id=cid, visit_id=str(lan["visit_id"]), chon=moi
                )
                await conn.execute(
                    "UPDATE public.payment_cycle SET tai_khoan_nhan_id = $3::uuid"
                    " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid",
                    cid,
                    payment_cycle_id,
                    moi,
                )
                await record_event(
                    conn,
                    event_type="payment.receiving_account_changed",
                    aggregate_type="payment_cycle",
                    aggregate_id=payment_cycle_id,
                    identity=identity,
                    origin="api:payment-doi-tai-khoan",
                    correlation_id=str(lan["visit_id"]),
                    payload={
                        "payment_cycle_id": payment_cycle_id,
                        "visit_id": lan["visit_id"],
                        "kind": lan["kind"],
                        "chuyen_khoan": ck,
                        "tai_khoan_cu": lan["tk"],
                        "tai_khoan_moi": moi,
                        "ly_do": ly,
                    },
                )
        logger.info(
            "payment_receiving_account_changed",
            payment_cycle_id=payment_cycle_id,
            tu=lan["tk"],
            sang=moi,
            by_staff_id=identity.staff_id,
        )
        return {
            "ok": True,
            "payment_cycle_id": payment_cycle_id,
            "tai_khoan_cu": lan["tk"],
            "tai_khoan_moi": moi,
        }


__all__ = [
    "CHUA_PHAN_LOAI",
    "QUYEN_QUAN_LY",
    "TaiKhoanNhanService",
    "chon_cho_lan_thu",
    "chon_mac_dinh",
    "doc_form",
    "dung_duoc",
    "nhan_tai_khoan",
    "ten_cac_tai_khoan",
]
