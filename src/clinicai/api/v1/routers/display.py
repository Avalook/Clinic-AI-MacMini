"""Display board configuration endpoint (C.4).

Public (no auth required for TV displays). Reads ``clinic.settings.display``
so each clinic can customise zones, footer text, and branding without a deploy.

When no display config exists, falls back to Dr4Women defaults.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.database import get_db_pool

router = APIRouter()

_DEFAULT_DISPLAY = {
    "zones": [
        {"key": "kham", "label": "Khám bác sĩ", "prefix": "C"},
        {"key": "sa1", "label": "SA1", "prefix": "SA"},
        {"key": "sa2", "label": "SA2", "prefix": "SA"},
        {"key": "sa3", "label": "SA3", "prefix": "SA"},
        {"key": "xn", "label": "Xét nghiệm", "prefix": "X"},
        {"key": "tt", "label": "Thanh toán", "prefix": "T"},
    ],
    "footer_text": "Vui lòng chờ đến lượt số của mình",
    "footer_info": "",
    "clinic_name": "ClinicAI",
}


@router.get("/display/config")
async def display_config(
    clinic_id: str = Query(..., description="Clinic UUID"),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Display board config for a clinic (public, no auth).

    Used by the TV display page to render the correct zones and branding.
    Falls back to defaults when ``clinic.settings.display`` is absent.
    """
    settings_raw = await pool.fetchval(
        "SELECT settings -> 'display' FROM clinic WHERE id = $1::uuid",
        clinic_id,
    )

    if settings_raw is None:
        return {"ok": True, **_DEFAULT_DISPLAY}

    display = (
        json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    )
    if not isinstance(display, dict):
        return {"ok": True, **_DEFAULT_DISPLAY}

    # Merge with defaults so missing keys don't break the TV.
    merged = {**_DEFAULT_DISPLAY, **display}
    return {"ok": True, **merged}


@router.get("/display/queue")
async def display_queue(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bảng gọi số cho màn hình TV — thứ tự theo LUẬT GỌI, không theo giờ hẹn.

    CÓ ĐÒI TOKEN, khác với `/display/config` ngay trên. Đây không phải mâu
    thuẫn mà là giữ nguyên thực tế: trang `/display` tự nhận là công cộng, nhưng
    RLS trên `appointment` khiến trình duyệt chưa đăng nhập đọc ra 0 dòng — nên
    máy tivi hôm nay VẪN phải đăng nhập bằng một tài khoản nhân viên. Mở endpoint
    này ra công cộng sẽ là một thay đổi về bảo mật thật sự (ai biết clinic_id sẽ
    đọc được nhịp bệnh nhân cả ngày), và đó là quyết định của chủ phòng khám,
    không phải hệ quả phụ của một lần sửa thứ tự sắp xếp.

    Phản hồi KHÔNG chứa tên, mã bệnh nhân, số điện thoại hay tên bác sĩ — xem
    ràng buộc ① trong display_board_service.
    """
    from datetime import datetime, time, timedelta

    from clinicai.services.display_board_service import DisplayBoardService

    hom_nay = datetime.now(CLINIC_TZ).date()
    dau = datetime.combine(hom_nay, time.min, tzinfo=CLINIC_TZ)
    return await DisplayBoardService(pool).board(
        clinic_id=identity.clinic_id,
        start=dau,
        end=dau + timedelta(days=1),
    )
