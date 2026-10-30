"""CANH GÁC MÁY CHỦ — ổ gốc VPS và độ mới của bản sao lưu.

Sự cố 11/10: ổ gốc đầy, sao lưu hỏng 21 giờ, không ai biết. 31/10 ổ lại tới 89%
mới lộ ra vì deploy staging bị chặn. Container không thấy ổ gốc, nên số lấy từ
`status.json` do `clinicai-ops-status.timer` chụp mỗi phút trên VPS (cùng tệp với
tab Hệ thống ở /ops); `su-kien` gắn thư mục ấy chỉ-đọc.

Không có tệp = máy này không chạy bộ đo (staging, dev) → không kiểm gì, tránh báo
sai. Có tệp mà cũ = bộ đo chết → báo, vì nếu im thì hai cảnh báo kia cũng im.

Bộ đo trả `backup = null` khi bản mới nhất không đạt (`verified` khác true) — nên
`null` trong khung giờ được tính là chuyện, không phải "chưa rõ".
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import structlog

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.canh_gac import KetQuaKiem

logger = structlog.get_logger()

#: Có khoảng đệm để ổ dao động quanh ngưỡng không gửi tin mở/đóng liên tục.
O_DIA_MO = 85.0
O_DIA_DONG = 82.0
O_DIA_RAT_DAY_MO = 92.0
O_DIA_RAT_DAY_DONG = 90.0
#: Bộ đo chạy mỗi phút; 15 phút không có số là nó chết, không phải trễ nhịp.
BO_DO_CU_PHUT = 15
SAO_LUU_CU_GIO = 2
#: Timer 15 phút chạy 07:00–22:00 (`clinicai-backup-15p.timer`). Ngoài khung, bản
#: mới nhất cũ tới 9 giờ là bình thường. Mở sau 07:00 để bản đầu ngày kịp xong.
KHUNG_SAO_LUU = (time(7, 30), time(22, 30))
TRAN_BYTE = 256 * 1024


def _gio(v: Any) -> datetime | None:
    """Mốc ISO của bộ đo → datetime có múi giờ; rác thì None, không ném."""
    if not isinstance(v, str):
        return None
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _nguong(gia_tri: float, mo: float, dong: float) -> bool | None:
    if gia_tri > mo:
        return True
    return False if gia_tri <= dong else None


def danh_gia_may_chu(snap: dict[str, Any] | None, luc: datetime) -> list[KetQuaKiem]:
    """HÀM THUẦN. Bỏ một mã khỏi kết quả = giữ nguyên trạng thái mã ấy."""
    if snap is None:
        return []
    chup = _gio(snap.get("generated_at"))
    if chup is None or luc - chup > timedelta(minutes=BO_DO_CU_PHUT):
        return [
            KetQuaKiem(
                "MAY_CHU_KHONG_DO",
                "warning",
                True,
                f"Bộ đo máy chủ không có số mới quá {BO_DO_CU_PHUT} phút — "
                "không biết ổ đĩa và sao lưu đang ra sao.",
            )
        ]
    ra = [
        KetQuaKiem(
            "MAY_CHU_KHONG_DO", "warning", False, "Bộ đo máy chủ chạy lại bình thường."
        )
    ]
    host = snap.get("host")
    pt = host.get("disk_used_percent") if isinstance(host, dict) else None
    if isinstance(pt, int | float) and not isinstance(pt, bool):
        ra += [
            KetQuaKiem(
                "O_DIA_GAN_DAY",
                "warning",
                _nguong(pt, O_DIA_MO, O_DIA_DONG),
                f"Ổ gốc VPS đang dùng {pt:.0f}% — chạy scripts/may-chu/don-o-vps.sh.",
            ),
            KetQuaKiem(
                "O_DIA_RAT_DAY",
                "critical",
                _nguong(pt, O_DIA_RAT_DAY_MO, O_DIA_RAT_DAY_DONG),
                f"Ổ gốc VPS đang dùng {pt:.0f}% — đầy là sao lưu và prod hỏng.",
            ),
        ]
    gio_vn = luc.astimezone(CLINIC_TZ).time()
    if KHUNG_SAO_LUU[0] <= gio_vn < KHUNG_SAO_LUU[1]:
        backup = snap.get("backup")
        xong = _gio(backup.get("completed_at")) if isinstance(backup, dict) else None
        tuoi = None if xong is None else (luc - xong) / timedelta(hours=1)
        ra.append(
            KetQuaKiem(
                "SAO_LUU_CU",
                "critical",
                tuoi is None or tuoi > SAO_LUU_CU_GIO,
                "Bản sao lưu mới nhất hỏng hoặc không đọc được."
                if tuoi is None
                else f"Bản sao lưu mới nhất cách đây {tuoi:.1f} giờ.",
            )
        )
    return ra


def doc_trang_thai() -> dict[str, Any] | None:
    """Đọc `status.json`. Không có tệp → None; hỏng → {} để báo bộ đo chết."""
    duong = Path(os.environ.get("OPS_STATUS_FILE") or "/run/clinicai-ops/status.json")
    try:
        with duong.open("rb") as f:
            tho = f.read(TRAN_BYTE + 1)
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning("canh_gac_may_chu_khong_doc_duoc")
        return {}
    if len(tho) > TRAN_BYTE:
        return {}
    try:
        d = json.loads(tho)
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def kiem_may_chu(luc: datetime | None = None) -> list[KetQuaKiem]:
    return danh_gia_may_chu(doc_trang_thai(), luc or datetime.now(UTC))
