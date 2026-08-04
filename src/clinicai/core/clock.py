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

from datetime import datetime
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
