"""Lịch trực có lịch sử thay đổi — phần thuần (Khối 3, 06/10/2026).

Đầu vào rác cho ngày / tuần / mã phiên bản trả rỗng chứ không ném (CLAUDE.md:
ba lần 500 vì luật này bị bỏ qua), và cách dựng phiên bản + so hai bản.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from clinicai.services.lich_truc_phien_ban_service import (
    LOAI_THAY_DOI,
    doc_ban,
    doc_tuan,
    dung_phien_ban,
    loc_phien_ban,
    so_sanh,
)


@pytest.mark.parametrize(
    "rac",
    [
        None,
        "",
        "   ",
        "abc",
        "2026-13-01",
        "2026-02-30",
        "99-99-9999",
        "2026/10/06",
        "'; DROP TABLE work_roster; --",
        123,
        12.5,
        [],
        {},
        True,
    ],
)
def test_doc_tuan_rac_tra_none(rac: object) -> None:
    assert doc_tuan(rac) is None


def test_doc_tuan_ve_thu_hai() -> None:
    assert doc_tuan("2026-10-08") == date(2026, 10, 5)
    assert doc_tuan("2026-10-05") == date(2026, 10, 5)
    assert doc_tuan("2026-10-11T23:00:00") == date(2026, 10, 5)
    assert doc_tuan(date(2026, 10, 11)) == date(2026, 10, 5)
    assert doc_tuan(datetime(2026, 10, 7, 9, 0)) == date(2026, 10, 5)
    # Ngày nhỏ nhất là thứ Hai — không tràn khi lùi về đầu tuần.
    assert doc_tuan("0001-01-01") == date(1, 1, 1)


@pytest.mark.parametrize(
    "rac",
    [None, "", "abc", "-5", "0", "1.5", "1e9", "9" * 30, True, False, -3, 0, 2.0, []],
)
def test_doc_ban_rac_tra_none(rac: object) -> None:
    assert doc_ban(rac) is None


def test_doc_ban_hop_le() -> None:
    assert doc_ban("12345") == 12345
    assert doc_ban(" 77 ") == 77
    assert doc_ban(9) == 9


def _o(
    rid: str,
    ten: str,
    *,
    ngay: str = "2090-01-02",
    ca: str = "FULL",
    tram: str = "BS1",
    status: str = "APPROVED",
) -> dict[str, Any]:
    return {
        "id": rid,
        "work_date": ngay,
        "shift": ca,
        "station": tram,
        "staff_id": f"s-{ten}",
        "staff_name": ten,
        "status": status,
    }


def test_so_sanh_ba_loai_va_doi_cho() -> None:
    truoc = {
        "a": _o("a", "Thành"),
        "b": _o("b", "Hà", tram="BS2"),
        "c": _o("c", "Lan", tram="BS3"),
        "p": _o("p", "Chờ", status="PENDING"),
    }
    sau = {
        "a": _o("a", "Hằng"),  # đổi người
        "c": _o("c", "Lan", tram="BS4"),  # đổi chỗ
        "d": _o("d", "Minh", tram="BS5"),  # thêm
        "p": _o("p", "Chờ", status="PENDING"),  # chưa duyệt: vô hình
    }
    k = so_sanh(truoc, sau)
    assert [
        d["truoc"]["staff_name"] + "→" + d["o"]["staff_name"] for d in k["doi_nguoi"]
    ] == ["Thành→Hằng"]
    assert sorted(o["id"] + o["station"] for o in k["them"]) == ["cBS4", "dBS5"]
    assert sorted(o["id"] + o["station"] for o in k["xoa"]) == ["bBS2", "cBS3"]


def test_so_sanh_duyet_ca_cho_la_them() -> None:
    k = so_sanh({"p": _o("p", "Chờ", status="PENDING")}, {"p": _o("p", "Chờ")})
    assert [o["id"] for o in k["them"]] == ["p"]


def test_dung_phien_ban_tu_anh_va_so() -> None:
    anh = [
        {
            "id": 1,
            "loai": "GOC",
            "txid": 100,
            "luc": None,
            "boi_staff_id": "q",
            "ca": [_o("a", "Thành"), _o("b", "Hà", tram="BS2")],
        },
    ]
    so = [
        # Xếp nháp TRƯỚC khi áp dụng: không phải phiên bản.
        {
            "id": 1,
            "txid": 90,
            "roster_id": "a",
            "hanh_dong": "THEM",
            "truoc": None,
            "sau": _o("a", "Thành"),
            "luc": None,
            "boi_staff_id": None,
        },
        # Đổi người: một giao dịch.
        {
            "id": 2,
            "txid": 110,
            "roster_id": "a",
            "hanh_dong": "DOI_NGUOI",
            "truoc": _o("a", "Thành"),
            "sau": _o("a", "Hằng"),
            "luc": None,
            "boi_staff_id": "tc",
        },
        # Xoá ca.
        {
            "id": 3,
            "txid": 120,
            "roster_id": "b",
            "hanh_dong": "XOA",
            "truoc": _o("b", "Hà", tram="BS2"),
            "sau": None,
            "luc": None,
            "boi_staff_id": "tc",
        },
        # Giao dịch chỉ đụng ca chờ duyệt → không hiện là phiên bản.
        {
            "id": 4,
            "txid": 125,
            "roster_id": "p",
            "hanh_dong": "THEM",
            "truoc": None,
            "sau": _o("p", "X", status="PENDING"),
            "luc": None,
            "boi_staff_id": "tc",
        },
        # Thêm người vào ca trống.
        {
            "id": 5,
            "txid": 130,
            "roster_id": "e",
            "hanh_dong": "THEM",
            "truoc": None,
            "sau": _o("e", "Minh", tram="BS9"),
            "luc": None,
            "boi_staff_id": "tc",
        },
    ]
    ds = loc_phien_ban(dung_phien_ban(anh, so))
    assert [(p.loai, p.txid) for p, _ in ds] == [
        ("GOC", 100),
        (LOAI_THAY_DOI, 110),
        (LOAI_THAY_DOI, 120),
        (LOAI_THAY_DOI, 130),
    ]
    goc, doi, xoa, them = (k for _, k in ds)
    assert goc is None
    assert doi is not None and doi["doi_nguoi"][0]["truoc"]["staff_name"] == "Thành"
    assert xoa is not None and [o["id"] for o in xoa["xoa"]] == ["b"]
    assert them is not None and [o["id"] for o in them["them"]] == ["e"]
    # Trạng thái tại bản cuối: Hằng + Minh (Hà đã xoá).
    cuoi = ds[-1][0].trang_thai
    assert sorted(
        o["staff_name"] for o in cuoi.values() if o["status"] == "APPROVED"
    ) == ["Hằng", "Minh"]


def test_anh_ap_dung_lai_luon_la_mot_moc() -> None:
    a = [_o("a", "Thành")]
    anh = [
        {
            "id": 1,
            "loai": "GOC",
            "txid": 100,
            "luc": None,
            "boi_staff_id": None,
            "ca": a,
        },
        {
            "id": 2,
            "loai": "AP_DUNG_LAI",
            "txid": 200,
            "luc": None,
            "boi_staff_id": None,
            "ca": a,
        },
    ]
    ds = loc_phien_ban(dung_phien_ban(anh, []))
    assert [p.loai for p, _ in ds] == ["GOC", "AP_DUNG_LAI"]


def test_khong_anh_thi_khong_lich_su() -> None:
    assert (
        dung_phien_ban(
            [],
            [
                {
                    "id": 1,
                    "txid": 5,
                    "roster_id": "a",
                    "hanh_dong": "THEM",
                    "sau": _o("a", "A"),
                }
            ],
        )
        == []
    )


def test_anh_dang_chuoi_json_van_doc_duoc() -> None:
    """asyncpg trả jsonb dạng chuỗi khi chưa đặt codec."""
    import json

    anh = [
        {
            "id": 1,
            "loai": "GOC",
            "txid": 1,
            "luc": None,
            "boi_staff_id": None,
            "ca": json.dumps([_o("a", "A")]),
        }
    ]
    so = [
        {
            "id": 1,
            "txid": 2,
            "roster_id": "a",
            "hanh_dong": "DOI_NGUOI",
            "truoc": json.dumps(_o("a", "A")),
            "sau": json.dumps(_o("a", "B")),
            "luc": None,
            "boi_staff_id": None,
        }
    ]
    ds = loc_phien_ban(dung_phien_ban(anh, so))
    assert ds[-1][1] is not None and ds[-1][1]["doi_nguoi"][0]["o"]["staff_name"] == "B"
