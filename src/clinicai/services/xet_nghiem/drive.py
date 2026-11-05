"""Kết quả đối tác tự về từ Google Drive — vòng quét (chặng 4, kế hoạch 4.7).

Chạy trong dịch vụ riêng `drive-xn` (`worker --drive`, gắn ổ VPS + khoá chỉ đọc; staging
tắt `day-tep` nên không đặt ở đó), mỗi `NHIP_GIAY`. Mỗi đối tác có `drive_folder_id`
(còn hoạt động): liệt kê thư mục, tệp nào chưa có dòng `drive_tep` (theo
`(file_id, md5)`) thì:

1. `quyet_ghep` (hàm thuần) đọc mã ống trong TÊN tệp: không mã / sai số kiểm / nhiều
   mã / không thấy ống / ống của đối tác khác / ống nhiều việc ⇒ CHỜ GHÉP TAY (lý do
   lưu vào `ly_do_cho`), KHÔNG đoán.
2. Khớp đúng một việc ⇒ tải tệp từ Drive, đưa qua ĐÚNG lõi `TepKetQuaService.tai_len`
   (`identity=MayQuet`, `tu_drive=True`) — như tải tay: báo bác sĩ + CSKH qua
   `result_file.uploaded`. Gửi khách vẫn qua "Đúng người, gửi".
3. Ghi dòng `drive_tep` (sự việc) + nhịp `drive_nhip`.

Vòng không bao giờ ném (mỗi đối tác bọc riêng); lỗi ghi vào `drive_nhip.loi_cuoi`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import structlog

from clinicai.events.catalogue import XetNghiemViec
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.services.nguon_tep import MayQuet
from clinicai.services.xet_nghiem import drive_api
from clinicai.services.xet_nghiem.ma_mau import co_dang_ma, tim_ma_trong_ten

logger = structlog.get_logger()

NHIP_GIAY: Final = 180
TRAN_DOI_TAC: Final = 50
#: Khoá tư vấn: chỉ MỘT tiến trình quét (hai container ⇒ cái sau đứng im).
KHOA_MOT_TIEN_TRINH: Final = "xet-nghiem-drive-quet"
#: Quá ngưỡng này không có lượt quét thành công ⇒ đèn đỏ (kế hoạch mục 7).
TRE_NHIP: Final = timedelta(hours=1)
_VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")


def den_drive(
    thu_muc: str | None,
    lan_quet: datetime | None,
    ok_cuoi: datetime | None,
    loi: str | None,
    bay_gio: datetime,
) -> dict[str, str]:
    """Đèn nhịp Drive trên thẻ đối tác: chữ + màu chip (một nơi tính, màn chỉ hiện)."""
    if not thu_muc:
        return {"nhan": "Chưa nối thư mục Drive", "mau": "neutral"}
    if lan_quet is None:
        return {"nhan": "Đã nối thư mục Drive · chưa quét lần nào", "mau": "neutral"}
    gio = lan_quet.astimezone(_VN).strftime("%H:%M %d/%m")
    if loi:
        return {"nhan": f"Drive lỗi lúc {gio}: {loi}", "mau": "danger"}
    if ok_cuoi is None or bay_gio - ok_cuoi > TRE_NHIP:
        return {
            "nhan": f"Drive quá 1 giờ chưa quét được (lần cuối {gio})",
            "mau": "danger",
        }
    return {"nhan": f"Drive ổn · quét lúc {gio}", "mau": "success"}


@dataclass(frozen=True)
class Quyet:
    order_id: str | None
    clinic_patient_id: str | None
    visit_id: str | None
    ly_do: str | None


def quyet_ghep(
    ten: str,
    doi_tac_thu_muc: str,
    mau: dict[str, Any] | None,
    viec: list[dict[str, Any]],
) -> Quyet:
    """Tên tệp + ống tìm được ⇒ ghép vào việc nào, hoặc vì sao chờ ghép tay.

    `mau`: ống còn hiệu lực có mã trong tên (None = không thấy). `viec`: các việc còn
    trong ống, mỗi việc có `co_tep` (đã có tờ kết quả còn hiệu lực). Nhiều việc mà chỉ
    một việc chưa có kết quả ⇒ việc đó; đúng một việc (dù đã có kết quả) ⇒ bản mới.
    """
    rong = Quyet(None, None, None, None)
    ma = set(tim_ma_trong_ten(ten))
    if not ma:
        return Quyet(
            **{
                **rong.__dict__,
                "ly_do": "SAI_SO_KIEM" if co_dang_ma(ten) else "KHONG_MA",
            }
        )
    if len(ma) > 1:
        return Quyet(**{**rong.__dict__, "ly_do": "NHIEU_MA"})
    if mau is None:
        return Quyet(**{**rong.__dict__, "ly_do": "KHONG_THAY_MAU"})
    if str(mau["doi_tac_id"]) != str(doi_tac_thu_muc):
        return Quyet(**{**rong.__dict__, "ly_do": "SAI_DOI_TAC"})
    chua = [v for v in viec if not v["co_tep"]]
    chon = chua if chua else viec
    if len(chon) != 1:
        return Quyet(
            **{**rong.__dict__, "ly_do": "ONG_NHIEU_VIEC" if chon else "KHONG_THAY_MAU"}
        )
    v = chon[0]
    return Quyet(str(v["order_id"]), v["clinic_patient_id"], v["visit_id"], None)


_ONG_SQL = """
SELECT m.id::text AS mau_id, m.doi_tac_id::text AS doi_tac_id
  FROM mau_xet_nghiem m
 WHERE m.clinic_id = $1::uuid AND m.ma_mau = $2 AND m.huy_luc IS NULL
"""
_VIEC_ONG_SQL = """
SELECT mv.service_order_id::text AS order_id,
       v.clinic_patient_id::text AS clinic_patient_id, o.visit_id::text AS visit_id,
       EXISTS (SELECT 1 FROM tep_ket_qua k
                WHERE k.clinic_id = mv.clinic_id
                  AND k.service_order_id = mv.service_order_id
                  AND k.da_xoa_luc IS NULL
                  AND coalesce(k.xac_nhan_trang_thai, '') NOT IN ('TU_CHOI', 'THU_HOI'))
           AS co_tep
  FROM mau_xet_nghiem_viec mv
  JOIN service_order o ON o.id = mv.service_order_id AND o.clinic_id = mv.clinic_id
  LEFT JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
 WHERE mv.clinic_id = $1::uuid AND mv.mau_id = $2::uuid AND mv.go_luc IS NULL
"""


async def xet(conn: asyncpg.Connection, cid: str, doi_tac_id: str, ten: str) -> Quyet:
    """Đọc ống theo mã trong tên rồi gọi `quyet_ghep`."""
    ma = tim_ma_trong_ten(ten)
    mau = viec = None
    if len(set(ma)) == 1:
        mau = await conn.fetchrow(_ONG_SQL, cid, ma[0])
        if mau is not None:
            viec = [
                dict(r) for r in await conn.fetch(_VIEC_ONG_SQL, cid, mau["mau_id"])
            ]
    return quyet_ghep(ten, doi_tac_id, dict(mau) if mau else None, viec or [])


async def _da_co(
    pool: asyncpg.Pool, cid: str, teps: list[drive_api.TepDrive]
) -> set[tuple[str, str]]:
    rows = await pool.fetch(
        "SELECT file_id, md5 FROM drive_tep"
        " WHERE clinic_id = $1::uuid AND file_id = ANY($2::text[])",
        cid,
        [t.file_id for t in teps],
    )
    return {(r["file_id"], r["md5"]) for r in rows}


async def _ghi_dong(
    pool: asyncpg.Pool,
    cid: str,
    doi_tac_id: str,
    t: drive_api.TepDrive,
    ly_do: str | None,
    tep_id: str | None,
) -> None:
    await pool.execute(
        """
        INSERT INTO drive_tep (clinic_id, doi_tac_id, file_id, md5, ten, mime, so_byte,
                               drive_tao_luc, drive_nguoi_tai, ly_do_cho,
                               tep_ket_qua_id, ghep_luc)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8::timestamptz, $9, $10,
                $11::uuid, CASE WHEN $11::uuid IS NULL THEN NULL ELSE now() END)
        ON CONFLICT (clinic_id, file_id, md5) DO NOTHING
        """,
        cid,
        doi_tac_id,
        t.file_id,
        t.md5,
        t.ten or "(không tên)",
        t.mime,
        t.so_byte,
        t.tao_luc,
        t.nguoi_tai,
        ly_do,
        tep_id,
    )


async def nhan_mot(
    pool: asyncpg.Pool,
    kh: httpx.AsyncClient,
    cid: str,
    doi_tac_id: str,
    t: drive_api.TepDrive,
) -> str | None:
    """Một tệp mới: quyết, (tự ghép), ghi sự việc. Trả `ly_do_cho` (None = đã ghép)."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    async with pool.acquire() as conn:
        q = await xet(conn, cid, doi_tac_id, t.ten)
    tep_id: str | None = None
    ly = q.ly_do
    if q.order_id and q.clinic_patient_id:
        try:
            data = await drive_api.tai_ve(kh, t.file_id)
            kq = await TepKetQuaService(pool).tai_len(
                identity=MayQuet(clinic_id=cid),
                clinic_patient_id=q.clinic_patient_id,
                data=data,
                ten_hien_thi=t.ten,
                service_order_id=q.order_id,
                la_tep_doi_tac=True,
                tu_drive=True,
                drive_nguoi_tai=t.nguoi_tai,
            )
            tep_id = str(kq["id"])
        except Exception:  # noqa: BLE001 — tệp hỏng/quá lớn/Drive lỗi ⇒ hàng ghép tay
            logger.exception("drive_tu_ghep_loi", file_id=t.file_id)
            ly = "LOI_TEP"
    await _ghi_dong(pool, cid, doi_tac_id, t, ly, tep_id)
    if tep_id and q.order_id:
        await _phat_den(pool, cid, q)
    return ly


async def _phat_den(pool: asyncpg.Pool, cid: str, q: Quyet) -> None:
    """Sự kiện sau khi tờ đã commit: lỗi phát KHÔNG được dừng lượt quét (dòng
    drive_tep đã ghi ⇒ không thử lại) — ghi log, không ném (như `ket_qua._phat`)."""
    assert q.order_id is not None
    try:
        async with pool.acquire() as conn, conn.transaction():
            await emit_event(
                conn,
                ten="lab.result_arrived",
                clinic_id=cid,
                aggregate_id=q.order_id,
                payload=XetNghiemViec(visit_id=q.visit_id, service_order_id=q.order_id),
                boi=HE_THONG,
                correlation_id=q.visit_id,
            )
    except Exception:  # noqa: BLE001 — tờ đã commit; chỉ mất vết sự kiện
        logger.exception("drive_phat_su_kien_loi", order_id=q.order_id)


async def _nhip(
    pool: asyncpg.Pool, cid: str, doi_tac_id: str, loi: str | None, so: int
) -> None:
    await pool.execute(
        """
        INSERT INTO drive_nhip (clinic_id, doi_tac_id, lan_quet_cuoi, ok_cuoi,
                                loi_cuoi, so_tep_cuoi)
        VALUES ($1::uuid, $2::uuid, now(),
                CASE WHEN $3::text IS NULL THEN now() END, $3, $4)
        ON CONFLICT (clinic_id, doi_tac_id) DO UPDATE
           SET lan_quet_cuoi = now(),
               ok_cuoi = CASE WHEN $3::text IS NULL THEN now()
                              ELSE drive_nhip.ok_cuoi END,
               loi_cuoi = $3, so_tep_cuoi = $4
        """,
        cid,
        doi_tac_id,
        loi,
        so,
    )


async def quet_doi_tac(
    pool: asyncpg.Pool, kh: httpx.AsyncClient, cid: str, doi_tac_id: str, thu_muc: str
) -> int:
    teps = [t for t in await drive_api.liet_ke(kh, thu_muc) if t.file_id and t.md5]
    da_co = await _da_co(pool, cid, teps) if teps else set()
    moi = [t for t in teps if (t.file_id, t.md5) not in da_co]
    for t in moi:
        await nhan_mot(pool, kh, cid, doi_tac_id, t)
    return len(moi)


async def mot_vong(pool: asyncpg.Pool) -> dict[str, int]:
    """Một lượt quét mọi đối tác có thư mục. Không có khoá ⇒ bỏ qua, không ném."""
    if not drive_api.co_cau_hinh():
        return {"bo_qua": 1}
    rows = await pool.fetch(
        "SELECT clinic_id::text AS cid, id::text AS id, drive_folder_id FROM doi_tac"
        " WHERE drive_folder_id IS NOT NULL AND ngung_luc IS NULL LIMIT $1",
        TRAN_DOI_TAC,
    )
    tong = loi = 0
    async with httpx.AsyncClient(timeout=60) as kh:
        for r in rows:
            try:
                so = await quet_doi_tac(
                    pool, kh, r["cid"], r["id"], r["drive_folder_id"]
                )
                tong += so
                await _nhip(pool, r["cid"], r["id"], None, so)
            except Exception as e:  # noqa: BLE001 — một đối tác lỗi không chặn đối tác khác
                loi += 1
                cau = (
                    str(e)[:300]
                    if isinstance(e, drive_api.DriveError)
                    else "Lỗi quét Drive."
                )
                logger.exception("drive_quet_loi", doi_tac_id=r["id"])
                try:
                    await _nhip(pool, r["cid"], r["id"], cau, 0)
                except Exception:  # noqa: BLE001
                    logger.exception("drive_ghi_nhip_loi", doi_tac_id=r["id"])
    return {"doi_tac": len(rows), "tep_moi": tong, "loi": loi}
