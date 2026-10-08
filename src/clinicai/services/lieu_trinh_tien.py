"""Liệu trình — tiền trả trước ở quầy thu dịch vụ (B2, 08/10/2026).

Q3: tiền LUÔN thu ở quầy khi khách có mặt. Khối "Liệu trình" của quầy (khách
đang thu): buổi đã làm / đã trả / còn lại / tiền còn lại, [Trả trước … buổi]
(1…tối đa, nút "Trả hết") → một dòng ``lieu_trinh_tra_truoc`` của lượt → hoá
đơn dịch vụ có thêm dòng ``source_type = 'lieu_trinh'`` (k × đơn giá CHỐT).
Thu, huỷ phiếu, hoàn tác, hoàn tiền: các lệnh tiền sẵn có — không đường thứ hai.

Buổi hôm nay đã nằm trong hoá đơn (thu lẻ) KHÔNG tính vào "trả trước": tối đa
= số buổi − đã trả − đã thu lẻ − đang chờ thu ở lượt khác − buổi trong hoá đơn
hôm nay. Vì thế "trả hết" một liệu trình 10 buổi khi buổi 1 đang trong hoá đơn
= buổi 1 thu lẻ + trả trước 9 — không thu trùng buổi 1 (#2).

Chia tiền trả trước cho từng buổi (phủ / bỏ phủ) là việc của Postgres, chạy mỗi
khi sổ tiền đổi (migration 20261008110000). Ở đây chỉ đọc + đặt / bỏ ý định.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import LieuTrinhTraTruocDaDat
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

QUYEN_THU = "payment.service.collect"
HET = "het"


#: #16 (giữ chặn — đặc tả): hoàn tác / huỷ phiếu lần thu có tiền trả trước mà
#: buổi đã làm bằng tiền ấy. Câu cho thu ngân — nói lối đi tiếp.
CAU_HUY_TRA_TRUOC_DA_DUNG = (
    "Lần thu này có tiền trả trước liệu trình và khách đã làm buổi bằng tiền ấy"
    " — không hoàn tác / huỷ phiếu được. Thu nhầm số buổi thì hoàn phần buổi CHƯA"
    " dùng bằng [Hoàn tiền] ở tab “Đã thanh toán”."
)


def loi_tien_lieu_trinh(
    e: asyncpg.PostgresError, *, cau_phu_vuot: str | None = None
) -> Exception:
    """Lỗi bất biến LIỆU TRÌNH từ lệnh tiền (huỷ phiếu, hoàn tiền) → 409 có câu;
    lỗi khác trả nguyên để nơi gọi ném lại như cũ. ``cau_phu_vuot`` thay câu kỹ
    thuật của Postgres khi lệnh làm buổi đã làm mất tiền trả trước."""
    from clinicai.services.lieu_trinh_service import RANG_BUOC_LIEU_TRINH, loi_db

    ten = getattr(e, "constraint_name", None) or ""
    if ten == "lieu_trinh_phu_vuot" and cau_phu_vuot:
        return LuotKhamConflictError("PHU_VUOT_DA_TRA", cau_phu_vuot)
    if ten in RANG_BUOC_LIEU_TRINH:
        return loi_db(e)
    nguyen: Exception = e
    return nguyen


def toi_da_tra_truoc(
    *, so_buoi: int, da_tra: int, tra_le: int, cho_noi_khac: int, buoi_hom_nay: int
) -> int:
    """Số buổi còn trả trước được ở lượt này. Thuần."""
    return max(so_buoi - da_tra - tra_le - cho_noi_khac - buoi_hom_nay, 0)


def doc_so_buoi_tra(raw: Any, toi_da: int) -> int | None:
    """``"het"`` → tối đa; số nguyên 1..tối đa; rác → None (không ném)."""
    if isinstance(raw, str) and raw.strip().lower() == HET:
        return toi_da if toi_da >= 1 else None
    if isinstance(raw, bool):
        return None
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= toi_da else None


#: Mỗi liệu trình của khách + các con số quầy cần, so với MỘT lượt đang thu.
_QUAY_SQL = """
SELECT lt.id::text AS id,
       public.lieu_trinh_so_buoi_da_tra(lt.clinic_id, lt.id) AS da_tra,
       (SELECT count(*) FROM public.lieu_trinh_buoi b
         WHERE b.lieu_trinh_id = lt.id AND b.go_luc IS NULL AND NOT b.tra_truoc
           AND public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id))
           AS tra_le,
       (SELECT coalesce(sum(t.so_buoi), 0) FROM public.lieu_trinh_tra_truoc t
          JOIN public.visit v
            ON v.clinic_id = t.clinic_id AND v.visit_id = t.visit_id
           AND v.closed_at IS NULL
         WHERE t.clinic_id = lt.clinic_id AND t.lieu_trinh_id = lt.id
           AND t.bo_luc IS NULL AND t.visit_id <> $3::uuid
           AND NOT EXISTS (
               SELECT 1 FROM public.payment_bill_line bl
                 JOIN public.payment_cycle c
                   ON c.clinic_id = bl.clinic_id
                  AND c.payment_cycle_id = bl.payment_cycle_id
                WHERE bl.clinic_id = t.clinic_id AND bl.source_type = 'lieu_trinh'
                  AND bl.source_id = t.id::text AND c.status = 'PAID'))
           AS cho_noi_khac,
       (SELECT count(*) FROM public.lieu_trinh_buoi b
          JOIN public.service_order o
            ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
         WHERE b.lieu_trinh_id = lt.id AND b.go_luc IS NULL AND NOT b.tra_truoc
           AND o.visit_id = $3::uuid
           AND NOT public.lieu_trinh_buoi_da_thu_le(b.clinic_id, b.service_order_id))
           AS buoi_hom_nay,
       -- Dòng ĐANG CHỌN của lượt: chưa bỏ, chưa nằm trong lần thu giữ phủ.
       (SELECT jsonb_build_object('id', t.id, 'so_buoi', t.so_buoi,
                                  'don_gia', t.don_gia)
          FROM public.lieu_trinh_tra_truoc t
         WHERE t.clinic_id = lt.clinic_id AND t.lieu_trinh_id = lt.id
           AND t.visit_id = $3::uuid AND t.bo_luc IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM public.payment_bill_line bl
                 JOIN public.payment_cycle c
                   ON c.clinic_id = bl.clinic_id
                  AND c.payment_cycle_id = bl.payment_cycle_id
                WHERE bl.clinic_id = t.clinic_id AND bl.source_type = 'lieu_trinh'
                  AND bl.source_id = t.id::text
                  AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
         ORDER BY t.chon_luc DESC LIMIT 1) AS dang_chon
  FROM public.lieu_trinh lt
 WHERE lt.clinic_id = $1::uuid AND lt.id = ANY($2::uuid[])
"""

#: Dòng trả trước đã thu còn hoàn được (Q5 — dừng giữa chừng hoàn buổi dư):
#: nút hoàn của quầy gọi đúng lệnh hoàn tiền sẵn có với các mã này.
_HOAN_DUOC_SQL = """
SELECT t.lieu_trinh_id::text AS lieu_trinh_id, bl.id::text AS payment_bill_line_id,
       bl.payment_cycle_id::text AS payment_cycle_id, bl.visit_id::text AS visit_id,
       bl.quantity, bl.unit_price, c.paid_at,
       bl.quantity - coalesce((
           SELECT sum(rl.quantity) FROM public.payment_refund_line rl
             JOIN public.payment_refund r
               ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
            WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
              AND r.status IN ('PENDING', 'COMPLETED')), 0) AS con_lai
  FROM public.lieu_trinh_tra_truoc t
  JOIN public.payment_bill_line bl
    ON bl.clinic_id = t.clinic_id AND bl.source_type = 'lieu_trinh'
   AND bl.source_id = t.id::text
  JOIN public.payment_cycle c
    ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
   AND c.status = 'PAID'
 WHERE t.clinic_id = $1::uuid AND t.lieu_trinh_id = ANY($2::uuid[])
 ORDER BY c.paid_at DESC
"""


class LieuTrinhTienService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _doi_thu(self, conn: asyncpg.Connection, identity: StaffIdentity) -> None:
        if not await can(conn, identity, QUYEN_THU):
            raise SafetyGateError(
                "Chỉ người có lego Thu tiền dịch vụ mới đặt trả trước liệu trình."
            )

    async def _so_lieu(
        self, conn: asyncpg.Connection, cid: str, vid: str, ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for r in await conn.fetch(_QUAY_SQL, cid, ids, vid):
            d = dict(r)
            dang = d.pop("dang_chon")
            if isinstance(dang, str):
                dang = json.loads(dang)
            d["dang_chon"] = (
                None
                if dang is None
                else {
                    "id": str(dang["id"]),
                    "so_buoi": int(dang["so_buoi"]),
                    "don_gia": int(dang["don_gia"]),
                }
            )
            out[d["id"]] = d
        return out

    async def quay(self, *, identity: StaffIdentity, visit_id: Any) -> dict[str, Any]:
        """Khối "Liệu trình" của quầy cho khách của lượt đang thu."""
        from clinicai.services.lieu_trinh_service import LieuTrinhService

        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._doi_thu(conn, identity)
            pid = await conn.fetchval(
                "SELECT clinic_patient_id::text FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                cid,
                vid,
            )
            if pid is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            ds = await LieuTrinhService.doc_nhieu(
                conn, cid, "lt.clinic_patient_id = $2::uuid", pid, kem_buoi=False
            )
            ids = [d["id"] for d in ds]
            so = await self._so_lieu(conn, cid, vid, ids) if ids else {}
            hoan = (
                [dict(r) for r in await conn.fetch(_HOAN_DUOC_SQL, cid, ids)]
                if ids
                else []
            )
        out: list[dict[str, Any]] = []
        for lt in ds:
            s = so.get(lt["id"], {})
            dang = s.get("dang_chon")
            # Dòng đang chọn (chưa thu) của chính lượt này không chiếm chỗ của nó.
            toi_da = toi_da_tra_truoc(
                so_buoi=lt["so_buoi"],
                da_tra=int(s.get("da_tra") or 0),
                tra_le=int(s.get("tra_le") or 0),
                cho_noi_khac=int(s.get("cho_noi_khac") or 0),
                buoi_hom_nay=int(s.get("buoi_hom_nay") or 0),
            )
            dong_hoan = [
                {
                    "payment_cycle_id": h["payment_cycle_id"],
                    "payment_bill_line_id": h["payment_bill_line_id"],
                    "visit_id": h["visit_id"],
                    "con_hoan_duoc": int(h["con_lai"]),
                    "don_gia": int(h["unit_price"] or 0),
                    "luc_thu": h["paid_at"].isoformat() if h["paid_at"] else None,
                }
                for h in hoan
                if h["lieu_trinh_id"] == lt["id"] and int(h["con_lai"]) > 0
            ]
            hien = (
                lt["trang_thai"] in ("DE_XUAT", "DANG_LAM")
                or lt["con_tra_truoc"] > 0
                or dang is not None
            )
            if not hien:
                continue
            out.append(
                {
                    **{
                        k: lt[k]
                        for k in (
                            "id",
                            "service_code",
                            "service_name",
                            "trang_thai",
                            "so_buoi",
                            "don_gia",
                            "da_lam",
                            "da_tra",
                            "tra_le",
                            "con_lai",
                            "con_tra_truoc",
                            "chua_tra",
                            "tien_con_lai",
                            "revision",
                        )
                    },
                    "buoi_hom_nay_trong_hoa_don": int(s.get("buoi_hom_nay") or 0),
                    "tra_truoc_dang_chon": dang,
                    "tra_truoc_toi_da": toi_da,
                    # #3: hết buổi đã trả mà kế hoạch còn → quầy gợi ý trả thêm.
                    "goi_y_tra_them": lt["con_tra_truoc"] == 0
                    and toi_da > 0
                    and lt["trang_thai"] == "DANG_LAM",
                    # Q5: buổi đã trả chưa dùng còn hoàn được (min với từng dòng).
                    "hoan_duoc_toi_da": lt["con_tra_truoc"],
                    "dong_hoan_duoc": dong_hoan,
                }
            )
        return {"visit_id": vid, "clinic_patient_id": pid, "lieu_trinh": out}

    async def dat_tra_truoc(
        self,
        *,
        identity: StaffIdentity,
        visit_id: Any,
        lieu_trinh_id: Any,
        so_buoi: Any,
        expected_so_buoi: Any = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """[Trả trước k buổi] / [Trả hết] (``so_buoi = "het"``) vào hoá đơn đang
        thu. Bấm lại = đổi số buổi của dòng đang chọn. ``expected_so_buoi`` =
        số màn đang thấy (rỗng = chưa chọn) — lệch → 409."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        if not idempotency_key:
            raise ValidationError("Thiếu khoá gửi lại (idempotency_key).")
        mong = None if expected_so_buoi in (None, "") else _so_nguyen(expected_so_buoi)
        cid = identity.clinic_id
        payload = {"vid": vid, "lt": lt, "so_buoi": str(so_buoi), "mong": mong}
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                await self._doi_thu(conn, identity)
                cached = await bien_nhan_doc(
                    conn, identity, "lieu_trinh.tra_truoc", idempotency_key, payload
                )
                if cached is not None:
                    return cached
                await khoa_luot(conn, cid, vid)
                row = await conn.fetchrow(
                    "SELECT lt.so_buoi, lt.don_gia, lt.trang_thai, lt.service_name"
                    "  FROM lieu_trinh lt JOIN visit v"
                    "    ON v.clinic_id = lt.clinic_id"
                    "   AND v.clinic_patient_id = lt.clinic_patient_id"
                    " WHERE lt.clinic_id = $1::uuid AND lt.id = $2::uuid"
                    "   AND v.visit_id = $3::uuid FOR UPDATE OF lt",
                    cid,
                    lt,
                    vid,
                )
                if row is None:
                    raise NotFoundError("Không tìm thấy liệu trình này của khách.")
                if int(row["don_gia"]) <= 0:
                    raise LuotKhamConflictError(
                        "DON_GIA_0", "Liệu trình 0đ — không có gì để trả trước."
                    )
                s = (await self._so_lieu(conn, cid, vid, [lt]))[lt]
                dang = s["dang_chon"]
                hien = None if dang is None else dang["so_buoi"]
                if hien != mong:
                    raise LuotKhamConflictError(
                        "STALE_TRA_TRUOC",
                        "Số buổi trả trước vừa được đổi ở máy khác — đã tải lại,"
                        " xem rồi bấm lại.",
                    )
                toi_da = toi_da_tra_truoc(
                    so_buoi=int(row["so_buoi"]),
                    da_tra=int(s["da_tra"]),
                    tra_le=int(s["tra_le"]),
                    cho_noi_khac=int(s["cho_noi_khac"]),
                    buoi_hom_nay=int(s["buoi_hom_nay"]),
                )
                n = doc_so_buoi_tra(so_buoi, toi_da)
                if n is None:
                    raise LuotKhamConflictError(
                        "TRA_VUOT",
                        f"Chỉ trả trước được 1–{toi_da} buổi (liệu trình"
                        f" {row['so_buoi']} buổi, đã trả {s['da_tra']}, buổi hôm nay"
                        f" trong hoá đơn {s['buoi_hom_nay']})."
                        if toi_da
                        else "Liệu trình không còn buổi nào để trả trước.",
                        {"toi_da": toi_da},
                    )
                if dang is not None:
                    tid = dang["id"]
                    await conn.execute(
                        "UPDATE lieu_trinh_tra_truoc SET so_buoi = $3,"
                        " chon_boi = $4::uuid, chon_luc = now()"
                        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                        cid,
                        tid,
                        n,
                        identity.staff_id,
                    )
                else:
                    tid = str(
                        await conn.fetchval(
                            "INSERT INTO lieu_trinh_tra_truoc"
                            " (clinic_id, visit_id, lieu_trinh_id, so_buoi, don_gia,"
                            "  chon_boi)"
                            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6::uuid)"
                            " RETURNING id",
                            cid,
                            vid,
                            lt,
                            n,
                            row["don_gia"],
                            identity.staff_id,
                        )
                    )
                await self._phat(conn, identity, vid, lt, tid, n, row["don_gia"], "dat")
                kq = {
                    "ok": True,
                    "tra_truoc_id": tid,
                    "so_buoi": n,
                    "don_gia": int(row["don_gia"]),
                    "thanh_tien": n * int(row["don_gia"]),
                    "toi_da": toi_da,
                }
                await bien_nhan_ghi(
                    conn,
                    identity,
                    "lieu_trinh.tra_truoc",
                    idempotency_key,
                    payload,
                    tid,
                    kq,
                )
        except (asyncpg.CheckViolationError, asyncpg.UniqueViolationError) as e:
            raise loi_tien_lieu_trinh(e) from None
        return kq

    async def bo_tra_truoc(
        self,
        *,
        identity: StaffIdentity,
        tra_truoc_id: Any,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Bỏ dòng trả trước khỏi hoá đơn đang thu (chưa thu). Đã nằm trong lần
        thu → 409: hoàn tác lần thu trước (luật chung như vật tư)."""
        tid = _uuid(tra_truoc_id, "Mã dòng trả trước không hợp lệ.")
        if not idempotency_key:
            raise ValidationError("Thiếu khoá gửi lại (idempotency_key).")
        cid = identity.clinic_id
        payload = {"tid": tid}
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                await self._doi_thu(conn, identity)
                cached = await bien_nhan_doc(
                    conn, identity, "lieu_trinh.bo_tra_truoc", idempotency_key, payload
                )
                if cached is not None:
                    return cached
                r = await conn.fetchrow(
                    "SELECT visit_id::text AS vid, lieu_trinh_id::text AS lt, so_buoi,"
                    "       don_gia, bo_luc FROM lieu_trinh_tra_truoc"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    tid,
                )
                if r is None:
                    raise NotFoundError("Không tìm thấy dòng trả trước này.")
                await khoa_luot(conn, cid, r["vid"])
                doi = r["bo_luc"] is None
                if doi:
                    await conn.execute(
                        "UPDATE lieu_trinh_tra_truoc SET bo_luc = now(),"
                        " bo_boi = $3::uuid"
                        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                        cid,
                        tid,
                        identity.staff_id,
                    )
                    await self._phat(
                        conn,
                        identity,
                        r["vid"],
                        r["lt"],
                        tid,
                        int(r["so_buoi"]),
                        r["don_gia"],
                        "bo",
                    )
                kq = {"ok": True, "changed": doi, "tra_truoc_id": tid}
                await bien_nhan_ghi(
                    conn,
                    identity,
                    "lieu_trinh.bo_tra_truoc",
                    idempotency_key,
                    payload,
                    tid,
                    kq,
                )
        except (asyncpg.CheckViolationError, asyncpg.UniqueViolationError) as e:
            raise loi_tien_lieu_trinh(e) from None
        return kq

    @staticmethod
    async def _phat(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        vid: str,
        lt: str,
        tid: str,
        so_buoi: int,
        don_gia: Any,
        hanh_dong: str,
    ) -> None:
        await emit_event(
            conn,
            ten="lieu_trinh.prepay_set",
            clinic_id=identity.clinic_id,
            aggregate_id=lt,
            so_ke_tiep=True,
            payload=LieuTrinhTraTruocDaDat(
                visit_id=vid,
                lieu_trinh_id=lt,
                tra_truoc_id=tid,
                so_buoi=so_buoi,
                don_gia=int(don_gia),
                hanh_dong=hanh_dong,
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )


def _so_nguyen(raw: Any) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValidationError("Số buổi màn đang thấy không hợp lệ.") from None


__all__ = [
    "CAU_HUY_TRA_TRUOC_DA_DUNG",
    "HET",
    "LieuTrinhTienService",
    "doc_so_buoi_tra",
    "loi_tien_lieu_trinh",
    "toi_da_tra_truoc",
]
