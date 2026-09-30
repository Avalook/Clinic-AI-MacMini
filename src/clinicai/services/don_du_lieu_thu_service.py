"""Dọn dữ liệu khách THỬ — quản trị viên tự CHỌN khách để xoá (Tuyền chốt 30/09/2026).

"Giao diện hiện theo kiểu tiếp đón khách để biết ngày nào là ai, lỡ xoá nhầm
người thật thì sao." Màn `/settings/don-du-lieu-thu` liệt kê khách theo NGÀY
(giờ, số, tên, SĐT che, bác sĩ, loại khám, trạng thái, chỉ định / tiền đã thu /
tệp), quản trị viên tick từng khách → xem trước số dòng sẽ xoá → gõ "XOA".

Ba lệnh, cả ba chỉ cho người có `permission.manage` (quản trị cao nhất):

* `danh_sach(ngay)` — khách có lịch / lượt trong ngày ấy.
* `xem_truoc(khach)` — gọi `don_khach_thu(..., lam_that=false)`, cuộn lại:
  số dòng theo loại + khách nào đang bị chặn.
* `xoa(khach, xac_nhan)` — MỘT giao dịch: chặn khách có lượt đang mở hôm nay,
  gọi `don_khach_thu(..., lam_that=true)` (lưu nguyên văn mọi dòng vào
  `du_lieu_da_xoa`, xoá, kiểm, ghi nhật ký `lan_don_du_lieu_thu`). Xong giao
  dịch mới chuyển tệp kết quả sang thư mục lưu trữ trên CÙNG ổ (không xoá hẳn),
  rồi ghi kết quả chuyển tệp vào nhật ký.

"Xoá một khách" là xoá những dòng nào thì CHỈ hàm SQL `don_khach_thu`
(migration 20261001240000) biết — `scripts/don-truoc-moc.sh` gọi cùng hàm ấy.
Ở đây chỉ có luật của MÀN: ai được làm, khách nào bị chặn, gõ chữ xác nhận.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.kho_tep import KHO_CFS, KHO_VPS, chay_tren_kho
from clinicai.permissions.can import doi_quyen
from clinicai.services import media_service

logger = structlog.get_logger()

#: Quản trị cao nhất: người cấp / thu được mọi quyền.
QUYEN = "permission.manage"
#: Chữ phải gõ đúng trước khi xoá.
CHU_XAC_NHAN = "XOA"
#: Một lần xoá tối đa bấy nhiêu khách (một ngày thử nhiều nhất vài chục).
TOI_DA_KHACH = 200
#: Thư mục lưu trữ tệp của khách đã xoá — NẰM TRONG gốc kho (cùng ổ, đổi tên là
#: xong; container api chỉ gắn hai gốc kho, không thấy thư mục anh em bên ngoài).
THU_MUC_LUU_TRU = ".luu-tru-don-du-lieu-thu"

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_NGAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Nhóm số dòng cho hộp xác nhận — người đọc hiểu "3 lượt khám", không hiểu
#: "work_item_dependency 24". Bảng không nằm ở đây gộp vào "khác".
NHOM_BANG: list[tuple[str, str, tuple[str, ...]]] = [
    ("khach", "Hồ sơ khách", ("patient",)),
    ("lich", "Lịch hẹn", ("appointment",)),
    ("luot", "Lượt khám", ("visit",)),
    ("chi_dinh", "Chỉ định dịch vụ", ("service_order",)),
    ("phieu_thu", "Phiếu thu", ("payment_cycle",)),
    ("don_thuoc", "Dòng đơn thuốc", ("prescription",)),
    ("tep", "Tệp kết quả", ("tep_ket_qua",)),
    ("phieu_kho", "Phiếu xuất thuốc (trả lại kho)", ("inventory_txn",)),
]
TEN_KHAC = "Dữ liệu kèm theo khác (bệnh án, việc, sổ sự kiện, thông báo…)"

TRANG_THAI_LICH = {
    "CONFIRMED": "Đã hẹn",
    "CHECKED_IN": "Đã đến",
    "COMPLETED": "Xong",
    "CANCELLED": "Đã huỷ",
    "NO_SHOW": "Không đến",
}
TRANG_THAI_LUOT = {
    "OPEN": "Mới vào",
    "IN_PROGRESS": "Đang khám",
    "INCOMPLETE": "Dừng giữa chừng",
    "FINALIZED": "Xong",
    "AMENDED": "Đã đính chính",
}


# ── Hàm thuần ───────────────────────────────────────────────────────────────
def che_sdt(sdt: str | None) -> str:
    """Che 3 số giữa: 0334567897 → 0334***897. Rỗng / quá ngắn → trả nguyên."""
    s = (sdt or "").strip()
    if len(s) < 7:
        return s
    return f"{s[:-6]}***{s[-3:]}"


def doc_ngay(chuoi: str | None) -> date | None:
    """`YYYY-MM-DD` → date; rỗng / rác → None (không ném — luật ngày giờ)."""
    s = (chuoi or "").strip()
    if not _NGAY_RE.fullmatch(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def ngay_mac_dinh(hom_nay: date) -> date:
    """Màn mở ngày HÔM QUA: dọn dữ liệu thử là việc nhìn lại ngày đã qua."""
    return hom_nay - timedelta(days=1)


def chuan_khach(ids: Any) -> list[str]:
    """Danh sách id khách hợp lệ, bỏ trùng, giữ thứ tự. Sai hình → ValidationError."""
    if not isinstance(ids, list) or not ids:
        raise ValidationError("Chưa chọn khách nào.")
    ra: list[str] = []
    for x in ids:
        s = str(x).strip().lower()
        if not _UUID_RE.fullmatch(s):
            raise ValidationError("Mã khách không hợp lệ.")
        if s not in ra:
            ra.append(s)
    if len(ra) > TOI_DA_KHACH:
        raise ValidationError(f"Mỗi lần xoá tối đa {TOI_DA_KHACH} khách.")
    return ra


def nhom_so_dong(so_dong: dict[str, int]) -> list[dict[str, Any]]:
    """{bảng: số} → các nhóm người đọc được, bỏ nhóm 0; phần còn lại vào "khác"."""
    ra: list[dict[str, Any]] = []
    da_tinh: set[str] = set()
    for ma, ten, bang in NHOM_BANG:
        so = sum(int(so_dong.get(b, 0)) for b in bang)
        da_tinh.update(bang)
        if so:
            ra.append({"ma": ma, "ten": ten, "so": so})
    khac = sum(int(v) for k, v in so_dong.items() if k not in da_tinh)
    if khac:
        ra.append({"ma": "khac", "ten": TEN_KHAC, "so": khac})
    return ra


def xac_nhan_dung(chu: Any) -> bool:
    return isinstance(chu, str) and chu.strip() == CHU_XAC_NHAN


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


# ── Chuyển tệp (chạy ở luồng phụ qua `chay_tren_kho`) ───────────────────────
def chuyen_mot_tep(goc: Path, khoa: str, lan_id: str) -> str:
    """Chuyển `goc/khoa` sang `goc/.luu-tru-don-du-lieu-thu/<lan>/khoa`.

    Trả "da_chuyen" | "khong_co". Khoá lạ (ra ngoài gốc) → "khong_co".
    Đồng bộ, chạm ổ — gọi trong `chay_tren_kho`.
    """
    nguon = media_service.giai_trong(goc, khoa)
    if nguon is None or not nguon.is_file():
        return "khong_co"
    dich = goc / THU_MUC_LUU_TRU / lan_id / khoa
    dich.parent.mkdir(parents=True, exist_ok=True)
    os.replace(nguon, dich)
    return "da_chuyen"


class DonDuLieuThuService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    async def _gac(conn: asyncpg.Connection, identity: StaffIdentity) -> None:
        await doi_quyen(
            conn,
            identity,
            QUYEN,
            cau="Chỉ quản trị viên (quyền Phân quyền) mới dọn được dữ liệu khách thử.",
        )

    # ── Đọc ────────────────────────────────────────────────────────────────
    async def danh_sach(
        self, *, identity: StaffIdentity, ngay: str | None
    ) -> dict[str, Any]:
        hom_nay = hom_nay_vn()
        d = doc_ngay(ngay) or ngay_mac_dinh(hom_nay)
        async with self._pool.acquire() as conn:
            await self._gac(conn, identity)
            dong = await conn.fetch(_SQL_DANH_SACH, identity.clinic_id, d)
            khach_ids = sorted({str(r["khach_id"]) for r in dong})
            ngay_khac = await conn.fetch(
                _SQL_NGAY_KHAC, identity.clinic_id, khach_ids, d
            )
            dang_mo = await conn.fetch(
                _SQL_DANG_MO_HOM_NAY, identity.clinic_id, khach_ids, hom_nay
            )
            lan = await conn.fetch(_SQL_LAN_GAN_DAY, identity.clinic_id)
        khac_theo_khach: dict[str, list[str]] = {}
        for r in ngay_khac:
            khac_theo_khach.setdefault(str(r["khach_id"]), []).append(
                r["ngay"].isoformat()
            )
        mo = {str(r["khach_id"]) for r in dang_mo}
        return {
            "ngay": d.isoformat(),
            "hom_nay": hom_nay.isoformat(),
            "dong": [
                _dong_ra(r, khac_theo_khach.get(str(r["khach_id"]), []), mo)
                for r in dong
            ],
            "lan_gan_day": [
                {
                    "id": str(r["id"]),
                    "luc": r["luc"].isoformat(),
                    "boi": r["boi_ten"],
                    "nguon": r["nguon"],
                    "khach": [
                        {"ma": k.get("ma"), "ten": k.get("ten")}
                        for k in (_json(r["khach"]) or [])
                    ],
                    "so_dong": sum(int(v) for v in (_json(r["so_dong"]) or {}).values()),
                }
                for r in lan
            ],
        }

    async def xem_truoc(
        self, *, identity: StaffIdentity, khach: Any
    ) -> dict[str, Any]:
        ids = chuan_khach(khach)
        async with self._pool.acquire() as conn:
            await self._gac(conn, identity)
            tx = conn.transaction()
            await tx.start()
            try:
                kq = _json(
                    await conn.fetchval(
                        "SELECT public.don_khach_thu($1::uuid, $2::uuid[], false)",
                        identity.clinic_id,
                        ids,
                    )
                )
                chan = await conn.fetch(
                    _SQL_DANG_MO_HOM_NAY, identity.clinic_id, ids, hom_nay_vn()
                )
                ngay = await conn.fetch(_SQL_NGAY_CUA_KHACH, identity.clinic_id, ids)
            except asyncpg.NoDataFoundError as loi:
                raise ValidationError(
                    "Có khách không còn tồn tại (có thể vừa bị xoá) — tải lại danh sách."
                ) from loi
            finally:
                # Chỉ xem: không bao giờ giữ gì của lần gọi này.
                await tx.rollback()
        ngay_theo: dict[str, list[str]] = {}
        for r in ngay:
            ngay_theo.setdefault(str(r["khach_id"]), []).append(r["ngay"].isoformat())
        so_dong = {k: int(v) for k, v in (kq.get("so_dong") or {}).items()}
        return {
            "khach": [
                {
                    "id": k["id"],
                    "ma": k["ma"],
                    "ten": k["ten"],
                    "ngay": ngay_theo.get(str(k["id"]), []),
                }
                for k in kq.get("khach") or []
            ],
            "nhom": nhom_so_dong(so_dong),
            "tong_dong": sum(so_dong.values()),
            "so_tep": len(kq.get("tep") or []),
            "bi_chan": [
                {"id": str(r["khach_id"]), "ten": r["ten"]} for r in chan
            ],
        }

    # ── Ghi ────────────────────────────────────────────────────────────────
    async def xoa(
        self, *, identity: StaffIdentity, khach: Any, xac_nhan: Any
    ) -> dict[str, Any]:
        ids = chuan_khach(khach)
        if not xac_nhan_dung(xac_nhan):
            raise ValidationError(f"Gõ đúng chữ {CHU_XAC_NHAN} để xác nhận xoá.")
        async with self._pool.acquire() as conn:
            await self._gac(conn, identity)
            try:
                async with conn.transaction():
                    # Chờ khoá tối đa 5 giây (hàm tắt tạm trigger chặn xoá của
                    # vài bảng lõi — phải chờ các lệnh đang chạy xong).
                    await conn.execute("SET LOCAL lock_timeout = '5s'")
                    # Khoá hồ sơ các khách được chọn: không ai check-in chen vào
                    # giữa lúc kiểm "đang mở" và lúc xoá.
                    await conn.execute(
                        "SELECT 1 FROM patient WHERE clinic_id = $1::uuid"
                        " AND clinic_patient_id = ANY($2::uuid[]) FOR UPDATE",
                        identity.clinic_id,
                        ids,
                    )
                    chan = await conn.fetch(
                        _SQL_DANG_MO_HOM_NAY, identity.clinic_id, ids, hom_nay_vn()
                    )
                    if chan:
                        ten = ", ".join(r["ten"] for r in chan)
                        raise ValidationError(
                            f"Không xoá được: {ten} đang có lượt khám MỞ hôm nay. "
                            "Đóng lượt (khách về) hoặc bỏ tick khách ấy rồi thử lại."
                        )
                    kq = _json(
                        await conn.fetchval(
                            "SELECT public.don_khach_thu($1::uuid, $2::uuid[], true,"
                            " NULL, $3::uuid, $4, 'man_quan_tri')",
                            identity.clinic_id,
                            ids,
                            identity.staff_id,
                            identity.full_name,
                        )
                    )
            except asyncpg.NoDataFoundError as loi:
                raise ValidationError(
                    "Có khách không còn tồn tại (có thể vừa bị xoá) — tải lại danh sách."
                ) from loi
            except asyncpg.LockNotAvailableError as loi:
                raise ConflictError(
                    "Hệ thống đang bận ghi dữ liệu — chưa xoá gì. Thử lại sau ít giây."
                ) from loi

        lan_id = str(kq.get("lan_id") or "")
        so_dong = {k: int(v) for k, v in (kq.get("so_dong") or {}).items()}
        tep = await self._chuyen_tep(kq.get("tep") or [], lan_id) if lan_id else {}
        if lan_id:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE lan_don_du_lieu_thu SET tep_da_chuyen = $3::jsonb"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    identity.clinic_id,
                    lan_id,
                    json.dumps(tep),
                )
        logger.info(
            "don_du_lieu_thu_xong",
            lan_id=lan_id,
            boi=identity.staff_id,
            so_khach=len(kq.get("khach") or []),
            tong_dong=sum(so_dong.values()),
            tep=tep.get("tong"),
        )
        return {
            "lan_id": lan_id,
            "khach": [
                {"ma": k["ma"], "ten": k["ten"]} for k in kq.get("khach") or []
            ],
            "nhom": nhom_so_dong(so_dong),
            "tong_dong": sum(so_dong.values()),
            "tep": tep,
        }

    @staticmethod
    async def _chuyen_tep(ds: list[dict[str, Any]], lan_id: str) -> dict[str, Any]:
        """Chuyển tệp của các dòng đã xoá sang thư mục lưu trữ, CẢ HAI ổ (bản ổ
        VPS nếu còn, bản CFS nếu đã đẩy). Ổ chậm / lỗi: ghi lại, không ném —
        dữ liệu đã xoá xong, tệp sót chuyển tay sau theo nhật ký."""
        ket: dict[str, Any] = {"tong": len(ds), "da_chuyen": 0, "khong_co": 0, "loi": []}
        for t in ds:
            khoa = str(t.get("khoa") or "")
            chuyen = False
            for goc, kho in (
                (media_service.goc_vps(), KHO_VPS),
                (media_service.goc_cfs(), KHO_CFS),
            ):
                try:
                    kq = await chay_tren_kho(
                        lambda g=goc: chuyen_mot_tep(g, khoa, lan_id), kho=kho
                    )
                except Exception as loi:  # noqa: BLE001 — ghi lại, không làm hỏng lần xoá
                    ket["loi"].append({"khoa": khoa, "kho": kho, "loi": str(loi)[:200]})
                    continue
                chuyen = chuyen or kq == "da_chuyen"
            if chuyen:
                ket["da_chuyen"] += 1
            else:
                ket["khong_co"] += 1
        return ket


def _dong_ra(r: asyncpg.Record, ngay_khac: list[str], mo: set[str]) -> dict[str, Any]:
    kid = str(r["khach_id"])
    trang_thai = r["trang_thai"] or ""
    return {
        "loai": r["loai"],
        "id": str(r["id"]),
        "gio": r["gio"].strftime("%H:%M") if r["gio"] else None,
        "so_booking": r["so_booking"],
        "so_quay": r["so_quay"],
        "khach": {
            "id": kid,
            "ma": r["ma"],
            "ten": r["ten"],
            "sdt": che_sdt(r["sdt"]),
        },
        "bac_si": r["bac_si"],
        "loai_kham": r["loai_kham"],
        "vang_lai": bool(r["vang_lai"]),
        "trang_thai": trang_thai,
        "trang_thai_ten": (
            TRANG_THAI_LICH if r["loai"] == "lich" else TRANG_THAI_LUOT
        ).get(trang_thai, trang_thai),
        "so_chi_dinh": int(r["so_chi_dinh"] or 0),
        "da_thu": int(r["da_thu"] or 0),
        "so_tep": int(r["so_tep"] or 0),
        "ngay_khac": ngay_khac,
        "dang_mo_hom_nay": kid in mo,
    }


# ── SQL ────────────────────────────────────────────────────────────────────
# Một dòng = một lịch hẹn trong ngày, hoặc một lượt KHÔNG lịch check-in trong
# ngày (như màn Tiếp đón). Chỉ định / tiền / tệp đếm theo các lượt của lịch ấy.
_SQL_DANH_SACH = """
WITH lich AS (
    SELECT 'lich'::text AS loai, a.id, a.clinic_patient_id AS khach_id,
           a.slot_start AS luc, a.so_booking, a.so_tiep_don AS so_quay,
           a.doctor_id AS bac_si_id, a.service_type_id, a.status AS trang_thai,
           a.is_walkin AS vang_lai,
           ARRAY(SELECT v.visit_id FROM visit v
                  WHERE v.clinic_id = a.clinic_id AND v.appointment_id = a.id) AS luot
      FROM appointment a
     WHERE a.clinic_id = $1::uuid
       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2::date
), luot AS (
    SELECT 'luot'::text AS loai, v.visit_id AS id, v.clinic_patient_id AS khach_id,
           coalesce(v.checked_in_at, v.created_at) AS luc, NULL::int AS so_booking,
           NULL::int AS so_quay, v.attending_doctor_id AS bac_si_id,
           v.service_type_id, v.status AS trang_thai, true AS vang_lai,
           ARRAY[v.visit_id] AS luot
      FROM visit v
     WHERE v.clinic_id = $1::uuid AND v.appointment_id IS NULL
       AND (coalesce(v.checked_in_at, v.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           = $2::date
), dong AS (SELECT * FROM lich UNION ALL SELECT * FROM luot)
SELECT d.loai, d.id, d.khach_id, d.luc AT TIME ZONE 'Asia/Ho_Chi_Minh' AS gio,
       d.so_booking, d.so_quay, d.trang_thai, d.vang_lai,
       p.patient_code AS ma, p.full_name AS ten, p.phone_primary AS sdt,
       s.full_name AS bac_si, st.name AS loai_kham,
       (SELECT count(*) FROM service_order o
         WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY (d.luot)) AS so_chi_dinh,
       (SELECT coalesce(sum(pc.amount), 0) FROM payment_cycle pc
         WHERE pc.clinic_id = $1::uuid AND pc.visit_id = ANY (d.luot)
           AND pc.status = 'PAID') AS da_thu,
       (SELECT count(*) FROM tep_ket_qua t
         WHERE t.clinic_id = $1::uuid
           AND (t.appointment_id = d.id
                OR t.service_order_id IN (SELECT o.id FROM service_order o
                                           WHERE o.clinic_id = $1::uuid
                                             AND o.visit_id = ANY (d.luot)))) AS so_tep
  FROM dong d
  JOIN patient p ON p.clinic_patient_id = d.khach_id AND p.clinic_id = $1::uuid
  LEFT JOIN staff s ON s.id = d.bac_si_id
  LEFT JOIN service_type st ON st.id = d.service_type_id
 ORDER BY d.luc, d.so_booking NULLS LAST, p.full_name
"""

# Ngày KHÁC (giờ VN) khách có lịch / lượt — để hiện "có lượt ngày khác".
_SQL_NGAY_KHAC = """
SELECT DISTINCT x.khach_id, x.ngay FROM (
    SELECT a.clinic_patient_id AS khach_id,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay
      FROM appointment a
     WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = ANY ($2::uuid[])
    UNION
    SELECT v.clinic_patient_id,
           (coalesce(v.checked_in_at, v.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
      FROM visit v
     WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = ANY ($2::uuid[])
) x
WHERE x.ngay <> $3::date
ORDER BY x.khach_id, x.ngay
"""

# Mọi ngày khách có dữ liệu (hộp xác nhận).
_SQL_NGAY_CUA_KHACH = """
SELECT DISTINCT x.khach_id, x.ngay FROM (
    SELECT a.clinic_patient_id AS khach_id,
           (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay
      FROM appointment a
     WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = ANY ($2::uuid[])
    UNION
    SELECT v.clinic_patient_id,
           (coalesce(v.checked_in_at, v.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
      FROM visit v
     WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = ANY ($2::uuid[])
) x
ORDER BY x.khach_id, x.ngay
"""

# Lượt ĐANG MỞ hôm nay: check-in hôm nay, chưa đóng (khách chưa về), chưa xong.
_SQL_DANG_MO_HOM_NAY = """
SELECT DISTINCT v.clinic_patient_id AS khach_id, p.full_name AS ten
  FROM visit v
  JOIN patient p ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = $1::uuid
 WHERE v.clinic_id = $1::uuid
   AND v.clinic_patient_id = ANY ($2::uuid[])
   AND (coalesce(v.checked_in_at, v.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       = $3::date
   AND v.closed_at IS NULL
   AND v.status IN ('OPEN', 'IN_PROGRESS')
 ORDER BY p.full_name
"""

_SQL_LAN_GAN_DAY = """
SELECT id, luc, boi_ten, nguon, khach, so_dong
  FROM lan_don_du_lieu_thu
 WHERE clinic_id = $1::uuid
 ORDER BY luc DESC
 LIMIT 10
"""
