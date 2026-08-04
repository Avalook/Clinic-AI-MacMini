"""Ảnh siêu âm: kiểu tệp và đường dẫn.

Đây là chỗ nhận TỆP TỪ NGƯỜI DÙNG rồi ghi xuống đĩa máy chủ — chỗ dễ hở nhất
trong cả hệ thống. Ba điều được thi hành ở service (không phải ở giao diện):
tên tệp do hệ thống đặt, đường dẫn luôn bắt đầu bằng clinic_id, và kiểu tệp
kiểm bằng nội dung chứ không bằng đuôi tên.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.media_service import (
    MAX_BYTES,
    MediaService,
    safe_path,
    sniff,
)
from tests.services.fake_pool import FakePool

CLINIC = "a0000000-0000-4000-8000-000000000001"
REC = "b0000000-0000-4000-8000-000000000002"

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _who() -> StaffIdentity:
    return StaffIdentity(
        auth_user_id="u-1",
        staff_id="s-1",
        full_name="KTV",
        department=ClinicRole.NURSE_ULTRASOUND.value,
        role=ClinicRole.NURSE_ULTRASOUND,
        clinic_id=CLINIC,
        location_id="c1100000-0000-4000-8000-000000000001",
        location_name="Kim Ngưu",
    )


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


# ── Phần ghi/đọc thật ──────────────────────────────────────────────────────
#
# Hai phương thức dưới đây chạm cả đĩa lẫn database. Chúng là nơi ba luật ở
# phần trên được THI HÀNH, và cho tới giờ chỉ phần thuần được kiểm.


class TestAttachIO:
    def test_an_empty_file_never_reaches_the_database(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="rỗng"):
            _run(
                MediaService(pool).attach_ultrasound_image(
                    identity=_who(), ultrasound_id=REC, data=b"", display_name=None
                )
            )
        assert pool.queries() == []

    def test_too_large_never_reaches_the_database(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="quá lớn"):
            _run(
                MediaService(pool).attach_ultrasound_image(
                    identity=_who(),
                    ultrasound_id=REC,
                    data=JPEG + b"\x00" * MAX_BYTES,
                    display_name=None,
                )
            )
        assert pool.queries() == []

    def test_unknown_record(self) -> None:
        pool = FakePool(None)
        with pytest.raises(ValidationError, match="Không tìm thấy bản ghi"):
            _run(
                MediaService(pool).attach_ultrasound_image(
                    identity=_who(), ultrasound_id=REC, data=JPEG, display_name=None
                )
            )

    def test_a_signed_report_is_locked_against_new_images(self) -> None:
        """Bác sĩ ký cái họ đã nhìn thấy. Một phiếu đã ký mà ảnh vẫn thêm được
        thì chữ ký không còn nói lên điều gì."""
        pool = FakePool({"ultrasound_id": REC, "signed_at": "2026-08-04"})
        with pytest.raises(ValidationError, match="đã ký"):
            _run(
                MediaService(pool).attach_ultrasound_image(
                    identity=_who(), ultrasound_id=REC, data=JPEG, display_name=None
                )
            )

    def test_a_hostile_display_name_never_touches_the_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tên người tải lên đặt được giữ lại làm NHÃN và chỉ là nhãn. Khoá
        trên đĩa do hệ thống sinh, nên "../../../etc/passwd" không đi đâu cả."""
        monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
        pool = FakePool({"ultrasound_id": REC, "signed_at": None})
        out = _run(
            MediaService(pool).attach_ultrasound_image(
                identity=_who(),
                ultrasound_id=REC,
                data=JPEG,
                display_name="  ../../../etc/passwd  ",
            )
        )
        assert out["display_name"] == "../../../etc/passwd"
        assert ".." not in out["key"] and out["key"].startswith(f"{CLINIC}/")
        ghi = tmp_path / out["key"]
        assert ghi.read_bytes() == JPEG
        # Ghi tệp tạm rồi đổi tên — không để lại rác khi ghi xong.
        assert list(ghi.parent.glob("*.tmp")) == []
        assert pool.wrote("UPDATE public.ultrasound_record")


class TestReadIO:
    def test_a_key_from_another_clinic_stops_before_the_query(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="không thuộc phòng khám"):
            _run(
                MediaService(pool).read_ultrasound_image(
                    identity=_who(),
                    key="b0000000-0000-4000-8000-000000000009/ultrasound/x/a.jpg",
                )
            )
        assert pool.queries() == []

    def test_right_clinic_but_not_in_any_record(self) -> None:
        """Thiếu phép kiểm này thì đoán được một UUID là đọc được ảnh của bệnh
        nhân bất kỳ trong cùng phòng khám."""
        pool = FakePool(None)
        with pytest.raises(ValidationError, match="Không tìm thấy ảnh"):
            _run(
                MediaService(pool).read_ultrasound_image(
                    identity=_who(), key=f"{CLINIC}/ultrasound/{REC}/a.jpg"
                )
            )

    def test_the_database_says_yes_but_the_file_is_gone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
        pool = FakePool(1)
        with pytest.raises(ValidationError, match="không còn trên máy chủ"):
            _run(
                MediaService(pool).read_ultrasound_image(
                    identity=_who(), key=f"{CLINIC}/ultrasound/{REC}/a.jpg"
                )
            )

    def test_the_mime_comes_from_the_bytes_not_the_extension(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
        key = f"{CLINIC}/ultrasound/{REC}/a.jpg"
        p = tmp_path / key
        p.parent.mkdir(parents=True)
        p.write_bytes(PNG)
        data, mime = _run(
            MediaService(FakePool(1)).read_ultrasound_image(identity=_who(), key=key)
        )
        assert data == PNG
        assert mime == "image/png"
