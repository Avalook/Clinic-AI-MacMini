from datetime import UTC, date, datetime

from clinicai.core.clock import CLINIC_TZ
from clinicai.permissions.ca_truc import _ngay_cua_luot_cu


def test_luot_sang_som_gio_viet_nam_khong_bi_coi_la_ngay_cu() -> None:
    # Asyncpg trả UTC: 01:00 tại VN vẫn là 18:00 ngày trước đó ở UTC.
    luc_check_in = datetime(2026, 10, 18, 18, 0, tzinfo=UTC)

    assert luc_check_in.date() == date(2026, 10, 18)
    assert _ngay_cua_luot_cu(luc_check_in, date(2026, 10, 19)) is False


def test_luot_hom_qua_theo_gio_viet_nam_la_ngay_cu() -> None:
    luc_check_in = datetime(2026, 10, 18, 23, 59, tzinfo=CLINIC_TZ)

    assert _ngay_cua_luot_cu(luc_check_in, date(2026, 10, 19)) is True
