"""Sentry không được biến thành đường xuất dữ liệu bệnh án.

Đây là hệ thống bệnh án. Một báo lỗi gửi ra máy chủ nước ngoài chỉ được mang
theo *loại lỗi, tệp, số dòng* — không được mang tên bệnh nhân, số điện thoại,
hay chẩn đoán.

Bài kiểm này khẳng định TÍNH CHẤT ("cái gì rời khỏi máy"), không khẳng định cú
pháp trong ``sentry.py``. Nếu ai đó viết lại phần khởi tạo bằng cách khác mà
vẫn giữ đúng ba chốt, bài kiểm vẫn xanh — đúng như mong muốn.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import sentry_sdk

from clinicai.core.sentry import init_sentry

# DSN giả, đúng định dạng nhưng trỏ vào hư không: đủ để SDK khởi tạo và cho đọc
# lại tuỳ chọn, không đủ để gửi gì đi đâu.
FAKE_DSN = "https://key@o0.ingest.sentry.io/0"


@pytest.fixture(autouse=True)
def _tat_sentry_sau_moi_bai() -> Iterator[None]:
    """``init_sentry()`` đặt client TOÀN CỤC — không dọn thì nó còn bật suốt
    phần còn lại của phiên kiểm.

    Hậu quả thật, đã thấy: các bài chạy sau bài này gọi API qua TestClient, lỗi
    trong đó bị Sentry bắt và xếp hàng gửi đi; cuối phiên ``pytest`` in "Sentry
    is attempting to send 5 pending events" rồi chờ 2 giây. Trên CI đó là một
    quãng treo không rõ nguyên do, mà nguồn cơn nằm ở tệp kiểm này.
    """
    yield
    sentry_sdk.get_client().close(timeout=0.0)
    sentry_sdk.init(dsn="")


def test_khong_co_dsn_thi_tat_han(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thiếu cấu hình phải là TẮT, không phải là sập."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    init_sentry()
    assert not sentry_sdk.get_client().is_active()


def test_ba_chot_rieng_tu_khi_bat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setenv("APP_ENV", "test")
    init_sentry()

    client = sentry_sdk.get_client()
    assert client.is_active(), "DSN hợp lệ thì Sentry phải bật"
    options = client.options

    # ① Không header, không cookie, không IP người dùng.
    assert options["send_default_pii"] is False

    # ② Không biến cục bộ. Đây là chốt QUAN TRỌNG NHẤT và cũng dễ quên nhất:
    #    SDK Python mặc định BẬT, và lúc nổ lỗi thì biến cục bộ thường đang giữ
    #    nguyên một hàng bệnh nhân hoặc một hồ sơ khám.
    assert options["include_local_variables"] is False

    # ③ Không thân request — nơi chứa dữ liệu người bệnh khi tạo/sửa hồ sơ.
    assert options["max_request_body_size"] == "never"


def test_moi_truong_va_ban_phat_hanh_co_gan_nhan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lỗi từ máy thật và lỗi từ máy thử phải phân biệt được, nếu không thì
    bảng báo lỗi trộn lẫn và mất tác dụng."""
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("IMAGE_TAG", "abc1234")
    init_sentry()

    options = sentry_sdk.get_client().options
    assert options["environment"] == "production"
    assert options["release"] == "clinicai@abc1234"
