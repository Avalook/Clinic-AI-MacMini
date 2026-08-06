"""Nguồn dữ liệu cho màn hình TV phòng chờ.

HAI RÀNG BUỘC, VÀ CẢ HAI ĐỀU KHÔNG ĐƯỢC ĐÁNH ĐỔI.

① KHÔNG MỘT MẨU DANH TÍNH NÀO RỜI MÁY CHỦ. Màn này treo ở phòng chờ. Thứ gì
   endpoint trả về là thứ đi thẳng vào payload trình duyệt, nên "không hiển thị"
   là chưa đủ — phải KHÔNG TẢI VỀ. Trang cũ đã giữ đúng nguyên tắc này (chú
   thích trong `app/display/page.tsx` nói rõ), và nó phải sống tiếp qua lần đổi
   này. Vì thế service trả về số thứ tự, khu vực, thứ tự gọi — không tên, không
   mã bệnh nhân, không số điện thoại, không cả tên bác sĩ.

② THỨ TỰ PHẢI GIỐNG HỆT BẢNG CỦA NHÂN VIÊN. Trước đây tivi xếp bằng
   `slot_start` thuần, trong khi Lễ tân và bác sĩ xếp theo luật gọi. Hai bảng
   nói hai thứ tự khác nhau, và người ngồi chờ đọc bảng nào cũng thấy có lý —
   cho tới lúc bị gọi sai lượt. Ở đây dùng CHÍNH `explain_queue`, qua cùng một
   hàm dựng hàng với ba bảng kia.

Và một thứ mà bảng nội bộ không cần nhưng tivi thì cần: LÝ DO. Khi một người có
hẹn được đẩy lên trên một người vãng lai đã ngồi đó trước, phòng chờ xứng đáng
được biết vì sao — nếu không, bảng số trông như một trò tuỳ hứng.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.services.queue_order import (
    REASON_DAT_TRUOC_DUNG_GIO,
    QueueDecision,
)
from clinicai.services.queue_rows import thu_tu_goi_theo_ngay

logger = structlog.get_logger()

MAX_ROWS = 200

# Câu hiện dưới số của người được đẩy lên. Viết ở backend, không ở TSX: nó phải
# khớp CHÍNH XÁC với lý do mà luật đưa ra, và một chuỗi nằm cạnh luật thì khó
# lệch hơn một chuỗi nằm cách đó hai tầng.
CHU_THICH_DAY_LEN = "Được ưu tiên vì đã đặt lịch trước"

_SQL = (
    """
SELECT a.id,
       a.slot_start,
       a.status,
       a.queue_number,
       a.booking_channel,
       a.doctor_id,
       st.name AS service_name,
       v.checked_in_at,
       v.status AS visit_status,
       cap.slot_minutes
  FROM appointment a
  LEFT JOIN service_type st ON st.id = a.service_type_id
  LEFT JOIN LATERAL (
      SELECT vi.checked_in_at, vi.status FROM visit vi
       WHERE vi.appointment_id = a.id AND vi.clinic_id = $1::uuid
       ORDER BY vi.checked_in_at DESC NULLS LAST
       LIMIT 1
  ) v ON TRUE
  LEFT JOIN LATERAL public.resolve_effective_cap(
      $1::uuid, a.doctor_id, a.slot_start
  ) cap ON TRUE
 WHERE a.clinic_id = $1::uuid
   AND a.slot_start >= $2
   AND a.slot_start <  $3
   AND a.status <> ALL (ARRAY['CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'])
 ORDER BY a.slot_start, a.id
 LIMIT %d
"""
    % MAX_ROWS
)

_ZONE_SQL = """
SELECT settings -> 'display' -> 'zones' AS zones
  FROM clinic
 WHERE id = $1::uuid
"""


class DisplayBoardService:
    """Bảng gọi số của màn hình phòng chờ."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def board(self, *, clinic_id: str, start: Any, end: Any) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_SQL, clinic_id, start, end)
            zone_row = await conn.fetchrow(_ZONE_SQL, clinic_id)

        quyet_dinh = thu_tu_goi_theo_ngay(rows)
        zones = _doc_zones(zone_row)

        muc: list[dict[str, Any]] = []
        for r in rows:
            d = quyet_dinh.get(str(r["id"]))
            muc.append(_mot_dong(r, d, zones))
        muc.sort(key=lambda m: (m["call_order"] is None, m["call_order"] or 0))

        logger.info("display_board", clinic_id=clinic_id, rows=len(muc))
        return {"zones": zones, "items": muc}


def _doc_zones(row: asyncpg.Record | None) -> list[dict[str, Any]]:
    """Khu vực lấy từ cấu hình phòng khám, không viết cứng trong TSX.

    Trống thì trả danh sách rỗng chứ không đoán: một bảng trắng khiến người ta
    đi sửa cấu hình, còn một bảng đoán sai khiến người bệnh đi nhầm phòng.
    """
    if row is None or row["zones"] is None:
        return []
    raw = row["zones"]
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    return list(parsed) if isinstance(parsed, list) else []


# Luật đoán khu MẶC ĐỊNH — bê nguyên `zoneOf()` cũ trong DisplayBoard.tsx.
#
# Cấu hình `clinic.settings->display->zones` trên máy chủ thật hôm nay CHỈ có
# key/label/prefix, KHÔNG có từ khoá khớp. Nếu chỉ đọc cấu hình thì mọi dòng
# rơi vào "không thuộc khu nào" và tivi trắng trơn — một cách im lặng để làm
# hỏng màn hình duy nhất mà người bệnh nhìn vào.
#
# Nên: cấu hình có khai `match` thì theo cấu hình; không khai thì theo luật này.
_KHU_MAC_DINH: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sa", ("siêu âm", "sieu am")),
    ("xn", ("xét nghiệm", "xet nghiem")),
)
_KHU_MAC_DINH_CUOI = "kham"


def _khu_vuc(service_name: str | None, zones: list[dict[str, Any]]) -> str | None:
    """Dịch vụ → khu vực.

    Khớp theo từ khoá phòng khám khai trong cấu hình nếu có — thêm một khu mới
    thì không phải sửa mã và dựng lại ứng dụng. Không khai thì rơi về đúng luật
    mà màn hình vẫn dùng từ trước tới nay.
    """
    ten = (service_name or "").lower()

    co_khai = False
    for z in zones:
        tu_khoa = z.get("match") or []
        if tu_khoa:
            co_khai = True
        for tu in tu_khoa:
            if str(tu).lower() in ten:
                return str(z.get("key"))
    if co_khai:
        return None

    ho = _KHU_MAC_DINH_CUOI
    for khoa, tu_khoa in _KHU_MAC_DINH:
        if any(tu in ten for tu in tu_khoa):
            ho = khoa
            break
    return _khop_vao_khu_that(ho, zones)


def _khop_vao_khu_that(ho: str, zones: list[dict[str, Any]]) -> str:
    """Đưa "họ khu" về đúng một khoá CÓ THẬT trong cấu hình.

    LỖI ĐÃ SỬA. Luật đoán trả về `"sa"` cho siêu âm, còn cấu hình khai ba khu
    `sa1`, `sa2`, `sa3`. Phép so ở màn hình là `zoneOf(a).startsWith(z.key)` —
    tức `"sa".startsWith("sa1")`, LUÔN SAI. Nghĩa là bệnh nhân siêu âm chưa bao
    giờ xuất hiện trên bảng gọi số của phòng chờ, và không có lỗi nào để thấy:
    ba ô SA chỉ hiện dấu gạch ngang, y như lúc thật sự chưa có ai.

    Ở đây khớp đúng chiều: khoá trùng hẳn thì lấy, không thì lấy khu ĐẦU TIÊN
    có khoá bắt đầu bằng họ ấy. Ba buồng siêu âm mà chỉ dồn về `sa1` là chưa
    hoàn hảo — nhưng "hiện ở một chỗ" đúng hơn "không hiện ở đâu", và việc chia
    buồng nào cho ai là dữ liệu điều phối chứ không phải phép đoán từ tên dịch
    vụ.
    """
    khoa = [str(z.get("key")) for z in zones if z.get("key")]
    if ho in khoa:
        return ho
    for k in khoa:
        if k.startswith(ho):
            return k
    return ho


def _mot_dong(
    r: asyncpg.Record, d: QueueDecision | None, zones: list[dict[str, Any]]
) -> dict[str, Any]:
    """CHỈ những trường không định danh — xem ràng buộc ① ở đầu module."""
    promoted = bool(d and d.promoted and d.call_reason == REASON_DAT_TRUOC_DUNG_GIO)
    return {
        "queue_number": r["queue_number"],
        "zone_key": _khu_vuc(r["service_name"], zones),
        "call_order": d.call_order if d else None,
        "call_reason": d.call_reason if d else None,
        # "Đang gọi" đọc từ TRẠNG THÁI LƯỢT KHÁM, không từ trạng thái lịch hẹn.
        # Bản cũ lọc `status === "IN_PROGRESS"` trên appointment — một giá trị
        # mà ràng buộc CHECK của bảng đó KHÔNG cho phép tồn tại. Tức là nhánh
        # ấy chưa bao giờ khớp dòng nào.
        "is_current": r["visit_status"] == "IN_PROGRESS",
        # "Còn đang chờ" = ĐÃ ĐẾN và CHƯA KHÁM XONG.
        #
        # Bỏ vế thứ hai là để người đã khám xong nằm lại trên bảng gọi số mãi
        # mãi — bảng cũ tránh được điều đó bằng cách lọc status == 'CHECKED_IN',
        # và bản đầu của file này đánh mất phép lọc ấy. Chỉ thấy khi nhìn bảng
        # thật: một số đã khám xong từ sáng vẫn đứng đó.
        "waiting": r["checked_in_at"] is not None and r["status"] != "COMPLETED",
        "promoted": promoted,
        "promoted_note": CHU_THICH_DAY_LEN if promoted else None,
    }
