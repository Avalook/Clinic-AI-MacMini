"""Đọc một form Nam khoa đã nhập và trả về những gì MÁY tính được.

Bốn phép tính đã có ở `andrology_service` (thuần, có test) nhưng CHƯA AI GỌI.
File này là chỗ nối: nhận `form_data` phẳng từ màn hình, đọc ngưỡng WHO đang
hiệu lực từ bảng, và trả về cờ + gợi ý cho bác sĩ đọc.

RANH GIỚI GIỮ NGUYÊN NHƯ Ở `andrology_service`: mọi thứ đây trả về là GỢI Ý,
không phải chẩn đoán và không phải chỉ định. Notion §13 của cả năm node khám đều
cấm hệ thống tự kết luận hoặc tự tạo chỉ định. Cụ thể:

  · cờ tinh dịch đồ nói "dưới ngưỡng WHO 2021", không nói "vô sinh";
  · gợi ý xét nghiệm di truyền kèm LÝ DO, và không hàm nào ở đây gọi
    `order_services()` — bác sĩ tự tick;
  · BMI là một phép chia, không phải một nhận định.

VÌ SAO TÍNH Ở BACKEND CHỨ KHÔNG Ở TSX (spec §7.1, §7.3). Ngưỡng WHO đã đổi qua
ba ấn bản. Nhốt số vào trình duyệt thì mỗi lần WHO đổi phải sửa code, và mất
luôn câu trả lời cho "kết quả năm ngoái được đọc theo ngưỡng nào" — bảng
`semen_reference_range` giữ được điều đó, biến hằng số trong TSX thì không.

LẦN 2 THẮNG LẦN 1. AUA yêu cầu làm lại tinh dịch đồ sau ~1 tháng khi kết quả
bất thường, nên khi có cả hai lần thì lần 2 là lần mới nhất. Đọc lần 1 khi đã
có lần 2 là đọc một kết quả đã bị thay thế.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity
from clinicai.services.andrology_service import (
    SemenRange,
    compute_bmi,
    flag_semen,
    suggest_genetic_tests,
)

logger = structlog.get_logger()

#: Khoá trong form (không hậu tố lần) → tên tham số ở `semen_reference_range`.
#: Chỉ những thông số CÓ ngưỡng dưới mới nằm ở đây; pH, NP, IM và bạch cầu đọc
#: theo cách khác nên không gắn cờ tự động.
_TDD_MAP: dict[str, str] = {
    "tdd_the_tich": "volume_ml",
    "tdd_nong_do": "concentration_m_ml",
    "tdd_tong_so": "total_count_m",
    "tdd_di_dong_tong": "total_motility_pct",
    "tdd_pr": "progressive_pct",
    "tdd_song": "vitality_pct",
    "tdd_kruger": "normal_forms_pct",
}

_RANGE_SQL = """
SELECT DISTINCT ON (parameter)
       parameter, label, lower_limit, unit, source
  FROM public.semen_reference_range
 WHERE clinic_id = $1::uuid AND effective_from <= current_date
 ORDER BY parameter, effective_from DESC
"""


def _so(value: Any) -> float | None:
    """Một số, hoặc None — chuỗi rỗng và chữ đều thành None.

    Màn hình gửi chuỗi rỗng cho ô chưa nhập. Đổi nó thành 0 sẽ gắn cờ "dưới
    ngưỡng" cho một xét nghiệm chưa làm.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _lan_moi_nhat(form: dict[str, Any], key: str) -> float | None:
    """Giá trị của lần 2 nếu có, không thì lần 1.

    `is not None` CHỨ KHÔNG PHẢI `or`. Số 0 là falsy trong Python, nên
    `_so(l2) or _so(l1)` sẽ bỏ qua lần 2 khi lần 2 bằng 0 — và 0 ở đây là KHÔNG
    THẤY TINH TRÙNG, kết quả quan trọng nhất của cả phiếu.

    Đã xảy ra thật: chạy thử một ca lần 1 = 3, lần 2 = 0, màn hình đọc ra 3 và
    gợi ý "thiểu tinh nặng" thay vì "không thấy tinh trùng trong mẫu" — hai
    hướng chẩn đoán khác hẳn nhau.
    """
    lan2 = _so(form.get(f"{key}_l2"))
    return lan2 if lan2 is not None else _so(form.get(f"{key}_l1"))


def semen_params(form: dict[str, Any]) -> dict[str, float | Decimal | None]:
    """Đổi form phẳng thành bộ tham số mà `flag_semen` đọc được."""
    return {
        param: _lan_moi_nhat(form, key)
        for key, param in _TDD_MAP.items()
        if _lan_moi_nhat(form, key) is not None
    }


def vas_palpable(form: dict[str, Any]) -> bool | None:
    """Có sờ thấy ống dẫn tinh không — None khi chưa khám đủ hai bên.

    `False` chỉ khi KHÔNG sờ thấy CẢ HAI BÊN: bất sản ống dẫn tinh một bên
    không hướng tới CBAVD, và gợi ý CFTR dựa trên một bên là gợi ý sai.
    """
    t = form.get("kls_ong_dan_tinh_t")
    p = form.get("kls_ong_dan_tinh_p")
    if not t or not p:
        return None
    if t == "khong_so_thay" and p == "khong_so_thay":
        return False
    return True


def larger_testis_volume(form: dict[str, Any]) -> float | None:
    """Thể tích tinh hoàn để suy luận — lấy bên LỚN HƠN.

    Bên lớn hơn là bên còn chức năng tốt hơn, và câu hỏi "sinh tinh có bảo tồn
    không" hỏi về bên tốt nhất. Lấy trung bình sẽ kéo một bên teo làm chìm cả
    hai, và biến một ca hướng tắc nghẽn thành hướng suy sinh tinh.
    """
    v = [
        x
        for x in (
            _so(form.get("kls_th_the_tich_t")),
            _so(form.get("kls_th_the_tich_p")),
        )
        if x is not None
    ]
    return max(v) if v else None


class AndrologyReviewService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ranges(self, *, identity: StaffIdentity) -> list[SemenRange]:
        rows = await self._pool.fetch(_RANGE_SQL, identity.clinic_id)
        return [
            SemenRange(
                parameter=r["parameter"],
                label=r["label"],
                lower_limit=r["lower_limit"],
                unit=r["unit"],
                source=r["source"],
            )
            for r in rows
        ]

    async def review(
        self, *, identity: StaffIdentity, form_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Cờ bất thường, gợi ý xét nghiệm di truyền, và BMI."""
        ranges = await self.ranges(identity=identity)
        params = semen_params(form_data)
        flags = flag_semen(params, ranges)

        nong_do = _lan_moi_nhat(form_data, "tdd_nong_do")
        suggestions = suggest_genetic_tests(
            concentration_m_ml=nong_do,
            fsh=_so(form_data.get("nt_fsh")),
            testis_volume_ml=larger_testis_volume(form_data),
            vas_palpable=vas_palpable(form_data),
        )

        # Testosterone ngoại sinh gây vô tinh, và bỏ sót nó là chẩn đoán nhầm
        # thành vô tinh không do tắc — một chẩn đoán đổi hẳn hướng điều trị.
        # Nhắc chứ không kết luận: hệ thống không biết bệnh nhân đã ngưng bao lâu
        # thật sự.
        notes: list[str] = []
        if form_data.get("ts_testosterone_ngoai") in ("dang_dung", "ngung_duoi_6"):
            notes.append(
                "Bệnh nhân đang hoặc mới ngưng testosterone / steroid đồng hoá — "
                "cân nhắc trước khi đọc kết quả tinh dịch đồ và nội tiết."
            )
        if nong_do is not None and nong_do == 0 and not form_data.get("tdd_song_l1"):
            notes.append(
                "Không thấy tinh trùng mà chưa có tỷ lệ sống — cân nhắc làm thêm "
                "để phân biệt tinh trùng chết với bất động."
            )

        out = {
            "semen_flags": flags,
            "genetic_suggestions": suggestions,
            "bmi": compute_bmi(
                _so(form_data.get("kls_chieu_cao")),
                _so(form_data.get("kls_can_nang")),
            ),
            "notes": notes,
            # Nói rõ đọc theo ấn bản nào. Một cờ đỏ không kèm nguồn thì bác sĩ
            # vẫn phải đi tra lại, và cái cờ ấy chỉ làm màn hình ồn hơn.
            "reference_source": ranges[0].source if ranges else None,
        }
        logger.info(
            "andrology_review",
            clinic_id=identity.clinic_id,
            flags=len(flags),
            suggestions=len(suggestions),
        )
        return out
