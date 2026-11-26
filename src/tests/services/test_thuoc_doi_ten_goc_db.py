"""PR C — đổi TÊN đơn vị gốc khi số tồn giữ nguyên nghĩa (kế hoạch
docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 15, 16; services/thuoc/doi_ten_goc.py).

Bất biến:
  G1  ca Ecanix "hộp 60 viên" → viên + hộp = 60: tồn giữ số, chữ lô đổi, 1 hộp vẫn
      550.000đ, 10 viên 91.667đ (hàm giá PR A), có sự kiện, hoàn tác về y như cũ;
  G2  từ chối khi còn chờ gán lô / tên có số / trùng tên / giá viên > giá hộp;
  G3  dòng đơn mở ghi chữ cũ vẫn là 1 hộp (tên gọi khác của đơn vị mẹ).
Tên thuốc giả, không dữ liệu khách thật.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.thuoc import doi_ten_goc
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_nhieu_don_vi_ban_db import _giao, _hd, _ke, _lo, _thu
from tests.services.test_thuoc_danh_muc_nhap_db import _goc_co_so, _me
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

D = Decimal


@pytest.fixture(autouse=True)
def _khong_tu_giao_khi_thu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_TU_GIAO_KHI_THU", "0")


@pytest.fixture(autouse=True)
def _thu_khong_cho_kho(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _doi(q: Quay, drug: str, **kw: Any) -> dict[str, Any]:
    """Đổi gốc đổi cả giá → người bấm cần quyền Sửa giá thuốc."""
    await q.pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, scope_type,"
        " tu_khoi, ly_do) VALUES ($1::uuid, $2::uuid, 'price.medicine.manage',"
        " 'CLINIC', 'gia_thuoc', 'test') ON CONFLICT DO NOTHING",
        CLINIC,
        q.duoc_si.staff_id,
    )
    tham = {"ten_moi": "viên", "don_vi_me": "hộp", "he_so_me": "60", **kw}
    return await doi_ten_goc.doi_ten_goc(q.pool, identity=q.duoc_si, thuoc=drug, **tham)


async def _hoan(q: Quay, su_kien: str, ly_do: str = "Đổi nhầm") -> dict[str, Any]:
    return await doi_ten_goc.hoan_tac_doi_ten_goc(
        q.pool, identity=q.duoc_si, su_kien_id=su_kien, ly_do=ly_do
    )


async def _anh(q: Quay, drug: str) -> tuple[Any, ...]:
    """Ảnh chụp mọi thứ lần đổi tên chạm tới — để so hoàn tác."""
    c = await q.pool.fetchrow(
        "SELECT don_vi_ban, unit_price FROM drug_catalog WHERE id = $1::uuid", drug
    )
    lo = await q.pool.fetch(
        "SELECT id, unit, quantity_on_hand FROM drug_batch"
        " WHERE drug_catalog_id = $1::uuid ORDER BY id",
        drug,
    )
    qd = await q.pool.fetch(
        "SELECT don_vi, he_so, gia, dang_ban, mac_dinh_ke FROM thuoc_quy_doi"
        " WHERE drug_catalog_id = $1::uuid ORDER BY don_vi",
        drug,
    )
    return (tuple(c), [tuple(r) for r in lo], [tuple(r) for r in qd])


async def test_doi_ten_goc_ecanix_ton_giu_so_gia_dung_su_kien_hoan_tac(q: Quay) -> None:
    drug = await _goc_co_so(q, "hộp 60 viên", 550_000)
    lo = await _lo(q, drug, 18_300, don_vi="hộp 60 viên")
    truoc = await _anh(q, drug)

    kq = await _doi(q, drug)
    assert (kq["so_lo"], kq["bi_danh"]) == (1, False)
    assert "1 hộp có 60 viên" in kq["cau"]
    c = await q.pool.fetchrow(
        "SELECT don_vi_ban, unit_price FROM drug_catalog WHERE id = $1::uuid", drug
    )
    assert (c["don_vi_ban"], c["unit_price"]) == ("viên", None)
    r = await q.pool.fetchrow(
        "SELECT unit, quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
    )
    assert (r["unit"], r["quantity_on_hand"]) == ("viên", D(18_300)), "tồn giữ số"
    assert await _me(q, drug) == ["hộp"]

    await _ke(q, drug, "1")
    await _ke(q, drug, "10 viên")
    hd = await _hd(q)
    assert sorted(d.thanh_tien for d in hd.dong) == [91_667, 550_000]

    ev = await q.pool.fetchrow(
        "SELECT event_type, payload->>'ten_cu' AS cu, payload->>'ten_moi' AS moi"
        " FROM domain_event WHERE event_id = $1::uuid",
        kq["su_kien_id"],
    )
    assert tuple(ev) == ("drug_unit.base_renamed", "hộp 60 viên", "viên")

    await _hoan(q, kq["su_kien_id"])
    assert await _anh(q, drug) == truoc, "hoàn tác đưa về y như cũ"
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE causation_id = $1::uuid"
            " AND event_type = 'drug_unit.base_rename_undone'",
            kq["su_kien_id"],
        )
        == 1
    )
    with pytest.raises(ConflictError, match="đã được hoàn tác"):
        await _hoan(q, kq["su_kien_id"], "lần 2")


async def test_hoan_tac_ca_lo_nhap_sau_khi_doi(q: Quay) -> None:
    drug = await _goc_co_so(q, "hộp 60 viên", 550_000)
    kq = await _doi(q, drug)
    lo = await _lo(q, drug, 120, don_vi="viên")
    await _hoan(q, kq["su_kien_id"])
    r = await q.pool.fetchrow(
        "SELECT unit, quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
    )
    assert (r["unit"], r["quantity_on_hand"]) == ("hộp 60 viên", D(120))
    assert await _me(q, drug) == []


async def test_dong_don_cu_ghi_chu_cu_van_la_mot_hop(q: Quay) -> None:
    """Dòng đơn mở ghi chữ cũ "Hộp/60v" (nhận không ra bằng chữ đầu): giữ chữ cũ làm
    tên gọi khác của hộp → vẫn 550.000đ, hệ số 60."""
    drug = await _goc_co_so(q, "Hộp/60v", 550_000)
    await _ke(q, drug, "1 Hộp/60v")
    kq = await _doi(q, drug)
    assert kq["bi_danh"] is True
    d = (await _hd(q)).dong[0]
    assert (d.thanh_tien, d.he_so) == (550_000, 60)


async def test_doi_ten_bi_tu_choi_khi_con_cho_gan_lo(q: Quay) -> None:
    drug = await _goc_co_so(q, "hộp 60 viên", 550_000)
    rx = await _ke(q, drug, "1")
    await _thu(q)
    await _giao(q, rx, 1)  # kho trống → chờ gán lô
    with pytest.raises(ConflictError, match="chờ gán lô"):
        await _doi(q, drug)
    assert (
        await q.pool.fetchval("SELECT don_vi_ban FROM drug_catalog WHERE id=$1", drug)
        == "hộp 60 viên"
    )


@pytest.mark.parametrize(
    ("kw", "loi"),
    [
        ({"ten_moi": "viên 5"}, "có chữ số"),
        ({"ten_moi": ""}, "Nhập tên"),
        ({"don_vi_me": "viên"}, "phải khác"),
        ({"he_so_me": "1"}, "nhiều hơn 1"),
        ({"he_so_me": "abc"}, "Số quy đổi"),
        ({"he_so_me": "-60"}, "Số quy đổi"),
        ({"gia_goc_moi": "600000"}, "cao hơn giá 1 hộp"),
        ({"gia_goc_moi": "abc"}, "phải là một con số"),
    ],
)
async def test_doi_ten_dau_vao_sai_cau_tieng_viet(
    q: Quay, kw: dict[str, Any], loi: str
) -> None:
    drug = await _goc_co_so(q, "hộp 60 viên", 550_000)
    with pytest.raises(ValidationError, match=loi):
        await _doi(q, drug, **kw)


async def test_doi_ten_trung_ten_cu_bi_tu_choi(q: Quay) -> None:
    drug = await _goc_co_so(q, "lọ", 550_000)
    with pytest.raises(ValidationError, match="giống tên"):
        await _doi(q, drug, ten_moi="Lọ")


async def test_doi_ten_kem_gia_vien_khai_tay(q: Quay) -> None:
    drug = await _goc_co_so(q, "hộp 60 viên", 550_000)
    await _doi(q, drug, gia_goc_moi="9.500")
    await _ke(q, drug, "10 viên")
    assert (await _hd(q)).dong[0].thanh_tien == 95_000
