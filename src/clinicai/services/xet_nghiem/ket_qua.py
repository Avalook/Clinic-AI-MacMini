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

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
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

#: Trần ô lọc đối tác (phòng khám có vài đối tác; chạm trần ⇒ cảnh báo log).
TRAN_DOI_TAC = 100


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


#: Việc bàn mới của khách — theo lượt (lịch hẹn) nếu có, không thì mọi lượt của khách.
#: $1 clinic · $2 khách · $3 lịch hẹn (NULL = theo khách).
_VIEC_CUA_KHACH_SQL = f"""
SELECT x.service_order_id::text
  FROM xet_nghiem_viec x
  JOIN service_order o ON o.id = x.service_order_id AND o.clinic_id = x.clinic_id
  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
 WHERE x.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
   AND v.appointment_id = $3::uuid
 ORDER BY x.tao_luc DESC
 LIMIT {TRAN_DOI_TAC}
"""


async def gui_theo_cskh(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    clinic_patient_id: str,
    appointment_id: str | None,
    kenh: str,
    hom_nay: date,
) -> int:
    """CSKH ghi sổ "đã trả kết quả" (TRA_KQ) ⇒ ghi "đã gửi" cho MỌI tờ còn hiệu lực,
    chưa gửi của việc bàn mới thuộc lượt đó, qua ĐÚNG lõi nút "Gửi khách"
    (`dung_nguoi_gui`). Trả số tờ đã ghi gửi.

    Gọi SAU khi dòng sổ CSKH đã commit; mọi lỗi ở đây chỉ ghi log, KHÔNG ném — sổ
    CSKH là bằng chứng chính, bàn XN bấm "Gửi khách" lại được. Việc không đủ điều kiện
    (`nut.gui` false: chưa có tờ, tờ đã gửi) thì bỏ qua.
    Kênh của sổ không phải kênh gửi tệp (GOI…) ⇒ TRUC_TIEP.
    CHƯA LÀM: hoàn tác dòng sổ CSKH không thu hồi mốc gửi ở đây (thu hồi = nút Thu hồi
    trên bàn XN, có lý do).
    """
    # Không gắn lịch hẹn ⇒ KHÔNG đánh dấu gì: theo khách sẽ ghi "đã gửi" cho tờ của
    # LƯỢT KHÁC (gửi nhầm là lỗi nặng nhất của tính năng này).
    if not appointment_id:
        return 0
    kenh_gui = kenh if kenh in KENH_GUI_HOP_LE else "TRUC_TIEP"
    n = 0
    try:
        ids = [
            r[0]
            for r in await pool.fetch(
                _VIEC_CUA_KHACH_SQL,
                identity.clinic_id,
                clinic_patient_id,
                appointment_id,
            )
        ]
        canh_bao_neu_day(
            "xet_nghiem_viec_cskh", len(ids), TRAN_DOI_TAC, clinic_id=identity.clinic_id
        )
        if not ids:
            return 0
        async with pool.acquire() as conn:
            ds = await doc_viec(
                conn, identity.clinic_id, hom_nay=hom_nay, order_ids=ids
            )
        for v in ds:
            if not v["nut"]["gui"] or not v["tep_id"]:
                continue
            try:
                await dung_nguoi_gui(
                    pool,
                    identity,
                    {"order_id": v["order_id"], "kenh": kenh_gui},
                    hom_nay,
                )
                n += 1
            except (ConflictError, NotFoundError) as e:
                # Tranh chấp (người khác vừa gửi/thu hồi) — bỏ qua việc này.
                logger.warning(
                    "xet_nghiem_gui_theo_cskh_bo_qua",
                    order_id=v["order_id"],
                    loi=str(e),
                )
    except Exception:  # noqa: BLE001 — sổ CSKH đã commit; bàn XN gửi lại được
        logger.exception(
            "xet_nghiem_gui_theo_cskh_loi", clinic_patient_id=clinic_patient_id
        )
    return n


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
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    hom_nay: date,
    tu_ngay: date | None,
    ngay_xem: date | None = None,
) -> dict[str, Any]:
    """Cả bàn: việc (xếp việc cần làm trước lên đầu), nhóm khách theo ngày chỉ định,
    chip lọc, và cờ `quan_ly` (màn hiện tab Tiền thu hộ + Cài đặt). `ngay_xem`: ngày
    màn đang xem (có thể cũ hơn cửa sổ) — nạp thêm đúng ngày đó."""
    async with pool.acquire() as conn:
        quan_ly = bool(await can(conn, identity, QUYEN_QUAN_LY))
        viec = sap_xep(
            await doc_viec(
                conn,
                identity.clinic_id,
                hom_nay=hom_nay,
                tu_ngay=tu_ngay,
                ngay_xem=ngay_xem,
            )
        )
        # Ô lọc đối tác: MỌI đối tác còn hoạt động (đối tác mới chưa có việc vẫn chọn
        # được) + đối tác đã ngưng mà còn việc trên bàn (việc dở không biến mất).
        doi_tac = await conn.fetch(
            "SELECT id::text AS id, ten FROM doi_tac"
            " WHERE clinic_id = $1::uuid"
            "   AND (ngung_luc IS NULL OR id = ANY($2::uuid[]))"
            f" ORDER BY lower(ten) LIMIT {TRAN_DOI_TAC}",
            identity.clinic_id,
            list({v["doi_tac_id"] for v in viec}),
        )
        canh_bao_neu_day(
            "doi_tac", len(doi_tac), TRAN_DOI_TAC, clinic_id=identity.clinic_id
        )
    return {
        "viec": viec,
        "khach": nhom_khach(viec),
        "loc": bo_loc(),
        "quan_ly": quan_ly,
        "doi_tac": [dict(r) for r in doi_tac],
    }
