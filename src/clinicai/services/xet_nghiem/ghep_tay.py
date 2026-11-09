"""Tab Kết quả — việc của NGƯỜI với tệp kết quả (chặng 4, Tuyền 05/11).

* **Ghép tay**: tệp Drive chờ ghép ⇒ chọn đúng việc ⇒ tải lại từ Drive, đi lõi `tai_len`
  (người bấm là người tải, nguồn vẫn DRIVE + tên người thả).
* **Từ chối tệp**: tệp Drive không thuộc ai (lý do ≥ 3 ký tự) — nhớ `(file_id, md5)`,
  lượt quét sau bỏ qua.
* **Gán sang**: tờ đã gán NHẦM khách ⇒ chép đúng tệp sang việc đúng (tờ mới), tờ cũ
  THU HỒI có lý do. Không sửa dòng cũ.
* **Tệp chờ ghép + nhịp quét** (đọc) và nội dung tệp chờ để xem trước (máy chủ đọc
  Drive; trình duyệt không bao giờ gọi Drive, không có link công khai).

Mọi luật "được không" ở đây; màn chỉ gửi lệnh và hiện câu lỗi.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Final

import asyncpg
import httpx

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import XetNghiemTepDrive
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.tep_ket_qua_service import TepKetQuaService, doc_dan
from clinicai.services.xet_nghiem import drive_api
from clinicai.services.xet_nghiem.ket_qua import _phat, _viec
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do

TRAN: Final = 200
#: Câu người đọc hiểu cho `drive_tep.ly_do_cho`.
LY_DO_CHO: Final = {
    "KHONG_MA": "Tên tệp không có mã ống",
    "SAI_SO_KIEM": "Mã ống trong tên tệp gõ sai (sai số kiểm)",
    "NHIEU_MA": "Tên tệp có nhiều mã ống",
    "KHONG_THAY_MAU": "Không thấy ống nào mang mã này",
    "SAI_DOI_TAC": "Ống của đối tác khác thư mục",
    "ONG_NHIEU_VIEC": "Ống có nhiều xét nghiệm — chọn đúng việc",
    "LOI_TEP": "Tệp không đọc được — tải tay hoặc từ chối",
    "KHONG_DOC_DUOC": "PDF không có chữ (ảnh scan) — chọn khách rồi Gán",
    "KHONG_KHOP_KHACH": "Không khách nào đang chờ khớp cả tên lẫn SĐT trong tệp",
    "NHIEU_KHACH": "Nhiều khách cùng khớp tên + SĐT — chọn đúng khách",
    "CHUA_LAY_MAU": "Khớp khách nhưng việc chưa bấm Lấy mẫu — kiểm rồi Gán",
    "CO_BAN_MOI": "Khách đã có tờ kết quả — có thể là bản sửa / bổ sung, kiểm rồi Gán",
}

_CHO_SQL = """
SELECT t.id::text AS id, t.doi_tac_id::text AS doi_tac_id, d.ten AS ten_doi_tac,
       t.ten, t.mime, t.drive_tao_luc, t.drive_nguoi_tai, t.nhan_luc, t.ly_do_cho,
       t.nguon, t.email_tieu_de, t.email_nhan_luc, t.goi_y_order_id::text,
       t.goi_y_clinic_patient_id::text
  FROM drive_tep t
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
 WHERE t.clinic_id = $1::uuid AND t.tep_ket_qua_id IS NULL AND t.tu_choi_luc IS NULL
   -- Thư Gmail Lưu trữ (trước mốc / không tự ghép được) chỉ ở Kho email (quyền riêng)
   -- — không ngập hàng này, không mở qua cửa theo id của nó. Thư Gmail SAU mốc đã xét
   -- ghép (G3) thì như tệp Drive.
   AND t.ly_do_cho IS DISTINCT FROM 'LUU_TRU'
 ORDER BY t.nhan_luc DESC
 LIMIT 200
"""

_NHIP_SQL = """
SELECT doi_tac_id::text AS doi_tac_id, lan_quet_cuoi, ok_cuoi, loi_cuoi,
       (ok_cuoi IS NULL OR ok_cuoi < now() - interval '1 hour') AS tre
  FROM drive_nhip
 WHERE clinic_id = $1::uuid AND nguon = 'DRIVE'
"""


def loai_xem(mime: str | None) -> str:
    """Hộp xem vẽ ảnh / PDF tại chỗ; loại khác ⇒ "Tải về"."""
    m = (mime or "").lower()
    if m.startswith("image/"):
        return "ANH"
    return "PDF" if m == "application/pdf" else "TAI_LIEU"


async def ds_cho(conn: asyncpg.Connection, cid: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(_CHO_SQL, cid)
    canh_bao_neu_day("drive_tep", len(rows), TRAN, clinic_id=cid)
    return [
        {
            **dict(r),
            "vi_sao": LY_DO_CHO.get(r["ly_do_cho"] or "", "Chờ ghép tay"),
            "loai": loai_xem(r["mime"]),
        }
        for r in rows
    ]


async def ds_nhip(conn: asyncpg.Connection, cid: str) -> list[dict[str, Any]]:
    return [dict(r) for r in await conn.fetch(_NHIP_SQL, cid)]


async def _dong_cho(
    pool: asyncpg.Pool, cid: str, drive_tep_id: object
) -> asyncpg.Record:
    try:
        r = await pool.fetchrow(
            "SELECT id::text AS id, doi_tac_id::text AS doi_tac_id, file_id, ten,"
            "       mime, nguon, khoa, vi_tri,"
            "       drive_nguoi_tai, tep_ket_qua_id, tu_choi_luc"
            "  FROM drive_tep WHERE clinic_id = $1::uuid AND id = $2::uuid"
            # Thư Gmail LƯU TRỮ không đi cửa này (không thì là đường lách quyền Kho
            # email: xem / Gán / Từ chối theo id) — cùng câu "không thấy".
            "   AND ly_do_cho IS DISTINCT FROM 'LUU_TRU'",
            cid,
            str(drive_tep_id),
        )
    except (asyncpg.DataError, ValueError):
        r = None
    if r is None:
        raise NotFoundError("Không thấy tệp Drive này — tải lại màn.")
    if r["tep_ket_qua_id"] or r["tu_choi_luc"]:
        raise ConflictError("Tệp này đã được ghép hoặc từ chối — tải lại màn.")
    return r


async def noi_dung_cho(
    pool: asyncpg.Pool, identity: StaffIdentity, drive_tep_id: object
) -> tuple[bytes, str]:
    """Xem trước tệp CHƯA ghép: máy chủ đọc từ Drive (trình duyệt không gọi Drive).

    KHÔNG tin mime Drive báo (đối tác thả `text/html`/SVG là chạy mã trên origin của
    màn). Kiểu lấy từ byte thật bằng đúng bộ nhận dạng của đường tải lên
    (`sniff_ket_qua`); chỉ ảnh/PDF được xem — loại khác từ chối (ghép rồi tải về)."""
    from clinicai.services.media_service import sniff_ket_qua

    r = await _dong_cho(pool, identity.clinic_id, drive_tep_id)
    noi = await _byte(r)
    try:
        mime, _duoi, loai = sniff_ket_qua(noi[:8192])
    except ValidationError:
        loai, mime = "", ""
    if loai not in ("ANH", "PDF"):
        raise ConflictError("Tệp này không xem trước được (không phải ảnh/PDF).")
    return noi, mime


async def _byte(r: asyncpg.Record) -> bytes:
    """Byte của tệp chờ: Drive đọc thẳng Drive; Gmail đọc bản đã lưu (G2a, `khoa`)."""
    if r["nguon"] == "GMAIL":
        from clinicai.services.xet_nghiem.gmail_luu import doc_het

        return await doc_het(str(r["khoa"]), str(r["vi_tri"]))
    async with httpx.AsyncClient(timeout=60) as kh:
        return await drive_api.tai_ve(kh, r["file_id"])


@asynccontextmanager
async def khoa_tep(pool: asyncpg.Pool, drive_tep_id: object) -> AsyncIterator[None]:
    """Một tệp chờ chỉ một bên xử lý một lúc (Gán / Từ chối / tự ghép Gmail —
    `gmail_ghep.gan_tu_dong`). `tai_len` tự mở
    giao dịch riêng nên không gói chung được một giao dịch ⇒ khoá tư vấn cấp phiên
    trên một kết nối giữ suốt lệnh; trong khoá mới đọc lại trạng thái dòng."""
    async with pool.acquire() as giu:
        khoa = f"drive-tep:{drive_tep_id}"
        await giu.execute("SELECT pg_advisory_lock(hashtextextended($1, 0))", khoa)
        try:
            yield
        finally:
            await giu.execute(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))", khoa
            )


async def ghep(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any], hom_nay: date
) -> dict[str, Any]:
    async with khoa_tep(pool, data.get("drive_tep_id")):
        return await _ghep(pool, identity, data, hom_nay)


async def _ghep(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any], hom_nay: date
) -> dict[str, Any]:
    r = await _dong_cho(pool, identity.clinic_id, data.get("drive_tep_id"))
    v = await _viec(pool, identity, data.get("order_id"), hom_nay)
    if str(v["doi_tac_id"]) != r["doi_tac_id"]:
        raise ConflictError(
            f"Tệp ở thư mục đối tác khác — việc này của {v['ten_doi_tac']}."
        )
    if not v["nut"]["tai_ket_qua"] or not v["clinic_patient_id"]:
        raise ConflictError(
            f"Chưa gán được cho việc đang «{v['trang_thai']['nhan']}» (cần đã lấy mẫu)."
        )
    noi = await _byte(r)
    kq = await TepKetQuaService(pool).tai_len(
        identity=identity,
        clinic_patient_id=v["clinic_patient_id"],
        data=noi,
        ten_hien_thi=r["ten"],
        service_order_id=v["order_id"],
        la_tep_doi_tac=True,
        tu_drive=True,
        tu_gmail=r["nguon"] == "GMAIL",
        drive_nguoi_tai=r["drive_nguoi_tai"],
    )
    n = await pool.execute(
        "UPDATE drive_tep SET tep_ket_qua_id = $3::uuid, ghep_luc = now(),"
        "       ghep_boi = $4::uuid"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid"
        "   AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL",
        identity.clinic_id,
        r["id"],
        kq["id"],
        identity.staff_id,
    )
    if n != "UPDATE 1":
        # Không thể xảy ra trong khoá; nếu có thì bù tờ vừa tạo, không để mồ côi.
        await TepKetQuaService(pool).xac_nhan_tep(
            identity=identity,
            tep_id=kq["id"],
            trang_thai="TU_CHOI",
            ly_do="Tệp Drive vừa được xử lý ở chỗ khác",
        )
        raise ConflictError("Tệp này vừa được người khác xử lý — tải lại màn.")
    await _phat(pool, identity, "den", v)
    return {"tep_id": kq["id"]}


async def tu_choi(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any]
) -> None:
    ly = doc_ly_do(data.get("ly_do"))
    async with khoa_tep(pool, data.get("drive_tep_id")):
        await _tu_choi(pool, identity, data.get("drive_tep_id"), ly)


async def _tu_choi(
    pool: asyncpg.Pool, identity: StaffIdentity, drive_tep_id: object, ly: str
) -> None:
    r = await _dong_cho(pool, identity.clinic_id, drive_tep_id)
    async with pool.acquire() as conn, conn.transaction():
        n = await conn.execute(
            "UPDATE drive_tep SET tu_choi_luc = now(), tu_choi_boi = $3::uuid,"
            "       ly_do_tu_choi = $4"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL",
            identity.clinic_id,
            r["id"],
            identity.staff_id,
            ly,
        )
        if n != "UPDATE 1":
            raise ConflictError("Tệp này vừa được người khác xử lý — tải lại màn.")
        await emit_event(
            conn,
            ten="lab.drive_file_rejected",
            clinic_id=identity.clinic_id,
            aggregate_id=r["id"],
            payload=XetNghiemTepDrive(drive_tep_id=r["id"], doi_tac_id=r["doi_tac_id"]),
            boi=nguoi(identity),
        )


async def _doc_tep(pool: asyncpg.Pool, identity: StaffIdentity, tep_id: str) -> bytes:
    tep = await TepKetQuaService(pool).mo_de_doc(identity=identity, tep_id=tep_id)
    return b"".join([p async for p in doc_dan(tep, 0, tep.so_byte - 1)])


async def gan_sang(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any], hom_nay: date
) -> dict[str, Any]:
    """Tờ của việc `order_id` gán nhầm ⇒ sang việc `order_id_moi` (cùng đối tác)."""
    ly = doc_ly_do(data.get("ly_do"))
    cu = await _viec(pool, identity, data.get("order_id"), hom_nay)
    moi = await _viec(pool, identity, data.get("order_id_moi"), hom_nay)
    if not cu["tep_id"]:
        raise ConflictError("Việc này chưa có tờ kết quả để gán sang.")
    if cu["order_id"] == moi["order_id"]:
        raise ConflictError("Chọn một việc KHÁC để gán sang.")
    if str(cu["doi_tac_id"]) != str(moi["doi_tac_id"]):
        raise ConflictError("Chỉ gán sang việc của cùng đối tác.")
    if not moi["nut"]["tai_ket_qua"] or not moi["clinic_patient_id"]:
        raise ConflictError(
            f"Việc đích đang «{moi['trang_thai']['nhan']}» — cần đã lấy mẫu."
        )
    goc = await pool.fetchrow(
        "SELECT ten_hien_thi, nguon, drive_nguoi_tai, xac_nhan_trang_thai"
        "  FROM tep_ket_qua"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        identity.clinic_id,
        cu["tep_id"],
    )
    if goc is None:
        raise NotFoundError("Không thấy tờ kết quả — tải lại màn.")
    noi = await _doc_tep(pool, identity, cu["tep_id"])
    svc = TepKetQuaService(pool)
    kq = await svc.tai_len(
        identity=identity,
        clinic_patient_id=moi["clinic_patient_id"],
        data=noi,
        ten_hien_thi=goc["ten_hien_thi"],
        service_order_id=moi["order_id"],
        la_tep_doi_tac=True,
        tu_drive=goc["nguon"] == "DRIVE",
        drive_nguoi_tai=goc["drive_nguoi_tai"],
    )
    cau = f"Gán nhầm, đã gán sang {moi['ten_khach'] or 'khách khác'}: {ly}"
    # Lệnh bù đúng theo trạng thái tờ cũ: còn chờ xác nhận (tệp Drive tự về) ⇒ Từ
    # chối tệp; đã hợp lệ (tải tay / đã gửi) ⇒ Thu hồi. Không sửa dòng cũ.
    if goc["xac_nhan_trang_thai"] == "CHO_XAC_NHAN":
        await svc.xac_nhan_tep(
            identity=identity, tep_id=cu["tep_id"], trang_thai="TU_CHOI", ly_do=cau
        )
    else:
        await svc.thu_hoi_tep(identity=identity, tep_id=cu["tep_id"], ly_do=cau)
    await pool.execute(
        "UPDATE drive_tep SET tep_ket_qua_id = $3::uuid"
        " WHERE clinic_id = $1::uuid AND tep_ket_qua_id = $2::uuid",
        identity.clinic_id,
        cu["tep_id"],
        kq["id"],
    )
    await _phat(pool, identity, "thu_hoi", cu)
    await _phat(pool, identity, "den", moi)
    return {"tep_id": kq["id"]}
