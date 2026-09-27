"""Phiếu khám v2 gọn (đợt 3, 27/09/2026) — thuộc tính hiển thị + bản xuất bản.

Góp ý phòng khám: B1 tiền sử thu gọn (`thu_gon`), B2 dị ứng thuốc Có/Không
(`hien_khi`), B3 bảng CLS gõ tay gập (`gap`). Canh ba lời hứa:

1. Khung khai SAI thuộc tính mới thì bị chặn lúc kiểm, với câu lỗi nói rõ ô nào.
2. v2 GIỮ NGUYÊN mọi `ma` của v1 (tập mã v1 ⊆ v2) — phiếu cũ đọc được, dữ liệu
   cũ lưu vào v2 không bị "ô không có trong phiếu".
3. Migration xuất bản ĐÚNG khung trong JSON (máy chủ đọc DB, test đọc JSON — hai
   bản lệch là test xanh mà màn sai).
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from clinicai.core.exceptions import ValidationError
from clinicai.phieu_kham.khung import (
    FORM_IDS,
    cac_o,
    dinh_nghia,
    kiem_du_lieu,
    kiem_khung,
)

GOC = Path(__file__).resolve().parents[3]
MIG = GOC / "supabase" / "migrations"
V1 = MIG / "20260924000008_phieu_kham_luot.sql"
V2 = MIG / "20260928000020_phieu_kham_v2_gon.sql"

DOI = ("NT", "HMVS", "PK", "SK", "NK")


def _khung_trong_sql(sql: str) -> dict[str, list[dict[str, Any]]]:
    """form_id → khung, từ các câu INSERT của migration (v1 và v2 cùng khuôn)."""
    ra: dict[str, list[dict[str, Any]]] = {}
    # Câu INSERT (không phải câu so `IS DISTINCT FROM` của CTE `cu`).
    for m in re.finditer(
        r"SELECT (?:c\.id|cu\.clinic_id), '(\w+)',[^$]*\$khung\$(.*?)\$khung\$",
        sql,
        re.S,
    ):
        ra[m.group(1)] = json.loads(m.group(2))
    return ra


def _moi_ma(khung: list[dict[str, Any]]) -> set[str]:
    ra: set[str] = set()
    for ma, o in cac_o(khung).items():
        ra.add(ma)
        ra.update(x["ma"] for x in o.get("lua_chon") or [])
    return ra


V1_KHUNG = _khung_trong_sql(V1.read_text(encoding="utf-8"))
V2_KHUNG = _khung_trong_sql(V2.read_text(encoding="utf-8"))


# ── 2. Giữ nguyên mọi mã ────────────────────────────────────────────────────
def test_doc_du_khung_hai_migration() -> None:
    assert set(V1_KHUNG) == set(FORM_IDS)
    assert set(V2_KHUNG) == set(DOI)


@pytest.mark.parametrize("form_id", FORM_IDS)
def test_v2_giu_moi_ma_cua_v1(form_id: str) -> None:
    v1 = _moi_ma(V1_KHUNG[form_id])
    v2 = _moi_ma(dinh_nghia(form_id)["khung"])
    assert v1 <= v2, sorted(v1 - v2)
    # Mục và thứ tự mục không đổi — KHOI_PHIEU / bản in không phải theo.
    assert [m["ma"] for m in V1_KHUNG[form_id]] == [
        m["ma"] for m in dinh_nghia(form_id)["khung"]
    ]


@pytest.mark.parametrize("form_id", FORM_IDS)
def test_o_v1_giu_kieu_va_lua_chon(form_id: str) -> None:
    """Giữ mã chưa đủ: đổi kiểu ô hay mã lựa chọn là dữ liệu cũ mất nghĩa."""
    cu = cac_o(V1_KHUNG[form_id])
    moi = cac_o(dinh_nghia(form_id)["khung"])
    for ma, o in cu.items():
        assert moi[ma]["kieu"] == o["kieu"], ma
        assert moi[ma].get("lua_chon") == o.get("lua_chon"), ma
        assert moi[ma].get("nhom") == o.get("nhom"), ma


def test_chi_them_dung_cac_o_di_ung() -> None:
    them = {
        f: sorted(set(cac_o(dinh_nghia(f)["khung"])) - set(cac_o(V1_KHUNG[f])))
        for f in FORM_IDS
    }
    assert them == {
        "NT": ["nt_allergy_co"],
        "HMVS": ["hmvs_allergy_co"],
        "PK": ["pk_allergy", "pk_allergy_co"],
        "SK": ["sk_allergy_co"],
        "NK": ["nk_allergy", "nk_allergy_co"],
        "THU_THUAT": [],
        "SAN_CHAU": [],
    }
    for f, ds in them.items():
        o = cac_o(dinh_nghia(f)["khung"])
        assert all(o[m].get("them_sau_nguon") for m in ds), f


@pytest.mark.parametrize("form_id", DOI)
def test_migration_v2_bang_dung_json(form_id: str) -> None:
    assert V2_KHUNG[form_id] == dinh_nghia(form_id)["khung"]


@pytest.mark.parametrize("form_id", ("THU_THUAT", "SAN_CHAU"))
def test_phieu_khong_doi_van_la_v1(form_id: str) -> None:
    assert dinh_nghia(form_id)["khung"] == V1_KHUNG[form_id]


def test_du_lieu_phieu_v1_luu_vao_khung_v2_duoc() -> None:
    """Mọi khoá v1 vẫn lưu được vào v2 — kể cả dị ứng gõ chữ từ trước."""
    khung = dinh_nghia("NT")["khung"]
    sach, cb = kiem_du_lieu(
        khung,
        {
            "nt_allergy": {"gia_tri": "Penicillin", "nguon": "USER"},
            "nt_para": {"gia_tri": "1001", "nguon": "USER"},
            "nt_allergy_co": {"gia_tri": "nt_allergy_co_2", "nguon": "USER"},
        },
    )
    assert cb == [] and sach["nt_allergy_co"]["gia_tri"] == "nt_allergy_co_2"


# ── Khung v2 khai đúng góp ý ────────────────────────────────────────────────
@pytest.mark.parametrize("form_id", DOI)
def test_di_ung_co_khong_va_chi_tiet_hien_khi_co(form_id: str) -> None:
    t = form_id.lower()
    o = cac_o(dinh_nghia(form_id)["khung"])
    chon = o[f"{t}_allergy_co"]
    assert chon["kieu"] == "chon"
    assert [(x["ma"], x["ten"]) for x in chon["lua_chon"]] == [
        (f"{t}_allergy_co_1", "Có"),
        (f"{t}_allergy_co_2", "Không"),
    ]
    assert o[f"{t}_allergy"]["hien_khi"] == {
        "o": f"{t}_allergy_co",
        "la": f"{t}_allergy_co_1",
    }
    assert o[f"{t}_allergy"]["ten"] == "Chi tiết dị ứng thuốc"
    # Ô chọn đứng NGAY TRƯỚC ô chi tiết, cùng nhóm.
    ds = list(o)
    assert ds.index(f"{t}_allergy_co") + 1 == ds.index(f"{t}_allergy")
    assert chon.get("nhom") == o[f"{t}_allergy"].get("nhom")


def test_nhom_tien_su_thu_gon_bang_cls_gap() -> None:
    def nhom(form_id: str, thuoc_tinh: str) -> set[str]:
        return {
            b["nhom"]
            for b in cac_o(dinh_nghia(form_id)["khung"]).values()
            if b.get(thuoc_tinh)
        }

    assert nhom("NT", "thu_gon") == {"2. Tiền sử phụ khoa và sản khoa"}
    assert nhom("HMVS", "thu_gon") == {
        "2. Tiền sử Phụ khoa, Sản khoa (vợ)",
        "3. Tiền sử Sản khoa (chồng)",
    }
    assert nhom("PK", "thu_gon") == {"Tiền sử bệnh", "Tiền sử phụ khoa"}
    assert nhom("SK", "thu_gon") == {"Tiền sử"}
    assert nhom("NK", "thu_gon") == {"Tiền sử nam khoa / sinh dục – tiết niệu"}
    assert {f: nhom(f, "gap") for f in DOI} == {
        "NT": {"6. Cận lâm sàng"},
        "HMVS": {"10. Cận lâm sàng"},
        "PK": {"Cận lâm sàng"},
        "SK": {"Cận lâm sàng"},
        "NK": {"Cận lâm sàng liên quan"},
    }
    # Thu gọn chỉ dành cho ô GÕ TAY — ô chọn luôn hiện.
    for f in DOI:
        for b in cac_o(dinh_nghia(f)["khung"]).values():
            if b.get("thu_gon"):
                assert b["kieu"] not in {"chon", "nhieu_chon"}, b["ma"]


# ── 1. Kiểm kiểu thuộc tính mới ─────────────────────────────────────────────
def _khung(*o: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"ma": "B", "ten": "B", "block": list(o)}]


CHON = {
    "ma": "x_co",
    "ten": "Dị ứng thuốc",
    "kieu": "chon",
    "lua_chon": [{"ma": "x_co_1", "ten": "Có"}, {"ma": "x_co_2", "ten": "Không"}],
}


def test_khung_hop_le_qua_kiem() -> None:
    kiem_khung(
        _khung(
            {"ma": "a", "ten": "A", "kieu": "text", "nhom": "N", "thu_gon": True},
            CHON,
            {
                "ma": "x",
                "ten": "X",
                "kieu": "doan_van",
                "hien_khi": {"o": "x_co", "la": "x_co_1"},
            },
            {"ma": "b", "ten": "B", "kieu": "text", "nhom": "CLS", "gap": True},
            {"ma": "c", "ten": "C", "kieu": "text", "nhom": "CLS", "gap": True},
        ),
        form_id="NT",
    )


def test_hien_khi_tro_o_dung_sau_van_duoc() -> None:
    """Ô điều khiển đứng SAU ô bị điều khiển vẫn hợp lệ — kiểm sau khi đủ ô."""
    kiem_khung(
        _khung(
            {
                "ma": "x",
                "ten": "X",
                "kieu": "text",
                "hien_khi": {"o": "x_co", "la": "x_co_2"},
            },
            CHON,
        ),
        form_id="NT",
    )


@pytest.mark.parametrize(
    ("o", "loi"),
    [
        ({"thu_gon": "true"}, "thu_gon` phải là true/false"),
        ({"thu_gon": 1}, "thu_gon` phải là true/false"),
        ({"gap": "có"}, "gap` phải là true/false"),
        ({"hien_khi": "x_co"}, "hien_khi` phải có dạng"),
        ({"hien_khi": {"o": "x_co"}}, "hien_khi` phải có dạng"),
        ({"hien_khi": {"o": "x_co", "la": 1}}, "hien_khi` phải có dạng"),
        ({"hien_khi": {"o": "x_co", "la": "Có"}}, "hien_khi` phải có dạng"),
        ({"hien_khi": {"o": "khong_co", "la": "x_co_1"}}, "trỏ ô không có"),
        ({"hien_khi": {"o": "x", "la": "x_co_1"}}, "trỏ ô không có"),
        ({"hien_khi": {"o": "x_co", "la": "x_co_9"}}, "không có lựa chọn"),
        ({"hien_khi": {"o": "a", "la": "x_co_1"}}, "phải trỏ một ô chọn"),
        (
            {"thu_gon": True, "hien_khi": {"o": "x_co", "la": "x_co_1"}},
            "một ô chỉ một cách ẩn",
        ),
        ({"them_sau_nguon": ""}, "them_sau_nguon"),
        ({"them_sau_nguon": True}, "them_sau_nguon"),
    ],
)
def test_thuoc_tinh_sai_bi_chan_ro_o_nao(o: dict[str, Any], loi: str) -> None:
    with pytest.raises(ValidationError, match=re.escape(loi)) as e:
        kiem_khung(
            _khung(
                {"ma": "a", "ten": "A", "kieu": "text"},
                CHON,
                {"ma": "x", "ten": "X", "kieu": "text", **o},
            ),
            form_id="NT",
        )
    assert "NT.x" in str(e.value)


def test_o_trong_bang_khong_thu_gon_duoc() -> None:
    bang = {"ma": "t", "ten": "Bảng", "cot": ["KQ"]}
    with pytest.raises(ValidationError, match="ô trong bảng"):
        kiem_khung(
            _khung(
                {"ma": "a", "ten": "A", "kieu": "text", "bang": bang, "thu_gon": True}
            ),
            form_id="NT",
        )


def test_gap_nua_nhom_bi_chan() -> None:
    with pytest.raises(ValidationError, match="gap` phải giống nhau"):
        kiem_khung(
            _khung(
                {"ma": "a", "ten": "A", "kieu": "text", "nhom": "CLS", "gap": True},
                {"ma": "b", "ten": "B", "kieu": "text", "nhom": "CLS"},
            ),
            form_id="NT",
        )


def test_hai_nhom_khac_ten_gap_khac_nhau_van_duoc() -> None:
    kiem_khung(
        _khung(
            {"ma": "a", "ten": "A", "kieu": "text", "nhom": "Tiền sử"},
            {"ma": "b", "ten": "B", "kieu": "text", "nhom": "CLS", "gap": True},
        ),
        form_id="NT",
    )


def test_ban_that_sua_sai_bi_chan() -> None:
    """Khung thật v2, làm hỏng một hien_khi → lỗi (lưới cho người sửa JSON tay)."""
    khung = copy.deepcopy(dinh_nghia("PK")["khung"])
    o = next(b for m in khung for b in m["block"] if b["ma"] == "pk_allergy")
    o["hien_khi"]["la"] = "pk_allergy_co_3"
    with pytest.raises(ValidationError, match="không có lựa chọn"):
        kiem_khung(khung, form_id="PK")
