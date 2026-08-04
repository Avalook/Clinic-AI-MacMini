"""Ảnh siêu âm: kiểu tệp và đường dẫn.

Đây là chỗ nhận TỆP TỪ NGƯỜI DÙNG rồi ghi xuống đĩa máy chủ — chỗ dễ hở nhất
trong cả hệ thống. Ba điều được thi hành ở service (không phải ở giao diện):
tên tệp do hệ thống đặt, đường dẫn luôn bắt đầu bằng clinic_id, và kiểu tệp
kiểm bằng nội dung chứ không bằng đuôi tên.
"""

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.media_service import MAX_BYTES, safe_path, sniff

CLINIC = "a0000000-0000-4000-8000-000000000001"
REC = "b0000000-0000-4000-8000-000000000002"


class TestFileTypeComesFromContent:
    def test_jpeg_is_recognised(self) -> None:
        assert sniff(b"\xff\xd8\xff" + b"x" * 100) == ("image/jpeg", ".jpg")

    def test_png_is_recognised(self) -> None:
        assert sniff(b"\x89PNG\r\n\x1a\n" + b"x" * 100)[0] == "image/png"

    def test_dicom_is_recognised_at_byte_128(self) -> None:
        """Máy siêu âm xuất thẳng DICOM là chuyện thường. Từ chối nó sẽ đẩy kỹ
        thuật viên sang chép tay qua USB — và lúc đó hệ thống mất dấu vết."""
        assert sniff(b"\x00" * 128 + b"DICM" + b"x" * 10)[0] == "application/dicom"

    def test_html_named_jpg_is_refused(self) -> None:
        """ĐÂY LÀ CHỖ NGUY HIỂM.

        Một tệp tên "anh.jpg" chứa HTML sẽ được trình duyệt CHẠY nếu phục vụ
        sai kiểu — mã của người tải lên chạy trong phiên của người xem. Đuôi
        tên là thứ người tải lên tự đặt; mấy byte đầu là thứ tệp thật sự là.
        """
        with pytest.raises(ValidationError, match="không phải ảnh"):
            sniff(b"<html><script>alert(1)</script></html>")

    def test_an_empty_file_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            sniff(b"")

    def test_a_pdf_is_refused(self) -> None:
        """Kết quả siêu âm là ảnh. PDF lọt vào đây nghĩa là ai đó đang dùng ô
        ảnh làm chỗ đính kèm chung — việc khác, chỗ khác."""
        with pytest.raises(ValidationError):
            sniff(b"%PDF-1.7\n%...")


class TestThePathIsNeverUserControlled:
    def test_it_always_starts_with_the_clinic(self) -> None:
        """Hai phòng khám không bao giờ đọc được tệp của nhau, kể cả khi một
        truy vấn nào đó sai."""
        _, key = safe_path(clinic_id=CLINIC, ultrasound_id=REC, ext=".jpg")
        assert key.startswith(f"{CLINIC}/")

    def test_two_uploads_never_collide(self) -> None:
        """Tên tệp là UUID mới sinh mỗi lần. Trùng tên nghĩa là ảnh sau đè ảnh
        trước — mất một ảnh siêu âm mà không ai biết."""
        a = safe_path(clinic_id=CLINIC, ultrasound_id=REC, ext=".jpg")[1]
        b = safe_path(clinic_id=CLINIC, ultrasound_id=REC, ext=".jpg")[1]
        assert a != b

    def test_no_part_of_the_name_can_escape_the_folder(self) -> None:
        """Không có gì từ người dùng lọt vào đường dẫn, nên không có gì để
        thoát ra. Kiểm bằng cách khẳng định khoá chỉ gồm ký tự an toàn."""
        _, key = safe_path(clinic_id=CLINIC, ultrasound_id=REC, ext=".jpg")
        assert ".." not in key
        assert not key.startswith("/")
        assert all(c.isalnum() or c in "-/._" for c in key)


class TestSizeLimit:
    def test_twelve_megabytes(self) -> None:
        """Ảnh máy siêu âm khoảng 200KB–2MB. 12MB rộng rãi mà vẫn chặn được một
        video bị kéo nhầm vào ô ảnh."""
        assert MAX_BYTES == 12 * 1024 * 1024
