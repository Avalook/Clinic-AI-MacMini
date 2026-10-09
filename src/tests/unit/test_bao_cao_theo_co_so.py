"""Tách báo cáo cuối ngày theo cơ sở — hàm thuần, không cần DB (08/10/2026)."""

from __future__ import annotations

from datetime import date, datetime

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bao_cao_cuoi_ngay_service import (
    csv_bao_cao,
    gom_bao_cao,
    tach_theo_co_so,
)
from clinicai.services.co_so_bao_cao import KHONG_KHOP, TEN_CHUA_RO, doc_co_so

L1 = "11111111-1111-1111-1111-111111111111"
L2 = "22222222-2222-2222-2222-222222222222"
NGAY = date(2026, 10, 8)
LUC = datetime(2026, 10, 8, 9, 0, tzinfo=CLINIC_TZ)


def _thu(i: int, co_so: str | None, so: int, **them: object) -> dict[str, object]:
    return {
        "id": f"c{i}",
        "visit_id": f"v{i}",
        "kind": "dich_vu",
        "status": "PAID",
        "amount": so,
        "method": "CASH",
        "paid_at": LUC,
        "nguoi_thu": "Thu ngân",
        "khach_id": f"k{i}",
        "co_so": co_so,
        **them,
    }


def test_doc_co_so_khong_nem() -> None:
    assert doc_co_so(None) is None
    assert doc_co_so("") is None
    assert doc_co_so("   ") is None
    assert doc_co_so(L1.upper()) == L1
    assert doc_co_so("rác") == KHONG_KHOP
    assert doc_co_so("1; DROP TABLE visit") == KHONG_KHOP


def test_tach_cong_lai_bang_tong_va_co_dong_chua_ro() -> None:
    lan_thu = [
        _thu(1, L1, 100_000),
        _thu(2, L2, 200_000),
        _thu(3, L2, 50_000, status="VOIDED"),
        _thu(4, None, 70_000),  # lần thu không gắn lượt
    ]
    hoan = [
        {
            "refund_id": "r1",
            "kind": "dich_vu",
            "amount": 30_000,
            "status": "COMPLETED",
            "method": "CASH",
            "created_at": LUC,
            "co_so": L2,
        }
    ]
    luot = {L1: 3, L2: 2, None: 1}
    chung = {
        "tu": NGAY,
        "den": NGAY,
        "lan_thu": lan_thu,
        "hoan": hoan,
        "dong": [],
        "doi_tac": [],
        "doi_hinh_thuc": [],
    }
    tong = gom_bao_cao(**chung, so_luot_kham=6)  # type: ignore[arg-type]
    phan = tach_theo_co_so(
        **chung,  # type: ignore[arg-type]
        co_so_ds=[{"id": L1, "ten": "Kim Ngưu"}, {"id": L2, "ten": "Hào Nam"}],
        luot=luot,
        luot_khong_chon={},
    )
    assert [p["ten"] for p in phan] == ["Kim Ngưu", "Hào Nam", TEN_CHUA_RO]
    for k in ("thu", "huy", "hoan", "thuc_thu", "so_phieu_thu"):
        assert sum(p["tong"][k] for p in phan) == tong["tong"][k], k
    assert sum(p["khach"]["so_luot_kham"] for p in phan) == 6
    hn = phan[1]
    assert (hn["tong"]["thu"], hn["tong"]["huy"], hn["tong"]["hoan"]) == (
        250_000,
        50_000,
        30_000,
    )
    assert hn["tong"]["thuc_thu"] == 170_000


def test_co_so_khong_so_lieu_van_hien_va_khong_dong_chua_ro() -> None:
    phan = tach_theo_co_so(
        tu=NGAY,
        den=NGAY,
        co_so_ds=[{"id": L1, "ten": "Kim Ngưu"}, {"id": L2, "ten": "Hào Nam"}],
        lan_thu=[_thu(1, L1, 100_000)],
        hoan=[],
        dong=[],
        doi_tac=[],
        doi_hinh_thuc=[],
        luot={L1: 1},
        luot_khong_chon={},
    )
    assert [(p["location_id"], p["tong"]["thu"]) for p in phan] == [
        (L1, 100_000),
        (L2, 0),
    ]


def test_csv_co_khoi_co_so_va_dong_tong() -> None:
    chung = {
        "tu": NGAY,
        "den": NGAY,
        "lan_thu": [_thu(1, L1, 100_000), _thu(2, L2, 200_000)],
        "hoan": [],
        "dong": [],
        "doi_tac": [],
        "doi_hinh_thuc": [],
    }
    bc = gom_bao_cao(**chung, so_luot_kham=2)  # type: ignore[arg-type]
    bc["theo_co_so"] = tach_theo_co_so(
        **chung,  # type: ignore[arg-type]
        co_so_ds=[{"id": L1, "ten": "Kim Ngưu"}, {"id": L2, "ten": "Hào Nam"}],
        luot={L1: 1, L2: 1},
        luot_khong_chon={},
    )
    out = csv_bao_cao(bc)
    assert "Cơ sở,Lượt khám,Phiếu thu,Thu gốc,Huỷ phiếu,Hoàn,Thực thu" in out
    assert "Kim Ngưu,1,1,100000,0,0,100000" in out
    assert "Hào Nam,1,1,200000,0,0,200000" in out
    assert "\r\nTổng,2,2,300000,0,0,300000\r\n" in out
