"""Liên thông đơn thuốc quốc gia — adapter THẬT theo QĐ 808/QĐ-BYT, chạy trên một
máy chủ giả (httpx.MockTransport — hệ thống quốc gia không có sandbox công khai):
gói JSON đúng tên trường, đăng nhập bác sĩ + nhớ token, 401/422/5xx, trường QĐ 808
bắt buộc thêm, lệnh thêm bác sĩ vào cơ sở."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import httpx
import pytest

from clinicai.adapters.don_thuoc_quoc_gia.that import ProviderThat, da_ton_tai, goi_api
from clinicai.ports.don_thuoc_quoc_gia import BacSiKe, DongThuoc, GuiDonError
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import CauHinh, doc_cau_hinh
from clinicai.services.don_thuoc_quoc_gia.them_bac_si import chuan_bi
from clinicai.services.don_thuoc_quoc_gia.vong import dung_nha_cung_cap
from tests.unit.test_don_thuoc_quoc_gia import BS, ENV, ENV_THAT, MAT_KHAU, _goi


def test_goi_api_dung_ten_truong_qd_808() -> None:
    d = goi_api(_goi(), None)
    assert (d["loai_don_thuoc"], d["ma_don_thuoc"], d["gioi_tinh"]) == (
        "c",
        "79abc1a2b3c4-c",
        3,
    )
    assert d["ngay_sinh_benh_nhan"] == "17/05/1990"
    assert d["ngay_gio_ke_don"] == "2026-12-02 17:30:05"
    assert d["hinh_thuc_dieu_tri"] == 2 and d["signature"] == ""
    assert d["chan_doan"][0]["ten_chan_doan"] == "Viêm âm đạo"
    (t,) = d["thong_tin_don_thuoc"]
    assert t == {
        "ma_thuoc": "SP000004",
        "biet_duoc": "Cefdinir",
        "ten_thuoc": "Thuốc A",
        "don_vi_tinh": "viên",
        "so_luong": 2.0,
        "cach_dung": "Uống",
    }
    gt_khong_ro = goi_api(
        _goi(nguoi_benh=replace(_goi().nguoi_benh, gioi_tinh=None)), None
    )
    assert gt_khong_ro["gioi_tinh"] == 1


def _that(xu_ly: Any) -> tuple[ProviderThat, list[httpx.Request]]:
    goi: list[httpx.Request] = []

    def _h(req: httpx.Request) -> httpx.Response:
        goi.append(req)
        return xu_ly(req, len(goi))  # type: ignore[no-any-return]

    p = ProviderThat(
        url="https://api.donthuocquocgia.vn",
        ma_lien_thong_co_so="0179abc",
        mat_khau_bac_si={"01000123HCM": MAT_KHAU},
        client=httpx.AsyncClient(
            base_url="https://api.donthuocquocgia.vn",
            transport=httpx.MockTransport(_h),
        ),
    )
    return p, goi


def _dang_nhap_ok(req: httpx.Request) -> httpx.Response | None:
    if req.url.path == "/api/auth/dang-nhap-bac-si":
        return httpx.Response(200, json={"token": "tk", "token_type": "bearer"})
    return None


@pytest.mark.asyncio
async def test_that_dang_nhap_bac_si_roi_gui_nho_token() -> None:
    def xu_ly(req: httpx.Request, _n: int) -> httpx.Response:
        return _dang_nhap_ok(req) or httpx.Response(
            200, json={"success": "Gửi đơn thuốc thành công"}
        )

    p, goi = _that(xu_ly)
    assert (await p.gui(_goi(), None)).ma_tra_ve == "Gửi đơn thuốc thành công"
    await p.gui(_goi(ma_don="79abc9z9z9z9-c"), None)
    assert [r.url.path for r in goi] == [
        "/api/auth/dang-nhap-bac-si",
        "/api/v1/gui-don-thuoc",
        "/api/v1/gui-don-thuoc",
    ]
    assert json.loads(goi[0].content) == {
        "ma_lien_thong_bac_si": "01000123HCM",
        "ma_lien_thong_co_so_kham_chua_benh": "0179abc",
        "password": MAT_KHAU,
    }
    assert goi[1].headers["Authorization"] == "bearer tk"


@pytest.mark.asyncio
async def test_that_401_dang_nhap_lai_mot_lan() -> None:
    def xu_ly(req: httpx.Request, n: int) -> httpx.Response:
        return _dang_nhap_ok(req) or httpx.Response(401 if n == 2 else 200, json={})

    p, goi = _that(xu_ly)
    await p.gui(_goi(), None)
    assert [r.url.path for r in goi].count("/api/auth/dang-nhap-bac-si") == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ma", "than", "thanh_cong", "thu_lai"),
    [
        (422, {"danh_sach_cac_loi": ["Mã đơn thuốc đã tồn tại"]}, True, None),
        (422, {"danh_sach_cac_loi": ["Thiếu ngày sinh"]}, False, False),
        (500, {}, False, True),
        (503, {}, False, True),
    ],
)
async def test_that_tra_loi_loi(
    ma: int, than: dict[str, Any], thanh_cong: bool, thu_lai: bool | None
) -> None:
    def xu_ly(req: httpx.Request, _n: int) -> httpx.Response:
        return _dang_nhap_ok(req) or httpx.Response(ma, json=than)

    p, _ = _that(xu_ly)
    if thanh_cong:
        assert (await p.gui(_goi(), None)).ma_tra_ve
        return
    with pytest.raises(GuiDonError) as e:
        await p.gui(_goi(), None)
    assert e.value.thu_lai is thu_lai


@pytest.mark.parametrize(
    ("cau", "la_trung_don"),
    [
        ("['Mã đơn thuốc đã tồn tại']", True),
        ("ma_don_thuoc: trùng", True),
        ("['Bác sĩ đã tồn tại trong cơ sở']", False),
        ("['Trùng mã thuốc dòng 2']", False),
        ("['Thiếu ngày sinh']", False),
    ],
)
def test_da_ton_tai_chi_khi_noi_ve_ma_don(cau: str, la_trung_don: bool) -> None:
    assert da_ton_tai(cau) is la_trung_don


def test_repr_khong_lo_mat_khau() -> None:
    p, _ = _that(lambda r, n: httpx.Response(200))
    p._token["01000123HCM"] = ("tok-bi-mat", 0.0)
    assert MAT_KHAU not in repr(p) and "tok-bi-mat" not in repr(p)
    ch = doc_cau_hinh(ENV_THAT)
    assert isinstance(ch, CauHinh) and MAT_KHAU not in repr(ch)


@pytest.mark.asyncio
async def test_that_dang_nhap_bi_tu_choi_khong_thu_lai() -> None:
    def xu_ly(req: httpx.Request, _n: int) -> httpx.Response:
        return httpx.Response(
            422, json={"danh_sach_cac_loi": ["Bác sĩ chưa được thêm vào cơ sở"]}
        )

    p, _ = _that(xu_ly)
    with pytest.raises(GuiDonError) as e:
        await p.gui(_goi(), None)
    assert e.value.thu_lai is False and MAT_KHAU not in str(e.value)


def test_that_doi_them_truong_qd_808() -> None:
    p, _ = _that(lambda r, n: httpx.Response(200))
    assert p.thieu(_goi()) == []
    g = _goi(
        bac_si=BacSiKe(BS, "BS B", "1", "chua-co-mat-khau"),
        nguoi_benh=replace(_goi().nguoi_benh, ngay_sinh=None, dia_chi=None),
        thuoc=[DongThuoc("T", None, None, "1 hộp", None, None, "Uống")],
    )
    assert p.thieu(g) == [
        "mã liên thông + mật khẩu của bác sĩ (DTQG_BAC_SI)",
        "ngày sinh đầy đủ của người bệnh (API đòi ngày/tháng/năm)",
        "địa chỉ người bệnh",
        "mã thuốc dòng 1",
        "số lượng dạng số dòng 1",
        "đơn vị tính dòng 1",
    ]


def test_dung_nha_cung_cap_that_giu_mot_ban_nho_token() -> None:
    ch = doc_cau_hinh(ENV_THAT)
    assert isinstance(ch, CauHinh)
    a, b = dung_nha_cung_cap(ch), dung_nha_cung_cap(ch)
    assert a is not None and b is not None
    p, ky = a
    assert isinstance(p, ProviderThat) and ky.ten == "khong"
    assert p.mat_khau_bac_si == {"01000123HCM": MAT_KHAU}
    assert b[0] is p  # cùng bản → token bác sĩ được nhớ giữa các vòng


# ── lệnh thêm bác sĩ vào cơ sở (QĐ 808 III + IV) ─────────────────────────────
def test_them_bac_si_chuan_bi() -> None:
    ok = chuan_bi([BS], {**ENV_THAT, "DTQG_MAT_KHAU_CO_SO": "mk-co-so"})
    assert not isinstance(ok, str) and ok[1:] == ("01000123HCM", "mk-co-so")
    assert "DTQG_MAT_KHAU_CO_SO" in str(chuan_bi([BS], ENV_THAT))
    assert "that" in str(chuan_bi([BS], {**ENV, "DTQG_MAT_KHAU_CO_SO": "x"}))
    assert "chưa có" in str(
        chuan_bi([ENV["DTQG_LOCATION_ID"]], {**ENV_THAT, "DTQG_MAT_KHAU_CO_SO": "x"})
    )
    assert "Cách dùng" in str(chuan_bi([], ENV_THAT))


@pytest.mark.asyncio
async def test_them_bac_si_dang_nhap_co_so_roi_them() -> None:
    def xu_ly(req: httpx.Request, _n: int) -> httpx.Response:
        if req.url.path == "/api/auth/dang-nhap-co-so-kham-chua-benh":
            return httpx.Response(200, json={"token": "tk-cs", "token_type": "bearer"})
        return httpx.Response(200, json={"success": "Bạn đã thêm bác sĩ thành công"})

    p, goi = _that(xu_ly)
    assert await p.them_bac_si("01000123HCM", "mk-co-so") == (
        "Bạn đã thêm bác sĩ thành công"
    )
    assert json.loads(goi[0].content) == {
        "ma_lien_thong_co_so_kham_chua_benh": "0179abc",
        "password": "mk-co-so",
    }
    assert goi[1].url.path == "/api/v1/them-bac-si"
    assert goi[1].headers["Authorization"] == "bearer tk-cs"
    assert json.loads(goi[1].content) == {"ma_lien_thong_bac_si": "01000123HCM"}
