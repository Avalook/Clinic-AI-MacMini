"""Kết quả về (tải tay) + "Đúng người, gửi" + thu hồi (kế hoạch 3.3, 3.4, 5c).

* **Tải tay**: nhân viên chọn ĐÚNG việc rồi tải ⇒ đi đường tệp đối tác
  (`tai_len(la_tep_doi_tac=True)`): xác nhận cùng bước (cờ XAC_NHAN_TEP_DOI_TAC tắt
  ⇒ HOP_LE ngay), báo bác sĩ + CSKH qua `bao_ket_qua_ve` như mọi tệp. Không tạo bảng
  tệp thứ hai.
* **Đúng người, gửi**: CHỈ GHI NHẬN đã gửi (Zalo/Pancake tính sau), kênh bắt buộc.
  Tệp còn CHO_XAC_NHAN (chặng 4 — Drive) ⇒ xác nhận HOP_LE trước rồi ghi gửi.
  LUẬT CẢN (luật 5): kế hoạch 3.4 muốn MỘT giao dịch, nhưng `xac_nhan_tep` và
  `danh_dau_da_gui` mỗi hàm tự mở giao dịch trong `tep_ket_qua_service.py` (1.900+
  dòng, quá trần). Tách lõi để chung giao dịch là việc riêng (chặng 4, cùng lúc
  Drive cần nó). Hôm nay: hai bước nối tiếp — bước 2 lỗi thì tệp đã HOP_LE, chưa gửi,
  bấm lại là xong (không sai lệch dữ liệu).
* **Thu hồi**: tệp HOP_LE ⇒ THU_HOI (lý do), mốc đã gửi GIỮ NGUYÊN trong lịch sử.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import XetNghiemViec
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.nhan_tep_luong import TepDaNhan
from clinicai.services.tep_ket_qua_service import KENH_GUI_HOP_LE, TepKetQuaService
from clinicai.services.xet_nghiem.ban import bo_loc, doc_viec, sap_xep
from clinicai.services.xet_nghiem.doi_tac import QUYEN_QUAN_LY
from clinicai.services.xet_nghiem.hanh_trinh import nhom_khach
from clinicai.services.xet_nghiem.mau import _mot_viec
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do

logger = structlog.get_logger()


async def _phat(
    pool: asyncpg.Pool, identity: StaffIdentity, ten_ok: str, v: dict[str, Any]
) -> None:
    """Ghi sự kiện SAU khi lệnh tệp đã commit (lệnh tệp tự mở giao dịch). Lệnh tệp
    đã xong thật ⇒ phát lỗi KHÔNG được thành 500 (bấm lại sẽ ra tệp trùng / "đã gửi
    rồi"): ghi log lỗi, không ném. Chuông vẫn đi qua `result_file.*` của lệnh tệp."""
    payload = XetNghiemViec(visit_id=v["visit_id"], service_order_id=v["order_id"])
    kw: dict[str, Any] = {
        "clinic_id": identity.clinic_id,
        "aggregate_id": v["order_id"],
        "payload": payload,
        "boi": nguoi(identity),
        "correlation_id": v["visit_id"],
    }
    try:
        async with pool.acquire() as conn, conn.transaction():
            if ten_ok == "den":
                await emit_event(conn, ten="lab.result_arrived", **kw)
            elif ten_ok == "gui":
                await emit_event(conn, ten="lab.result_sent", **kw)
            elif ten_ok == "thu_hoi":
                await emit_event(conn, ten="lab.result_rejected", **kw)
            else:
                raise ValueError(f"loại sự kiện kết quả lạ: {ten_ok}")
    except Exception:  # noqa: BLE001 — lệnh chính đã commit; chỉ mất vết sự kiện
        logger.exception(
            "xet_nghiem_phat_su_kien_loi", loai=ten_ok, order_id=v["order_id"]
        )


async def _viec(
    pool: asyncpg.Pool, identity: StaffIdentity, order_id: object, hom_nay: date
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        return await _mot_viec(conn, identity, order_id, hom_nay)


async def tai_tay(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    order_id: object,
    hom_nay: date,
    *,
    tep: TepDaNhan | None = None,
    data: bytes | None = None,
    ten: str | None = None,
) -> dict[str, Any]:
    """`tep` = thân multipart đã chảy vào kho (cửa HTTP); `data` = bytes (test)."""
    v = await _viec(pool, identity, order_id, hom_nay)
    if not v["nut"]["tai_ket_qua"]:
        raise ConflictError(
            f"Chưa tải kết quả được cho việc đang «{v['trang_thai']['nhan']}»"
            " (cần đã lấy mẫu)."
        )
    if not v["clinic_patient_id"]:
        raise ConflictError("Việc này chưa gắn khách — báo kỹ thuật.")
    kq = await TepKetQuaService(pool).tai_len(
        identity=identity,
        clinic_patient_id=v["clinic_patient_id"],
        tep_da_nhan=tep,
        data=data,
        ten_hien_thi=tep.ten if tep is not None else ten,
        service_order_id=v["order_id"],
        la_tep_doi_tac=True,
    )
    await _phat(pool, identity, "den", v)
    return kq


async def dung_nguoi_gui(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any], hom_nay: date
) -> None:
    kenh = str(data.get("kenh") or "").strip().upper()
    if kenh not in KENH_GUI_HOP_LE:
        raise ValidationError("Chọn kênh đã gửi (Zalo, SMS, trực tiếp, email).")
    v = await _viec(pool, identity, data.get("order_id"), hom_nay)
    if not v["nut"]["gui"] or not v["tep_id"]:
        raise ConflictError("Không có kết quả mới để gửi — tải lại màn.")
    svc = TepKetQuaService(pool)
    xn = await pool.fetchval(
        "SELECT xac_nhan_trang_thai FROM public.tep_ket_qua"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        identity.clinic_id,
        v["tep_id"],
    )
    if xn == "CHO_XAC_NHAN":
        await svc.xac_nhan_tep(
            identity=identity, tep_id=v["tep_id"], trang_thai="HOP_LE"
        )
    await svc.danh_dau_da_gui(identity=identity, tep_id=v["tep_id"], kenh=kenh)
    await _phat(pool, identity, "gui", v)


async def thu_hoi(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any], hom_nay: date
) -> None:
    ly = doc_ly_do(data.get("ly_do"))
    v = await _viec(pool, identity, data.get("order_id"), hom_nay)
    if not v["tep_id"]:
        raise ConflictError("Việc này chưa có tệp kết quả để thu hồi.")
    await TepKetQuaService(pool).thu_hoi_tep(
        identity=identity, tep_id=v["tep_id"], ly_do=ly
    )
    await _phat(pool, identity, "thu_hoi", v)


async def ban(
    pool: asyncpg.Pool, identity: StaffIdentity, hom_nay: date, tu_ngay: date | None
) -> dict[str, Any]:
    """Cả bàn: việc (xếp việc cần làm trước lên đầu), nhóm khách theo ngày chỉ định,
    chip lọc, và cờ `quan_ly` (màn hiện tab Tiền thu hộ + Cài đặt)."""
    async with pool.acquire() as conn:
        quan_ly = bool(await can(conn, identity, QUYEN_QUAN_LY))
        viec = sap_xep(
            await doc_viec(conn, identity.clinic_id, hom_nay=hom_nay, tu_ngay=tu_ngay)
        )
        # Ô lọc đối tác: MỌI đối tác còn hoạt động (đối tác mới chưa có việc vẫn chọn
        # được) + đối tác đã ngưng mà còn việc trên bàn (việc dở không biến mất).
        doi_tac = await conn.fetch(
            "SELECT id::text AS id, ten FROM doi_tac"
            " WHERE clinic_id = $1::uuid"
            "   AND (ngung_luc IS NULL OR id = ANY($2::uuid[]))"
            " ORDER BY lower(ten) LIMIT 100",
            identity.clinic_id,
            list({v["doi_tac_id"] for v in viec}),
        )
    return {
        "viec": viec,
        "khach": nhom_khach(viec),
        "loc": bo_loc(),
        "quan_ly": quan_ly,
        "doi_tac": [dict(r) for r in doi_tac],
    }
