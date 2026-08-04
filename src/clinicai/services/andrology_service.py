"""Bộ khám Nam khoa — bốn phép tính, và không cái nào tự kết luận.

Theo docs/spec-form-nam-khoa.md §6.4.

RANH GIỚI QUAN TRỌNG NHẤT Ở FILE NÀY: mọi thứ đây tính ra đều là GỢI Ý cho bác
sĩ đọc, không phải chẩn đoán và không phải chỉ định. Notion §13 của cả năm node
khám đều cấm rõ việc hệ thống tự kết luận hoặc tự tạo chỉ định.

Cụ thể là:
  · `flag_semen` nói "dưới ngưỡng WHO", KHÔNG nói "vô sinh".
  · `suggest_genetic_tests` trả về danh sách KÈM LÝ DO để bác sĩ cân nhắc, và
    không hàm nào ở đây được gọi `order_services()`.
  · `score_iief5` trả về điểm và mức theo thang chuẩn — mức là cách đọc điểm,
    không phải chẩn đoán rối loạn.

Tất cả đều THUẦN: vào là số, ra là số. Không chạm database, không chạm giờ hệ
thống. Nên kiểm được mọi tổ hợp bằng bảng, và một luật lâm sàng sai sẽ hiện ra
ở bài test chứ không hiện ra trên một bệnh nhân.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# ── IIEF-5 ─────────────────────────────────────────────────────────────────
#
# Năm câu, mỗi câu 1–5 điểm, tổng 5–25. Ngưỡng mức độ là thang đã công bố, chép
# nguyên: 22–25 không rối loạn · 17–21 nhẹ · 12–16 nhẹ-vừa · 8–11 vừa · 5–7 nặng.
_IIEF5_BANDS: tuple[tuple[int, int, str], ...] = (
    (22, 25, "Không rối loạn"),
    (17, 21, "Rối loạn nhẹ"),
    (12, 16, "Rối loạn nhẹ – vừa"),
    (8, 11, "Rối loạn vừa"),
    (5, 7, "Rối loạn nặng"),
)


def score_iief5(answers: list[int]) -> dict[str, Any]:
    """Tổng điểm IIEF-5 và mức đọc kèm.

    Từ chối khi thiếu câu hoặc điểm ngoài thang, thay vì cho điểm phần đã trả
    lời: một bảng câu hỏi trả lời dở dang cho ra một tổng thấp giả tạo, và tổng
    đó đọc thành "rối loạn nặng".
    """
    if len(answers) != 5:
        raise ValueError(f"IIEF-5 cần đúng 5 câu trả lời, nhận {len(answers)}.")
    for i, a in enumerate(answers, start=1):
        if not isinstance(a, int) or not 1 <= a <= 5:
            raise ValueError(f"Câu {i}: điểm phải từ 1 đến 5, nhận {a!r}.")

    total = sum(answers)
    severity = next((name for lo, hi, name in _IIEF5_BANDS if lo <= total <= hi), "—")
    return {"score": total, "severity": severity}


# ── Tinh dịch đồ ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SemenRange:
    """Một ngưỡng dưới, đọc từ bảng `semen_reference_range`."""

    parameter: str
    label: str
    lower_limit: Decimal
    unit: str
    source: str


def flag_semen(
    params: dict[str, float | Decimal | None], ranges: list[SemenRange]
) -> list[dict[str, Any]]:
    """Chỉ số nào dưới ngưỡng — KHÔNG kết luận gì thêm.

    Trả về cả `label`, `unit` và `source` để màn hình nói được "Nồng độ 12
    triệu/mL, dưới ngưỡng WHO 2021 (16)". Một cái cờ đỏ không kèm con số và
    nguồn thì bác sĩ vẫn phải đi tra lại, và cái cờ ấy chỉ làm màn hình ồn hơn.

    Chỉ số KHÔNG có trong kết quả thì bỏ qua, không coi là dưới ngưỡng: không
    làm xét nghiệm và làm ra kết quả 0 là hai chuyện khác nhau.
    """
    out: list[dict[str, Any]] = []
    for r in ranges:
        raw = params.get(r.parameter)
        if raw is None:
            continue
        value = Decimal(str(raw))
        if value < r.lower_limit:
            out.append(
                {
                    "parameter": r.parameter,
                    "label": r.label,
                    "value": float(value),
                    "lower_limit": float(r.lower_limit),
                    "unit": r.unit,
                    "source": r.source,
                    # Câu chữ dừng ở "dưới ngưỡng". Bước từ đây sang một chẩn
                    # đoán là việc của bác sĩ, không phải của hàm này.
                    "message": (
                        f"{r.label} {value} {r.unit} — dưới ngưỡng "
                        f"{r.lower_limit} ({r.source})"
                    ),
                }
            )
    return out


# ── Gợi ý xét nghiệm di truyền ─────────────────────────────────────────────


def suggest_genetic_tests(
    *,
    concentration_m_ml: float | None,
    fsh: float | None,
    testis_volume_ml: float | None,
    vas_palpable: bool | None,
) -> list[dict[str, str]]:
    """Xét nghiệm di truyền NÊN CÂN NHẮC, kèm lý do (spec §5.8).

    Mỗi gợi ý phải nói VÌ SAO. Một danh sách xét nghiệm không kèm lý do thì
    hoặc bác sĩ bỏ qua cả danh sách, hoặc chỉ định hết — cả hai đều tệ hơn là
    không gợi ý gì.

    Không đoán khi thiếu dữ liệu: `None` nghĩa là chưa có kết quả, và một gợi ý
    dựng trên số liệu chưa có là một gợi ý sai.
    """
    out: list[dict[str, str]] = []

    # Vô tinh / thiểu tinh nặng → bất thường nhiễm sắc thể và mất đoạn AZF là
    # hai nguyên nhân cần loại trừ trước khi bàn tới hỗ trợ sinh sản.
    if concentration_m_ml is not None and concentration_m_ml < 5:
        ly_do = (
            f"nồng độ {concentration_m_ml} triệu/mL — thiểu tinh nặng"
            if concentration_m_ml > 0
            else "không thấy tinh trùng trong mẫu"
        )
        out.append({"test": "CLS_KARYOTYPE", "reason": ly_do})
        out.append({"test": "CLS_Y_MICRODELETION", "reason": ly_do})

    # Không sờ thấy ống dẫn tinh hai bên → nghĩ tới CBAVD, liên quan CFTR. Đây
    # là dấu hiệu KHÁM, không phải xét nghiệm, nên nó đứng độc lập.
    if vas_palpable is False:
        out.append(
            {
                "test": "CLS_CFTR",
                "reason": "không sờ thấy ống dẫn tinh — cân nhắc CBAVD",
            }
        )

    # FSH bình thường + tinh hoàn thể tích bình thường + vô tinh → hướng tắc
    # nghẽn nhiều hơn hướng sinh tinh. Chỉ nêu khi có ĐỦ ba dữ kiện.
    if (
        concentration_m_ml is not None
        and concentration_m_ml == 0
        and fsh is not None
        and fsh <= 7.6
        and testis_volume_ml is not None
        and testis_volume_ml >= 15
    ):
        out.append(
            {
                "test": "CLS_CFTR",
                "reason": (
                    "vô tinh với FSH và thể tích tinh hoàn bình thường — "
                    "hướng tắc nghẽn"
                ),
            }
        )

    # Bỏ trùng, giữ lý do ĐẦU TIÊN: hai lý do cho cùng một xét nghiệm chỉ làm
    # màn hình dài ra, và bác sĩ đọc lý do đầu là đủ để quyết.
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in out:
        if item["test"] in seen:
            continue
        seen.add(item["test"])
        unique.append(item)
    return unique


# ── BMI ────────────────────────────────────────────────────────────────────


def compute_bmi(height_cm: float | None, weight_kg: float | None) -> float | None:
    """BMI, hoặc None khi thiếu số đo.

    None chứ không phải 0: một BMI bằng 0 lọt vào biểu đồ và vào mọi phép so
    sánh, còn None thì màn hình hiện dấu gạch và không ai đọc nhầm.
    """
    if not height_cm or not weight_kg or height_cm <= 0 or weight_kg <= 0:
        return None
    m = height_cm / 100
    return round(weight_kg / (m * m), 1)
