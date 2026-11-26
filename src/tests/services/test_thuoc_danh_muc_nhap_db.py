"""PR C — Danh mục + Nhập thuốc nói bằng lời người (kế hoạch
docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 2, 15, 16).

Bất biến:
  N1  nhập chỉ theo đơn vị ĐÃ KHAI; câu "1 hộp có bao nhiêu viên?" + "47 hộp =
      1.410 viên"; đơn vị chưa khai → từ chối, không tạo lô, không tự nhớ đơn vị;
  N2  thuốc gốc "hộp 30 viên" nhập "hộp" là ĐÚNG đơn vị gốc — không hỏi đổi (ca Aktiv);
  N3  hệ số rác → câu tiếng Việt, không 500;
  D1  tên đơn vị MỚI không có chữ số; tên cũ đang dùng vẫn lưu lại được;
  D2  một thuốc tối đa MỘT đơn vị mặc định khi kê; tắt bán đơn vị đó → câu tiếng Việt;
  G1  đổi TÊN gốc (ca Ecanix "hộp 60 viên" → viên + hộp = 60): tồn giữ số, chữ lô đổi,
      1 hộp vẫn 550.000đ, 10 viên 91.667đ (hàm PR A), có sự kiện, hoàn tác về như cũ;
  G2  đổi tên bị từ chối khi còn chờ gán lô / tên có số / giá viên > giá hộp.
Tên thuốc giả, không dữ liệu khách thật.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.thuoc.don_vi_nhap import xem_truoc_quy_doi
from tests.services.test_nhieu_don_vi_ban_db import _lo, _luu
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


def _ten_gia(goc: str) -> str:
    return f"{goc} {uuid.uuid4().hex[:8]}"


async def _vien_hop(q: Quay, he_so: int = 30, gia_hop: int = 410_000) -> str:
    """Gốc viên 15.000đ, hộp = `he_so` viên — không cờ mẹ."""
    return await _luu(
        q,
        _ten_gia("Vien hop"),
        gia=15_000,
        don_vi_ban="viên",
        cac_don_vi=[{"don_vi": "hộp", "he_so": he_so, "gia": gia_hop}],
    )


async def _goc_co_so(q: Quay, goc: str, gia: int) -> str:
    """Dữ liệu CŨ như prod: gốc mang số ("hộp 60 viên") — ghi thẳng vì form mới chặn."""
    drug = await _luu(q, _ten_gia("Ecanix thu"), gia=gia, don_vi_ban="hộp")
    await q.pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = $2 WHERE id = $1::uuid", drug, goc
    )
    return drug


async def _xem(q: Quay, drug: str, unit: str, **kw: Any) -> dict[str, Any]:
    return await xem_truoc_quy_doi(
        q.pool, identity=q.duoc_si, drug_catalog_id=drug, unit=unit, **kw
    )


async def _so_lo(q: Quay, drug: str) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_batch WHERE drug_catalog_id = $1::uuid", drug
        )
    )


async def _sua(q: Quay, drug: str, **kw: Any) -> dict[str, Any]:
    r = await q.pool.fetchrow(
        "SELECT name_raw, unit_price, don_vi_ban FROM drug_catalog WHERE id=$1", drug
    )
    goc = {"ten": r["name_raw"], "gia": r["unit_price"], "don_vi_ban": r["don_vi_ban"]}
    return await PharmacyService(q.pool).luu_thuoc(
        identity=q.duoc_si, drug_catalog_id=drug, **{**goc, **kw}
    )


async def _cac_dong(q: Quay, drug: str) -> list[dict[str, Any]]:
    ds = await PharmacyService(q.pool).danh_muc(identity=q.duoc_si)
    return list(next(t for t in ds if t["id"] == drug)["cac_don_vi"])


async def _me(q: Quay, drug: str) -> list[str]:
    return [
        r["don_vi"]
        for r in await q.pool.fetch(
            "SELECT don_vi FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid"
            " AND mac_dinh_ke",
            drug,
        )
    ]


# ── N1–N3: nhập ────────────────────────────────────────────────────────────


async def test_xem_truoc_noi_bang_loi_nguoi_hai_chieu(q: Quay) -> None:
    drug = await _vien_hop(q)
    kq = await _xem(q, drug, "hộp", so_luong="47")
    assert kq["cau_hoi"] == "1 hộp có bao nhiêu viên?"
    assert kq["ket_qua"] == "47 hộp = 1.410 viên"
    assert kq["so_luong_quy_doi"] == D(1410)
    assert [d["don_vi"] for d in kq["cac_don_vi"]] == ["viên", "hộp"]
    trong = await _xem(q, drug, "")
    assert [d["don_vi"] for d in trong["cac_don_vi"]] == ["viên", "hộp"]
    assert trong["cau_hoi"] is None and trong["ket_qua"] is None


async def test_nhap_47_hop_thanh_1410_vien(q: Quay) -> None:
    drug = await _vien_hop(q)
    kq = await PharmacyService(q.pool).nhap_lo(
        identity=q.duoc_si,
        drug_catalog_id=drug,
        so_luong=47,
        batch_code=f"LO-{uuid.uuid4().hex[:10]}",
        expiry_date=None,
        unit="Hộp",
    )
    r = await q.pool.fetchrow(
        "SELECT unit, quantity_on_hand FROM drug_batch WHERE id = $1::uuid",
        kq["drug_batch_id"],
    )
    assert (r["unit"], r["quantity_on_hand"]) == ("viên", D(1410))


async def test_don_vi_chua_khai_bi_tu_choi_khong_tao_lo_khong_tu_nho(q: Quay) -> None:
    drug = await _vien_hop(q)
    xem = await _xem(q, drug, "lọ", so_luong="2")
    assert xem["loi"] and "chưa khai đơn vị “lọ”" in xem["loi"]
    assert xem["ket_qua"] is None
    with pytest.raises(ValidationError, match="Danh mục kho"):
        await _lo(q, drug, 2, don_vi="lọ", han=None)
    with pytest.raises(ValidationError, match="chưa khai"):
        await _lo(q, drug, 2, don_vi="lọ", han=None)
    assert await _so_lo(q, drug) == 0
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid"
            " AND don_vi = 'lọ'",
            drug,
        )
        == 0
    )


async def test_goc_hop_30_vien_nhap_hop_khong_hoi_doi(q: Quay) -> None:
    """Ca Aktiv: câu cũ "1 hộp = ? hộp 30 viên" làm 47 hộp thành 1.410."""
    drug = await _goc_co_so(q, "hộp 30 viên", 410_000)
    xem = await _xem(q, drug, "", so_luong="47")
    assert [d["don_vi"] for d in xem["cac_don_vi"]] == ["hộp 30 viên"]
    xem = await _xem(q, drug, "hộp 30 viên", so_luong="47")
    assert xem["can_doi"] is False and xem["cau_hoi"] is None
    # Gõ "hộp" (không có trong danh sách): từ chối, KHÔNG hỏi "1 hộp = ? hộp 30 viên".
    go = await _xem(q, drug, "hộp", so_luong="47")
    assert go["loi"] and "“hộp 30 viên”" in go["loi"] and go["ket_qua"] is None
    lo = await _lo(q, drug, 47, don_vi="hộp 30 viên")
    r = await q.pool.fetchrow(
        "SELECT unit, quantity_on_hand FROM drug_batch WHERE id = $1::uuid", lo
    )
    assert (r["unit"], r["quantity_on_hand"]) == ("hộp 30 viên", D(47))


@pytest.mark.parametrize(
    "rac", ["0", "-3", "abc", "nan", "inf", "1e12", "10001", "0.0001", [], {}]
)
async def test_he_so_rac_cau_tieng_viet(q: Quay, rac: Any) -> None:
    drug = await _vien_hop(q)
    with pytest.raises(ValidationError, match="Số quy đổi"):
        await _xem(q, drug, "hộp", he_so=rac, so_luong="2")


async def test_he_so_go_lech_10_lan_phai_xac_nhan(q: Quay) -> None:
    drug = await _vien_hop(q)
    xem = await _xem(q, drug, "hộp", he_so="301", so_luong="1")
    assert xem["can_xac_nhan"] is True
    with pytest.raises(ValidationError, match="lệch hơn 10 lần"):
        await PharmacyService(q.pool).nhap_lo(
            identity=q.duoc_si,
            drug_catalog_id=drug,
            so_luong=1,
            batch_code=f"LO-{uuid.uuid4().hex[:10]}",
            expiry_date=None,
            unit="hộp",
            he_so="301",
        )


# ── D1: tên đơn vị không có số ─────────────────────────────────────────────


async def test_ten_don_vi_moi_co_so_bi_chan(q: Quay) -> None:
    drug = await _luu(q, _ten_gia("Thu so"), gia=10_000, don_vi_ban="viên")
    with pytest.raises(ValidationError, match="có chữ số"):
        await _sua(q, drug, cac_don_vi=[{"don_vi": "hộp 30 viên", "he_so": 30}])
    with pytest.raises(ValidationError, match="có chữ số"):
        await _luu(q, _ten_gia("Thu goc so"), gia=10_000, don_vi_ban="hộp 60 viên")
    with pytest.raises(ValidationError, match="có chữ số"):
        await _sua(q, drug, don_vi_ban="vỉ 10 viên")


async def test_goc_cu_co_so_van_luu_duoc_khi_sua_cho_khac(q: Quay) -> None:
    drug = await _goc_co_so(q, "hộp 60 viên", 550_000)
    await _sua(q, drug, cach_dung="Ngày uống 1 viên")
    assert (
        await q.pool.fetchval("SELECT don_vi_ban FROM drug_catalog WHERE id=$1", drug)
        == "hộp 60 viên"
    )


# ── D2: mặc định khi kê ────────────────────────────────────────────────────


async def test_dat_doi_bo_don_vi_mac_dinh_ke_toi_da_mot(q: Quay) -> None:
    drug = await _luu(
        q,
        _ten_gia("Mac dinh"),
        gia=10_000,
        don_vi_ban="viên",
        cac_don_vi=[
            {"don_vi": "vỉ", "he_so": 10, "gia": 95_000},
            {"don_vi": "hộp", "he_so": 30, "gia": 280_000},
        ],
    )
    dong = await _cac_dong(q, drug)
    assert [d["mac_dinh_ke"] for d in dong] == [False, False]

    def gui(me: str) -> list[dict[str, Any]]:
        return [{**d, "mac_dinh_ke": d["don_vi"] == me} for d in dong]

    await _sua(q, drug, cac_don_vi=gui("hộp"))
    assert await _me(q, drug) == ["hộp"]
    dong = await _cac_dong(q, drug)
    assert {d["don_vi"]: d["mac_dinh_ke"] for d in dong} == {"vỉ": False, "hộp": True}
    await _sua(q, drug, cac_don_vi=gui("vỉ"))
    assert await _me(q, drug) == ["vỉ"]
    dong = await _cac_dong(q, drug)
    await _sua(q, drug, cac_don_vi=gui(""))  # gốc là mặc định
    assert await _me(q, drug) == []
    dong = await _cac_dong(q, drug)
    with pytest.raises(ValidationError, match="MỘT đơn vị"):
        await _sua(q, drug, cac_don_vi=[{**d, "mac_dinh_ke": True} for d in dong])
    assert await _me(q, drug) == []
    # Không gửi khoá `mac_dinh_ke` = giữ nguyên.
    await _sua(q, drug, cac_don_vi=gui("hộp"))
    dong = await _cac_dong(q, drug)
    bo_khoa = [{k: v for k, v in d.items() if k != "mac_dinh_ke"} for d in dong]
    await _sua(q, drug, cac_don_vi=bo_khoa)
    assert await _me(q, drug) == ["hộp"]


async def test_tat_ban_don_vi_mac_dinh_ke_cau_tieng_viet(q: Quay) -> None:
    drug = await _vien_hop(q)
    dong = await _cac_dong(q, drug)
    await _sua(q, drug, cac_don_vi=[{**dong[0], "mac_dinh_ke": True}])
    dong = await _cac_dong(q, drug)
    with pytest.raises(ValidationError, match="đang là đơn vị mặc định khi kê"):
        await _sua(q, drug, cac_don_vi=[{**dong[0], "dang_ban": False}])
    assert await _me(q, drug) == ["hộp"]
    with pytest.raises(ValidationError, match="đang là đơn vị mặc định khi kê"):
        await _sua(
            q,
            drug,
            cac_don_vi=[{**dong[0], "dang_ban": False, "mac_dinh_ke": True}],
        )
