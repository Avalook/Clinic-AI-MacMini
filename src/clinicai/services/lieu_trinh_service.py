"""Liệu trình điều trị nhiều buổi — kế hoạch, buổi, lịch sử (B1, 08/10/2026).

Đặc tả: ``docs/KE-HOACH-LIEU-TRINH.md`` Phần B. Liệu trình = SỔ KẾ HOẠCH của một
khách cho một dịch vụ nhóm DIEU_TRI (số buổi, đơn giá CHỐT lúc tạo, ghi chú tần
suất). Mỗi buổi vẫn là một ``service_order`` thường; nối qua ``lieu_trinh_buoi``.

Phần Postgres (migration 20261008100000) giữ mọi luật có tranh chấp:
  * gắn / gỡ buổi theo trạng thái chỉ định — trigger trên ``service_order``, một
    chỗ cho mọi đường tạo chỉ định;
  * ``trang_thai`` SUY RA (DE_XUAT / DANG_LAM / XONG / DUNG) — không ai ghi tay;
  * lịch sử chỉ-thêm, revision tăng mỗi lần kế hoạch đổi;
  * buổi dùng tiền trả trước ≤ số buổi đã trả (khoá dòng liệu trình).

Ở đây: quyền, đọc cho các màn, và lệnh của người (có ``expected_revision`` →
409 khi màn cầm bản cũ, có khoá gửi lại ``idempotency_key``). Lỗi bất biến của
Postgres đổi thành 409 kèm câu cho người bấm — không bao giờ 500.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import LieuTrinhBuoiDaDoi, LieuTrinhDaSua, LieuTrinhDaTao
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.permissions.y_khoa import QUYEN_Y_KHOA
from clinicai.services.bill_service import CLINIC, giai_gia
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    bien_nhan_doc,
    bien_nhan_ghi,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.service_execution_service import NOI_BAN_KHAM

#: Đề xuất / điều chỉnh / dừng / mở lại / gắn-gỡ buổi: khối y khoa (bác sĩ, ĐD,
#: TKYK) + trưởng ca (quản lý có mọi khối).
QUYEN_SUA: tuple[str, ...] = (*QUYEN_Y_KHOA, "clinical.order.place", "dispatch.manage")
#: CSKH đăng ký (khách gọi lại nhận liệu trình) — và dừng khi khách báo thôi.
QUYEN_CSKH: tuple[str, ...] = ("crm.manage", "booking.create")
QUYEN_DANG_KY: tuple[str, ...] = (*QUYEN_SUA, *QUYEN_CSKH)
#: Đọc: mọi màn có thẻ / khối liệu trình (hồ sơ khám, quầy, CSKH, tiếp đón).
QUYEN_DOC: tuple[str, ...] = (
    *QUYEN_DANG_KY,
    "payment.service.collect",
    "reception.checkin.perform",
)

SO_BUOI_TOI_DA = 200
GHI_CHU_TOI_DA = 1000
LY_DO_TOI_DA = 500
QUA_NGAY_MAC_DINH = 14
QUA_NGAY_TOI_DA = 3650
TRAN_DANH_SACH = 200
TRAN_LUOT = 300

#: "Sắp hết lộ trình" (Tuyền 08/10/2026): liệu trình đang làm còn ≤ ngần này buổi
#: chưa làm thì CSKH gọi tư vấn thêm buổi / đặt lịch buổi kế. MỘT chỗ để đổi.
SAP_HET_CON_TOI_DA = 1
#: Tiền tố mã "đã xử lý" ghi vào ``tuong_tac_cskh.trang_thai_ma`` — mã đầy đủ là
#: MỐC ``LT_SAP_HET:<liệu trình>:<đã làm>:<số buổi>:<đã trả>``: mốc đổi (làm thêm
#: buổi, thêm buổi, trả thêm) thì dòng hiện lại.
MA_SAP_HET = "LT_SAP_HET"

#: Lần sửa người bấm hoàn tác được (lần tự động thì không — nó là hệ quả).
HANH_DONG_HOAN_TAC_DUOC = frozenset(
    {"DIEU_CHINH", "DANG_KY", "DUNG", "MO_LAI", "HOAN_TAC"}
)

#: Tên ràng buộc Postgres → mã 409 cho màn.
_MA_LOI_DB: dict[str, str] = {
    "lieu_trinh_chi_dieu_tri": "KHONG_PHAI_DIEU_TRI",
    "lieu_trinh_bat_bien": "LIEU_TRINH_BAT_BIEN",
    "lieu_trinh_don_gia_chot": "DON_GIA_DA_CHOT",
    "lieu_trinh_so_buoi_duoi_gan": "SO_BUOI_DUOI_SO_GAN",
    "lieu_trinh_so_buoi_duoi_da_tra": "SO_BUOI_DUOI_DA_TRA",
    "lieu_trinh_buoi_khop": "BUOI_KHONG_KHOP",
    "lieu_trinh_buoi_da_dung": "LIEU_TRINH_DA_DUNG",
    "lieu_trinh_buoi_bat_bien": "LIEU_TRINH_BAT_BIEN",
    "lieu_trinh_phu_vuot": "PHU_VUOT_DA_TRA",
    "uq_lieu_trinh_buoi_chi_dinh_song": "DA_GAN_LIEU_TRINH",
    "uq_lieu_trinh_buoi_so_song": "TRUNG_SO_BUOI",
    # B2 — tiền trả trước.
    "lieu_trinh_tra_vuot": "TRA_VUOT",
    "lieu_trinh_tra_truoc_da_thu": "DA_NAM_TRONG_LAN_THU",
    "lieu_trinh_tra_truoc_da_dung": "LIEU_TRINH_DA_DUNG",
    "payment_bill_line_buoi_da_tra_truoc": "BUOI_DA_TRA_TRUOC",
}

#: Ràng buộc của liệu trình — lỗi khác (của bảng tiền cũ) để nguyên cho nơi gọi.
RANG_BUOC_LIEU_TRINH = frozenset(_MA_LOI_DB)

_KHONG_DOI: Any = object()

_GAN_TAY = "SELECT lieu_trinh_gan_buoi($1::uuid, $2::uuid, $3::uuid, 'TAY', $4::uuid)"
_GO_TAY = "SELECT lieu_trinh_go_buoi($1::uuid, $2::uuid, 'TAY', $3::uuid)"
_GO_CHUYEN = "SELECT lieu_trinh_go_buoi($1::uuid, $2::uuid, 'CHUYEN', $3::uuid)"


# ---------------------------------------------------------------------------
# Phần thuần — đọc đầu vào người dùng (rác → rỗng hoặc 422, không 500)
# ---------------------------------------------------------------------------


def doc_so_buoi(raw: Any) -> int | None:
    """Số buổi 1..200; rác / ngoài khoảng → None."""
    if isinstance(raw, bool):
        return None
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= SO_BUOI_TOI_DA else None


def doc_ghi_chu(raw: Any) -> str | None:
    """Ghi chú lộ trình: chuỗi gọn; rỗng → None; quá dài → 422."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationError("Ghi chú lộ trình phải là chữ.")
    gon = raw.strip()
    if len(gon) > GHI_CHU_TOI_DA:
        raise ValidationError(f"Ghi chú lộ trình tối đa {GHI_CHU_TOI_DA} ký tự.")
    return gon or None


def doc_so_ngay(raw: Any) -> int | None:
    """ "Quá X ngày chưa quay lại": số ngày 0..3650; rác → None (người gọi dùng
    mặc định) — KHÔNG ném (luật hàm nhận ngày/giờ từ người dùng)."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= QUA_NGAY_TOI_DA else None


def doc_ds_uuid(raw: Any, tran: int = TRAN_LUOT) -> list[str]:
    """Danh sách mã cách nhau dấu phẩy; mã rác bị bỏ qua (không ném)."""
    if not isinstance(raw, str):
        return []
    out: list[str] = []
    for phan in raw.split(","):
        try:
            ma = _uuid(phan.strip(), "")
        except ValidationError:
            continue
        if ma not in out:
            out.append(ma)
        if len(out) >= tran:
            break
    return out


def loi_db(e: asyncpg.PostgresError) -> LuotKhamConflictError:
    """Lỗi bất biến của Postgres → 409 có mã + câu đọc được (bỏ tiền tố bảng)."""
    ten = getattr(e, "constraint_name", None) or ""
    ma = _MA_LOI_DB.get(ten, "LIEU_TRINH_XUNG_DOT")
    cau = str(getattr(e, "message", None) or e)
    if ": " in cau:
        cau = cau.split(": ", 1)[1]
    if ma == "DA_GAN_LIEU_TRINH":
        cau = "Chỉ định này vừa được gắn vào một liệu trình khác — tải lại."
    elif ma == "TRUNG_SO_BUOI":
        cau = "Số buổi vừa được người khác dùng — tải lại rồi bấm lại."
    return LuotKhamConflictError(ma, cau[:1].upper() + cau[1:])


def con_lai(lt: dict[str, Any]) -> dict[str, int]:
    """Đếm của một liệu trình cho thẻ / quầy. Thuần."""
    so_buoi = int(lt["so_buoi"])
    da_lam = int(lt["da_lam"])
    da_tra = int(lt["da_tra"])
    dung_tra = int(lt["dung_tra_truoc"])
    return {
        "con_lai": max(so_buoi - da_lam, 0),
        "con_tra_truoc": max(da_tra - dung_tra, 0),
        "chua_tra": max(so_buoi - da_tra - int(lt.get("tra_le") or 0), 0),
    }


def ly_do_sap_het(lt: dict[str, Any]) -> str | None:
    """Vì sao liệu trình này "sắp hết lộ trình" (None = không sắp hết). Thuần.

    Chỉ liệu trình ĐANG LÀM còn buổi chưa làm, và:
      * còn ≤ ``SAP_HET_CON_TOI_DA`` buổi → "còn 1 buổi";
      * HOẶC đã dùng hết buổi trả trước (đã trả > 0, buổi đang dùng tiền trả
        trước ≥ đã trả) mà còn buổi chưa trả → "đã dùng hết 2 buổi trả trước,
        còn 1 buổi chưa trả".
    Cả hai cùng đúng → nối bằng " · "."""
    if lt.get("trang_thai") != "DANG_LAM":
        return None
    so_buoi = int(lt.get("so_buoi") or 0)
    da_lam = int(lt.get("da_lam") or 0)
    da_tra = int(lt.get("da_tra") or 0)
    phu = int(lt.get("dung_tra_truoc") or 0)
    con = so_buoi - da_lam
    if con <= 0:
        return None
    ly: list[str] = []
    if con <= SAP_HET_CON_TOI_DA:
        ly.append(f"còn {con} buổi")
    chua_tra = max(so_buoi - da_tra - int(lt.get("tra_le") or 0), 0)
    if da_tra > 0 and da_tra - phu <= 0 and chua_tra > 0:
        ly.append(f"đã dùng hết {da_tra} buổi trả trước, còn {chua_tra} buổi chưa trả")
    return " · ".join(ly) or None


def moc_sap_het(lt: dict[str, Any]) -> str:
    """Mốc "sắp hết" = (liệu trình, đã làm, số buổi, đã trả). Thuần."""
    return (
        f"{MA_SAP_HET}:{lt['id']}:{int(lt['da_lam'])}:{int(lt['so_buoi'])}"
        f":{int(lt['da_tra'])}"
    )


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, datetime) else v


def _json(v: Any) -> Any:
    if isinstance(v, str):
        return json.loads(v)
    return v


# ---------------------------------------------------------------------------
# SQL đọc
# ---------------------------------------------------------------------------

_LT_SQL = """
SELECT lt.id::text AS id, lt.clinic_patient_id::text AS khach_id,
       p.full_name AS ten_khach, p.patient_code AS ma_khach,
       p.phone_primary AS sdt,
       lt.service_code, lt.service_name, lt.so_buoi, lt.don_gia,
       lt.ghi_chu_lo_trinh, lt.trang_thai, lt.nguon,
       lt.nguon_visit_id::text AS nguon_visit_id,
       lt.nguon_order_id::text AS nguon_order_id,
       lt.tao_luc, sd.full_name AS de_xuat_boi,
       lt.dang_ky_luc, sk.full_name AS dang_ky_boi,
       lt.dung_luc, sg.full_name AS dung_boi, lt.ly_do_dung,
       lt.revision, lt.hanh_dong, lt.sua_luc,
       public.lieu_trinh_so_buoi_da_tra(lt.clinic_id, lt.id) AS da_tra,
       coalesce(b.so_gan, 0) AS so_gan, coalesce(b.da_lam, 0) AS da_lam,
       coalesce(b.dung_tra_truoc, 0) AS dung_tra_truoc,
       coalesce(b.tra_le, 0) AS tra_le, b.lan_cuoi, b.dang_cho,
       -- Loại khám nhóm Điều trị của đúng dịch vụ: CSKH [Đặt lịch buổi kế] mở bộ
       -- đặt lịch sẵn có khoá vào loại khám này (rỗng = chưa có, nút tắt).
       (SELECT st.id::text FROM public.service_type st
          JOIN public.service_price sp
            ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id
         WHERE st.clinic_id = lt.clinic_id AND st.nhom = 'DIEU_TRI'
           AND st.is_active AND sp.service_code = lt.service_code
         ORDER BY st.created_at, st.id LIMIT 1) AS service_type_id
  FROM public.lieu_trinh lt
  JOIN public.patient p ON p.clinic_patient_id = lt.clinic_patient_id
  LEFT JOIN public.staff sd ON sd.id = lt.de_xuat_boi
  LEFT JOIN public.staff sk ON sk.id = lt.dang_ky_boi
  LEFT JOIN public.staff sg ON sg.id = lt.dung_boi
  LEFT JOIN LATERAL (
      SELECT count(*) AS so_gan,
             count(*) FILTER (
                 WHERE (coalesce(o.execution_status, '') = 'COMPLETED'
                        OR (o.execution_status IS NULL
                            AND o.exec_status = 'performed')))
                 AS da_lam,
             count(*) FILTER (WHERE b.tra_truoc) AS dung_tra_truoc,
             count(*) FILTER (
                 WHERE NOT b.tra_truoc
                   AND public.lieu_trinh_buoi_da_thu_le(b.clinic_id,
                                                        b.service_order_id))
                 AS tra_le,
             max(coalesce(v.checked_in_at, v.created_at)) AS lan_cuoi,
             bool_or(coalesce(o.execution_status, 'PENDING') <> 'COMPLETED'
                     AND o.exec_status <> 'performed') AS dang_cho
        FROM public.lieu_trinh_buoi b
        JOIN public.service_order o
          ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
        JOIN public.visit v ON v.clinic_id = o.clinic_id AND v.visit_id = o.visit_id
       WHERE b.clinic_id = lt.clinic_id AND b.lieu_trinh_id = lt.id
         AND b.go_luc IS NULL
  ) b ON true
 WHERE lt.clinic_id = $1::uuid AND {dieu_kien}
 ORDER BY {thu_tu}
"""

_BUOI_SQL = """
SELECT b.id::text AS id, b.lieu_trinh_id::text AS lieu_trinh_id,
       b.service_order_id::text AS order_id, b.buoi_so, b.tra_truoc,
       b.gan_luc, b.gan_cach, sg.full_name AS gan_boi,
       b.go_luc, b.go_cach, so.full_name AS go_boi,
       o.visit_id::text AS visit_id, o.selection_status, o.execution_status,
       o.exec_status, coalesce(v.checked_in_at, v.created_at) AS ngay,
       -- Nơi làm buổi (thẻ liệu trình ở hồ sơ khám): lần làm mới nhất — bàn
       -- khám hay phòng nào; chưa làm thì phòng đang xếp.
       a.noi_lam, ra.name AS phong
  FROM public.lieu_trinh_buoi b
  JOIN public.service_order o
    ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
  JOIN public.visit v ON v.clinic_id = o.clinic_id AND v.visit_id = o.visit_id
  LEFT JOIN LATERAL (
       SELECT x.noi_lam, x.room_id_snapshot
         FROM public.service_execution_attempt x
        WHERE x.clinic_id = o.clinic_id AND x.service_order_id = o.id
        ORDER BY x.attempt_no DESC LIMIT 1) a ON true
  LEFT JOIN public.clinic_room ra
    ON ra.clinic_id = o.clinic_id AND ra.id = coalesce(a.room_id_snapshot, o.room_id)
  LEFT JOIN public.staff sg ON sg.id = b.gan_boi
  LEFT JOIN public.staff so ON so.id = b.go_boi
 WHERE b.clinic_id = $1::uuid AND b.lieu_trinh_id = ANY($2::uuid[])
 ORDER BY b.lieu_trinh_id, (b.go_luc IS NULL) DESC, b.buoi_so, b.gan_luc
"""

#: Chỉ định ĐIỀU TRỊ của một lượt + buổi đang gắn (nếu có).
_CHI_DINH_LUOT_SQL = """
SELECT o.id::text AS order_id, o.service_code, o.service_name,
       o.selection_status, o.execution_status, o.exec_status,
       public.lieu_trinh_chi_dinh_song(o.exec_status, o.execution_status,
                                       o.selection_status) AS song,
       b.lieu_trinh_id::text AS lieu_trinh_id, b.buoi_so, b.tra_truoc
  FROM public.service_order o
  LEFT JOIN public.lieu_trinh_buoi b
    ON b.clinic_id = o.clinic_id AND b.service_order_id = o.id AND b.go_luc IS NULL
 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
   AND o.service_code IN (
       SELECT sp.service_code FROM public.service_type st
         JOIN public.service_price sp
           ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id
        WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI')
 ORDER BY o.created_at, o.id
"""


def _lt(r: asyncpg.Record | dict[str, Any]) -> dict[str, Any]:
    d = {k: _iso(v) for k, v in dict(r).items()}
    for k in ("so_buoi", "da_tra", "so_gan", "da_lam", "dung_tra_truoc", "tra_le"):
        d[k] = int(d.get(k) or 0)
    d["don_gia"] = int(Decimal(str(d["don_gia"])))
    d["dang_cho"] = bool(d.get("dang_cho"))
    d.update(con_lai(d))
    d["tien_con_lai"] = d["chua_tra"] * d["don_gia"]
    d["sap_het_ly_do"] = ly_do_sap_het(d)
    return d


def _buoi(r: asyncpg.Record) -> dict[str, Any]:
    d = {k: _iso(v) for k, v in dict(r).items()}
    d["song"] = d["go_luc"] is None
    d["da_lam"] = d["execution_status"] == "COMPLETED" or (
        d["execution_status"] is None and d["exec_status"] == "performed"
    )
    d["noi_lam"] = "Bàn khám" if d.pop("noi_lam", None) == NOI_BAN_KHAM else d["phong"]
    return d


def nut_lieu_trinh(lt: dict[str, Any]) -> dict[str, bool]:
    """Nút trên dải liệu trình (hồ sơ khám) theo trạng thái. Thuần.

    Dừng rồi thì chỉ còn Mở lại; còn lại được điều chỉnh và dừng. Quyền do lệnh
    gác lại (màn chỉ đọc khi ``choGhi`` tắt)."""
    dung = lt.get("trang_thai") == "DUNG"
    return {"dieu_chinh": not dung, "dung": not dung, "mo_lai": dung}


def nut_chi_dinh(c: dict[str, Any]) -> dict[str, bool]:
    """Nút liệu trình trên thẻ một chỉ định điều trị. Thuần.

    ``tao``: chỉ định còn sống chưa thuộc liệu trình nào → ô "Lộ trình N buổi".
    ``go``: đang là buổi của một liệu trình → gỡ thành buổi lẻ. ``tach``: đang là
    buổi của liệu trình cũ → lập liệu trình MỚI (xác nhận tách, #14).
    ``chon``: có liệu trình cùng dịch vụ để gắn / chuyển sang (#15)."""
    song = bool(c.get("song"))
    co = bool(c.get("lieu_trinh_id"))
    khac = [u for u in c.get("ung_vien") or [] if u.get("id") != c.get("lieu_trinh_id")]
    return {
        "tao": song and not co,
        "go": song and co,
        "tach": song and co,
        "chon": song and bool(khac),
    }


# ---------------------------------------------------------------------------
# Dịch vụ
# ---------------------------------------------------------------------------


class LieuTrinhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── quyền ────────────────────────────────────────────────────────────────

    @staticmethod
    async def _co_mot(
        conn: asyncpg.Connection, identity: StaffIdentity, quyen: Sequence[str]
    ) -> bool:
        for q in dict.fromkeys(quyen):
            if await can(conn, identity, q):
                return True
        return False

    async def _doi(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        quyen: Sequence[str],
        cau: str,
    ) -> None:
        if not await self._co_mot(conn, identity, quyen):
            raise SafetyGateError(cau)

    async def _doi_doc(self, conn: asyncpg.Connection, identity: StaffIdentity) -> None:
        await self._doi(
            conn, identity, QUYEN_DOC, "Bạn không có quyền xem liệu trình điều trị."
        )

    # ── đọc nền ──────────────────────────────────────────────────────────────

    @staticmethod
    async def doc_nhieu(
        conn: asyncpg.Connection,
        cid: str,
        dieu_kien: str,
        *args: Any,
        thu_tu: str = "lt.tao_luc DESC, lt.id",
        kem_buoi: bool = True,
    ) -> list[dict[str, Any]]:
        rows = await conn.fetch(
            _LT_SQL.format(dieu_kien=dieu_kien, thu_tu=thu_tu), cid, *args
        )
        ds = [_lt(r) for r in rows]
        if kem_buoi and ds:
            buoi = await conn.fetch(_BUOI_SQL, cid, [d["id"] for d in ds])
            theo: dict[str, list[dict[str, Any]]] = {}
            for b in buoi:
                theo.setdefault(b["lieu_trinh_id"], []).append(_buoi(b))
            for d in ds:
                d["buoi"] = theo.get(d["id"], [])
        return ds

    async def _mot(
        self, conn: asyncpg.Connection, cid: str, lt_id: str
    ) -> dict[str, Any]:
        ds = await self.doc_nhieu(conn, cid, "lt.id = $2::uuid", lt_id)
        if not ds:
            raise NotFoundError("Không tìm thấy liệu trình này.")
        return ds[0]

    # ── đọc cho màn ──────────────────────────────────────────────────────────

    async def chi_tiet(
        self, *, identity: StaffIdentity, lieu_trinh_id: Any
    ) -> dict[str, Any]:
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        async with self._pool.acquire() as conn:
            await self._doi_doc(conn, identity)
            return await self._mot(conn, identity.clinic_id, lt)

    async def theo_khach(
        self, *, identity: StaffIdentity, clinic_patient_id: Any
    ) -> dict[str, Any]:
        """Khung khách / quầy: MỌI liệu trình của khách, mới nhất trước."""
        pid = _uuid(clinic_patient_id, "Mã khách không hợp lệ.")
        async with self._pool.acquire() as conn:
            await self._doi_doc(conn, identity)
            ds = await self.doc_nhieu(
                conn, identity.clinic_id, "lt.clinic_patient_id = $2::uuid", pid
            )
            # Màn (khung khách) hiện nút Đăng ký / Dừng / Mở lại / Hoàn tác theo
            # cờ này — chính lệnh vẫn tự gác quyền.
            quyen_cskh = await self._co_mot(conn, identity, QUYEN_DANG_KY)
            # Chip "Sắp hết lộ trình" hiện cả khi CSKH đã xử lý (khung khách là
            # hồ sơ), kèm cờ đã xử lý mốc này chưa.
            da = await self.da_xu_ly_sap_het_cac_moc(
                conn,
                identity.clinic_id,
                [moc_sap_het(d) for d in ds if d["sap_het_ly_do"]],
            )
        for d in ds:
            d["sap_het_da_xu_ly"] = bool(d["sap_het_ly_do"]) and moc_sap_het(d) in da
        return {"clinic_patient_id": pid, "lieu_trinh": ds, "quyen_cskh": quyen_cskh}

    @staticmethod
    async def da_xu_ly_sap_het_cac_moc(
        conn: asyncpg.Connection, cid: str, cac_moc: Sequence[str]
    ) -> set[str]:
        """Mốc "sắp hết" nào CSKH đã [Đã xử lý] (dòng sổ chạm khách còn hiệu lực
        — hoàn tác thì dòng thôi được tính, mốc hiện lại)."""
        if not cac_moc:
            return set()
        rows = await conn.fetch(
            "SELECT DISTINCT trang_thai_ma FROM public.tuong_tac_cskh"
            " WHERE clinic_id = $1::uuid AND huy_luc IS NULL"
            "   AND trang_thai_ma = ANY($2::text[])",
            cid,
            list(cac_moc),
        )
        return {str(r["trang_thai_ma"]) for r in rows}

    async def theo_luot(
        self, *, identity: StaffIdentity, visit_id: Any
    ) -> dict[str, Any]:
        """Thẻ liệu trình ở hồ sơ khám của MỘT lượt.

        ``lieu_trinh``: liệu trình có buổi (còn sống hoặc đã gỡ) trên chỉ định
        của lượt, hoặc đề xuất từ lượt này. ``chi_dinh``: mỗi chỉ định ĐIỀU TRỊ
        của lượt + buổi đang gắn + ``ung_vien`` (liệu trình cùng dịch vụ của
        khách chọn được) + ``can_chon`` (≥ 2 liệu trình đang làm → thẻ bắt chọn).
        Lượt không liên quan → hai danh sách rỗng (màn không hiện thẻ).
        """
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._doi_doc(conn, identity)
            pid = await conn.fetchval(
                "SELECT clinic_patient_id::text FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                cid,
                vid,
            )
            if pid is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            chi_dinh = [
                dict(r) for r in await conn.fetch(_CHI_DINH_LUOT_SQL, cid, [vid])
            ]
            ds = await self.doc_nhieu(
                conn,
                cid,
                """(lt.nguon_visit_id = $2::uuid OR lt.id IN (
                       SELECT b.lieu_trinh_id FROM public.lieu_trinh_buoi b
                         JOIN public.service_order o
                           ON o.clinic_id = b.clinic_id AND o.id = b.service_order_id
                        WHERE b.clinic_id = $1::uuid AND o.visit_id = $2::uuid))""",
                vid,
            )
            ma = sorted({c["service_code"] for c in chi_dinh})
            ung_vien = (
                await self.doc_nhieu(
                    conn,
                    cid,
                    "lt.clinic_patient_id = $2::uuid"
                    " AND lt.service_code = ANY($3::text[])"
                    " AND lt.trang_thai <> 'DUNG'",
                    pid,
                    ma,
                    kem_buoi=False,
                )
                if ma
                else []
            )
            # [Hoàn tác] trên dải: lần sửa MỚI NHẤT do người bấm (cùng luật lệnh
            # hoàn tác — lần tự động thì không).
            moi_nhat = {
                r["lt"]: r
                for r in await conn.fetch(
                    "SELECT DISTINCT ON (h.lieu_trinh_id) h.lieu_trinh_id::text AS lt,"
                    "       h.id::text AS id, h.revision, h.hanh_dong"
                    "  FROM public.lieu_trinh_lich_su h"
                    " WHERE h.clinic_id = $1::uuid"
                    "   AND h.lieu_trinh_id = ANY($2::uuid[])"
                    " ORDER BY h.lieu_trinh_id, h.revision DESC, h.luc DESC",
                    cid,
                    [d["id"] for d in ds],
                )
            }
            # "Chỉ đề xuất liệu trình (không làm hôm nay)": dịch vụ nhóm Điều trị.
            dich_vu = [
                dict(r)
                for r in await conn.fetch(
                    "SELECT DISTINCT ON (sp.service_code) sp.service_code,"
                    "       sp.name AS ten"
                    "  FROM public.service_type st JOIN public.service_price sp"
                    "    ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id"
                    " WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI'"
                    " ORDER BY sp.service_code, sp.name",
                    cid,
                )
            ]
        for d in ds:
            d["nut"] = nut_lieu_trinh(d)
            h = moi_nhat.get(d["id"])
            d["hoan_tac"] = (
                {"lich_su_id": h["id"], "hanh_dong": h["hanh_dong"]}
                if h is not None
                and int(h["revision"]) == int(d["revision"])
                and h["hanh_dong"] in HANH_DONG_HOAN_TAC_DUOC
                else None
            )
        for c in chi_dinh:
            uv = [u for u in ung_vien if u["service_code"] == c["service_code"]]
            c["ung_vien"] = [
                {
                    "id": u["id"],
                    "trang_thai": u["trang_thai"],
                    "so_buoi": u["so_buoi"],
                    "da_lam": u["da_lam"],
                    "tao_luc": u["tao_luc"],
                }
                for u in uv
            ]
            # Cùng bậc với trigger tự gắn (`lieu_trinh_ung_vien_duy_nhat`):
            # DANG_LAM trước, không có thì DE_XUAT; ≥ 2 cùng bậc = phải chọn.
            bac = [u for u in uv if u["trang_thai"] == "DANG_LAM"] or [
                u for u in uv if u["trang_thai"] == "DE_XUAT"
            ]
            c["can_chon"] = bool(c["song"]) and not c["lieu_trinh_id"] and len(bac) > 1
            c["nut"] = nut_chi_dinh(c)
        return {
            "visit_id": vid,
            "clinic_patient_id": pid,
            "lieu_trinh": ds,
            "chi_dinh": chi_dinh,
            "dich_vu_de_xuat": dich_vu,
        }

    async def chip(self, *, identity: StaffIdentity, visit_ids: Any) -> dict[str, Any]:
        """Chip "Buổi k/N · đã trả trước" cho chỉ định hôm nay của các lượt +
        "còn N buổi đã trả" theo khách (tiếp đón). Một câu cho cả lô lượt."""
        ids = doc_ds_uuid(visit_ids)
        cid = identity.clinic_id
        if not ids:
            return {"chi_dinh": {}, "khach": {}}
        async with self._pool.acquire() as conn:
            await self._doi_doc(conn, identity)
            rows = await conn.fetch(
                """
                SELECT o.id::text AS order_id, o.visit_id::text AS visit_id,
                       b.lieu_trinh_id::text AS lieu_trinh_id, b.buoi_so, b.tra_truoc,
                       lt.so_buoi, lt.service_name, lt.trang_thai
                  FROM public.service_order o
                  JOIN public.lieu_trinh_buoi b
                    ON b.clinic_id = o.clinic_id AND b.service_order_id = o.id
                   AND b.go_luc IS NULL
                  JOIN public.lieu_trinh lt
                    ON lt.clinic_id = b.clinic_id AND lt.id = b.lieu_trinh_id
                 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                """,
                cid,
                ids,
            )
            khach = await self.doc_nhieu(
                conn,
                cid,
                "lt.trang_thai IN ('DANG_LAM', 'XONG') AND lt.clinic_patient_id IN ("
                " SELECT clinic_patient_id FROM public.visit"
                "  WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[]))",
                ids,
                kem_buoi=False,
            )
            luot_khach = {
                r["visit_id"]: r["pid"]
                for r in await conn.fetch(
                    "SELECT visit_id::text, clinic_patient_id::text AS pid FROM visit"
                    " WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])",
                    cid,
                    ids,
                )
            }
        theo_khach: dict[str, list[dict[str, Any]]] = {}
        for lt in khach:
            if lt["trang_thai"] == "XONG" and lt["con_tra_truoc"] <= 0:
                continue
            theo_khach.setdefault(lt["khach_id"], []).append(
                {
                    "lieu_trinh_id": lt["id"],
                    "service_name": lt["service_name"],
                    "so_buoi": lt["so_buoi"],
                    "da_lam": lt["da_lam"],
                    "con_lai": lt["con_lai"],
                    "con_tra_truoc": lt["con_tra_truoc"],
                }
            )
        return {
            "chi_dinh": {
                r["order_id"]: {
                    # Màn theo lượt (bàn khám, tiếp đón) gom chip theo lượt.
                    "visit_id": r["visit_id"],
                    "lieu_trinh_id": r["lieu_trinh_id"],
                    "buoi_so": int(r["buoi_so"]),
                    "so_buoi": int(r["so_buoi"]),
                    "tra_truoc": bool(r["tra_truoc"]),
                    "service_name": r["service_name"],
                    "trang_thai": r["trang_thai"],
                }
                for r in rows
            },
            "khach": {vid: theo_khach.get(pid, []) for vid, pid in luot_khach.items()},
        }

    async def cskh(
        self,
        *,
        identity: StaffIdentity,
        loai: Any,
        qua_ngay: Any = None,
        ca_co_lich: Any = False,
    ) -> dict[str, Any]:
        """Ba danh sách của CSKH: ``de_xuat`` (đề xuất chưa đăng ký),
        ``dang_do`` (đang làm dở, quá X ngày chưa quay lại, không còn buổi đang
        chờ làm) và ``sap_het`` (sắp hết lộ trình — ``ly_do_sap_het``; bỏ dòng
        CSKH đã [Đã xử lý] đúng mốc hiện tại). Mặc định bỏ khách đã có lịch hẹn
        sắp tới (``ca_co_lich``) — trừ ``sap_het``: có lịch buổi cuối vẫn cần gọi
        tư vấn thêm buổi."""
        if loai not in ("de_xuat", "dang_do", "sap_het"):
            raise ValidationError(
                "Loại danh sách không hợp lệ (de_xuat | dang_do | sap_het)."
            )
        so_ngay = doc_so_ngay(qua_ngay)
        if so_ngay is None:
            so_ngay = QUA_NGAY_MAC_DINH
        cid = identity.clinic_id
        lich = (
            "(SELECT min(a.slot_start) FROM public.appointment a"
            "  WHERE a.clinic_id = lt.clinic_id"
            "    AND a.clinic_patient_id = lt.clinic_patient_id"
            "    AND a.slot_start >= now()"
            "    AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'COMPLETED'))"
        )
        async with self._pool.acquire() as conn:
            await self._doi(
                conn,
                identity,
                QUYEN_DANG_KY,
                "Bạn không có quyền xem danh sách liệu trình của CSKH.",
            )
            thu_tu = "coalesce(b.lan_cuoi, lt.tao_luc), lt.id"
            if loai == "de_xuat":
                dk = "lt.trang_thai = 'DE_XUAT'"
                args: list[Any] = []
            elif loai == "dang_do":
                dk = (
                    "lt.trang_thai = 'DANG_LAM' AND NOT coalesce(b.dang_cho, false)"
                    " AND coalesce(b.lan_cuoi, lt.dang_ky_luc, lt.tao_luc)"
                    "     < now() - make_interval(days => $2::int)"
                )
                args = [so_ngay]
            else:
                # Lọc thô ở SQL (để LIMIT không cắt mất dòng), luật đúng ở
                # ``ly_do_sap_het`` bên dưới.
                dk = (
                    "lt.trang_thai = 'DANG_LAM'"
                    " AND lt.so_buoi > coalesce(b.da_lam, 0)"
                    " AND (lt.so_buoi - coalesce(b.da_lam, 0) <= $2::int"
                    "  OR (public.lieu_trinh_so_buoi_da_tra(lt.clinic_id, lt.id) > 0"
                    "      AND public.lieu_trinh_so_buoi_da_tra(lt.clinic_id, lt.id)"
                    "          <= coalesce(b.dung_tra_truoc, 0)))"
                )
                args = [SAP_HET_CON_TOI_DA]
                thu_tu = "coalesce(b.lan_cuoi, lt.tao_luc) DESC, lt.id"
            if not ca_co_lich and loai != "sap_het":
                dk += f" AND {lich} IS NULL"
            ds = await self.doc_nhieu(
                conn,
                cid,
                dk,
                *args,
                thu_tu=f"{thu_tu} LIMIT {TRAN_DANH_SACH}",
                kem_buoi=False,
            )
            if loai == "sap_het":
                ds = [d for d in ds if d["sap_het_ly_do"]]
                da = await self.da_xu_ly_sap_het_cac_moc(
                    conn, cid, [moc_sap_het(d) for d in ds]
                )
                ds = [d for d in ds if moc_sap_het(d) not in da]
            if ds:
                hen = {
                    r["id"]: _iso(r["hen"])
                    for r in await conn.fetch(
                        f"SELECT lt.id::text AS id, {lich} AS hen"
                        " FROM public.lieu_trinh lt"
                        " WHERE lt.clinic_id = $1::uuid AND lt.id = ANY($2::uuid[])",
                        cid,
                        [d["id"] for d in ds],
                    )
                }
                for d in ds:
                    d["lich_hen_sap_toi"] = hen.get(d["id"])
        return {"loai": loai, "qua_ngay": so_ngay, "lieu_trinh": ds}

    async def lich_su(
        self, *, identity: StaffIdentity, lieu_trinh_id: Any
    ) -> dict[str, Any]:
        """ "Lịch sử sửa" trên thẻ: mọi lần kế hoạch đổi + mọi lần gắn / gỡ buổi,
        mới nhất trước. Dòng ``hoan_tac_duoc`` = nút Hoàn tác (chỉ lần sửa mới
        nhất do người bấm)."""
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._doi_doc(conn, identity)
            hien = await conn.fetchval(
                "SELECT revision FROM lieu_trinh"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lt,
            )
            if hien is None:
                raise NotFoundError("Không tìm thấy liệu trình này.")
            sua = await conn.fetch(
                """
                SELECT h.id::text AS id, h.revision, h.hanh_dong, h.ban_cu, h.ban_moi,
                       h.luc, s.full_name AS boi
                  FROM public.lieu_trinh_lich_su h
                  LEFT JOIN public.staff s ON s.id = h.boi
                 WHERE h.clinic_id = $1::uuid AND h.lieu_trinh_id = $2::uuid
                 ORDER BY h.revision DESC, h.luc DESC
                """,
                cid,
                lt,
            )
            buoi = await conn.fetch(_BUOI_SQL, cid, [lt])
        dong: list[dict[str, Any]] = [
            {
                "loai": "SUA",
                "id": r["id"],
                "revision": int(r["revision"]),
                "hanh_dong": r["hanh_dong"],
                "ban_cu": _json(r["ban_cu"]),
                "ban_moi": _json(r["ban_moi"]),
                "luc": _iso(r["luc"]),
                "boi": r["boi"],
                "hoan_tac_duoc": int(r["revision"]) == int(hien)
                and r["hanh_dong"] in HANH_DONG_HOAN_TAC_DUOC,
            }
            for r in sua
        ]
        for b in buoi:
            dong.append(
                {
                    "loai": "GAN",
                    "id": b["id"],
                    "order_id": b["order_id"],
                    "buoi_so": int(b["buoi_so"]),
                    "cach": b["gan_cach"],
                    "luc": _iso(b["gan_luc"]),
                    "boi": b["gan_boi"],
                    "hoan_tac_duoc": False,
                }
            )
            if b["go_luc"] is not None:
                dong.append(
                    {
                        "loai": "GO",
                        "id": b["id"],
                        "order_id": b["order_id"],
                        "buoi_so": int(b["buoi_so"]),
                        "cach": b["go_cach"],
                        "luc": _iso(b["go_luc"]),
                        "boi": b["go_boi"],
                        "hoan_tac_duoc": False,
                    }
                )
        dong.sort(key=lambda d: str(d["luc"]), reverse=True)
        return {"lieu_trinh_id": lt, "revision": int(hien), "dong": dong}

    # ── khung lệnh ghi ───────────────────────────────────────────────────────

    async def _lenh(
        self,
        *,
        identity: StaffIdentity,
        action: str,
        key: str | None,
        payload: dict[str, Any],
        quyen: Sequence[str],
        cau_quyen: str,
        lam: Callable[[asyncpg.Connection], Awaitable[tuple[dict[str, Any], str]]],
    ) -> dict[str, Any]:
        if not key:
            raise ValidationError(
                "Thiếu khoá gửi lại (idempotency_key) cho lệnh liệu trình."
            )
        async with self._pool.acquire() as conn, conn.transaction():
            await self._doi(conn, identity, quyen, cau_quyen)
            cached = await bien_nhan_doc(conn, identity, action, key, payload)
            if cached is not None:
                return cached
            try:
                kq, dich = await lam(conn)
            except (asyncpg.CheckViolationError, asyncpg.UniqueViolationError) as e:
                raise loi_db(e) from None
            await bien_nhan_ghi(conn, identity, action, key, payload, dich, kq)
        return kq

    @staticmethod
    async def _khoa(conn: asyncpg.Connection, cid: str, lt_id: str) -> asyncpg.Record:
        row = await conn.fetchrow(
            "SELECT id::text AS id, clinic_patient_id::text AS khach_id, so_buoi,"
            "       ghi_chu_lo_trinh, trang_thai, revision, dang_ky_luc, dung_luc"
            "  FROM lieu_trinh WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
            cid,
            lt_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy liệu trình này.")
        return row

    @staticmethod
    def _dung_ban(row: asyncpg.Record, expected_revision: Any) -> None:
        try:
            mong = int(expected_revision)
        except (TypeError, ValueError):
            raise ValidationError("Phiên bản liệu trình không hợp lệ.") from None
        if int(row["revision"]) != mong:
            raise LuotKhamConflictError(
                "STALE_LIEU_TRINH",
                "Liệu trình vừa được người khác sửa — đã tải lại, xem bản mới rồi"
                " bấm lại.",
            )

    async def _phat_sua(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        lt: dict[str, Any],
        hanh_dong: str,
    ) -> None:
        await emit_event(
            conn,
            ten="lieu_trinh.revised",
            clinic_id=identity.clinic_id,
            aggregate_id=lt["id"],
            so_ke_tiep=True,
            payload=LieuTrinhDaSua(
                lieu_trinh_id=lt["id"],
                clinic_patient_id=lt["khach_id"],
                hanh_dong=hanh_dong,
                revision=lt["revision"],
                trang_thai=lt["trang_thai"],
                so_buoi=lt["so_buoi"],
            ),
            boi=nguoi(identity),
        )

    async def _sua(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        lt_id: str,
        hanh_dong: str,
        set_sql: str,
        *args: Any,
    ) -> dict[str, Any]:
        """Một lần sửa kế hoạch: trigger suy trạng thái + ghi lịch sử. Không đổi
        gì (bấm lại) → trả bản hiện tại, ``changed`` = False, không sự kiện."""
        cid = identity.clinic_id
        doi = await conn.fetchval(
            f"UPDATE lieu_trinh SET {set_sql}, hanh_dong = $3, sua_boi = $4::uuid"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid RETURNING revision",
            cid,
            lt_id,
            hanh_dong,
            identity.staff_id,
            *args,
        )
        lt = await self._mot(conn, cid, lt_id)
        if doi is not None:
            await self._phat_sua(conn, identity, lt, hanh_dong)
        return {"ok": True, "changed": doi is not None, "lieu_trinh": lt}

    # ── lệnh ─────────────────────────────────────────────────────────────────

    async def _dich_vu_dieu_tri(
        self, conn: asyncpg.Connection, cid: str, ma: str
    ) -> tuple[str, Decimal]:
        """Tên + đơn giá hiện hành của một dịch vụ nhóm DIEU_TRI (Q2: chốt vào
        liệu trình lúc tạo). Không phải điều trị / chưa có giá → 409."""
        ten = await conn.fetchval(
            "SELECT sp.name FROM service_type st JOIN service_price sp"
            "   ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id"
            " WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI'"
            "   AND sp.service_code = $2 LIMIT 1",
            cid,
            ma,
        )
        if ten is None:
            raise LuotKhamConflictError(
                "KHONG_PHAI_DIEU_TRI",
                "Liệu trình chỉ dành cho dịch vụ nhóm Điều trị.",
            )
        gia = await conn.fetchrow(
            "SELECT coalesce(array_agg(unit_price)"
            "                FILTER (WHERE unit_price IS NOT NULL),"
            "                '{}') AS gia,"
            "       coalesce(array_agg(DISTINCT billing_owner)"
            "                FILTER (WHERE billing_owner IS NOT NULL), '{}') AS ben_thu"
            "  FROM service_price"
            " WHERE clinic_id = $1::uuid AND service_code = $2 AND active"
            "   AND \"group\" = 'dich_vu'",
            cid,
            ma,
        )
        ben, don_gia, van_de = giai_gia(
            list(gia["gia"]) if gia else [], list(gia["ben_thu"]) if gia else []
        )
        if van_de or ben != CLINIC or don_gia is None:
            raise LuotKhamConflictError(
                "CHUA_CO_GIA",
                f"Dịch vụ “{ten}” chưa có giá phòng khám thu"
                f" ({van_de or 'đối tác thu'})"
                " — sửa ở Bảng giá trước khi lập liệu trình.",
            )
        return str(ten), don_gia

    async def tao(
        self,
        *,
        identity: StaffIdentity,
        visit_id: Any,
        so_buoi: Any,
        service_order_id: Any = None,
        service_code: Any = None,
        ghi_chu: Any = None,
        tach_khoi_lieu_trinh_cu: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Đề xuất liệu trình (DE_XUAT) từ thẻ chỉ định điều trị ở hồ sơ khám.

        Có ``service_order_id``: chỉ định hôm nay thành buổi 1. Chỉ định ấy đang
        thuộc liệu trình khác (tự gắn vì khách đang làm dở) → 409
        ``DA_GAN_LIEU_TRINH`` kèm mã liệu trình; bác sĩ bấm rõ "liệu trình mới"
        (``tach_khoi_lieu_trinh_cu``) thì chuyển sang. Không có chỉ định = "Chỉ
        đề xuất, không làm hôm nay" (cần ``service_code``).
        """
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        oid = (
            _uuid(service_order_id, "Mã chỉ định không hợp lệ.")
            if service_order_id
            else None
        )
        n = doc_so_buoi(so_buoi)
        if n is None:
            raise ValidationError(f"Số buổi phải từ 1 đến {SO_BUOI_TOI_DA}.")
        gc = doc_ghi_chu(ghi_chu)
        ma_vao = str(service_code).strip() if service_code else None
        if oid is None and not ma_vao:
            raise ValidationError("Cần chỉ định hôm nay hoặc mã dịch vụ điều trị.")
        cid = identity.clinic_id
        payload = {
            "visit_id": vid,
            "service_order_id": oid,
            "service_code": ma_vao,
            "so_buoi": n,
            "ghi_chu": gc,
            "tach": bool(tach_khoi_lieu_trinh_cu),
        }

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            pid = await conn.fetchval(
                "SELECT clinic_patient_id::text FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                cid,
                vid,
            )
            if pid is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            ma = ma_vao
            cu: str | None = None
            if oid is not None:
                o = await conn.fetchrow(
                    "SELECT visit_id::text AS visit_id, service_code,"
                    "       lieu_trinh_chi_dinh_song(exec_status, execution_status,"
                    "                                selection_status) AS song"
                    "  FROM service_order WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    "   FOR UPDATE",
                    cid,
                    oid,
                )
                if o is None or o["visit_id"] != vid:
                    raise NotFoundError("Không tìm thấy chỉ định này trong lượt.")
                if not o["song"]:
                    raise LuotKhamConflictError(
                        "CHI_DINH_DA_BO",
                        "Chỉ định đã bỏ / không làm — bấm “Chỉ đề xuất, không làm"
                        " hôm nay”.",
                    )
                ma = o["service_code"]
                cu = await conn.fetchval(
                    "SELECT lieu_trinh_id::text FROM lieu_trinh_buoi"
                    " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                    "   AND go_luc IS NULL",
                    cid,
                    oid,
                )
                if cu is not None and not tach_khoi_lieu_trinh_cu:
                    raise LuotKhamConflictError(
                        "DA_GAN_LIEU_TRINH",
                        "Chỉ định này đang là một buổi của liệu trình khách đang làm."
                        " Muốn lập liệu trình MỚI thì xác nhận tách ra.",
                        {"lieu_trinh_id": cu},
                    )
            assert ma is not None
            ten, don_gia = await self._dich_vu_dieu_tri(conn, cid, ma)
            lt_id = str(
                await conn.fetchval(
                    """
                    INSERT INTO lieu_trinh
                        (clinic_id, clinic_patient_id, service_code, service_name,
                         so_buoi, don_gia, ghi_chu_lo_trinh, nguon, nguon_visit_id,
                         nguon_order_id, de_xuat_boi, hanh_dong, sua_boi)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, 'BAC_SI', $8::uuid,
                            $9::uuid, $10::uuid, 'TAO', $10::uuid)
                    RETURNING id
                    """,
                    cid,
                    pid,
                    ma,
                    ten,
                    n,
                    don_gia,
                    gc,
                    vid,
                    oid,
                    identity.staff_id,
                )
            )
            if oid is not None:
                if cu is not None:
                    await conn.execute(
                        _GO_CHUYEN,
                        cid,
                        oid,
                        identity.staff_id,
                    )
                await conn.execute(
                    _GAN_TAY,
                    cid,
                    lt_id,
                    oid,
                    identity.staff_id,
                )
            await emit_event(
                conn,
                ten="lieu_trinh.created",
                clinic_id=cid,
                aggregate_id=lt_id,
                so_ke_tiep=True,
                payload=LieuTrinhDaTao(
                    lieu_trinh_id=lt_id,
                    clinic_patient_id=pid,
                    service_code=ma,
                    so_buoi=n,
                    visit_id=vid,
                    service_order_id=oid,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            return {"ok": True, "lieu_trinh": await self._mot(conn, cid, lt_id)}, lt_id

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.tao",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_SUA,
            cau_quyen="Chỉ khối y khoa / trưởng ca đề xuất được liệu trình.",
            lam=lam,
        )

    async def dieu_chinh(
        self,
        *,
        identity: StaffIdentity,
        lieu_trinh_id: Any,
        expected_revision: Any,
        so_buoi: Any = _KHONG_DOI,
        ghi_chu: Any = _KHONG_DOI,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Đổi số buổi / ghi chú lộ trình. Giảm dưới số đã trả → 409 (#11) nói
        rõ "hoàn tiền trước" — không khoá: hoàn xong là giảm được."""
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        n: int | None = None
        if so_buoi is not _KHONG_DOI:
            n = doc_so_buoi(so_buoi)
            if n is None:
                raise ValidationError(f"Số buổi phải từ 1 đến {SO_BUOI_TOI_DA}.")
        doi_gc = ghi_chu is not _KHONG_DOI
        gc = doc_ghi_chu(ghi_chu) if doi_gc else None
        if n is None and not doi_gc:
            raise ValidationError("Không có gì để điều chỉnh.")
        payload = {
            "lt": lt,
            "so_buoi": n,
            "doi_gc": doi_gc,
            "gc": gc,
            "rev": expected_revision,
        }

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            row = await self._khoa(conn, cid, lt)
            self._dung_ban(row, expected_revision)
            if n is not None and n < int(row["so_buoi"]):
                hien = await self._mot(conn, cid, lt)
                if n < hien["da_tra"]:
                    raise LuotKhamConflictError(
                        "SO_BUOI_DUOI_DA_TRA",
                        f"Đã trả trước {hien['da_tra']} buổi — hoàn tiền phần dư ở quầy"
                        " trước rồi giảm số buổi.",
                        {"da_tra": hien["da_tra"]},
                    )
                if n < hien["so_gan"]:
                    raise LuotKhamConflictError(
                        "SO_BUOI_DUOI_SO_GAN",
                        f"Đang có {hien['so_gan']} buổi gắn liệu trình — gỡ buổi trước"
                        " khi giảm số buổi.",
                    )
            kq = await self._sua(
                conn,
                identity,
                lt,
                "DIEU_CHINH",
                "so_buoi = coalesce($5, so_buoi),"
                " ghi_chu_lo_trinh = CASE WHEN $6 THEN $7 ELSE ghi_chu_lo_trinh END",
                n,
                doi_gc,
                gc,
            )
            return kq, lt

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.dieu_chinh",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_SUA,
            cau_quyen="Chỉ khối y khoa / trưởng ca điều chỉnh được liệu trình.",
            lam=lam,
        )

    async def dang_ky(
        self,
        *,
        identity: StaffIdentity,
        lieu_trinh_id: Any,
        expected_revision: Any,
        so_buoi: Any = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """CSKH [Đăng ký] (Q3: chỉ ghi đăng ký — tiền thu ở quầy khi khách đến):
        đề xuất → DANG_LAM; ``so_buoi`` = khách nhận 1 buổi / N buổi."""
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        n = None if so_buoi is None else doc_so_buoi(so_buoi)
        if so_buoi is not None and n is None:
            raise ValidationError(f"Số buổi phải từ 1 đến {SO_BUOI_TOI_DA}.")
        payload = {"lt": lt, "so_buoi": n, "rev": expected_revision}

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            row = await self._khoa(conn, cid, lt)
            self._dung_ban(row, expected_revision)
            if row["trang_thai"] == "DUNG":
                raise LuotKhamConflictError(
                    "LIEU_TRINH_DA_DUNG",
                    "Liệu trình đã dừng — mở lại trước khi đăng ký.",
                )
            kq = await self._sua(
                conn,
                identity,
                lt,
                "DANG_KY",
                "dang_ky_luc = coalesce(dang_ky_luc, now()),"
                " dang_ky_boi = coalesce(dang_ky_boi, $4::uuid),"
                " so_buoi = coalesce($5, so_buoi)",
                n,
            )
            return kq, lt

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.dang_ky",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_DANG_KY,
            cau_quyen="Bạn không có quyền đăng ký liệu trình cho khách.",
            lam=lam,
        )

    async def dung(
        self,
        *,
        identity: StaffIdentity,
        lieu_trinh_id: Any,
        expected_revision: Any,
        ly_do: Any = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Dừng liệu trình (Q5: mở lại được, không hạn dùng). Còn buổi đã trả
        chưa dùng → ``con_tra_truoc`` > 0: màn chỉ đường hoàn tiền ở quầy."""
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        ly = (str(ly_do).strip() or None) if ly_do is not None else None
        if ly is not None and len(ly) > LY_DO_TOI_DA:
            raise ValidationError(f"Lý do tối đa {LY_DO_TOI_DA} ký tự.")
        payload = {"lt": lt, "ly_do": ly, "rev": expected_revision}

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            row = await self._khoa(conn, cid, lt)
            self._dung_ban(row, expected_revision)
            kq = await self._sua(
                conn,
                identity,
                lt,
                "DUNG",
                "dung_luc = coalesce(dung_luc, now()),"
                " dung_boi = coalesce(dung_boi, $4::uuid),"
                " ly_do_dung = coalesce(ly_do_dung, $5)",
                ly,
            )
            return kq, lt

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.dung",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_DANG_KY,
            cau_quyen="Bạn không có quyền dừng liệu trình.",
            lam=lam,
        )

    async def mo_lai(
        self,
        *,
        identity: StaffIdentity,
        lieu_trinh_id: Any,
        expected_revision: Any,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        payload = {"lt": lt, "rev": expected_revision}

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            row = await self._khoa(conn, cid, lt)
            self._dung_ban(row, expected_revision)
            kq = await self._sua(
                conn,
                identity,
                lt,
                "MO_LAI",
                "dung_luc = NULL, dung_boi = NULL, ly_do_dung = NULL",
            )
            return kq, lt

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.mo_lai",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_DANG_KY,
            cau_quyen="Bạn không có quyền mở lại liệu trình.",
            lam=lam,
        )

    async def da_xu_ly_sap_het(
        self, *, identity: StaffIdentity, lieu_trinh_id: Any
    ) -> dict[str, Any]:
        """CSKH [Đã xử lý] dòng "Sắp hết lộ trình" ở ĐÚNG mốc hiện tại.

        Ghi MỘT dòng sổ chạm khách (``tuong_tac_cskh``, chỉ-thêm, hoàn tác bằng
        lệnh hoàn tác sẵn có ``/cskh/tuong-tac/{id}/hoan-tac``) với
        ``trang_thai_ma`` = mốc — KHÔNG phải một cuộc gọi (kênh "không liên hệ",
        kết quả "bỏ qua"; gọi thì ghi bằng [Ghi cuộc gọi]). Mốc đổi → dòng hiện
        lại. Bấm lại ở cùng mốc → trả dòng đã có (không ghi thêm)."""
        from clinicai.services.tuong_tac_cskh_service import TuongTacCskhService

        lt_id = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._doi(
                conn,
                identity,
                QUYEN_DANG_KY,
                "Bạn không có quyền xử lý danh sách liệu trình của CSKH.",
            )
            lt = await self._mot(conn, cid, lt_id)
            ly_do = lt["sap_het_ly_do"]
            if not ly_do:
                raise LuotKhamConflictError(
                    "KHONG_SAP_HET",
                    "Liệu trình này không còn ở mốc sắp hết lộ trình — đã tải lại.",
                )
            moc = moc_sap_het(lt)
            cu = await conn.fetchval(
                "SELECT id::text FROM public.tuong_tac_cskh"
                " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
                "   AND huy_luc IS NULL AND trang_thai_ma = $3"
                " ORDER BY created_at DESC LIMIT 1",
                cid,
                lt["khach_id"],
                moc,
            )
        if cu is not None:
            return {"ok": True, "tuong_tac_id": cu, "moc": moc, "da_co": True}
        kq = await TuongTacCskhService(self._pool).ghi(
            identity=identity,
            clinic_patient_id=lt["khach_id"],
            loai="KHAC",
            kenh="KHONG_LIEN_HE",
            ket_qua="BO_QUA",
            noi_dung=f"Đã xử lý sắp hết lộ trình {lt['service_name']}: {ly_do}.",
            trang_thai_ma=moc,
        )
        return {"ok": True, "tuong_tac_id": kq.get("id"), "moc": moc, "da_co": False}

    async def hoan_tac(
        self,
        *,
        identity: StaffIdentity,
        lieu_trinh_id: Any,
        lich_su_id: Any,
        expected_revision: Any,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Hoàn tác LẦN SỬA MỚI NHẤT do người bấm: đưa kế hoạch về bản cũ của dòng
        lịch sử ấy (là một lần sửa mới — lịch sử chỉ thêm, không xoá dòng)."""
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        hid = _uuid(lich_su_id, "Mã dòng lịch sử không hợp lệ.")
        payload = {"lt": lt, "hid": hid, "rev": expected_revision}

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            row = await self._khoa(conn, cid, lt)
            self._dung_ban(row, expected_revision)
            h = await conn.fetchrow(
                "SELECT revision, hanh_dong, ban_cu FROM lieu_trinh_lich_su"
                " WHERE clinic_id = $1::uuid AND lieu_trinh_id = $2::uuid"
                " AND id = $3::uuid",
                cid,
                lt,
                hid,
            )
            if h is None:
                raise NotFoundError("Không tìm thấy dòng lịch sử này.")
            if (
                int(h["revision"]) != int(row["revision"])
                or h["hanh_dong"] not in HANH_DONG_HOAN_TAC_DUOC
            ):
                raise LuotKhamConflictError(
                    "KHONG_HOAN_TAC_DUOC",
                    "Chỉ hoàn tác được lần sửa mới nhất do người bấm — sau đó đã có"
                    " thay đổi khác.",
                )
            cu = _json(h["ban_cu"])
            kq = await self._sua(
                conn,
                identity,
                lt,
                "HOAN_TAC",
                "so_buoi = $5, ghi_chu_lo_trinh = $6, dang_ky_luc = $7::timestamptz,"
                " dang_ky_boi = $8::uuid, dung_luc = $9::timestamptz,"
                " dung_boi = $10::uuid, ly_do_dung = $11",
                int(cu["so_buoi"]),
                cu.get("ghi_chu_lo_trinh"),
                _ts(cu.get("dang_ky_luc")),
                cu.get("dang_ky_boi"),
                _ts(cu.get("dung_luc")),
                cu.get("dung_boi"),
                cu.get("ly_do_dung"),
            )
            return kq, lt

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.hoan_tac",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_DANG_KY,
            cau_quyen="Bạn không có quyền hoàn tác thay đổi liệu trình.",
            lam=lam,
        )

    async def gan(
        self,
        *,
        identity: StaffIdentity,
        service_order_id: Any,
        lieu_trinh_id: Any,
        expected_lieu_trinh_id: Any = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Chọn liệu trình cho MỘT chỉ định (#15: khách có 2 liệu trình cùng
        dịch vụ; hoặc gắn vào liệu trình đã Xong → tự thêm buổi). Đang thuộc
        liệu trình khác thì chuyển. ``expected_lieu_trinh_id`` = liệu trình màn
        đang thấy (rỗng = chưa gắn) — lệch → 409."""
        oid = _uuid(service_order_id, "Mã chỉ định không hợp lệ.")
        lt = _uuid(lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        mong = (
            _uuid(expected_lieu_trinh_id, "Mã liệu trình không hợp lệ.")
            if expected_lieu_trinh_id
            else None
        )
        payload = {"oid": oid, "lt": lt, "mong": mong}

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            hien = await self._khoa_chi_dinh(conn, cid, oid)
            if hien == lt:
                return {
                    "ok": True,
                    "changed": False,
                    "lieu_trinh": await self._mot(conn, cid, lt),
                }, lt
            if hien != mong:
                raise LuotKhamConflictError(
                    "STALE_LIEU_TRINH",
                    "Buổi này vừa được gắn / gỡ ở màn khác — đã tải lại, bấm lại.",
                )
            if hien is not None:
                await conn.execute(
                    _GO_CHUYEN,
                    cid,
                    oid,
                    identity.staff_id,
                )
            await conn.execute(
                _GAN_TAY,
                cid,
                lt,
                oid,
                identity.staff_id,
            )
            moi = await self._mot(conn, cid, lt)
            so = next(
                (
                    b["buoi_so"]
                    for b in moi["buoi"]
                    if b["order_id"] == oid and b["song"]
                ),
                None,
            )
            await self._phat_buoi(conn, identity, lt, oid, "GAN", so)
            return {"ok": True, "changed": True, "lieu_trinh": moi}, lt

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.gan",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_SUA,
            cau_quyen="Chỉ khối y khoa / trưởng ca gắn được buổi vào liệu trình.",
            lam=lam,
        )

    async def go(
        self,
        *,
        identity: StaffIdentity,
        service_order_id: Any,
        expected_lieu_trinh_id: Any,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Gỡ chỉ định khỏi liệu trình (buổi lẻ). Buổi đang dùng tiền trả trước
        thì trả buổi đã trả về liệu trình. Gắn lại = lệnh ``gan``."""
        oid = _uuid(service_order_id, "Mã chỉ định không hợp lệ.")
        mong = _uuid(expected_lieu_trinh_id, "Mã liệu trình không hợp lệ.")
        payload = {"oid": oid, "mong": mong}

        async def lam(conn: asyncpg.Connection) -> tuple[dict[str, Any], str]:
            cid = identity.clinic_id
            hien = await self._khoa_chi_dinh(conn, cid, oid)
            if hien is None:
                return {
                    "ok": True,
                    "changed": False,
                    "lieu_trinh": await self._mot(conn, cid, mong),
                }, mong
            if hien != mong:
                raise LuotKhamConflictError(
                    "STALE_LIEU_TRINH",
                    "Buổi này vừa được gắn / gỡ ở màn khác — đã tải lại, bấm lại.",
                )
            await conn.execute(
                _GO_TAY,
                cid,
                oid,
                identity.staff_id,
            )
            await self._phat_buoi(conn, identity, mong, oid, "GO", None)
            return {
                "ok": True,
                "changed": True,
                "lieu_trinh": await self._mot(conn, cid, mong),
            }, mong

        return await self._lenh(
            identity=identity,
            action="lieu_trinh.go",
            key=idempotency_key,
            payload=payload,
            quyen=QUYEN_SUA,
            cau_quyen="Chỉ khối y khoa / trưởng ca gỡ được buổi khỏi liệu trình.",
            lam=lam,
        )

    @staticmethod
    async def _khoa_chi_dinh(
        conn: asyncpg.Connection, cid: str, oid: str
    ) -> str | None:
        """Khoá chỉ định (xếp hàng với lệnh đổi trạng thái), trả liệu trình đang gắn."""
        song = await conn.fetchval(
            "SELECT lieu_trinh_chi_dinh_song(exec_status, execution_status,"
            "                                selection_status)"
            "  FROM service_order WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   FOR UPDATE",
            cid,
            oid,
        )
        if song is None:
            raise NotFoundError("Không tìm thấy chỉ định này.")
        if not song:
            raise LuotKhamConflictError(
                "CHI_DINH_DA_BO",
                "Chỉ định đã bỏ / không làm — không gắn vào liệu trình.",
            )
        hien = await conn.fetchval(
            "SELECT lieu_trinh_id::text FROM lieu_trinh_buoi"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND go_luc IS NULL",
            cid,
            oid,
        )
        return str(hien) if hien is not None else None

    async def _phat_buoi(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        lt: str,
        oid: str,
        hanh_dong: str,
        buoi_so: int | None,
    ) -> None:
        await emit_event(
            conn,
            ten="lieu_trinh.session_relinked",
            clinic_id=identity.clinic_id,
            aggregate_id=lt,
            so_ke_tiep=True,
            payload=LieuTrinhBuoiDaDoi(
                lieu_trinh_id=lt,
                service_order_id=oid,
                hanh_dong=hanh_dong,
                buoi_so=buoi_so,
            ),
            boi=nguoi(identity),
        )


def _ts(raw: Any) -> datetime | None:
    """Mốc giờ lưu trong lịch sử (chuỗi ISO) → datetime; rác → None (không ném)."""
    if raw is None or isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None


__all__ = [
    "LieuTrinhService",
    "QUYEN_DANG_KY",
    "QUYEN_DOC",
    "QUYEN_SUA",
    "con_lai",
    "doc_ds_uuid",
    "doc_ghi_chu",
    "doc_so_buoi",
    "doc_so_ngay",
    "loi_db",
]
