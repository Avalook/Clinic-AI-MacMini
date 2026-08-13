"""Sentry APM integration — error tracking + performance monitoring.

Phase 1 of the DevOps/Monitoring plan.

Reads ``SENTRY_DSN`` from the environment. If unset or empty, Sentry is
silently disabled (no crash, no side-effects). This lets the same Docker
image run with or without Sentry configured.

Usage: call ``init_sentry()`` once at app startup, before creating the
FastAPI app.
"""

from __future__ import annotations

import os

import structlog

logger = structlog.get_logger()


def init_sentry() -> None:
    """Initialize Sentry SDK if SENTRY_DSN is configured.

    Safe to call unconditionally — skips silently when DSN is empty.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("sentry_disabled", reason="SENTRY_DSN not set")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        environment = os.environ.get("APP_ENV", "development")
        release = os.environ.get("IMAGE_TAG", "unknown")

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=f"clinicai@{release}",
            # Sample 10% of requests for performance tracing (keep costs low).
            traces_sample_rate=0.1,
            # Profile 10% of traced requests (CPU flame graphs).
            profiles_sample_rate=0.1,
            # KHÔNG gửi PII mặc định: không header, không cookie, không IP, và
            # không thân request. Thân request của hệ này chứa tên bệnh nhân,
            # số điện thoại, chẩn đoán.
            #
            # (Chú thích cũ ở đây ghi "Send PII … acceptable for internal clinic
            # tool" trong khi code đặt False — chú thích nói ngược với code, và
            # người đọc sau có thể sửa code cho khớp chú thích.)
            send_default_pii=False,
            # ĐÂY MỚI LÀ CHỖ RÒ THẬT SỰ, và nó KHÔNG do send_default_pii lo.
            #
            # SDK Python mặc định đính kèm BIẾN CỤC BỘ của từng khung ngăn xếp.
            # Trong ứng dụng này, biến cục bộ lúc nổ lỗi thường đang giữ nguyên
            # một hàng `patient` hoặc `clinical_record` — tức là tên, ngày sinh,
            # số điện thoại, chẩn đoán, tất cả đi thẳng lên máy chủ Sentry ở
            # nước ngoài. Một báo lỗi không được phép trở thành đường xuất dữ
            # liệu bệnh án.
            #
            # Tắt nó làm việc dò lỗi khó hơn một chút — đổi lại, thứ rời khỏi
            # máy chỉ còn loại lỗi, tệp, và số dòng.
            include_local_variables=False,
            # Không gửi thân request trong mọi trường hợp, kể cả khi ai đó bật
            # send_default_pii sau này.
            max_request_body_size="never",
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],
        )
        logger.info(
            "sentry_initialized",
            environment=environment,
            release=f"clinicai@{release}",
        )
    except ImportError:
        logger.warning(
            "sentry_import_failed",
            reason="sentry-sdk not installed; pip install sentry-sdk[fastapi]",
        )
    except Exception as exc:
        # Never let Sentry init crash the app.
        logger.error("sentry_init_error", error=str(exc))
