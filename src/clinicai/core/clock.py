"""Giờ phòng khám. MỘT múi giờ, và đây là chỗ nó được khai báo.

QUYẾT ĐỊNH SẢN PHẨM (Quang, 2026-08-03): ClinicAI phục vụ phòng khám tại Việt
Nam. Không bán ra nước ngoài. Múi giờ là ``Asia/Ho_Chi_Minh``, cố định.

Đây là một lựa chọn, không phải một thiếu sót — và ghi nó ra thành mã có giá
trị hơn ghi vào tài liệu, vì người đọc mã sau này sẽ thấy nó trước.

VÌ SAO CẦN MỘT FILE CHO MỘT HẰNG SỐ. Trước đây cùng sự thật ấy được khai báo
lại ở năm chỗ trong Python, tám chỗ trong TypeScript, và — đáng nói nhất —
``visit_progress_service`` dùng ``timezone(timedelta(hours=7))``, tức một
OFFSET CỐ ĐỊNH chứ không phải một vùng IANA. Với Việt Nam hai thứ đó cho cùng
kết quả (nước này chưa từng dùng giờ mùa hè), nên sai lệch chưa bao giờ lộ ra.
Nó chỉ lộ vào ngày ai đó copy dòng ấy sang một chỗ có DST.

Một hằng số đúng-nhờ-may-mắn ở nhiều bản sao là thứ khó sửa nhất: không test
nào đỏ, không log nào kêu, và nó chỉ sai ở một trong các bản.

CÒN ``clinic.timezone`` THÌ SAO. Cột đó tồn tại trong schema và KHÔNG AI ĐỌC.
Một cột cấu hình mà hệ thống bỏ qua là một lời hứa suông: người vận hành đổi
nó, không có gì xảy ra, và không có gì báo. Migration 20260803000012 thêm CHECK
ghim nó về đúng giá trị này — đổi sẽ bị từ chối kèm câu giải thích, thay vì
được nhận rồi lặng lẽ vô hiệu.

NGÀY MUỐN ĐA MÚI GIỜ. Sửa ở đây, ở ``lib/datetime.ts``, gỡ CHECK, rồi cho
``resolve_effective_cap`` và các hàm SQL cùng họ đọc ``clinic.timezone`` thay
cho hằng chuỗi. Ba chỗ, và chúng được liệt kê ra để việc đó là một thay đổi có
thể lập kế hoạch, không phải một cuộc đi tìm.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

#: Múi giờ vận hành của mọi phòng khám ClinicAI.
CLINIC_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

#: Tên IANA, cho những nơi cần chuỗi (tham số SQL, JSON trả về API).
CLINIC_TZ_NAME = "Asia/Ho_Chi_Minh"


def now_vn() -> datetime:
    """Thời điểm hiện tại theo giờ phòng khám.

    Dùng cái này thay cho ``datetime.now()`` trần: máy chủ chạy UTC, nên một
    ``now()`` không mang múi giờ sẽ lệch bảy tiếng đúng vào các phép so sánh
    ranh giới ngày — và bảy tiếng đủ để "hôm nay" thành "hôm qua" trong suốt ca
    tối, tức chính khung giờ phòng khám làm việc.
    """
    return datetime.now(CLINIC_TZ)


def hom_nay_vn() -> date:
    """Ngày hôm nay theo giờ phòng khám."""
    return now_vn().date()


#: Mốc sớm nhất một màn "xem ngày cũ" nhận — trước đó hệ thống chưa có dữ liệu.
NGAY_XEM_SOM_NHAT = date(2020, 1, 1)

# Chỉ nhận dạng có gạch, đủ hai chữ số: ``fromisoformat`` 3.11+ còn nhận
# "20260929" và "2026-W40-1" — hai dạng không màn nào gửi, trước đây lọt qua
# vài bản sao và ra một ngày khác hẳn ("2026-W45-1" thành 02/11).
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_ISO_LONG = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_VN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def _ngay_tu(nam: str, thang: str, ngay: str) -> date | None:
    try:
        return date(int(nam), int(thang), int(ngay))
    except ValueError:
        return None


def doc_ngay(value: object, *, go_tay: bool = False) -> date | None:
    """MỘT hàm đọc ngày cho cả backend. Rác / rỗng / sai kiểu → None, KHÔNG ném.

    CLAUDE.md: hàm nhận ngày giờ từ người dùng trả rỗng thay vì ném — đã có ba
    lần 500. Trước 24/11/2026 có mười bản sao khác thân; ba bản ném
    ``AttributeError`` khi gặp số, một bản trả ``datetime`` thay vì ``date``.

    Nhận:
    - ``date`` → giữ nguyên; ``datetime`` → ``.date()`` theo múi của chính nó
      (không đổi sang giờ VN — giữ đúng hành vi các bản cũ);
    - ``"YYYY-MM-DD"``, hoặc chuỗi ngày-giờ ISO hợp lệ bắt đầu bằng nó
      (``"2026-11-08T10:00"``, ``"2026-11-08 10:00+07:00"``) → phần ngày;
    - ``go_tay=True`` (ô người gõ tay trên phiếu, hạn dùng thuốc): nhận thêm
      ``"D/M/YYYY"`` và ``"YYYY-M-D"`` không đệm số 0.
    Không nhận: số, bool, list, "20261108", "2026-W45-1", "2026-11-08abc".
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    chu = value.strip()
    if m := _ISO.fullmatch(chu):
        return _ngay_tu(*m.groups())
    if len(chu) > 10 and _ISO.match(chu) and chu[10] in "T ":
        try:
            return datetime.fromisoformat(chu).date()
        except ValueError:
            return None
    if not go_tay:
        return None
    if m := _ISO_LONG.fullmatch(chu):
        return _ngay_tu(*m.groups())
    if m := _VN.fullmatch(chu):
        d, th, n = m.groups()
        return _ngay_tu(n, th, d)
    return None


def doc_ngay_xem(value: object) -> date | None:
    """Ngày người dùng chọn để xem (``YYYY-MM-DD``) → ``date``.

    Như ``doc_ngay`` nhưng chặt hơn: chuỗi phải đúng 10 ký tự (không kèm giờ)
    và không trước 2020 (chưa có dữ liệu). None nghĩa là "hôm nay" ở nơi gọi.
    Ngày tương lai vẫn nhận: nơi gọi chỉ đọc, ngày chưa tới thì danh sách rỗng.
    """
    if isinstance(value, str) and len(value.strip()) != 10:
        return None
    ngay = doc_ngay(value)
    if ngay is None or ngay < NGAY_XEM_SOM_NHAT:
        return None
    return ngay


def iso(moc: object) -> str | None:
    """Mốc giờ / ngày → chuỗi ISO-8601 cho JSON; không có → None. KHÔNG ném.

    ``date``/``datetime`` → ``.isoformat()`` (chữ T, không phải ``str()`` có dấu
    cách — ảnh chụp phiếu còn phải mở ra sau nhiều năm); chuỗi đã là ISO hợp lệ
    (vd đọc lại từ jsonb) → giữ nguyên; còn lại (None, "", số, chữ rác) → None.
    Trước 24/11/2026: 26 bản sao, 11 bản ném ``AttributeError`` khi gặp chuỗi,
    7 bản trả None cho kiểu ``date``.
    """
    if isinstance(moc, (date, datetime)):
        return moc.isoformat()
    if isinstance(moc, str):
        try:
            datetime.fromisoformat(moc)
        except ValueError:
            return None
        return moc
    return None


def iso_sau(gia_tri: Any) -> Any:
    """Đổi MỌI mốc giờ / ngày thành chuỗi ISO, kể cả lồng trong dict / list.

    Cho chỗ trả cả dòng DB (``{k: ...}``) hoặc cây dữ liệu ra JSON: giá trị
    khác (số, UUID, chuỗi, None) giữ nguyên — khác ``iso`` ở chỗ đó.
    """
    if isinstance(gia_tri, (date, datetime)):
        return gia_tri.isoformat()
    if isinstance(gia_tri, dict):
        return {k: iso_sau(x) for k, x in gia_tri.items()}
    if isinstance(gia_tri, (list, tuple)):
        return [iso_sau(x) for x in gia_tri]
    return gia_tri
