"""Ô lịch tô màu theo CHỖ ĐẶT HẸN, và chỉ có ba trạng thái.

Trước đây màu ô đến từ `block_budget` — một bảng thứ hai, mịn theo giờ, mang mô
hình "ngân sách phút của bác sĩ" đã bị bỏ. Không ai đối chiếu nó với thứ trigger
thật sự thi hành, nên lưới vẽ "còn chỗ" trong khi database từ chối là chuyện có
thể xảy ra và không có phép kiểm nào phát hiện được.

Giờ cả hai đọc `resolve_effective_cap()`. Còn lại một quyết định thuộc về giao
diện, và nó ở đây: ngưỡng nào thì gọi là "còn ít".
"""

from __future__ import annotations

import pytest

from clinicai.services.capacity_service import cell_state


class TestCellState:
    @pytest.mark.parametrize("cap,used", [(6, 0), (6, 1), (6, 4), (3, 1)])
    def test_room_to_spare_reads_free(self, cap: int, used: int) -> None:
        assert cell_state(cap, used) == "free"

    @pytest.mark.parametrize("cap,used", [(6, 5), (3, 2), (1, 0)])
    def test_one_seat_left_reads_few(self, cap: int, used: int) -> None:
        """Ngưỡng tính theo CHỖ, không theo phần trăm.

        Với trần 3, "còn 33%" nghe như vẫn rộng; thực tế còn đúng một người nữa
        là hết. Người đọc ô lịch cần biết điều thứ hai.
        """
        assert cell_state(cap, used) == "few"

    @pytest.mark.parametrize("cap,used", [(6, 6), (3, 3), (1, 1)])
    def test_at_the_cap_reads_full(self, cap: int, used: int) -> None:
        assert cell_state(cap, used) == "full"

    def test_over_the_cap_still_reads_full(self) -> None:
        """Vượt trần vẫn là đầy, không phải một trạng thái thứ tư.

        Có thể vượt thật: trần bị hạ xuống sau khi lịch đã đặt. Ô phải nói "đã
        đầy" chứ không rơi về nhánh mặc định và hiện màu xanh.
        """
        assert cell_state(3, 5) == "full"

    def test_walkin_seats_never_colour_the_cell(self) -> None:
        """Chỗ vãng lai để dành cho khách đến thẳng quầy.

        cell_state cố ý KHÔNG nhận walkin_cap: nếu đếm nó vào ô mà CSKH nhìn khi
        đặt trước, khung sẽ trông còn chỗ trong khi phần đặt hẹn đã hết — và
        trigger từ chối đúng lượt đặt tiếp theo. Chữ ký hàm là nơi ràng buộc đó
        được phát biểu.
        """
        import inspect

        params = list(inspect.signature(cell_state).parameters)
        assert params == ["regular_cap", "regular_used"]
