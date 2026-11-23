"""Ghi NHẬT KÝ XEM HỒ SƠ cho các cửa đọc hồ sơ khách — khai ở MỘT chỗ (24/11/2026).

Vì sao một bảng khai thay vì một dòng trong từng router: router đọc hồ sơ phần lớn
đã quá trần kích thước (luật 5) — thêm tham số + dòng gọi ở mỗi cửa là làm chúng dài
thêm. Ở đây: `CUA_XEM` (mẫu đường dẫn → loại hồ sơ + tham số mang id) và một
dependency CHUNG `ghi_xem_sau_khi_doc` gắn vào `CUA_NOI_BO` (`api/cua_noi_bo.py`),
tức mọi router nội bộ. Cửa không có trong bảng → không làm gì (một lần tra dict).

Chỉ ghi khi cửa đọc THÀNH CÔNG: đây là dependency `yield`; từ FastAPI 0.106 lỗi của
cửa (403, 404, 500) được ném vào dependency tại `yield`, nên đoạn sau `yield` chỉ
chạy khi cửa đã trả xong, trước khi gửi phản hồi
(https://fastapi.tiangolo.com/advanced/advanced-dependencies/).

Thêm một cửa = thêm một dòng vào `CUA_XEM`. Test `test_cua_xem_khop_route_that`
đỏ khi mẫu đường dẫn ở đây không còn khớp route thật (đổi tên cửa mà quên sửa).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

import asyncpg
import structlog
from fastapi import Depends, Request

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services import kho_loi, nhat_ky_xem_ho_so

logger = structlog.get_logger()

#: Ghi một dòng nhật ký quá ngần này giây → bỏ, vào kho lỗi (người đọc không chờ).
TRAN_GIAY_GHI = 2.0


@dataclass(frozen=True)
class CuaXem:
    #: loại hồ sơ — khoá của `nhat_ky_xem_ho_so.LOAI`.
    loai: str
    #: "khach" (id khách có sẵn) hoặc một khoá tra của `_SQL_TRA_KHACH`.
    khoa: str
    #: tên tham số đường dẫn / truy vấn mang id.
    tham_so: str


_V = "GET /api/v1"
_K, _VI = "khach", "visit_id"

CUA_XEM: dict[str, CuaXem] = {
    f"{_V}/clinical-records/doc": CuaXem("phieu_kham", _K, "patient_id"),
    f"{_V}/clinical-records/in-theo-lich/{{appointment_id}}": CuaXem(
        "ban_in", "appointment_id", "appointment_id"
    ),
    f"{_V}/clinical-forms": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/clinical-forms/history": CuaXem("lich_su_kham", _K, "clinic_patient_id"),
    f"{_V}/phieu-kham/luot/{{visit_id}}/dau-phieu": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/phieu-kham/luot/{{visit_id}}/ket-qua-chi-dinh": CuaXem("ket_qua", _VI, _VI),
    f"{_V}/phieu-kham/luot/{{visit_id}}/phieu": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/phieu-kham/luot/{{visit_id}}/lich-su": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/phieu-kham/luot/{{visit_id}}/don-thuoc": CuaXem("don_thuoc", _VI, _VI),
    f"{_V}/ho-so-khach/{{clinic_patient_id}}/hanh-chinh": CuaXem(
        "ho_so_khach", _K, "clinic_patient_id"
    ),
    f"{_V}/ho-so-khach/{{clinic_patient_id}}/lich-su-lam-sang": CuaXem(
        "lich_su_kham", _K, "clinic_patient_id"
    ),
    f"{_V}/ho-so-kham/lich-su": CuaXem("lich_su_kham", _K, "clinic_patient_id"),
    f"{_V}/ho-so-kham/tom-tat-kham": CuaXem("ban_in", _K, "clinic_patient_id"),
    f"{_V}/ho-so-kham/{{visit_id}}/dieu-tri": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/ho-so-kham/{{visit_id}}/ghi-chu": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/patients/{{id:uuid}}": CuaXem("ho_so_khach", _K, "id"),
    f"{_V}/patients/{{id:uuid}}/lich-su-notion": CuaXem("lich_su_kham", _K, "id"),
    f"{_V}/lich-su-notion/luot/{{luot_id:uuid}}": CuaXem(
        "phieu_kham", "luot_cu_id", "luot_id"
    ),
    f"{_V}/lich-su-notion/xet-nghiem/{{xn_id:uuid}}/tep/{{i}}": CuaXem(
        "tep_ket_qua", "xn_cu_id", "xn_id"
    ),
    f"{_V}/cskh/ho-so-kham/{{appointment_id}}": CuaXem(
        "phieu_kham", "appointment_id", "appointment_id"
    ),
    f"{_V}/cskh/ket-qua/{{clinic_patient_id}}": CuaXem(
        "ket_qua", _K, "clinic_patient_id"
    ),
    f"{_V}/cskh/ket-qua/tep/{{tep_id}}/noi-dung": CuaXem(
        "tep_ket_qua", "tep_id", "tep_id"
    ),
    f"{_V}/phieu/xem/{{service_order_id}}": CuaXem(
        "ket_qua", "service_order_id", "service_order_id"
    ),
    f"{_V}/phieu/in/{{service_order_id}}": CuaXem(
        "ban_in", "service_order_id", "service_order_id"
    ),
    f"{_V}/thai-ky": CuaXem("phieu_kham", _K, "clinic_patient_id"),
    f"{_V}/xem-luot/{{visit_id}}": CuaXem("lich_su_kham", _VI, _VI),
    f"{_V}/quay-thuoc/luot/{{visit_id}}": CuaXem("don_thuoc", _VI, _VI),
    f"{_V}/ultrasound/image": CuaXem("tep_ket_qua", "anh_sieu_am", "key"),
    f"{_V}/lieu-trinh/theo-luot/{{visit_id}}": CuaXem("phieu_kham", _VI, _VI),
    f"{_V}/lieu-trinh/theo-khach/{{clinic_patient_id}}": CuaXem(
        "lich_su_kham", _K, "clinic_patient_id"
    ),
    f"{_V}/pharmacy/ban-le/{{visit_id}}": CuaXem("don_thuoc", _VI, _VI),
    f"{_V}/pharmacy/ban-le/lich-su-don": CuaXem("don_thuoc", _K, "clinic_patient_id"),
}


async def ghi_an_toan(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    cua: str,
    khai: CuaXem,
    gia_tri: str,
) -> None:
    """Ghi một lượt xem; KHÔNG BAO GIỜ ném — lỗi vào kho lỗi (/ops "Lỗi & cảnh
    báo"). Bác sĩ đang khám mà mở bệnh án ra 500 vì nhật ký hỏng là tệ hơn mất
    một dòng nhật ký."""
    try:
        # Trần giờ: đoạn này chạy TRƯỚC khi phản hồi rời máy chủ; bể kết nối đầy
        # (30–31/10) thì không được bắt người đọc chờ thêm một lần acquire.
        await asyncio.wait_for(
            nhat_ky_xem_ho_so.ghi_luot_xem(
                pool,
                clinic_id=identity.clinic_id,
                staff_id=identity.staff_id,
                vai=identity.vai_goc.value,
                loai=khai.loai,
                cua=cua,
                khach=gia_tri if khai.khoa == "khach" else None,
                tra={} if khai.khoa == "khach" else {khai.khoa: gia_tri},
            ),
            timeout=TRAN_GIAY_GHI,
        )
    except Exception as exc:  # noqa: BLE001 — nhật ký hỏng không chặn người đọc
        logger.error("nhat_ky_xem_ho_so_loi", cua=cua, loai=khai.loai)
        await kho_loi.ghi_loi(pool, nguon="api", vi_tri=f"nhat-ky-xem {cua}", exc=exc)


def _pool(request: Request) -> asyncpg.Pool | None:
    """Pool của lượt gọi, lấy y như FastAPI giải `Depends(get_db_pool)` (bản thay
    trong `dependency_overrides` trước, không thì `app.state.db_pool`).

    KHÔNG khai `Depends(get_db_pool)` ở dependency chung: nó gắn vào MỌI router nội
    bộ, nên cửa không cần DB (hay bài kiểm không dựng pool) sẽ hỏng theo — chỉ lấy
    pool khi cửa nằm trong `CUA_XEM`."""
    thay = request.app.dependency_overrides.get(get_db_pool)
    pool = thay() if thay is not None else getattr(request.app.state, "db_pool", None)
    return pool if isinstance(pool, asyncpg.Pool) else None


async def ghi_xem_sau_khi_doc(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
) -> AsyncIterator[None]:
    """Dependency chung: cửa đọc trong `CUA_XEM` trả THÀNH CÔNG → một dòng nhật ký.

    Cửa = MẪU đường dẫn (không đường thật — đường thật có thể mang tham số tìm
    kiếm). Danh tính lấy cùng `get_current_identity` mà `runaway_guard` đã giải
    (FastAPI nhớ kết quả trong một lượt gọi — không giải hai lần)."""
    yield  # cửa lỗi → lỗi ném vào đây, dòng dưới không chạy
    await _ghi_neu_co_khai(request, identity)


async def _ghi_neu_co_khai(request: Request, identity: StaffIdentity) -> None:
    route = request.scope.get("route")
    cua = f"{request.method} {getattr(route, 'path', '')}"
    khai = CUA_XEM.get(cua)
    if khai is None:
        return
    gia_tri = request.path_params.get(khai.tham_so) or request.query_params.get(
        khai.tham_so
    )
    pool = _pool(request)
    if gia_tri and pool is not None:
        await ghi_an_toan(pool, identity, cua, khai, str(gia_tri))


__all__ = ["CUA_XEM", "CuaXem", "ghi_an_toan", "ghi_xem_sau_khi_doc"]
