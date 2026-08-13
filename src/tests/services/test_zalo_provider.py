"""Ranh giới của provider Zalo: không rò dữ liệu, và không nói dối.

HAI TÍNH CHẤT, VÀ CẢ HAI ĐỀU CÓ TIỀN LỆ HỎNG:

  1. NHẬT KÝ KHÔNG MANG SỐ ĐIỆN THOẠI HAY NỘI DUNG. Nhật ký đi ra ngoài máy;
     một dòng log mang "0989862764 — chị Lan đang đau bụng" là hồ sơ bệnh nhân
     nằm trong hệ thống giám sát.
  2. `da_gui` CHỈ ĐÚNG KHI ZALO NHẬN. Bản cũ trả `{"ok": True, "stub": True}`
     cho một việc chưa hề xảy ra. Ai đọc `ok` để quyết định cũng kết luận sai,
     và cách hỏng là: phòng khám tin tin nhắn đã tới, không ai gọi điện nữa,
     bệnh nhân không đến.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from clinicai.services.providers import zalo


class _TraLoi:
    """Đủ giống httpx.Response cho những gì gui_zns đọc tới."""

    def __init__(self, than: Any, status: int = 200, hong_json: bool = False) -> None:
        self._than = than
        self.status_code = status
        self._hong = hong_json

    def json(self) -> Any:
        if self._hong:
            raise ValueError("không phải JSON")
        return self._than


def _gia_lap_post(monkeypatch: pytest.MonkeyPatch, tra_loi: Any) -> dict[str, Any]:
    """Thay lời gọi mạng, và giữ lại đúng những gì đã gửi đi."""
    da_gui: dict[str, Any] = {}

    class _Client:
        def __init__(self, *_a: Any, **_k: Any) -> None: ...

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, **kw: Any) -> Any:
            da_gui.update({"url": url, **kw})
            if isinstance(tra_loi, Exception):
                raise tra_loi
            return tra_loi

    # Vá qua chính module httpx, không qua thuộc tính của zalo: mypy không coi
    # `zalo.httpx` là thứ được xuất ra, và một `# type: ignore` ở đây sẽ che
    # luôn những lỗi thật sau này.
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return da_gui


# ── Số điện thoại ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        ("0989862764", "84989862764"),
        ("84989862764", "84989862764"),
        ("098 986 2764", "84989862764"),
        ("+84 989 862 764", "84989862764"),
    ],
)
def test_chuan_hoa_sdt(vao: str, ra: str) -> None:
    """ZNS đòi 84xxxxxxxxx; phòng khám lưu 0xxxxxxxxx.

    Gửi nguyên số có `0` đứng đầu thì Zalo trả -136 và người trực đọc thành
    "số sai" — trong khi số hoàn toàn đúng, chỉ sai định dạng.
    """
    assert zalo.chuan_hoa_sdt(vao) == ra


@pytest.mark.parametrize("xau", ["", "abc", "0989", "0989862764123"])
def test_sdt_khong_hop_le_thi_tra_none(xau: str) -> None:
    assert zalo.chuan_hoa_sdt(xau) is None


# ── Chưa cấu hình ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chua_co_token_thi_noi_chua_cau_hinh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZALO_ZNS_ACCESS_TOKEN", raising=False)
    d = await zalo.gui_zns(sdt="0989862764", template_id="t1", du_lieu={})
    assert d["da_gui"] is False
    assert d["ly_do"] == "CHUA_CAU_HINH"


@pytest.mark.asyncio
async def test_chua_co_template_thi_cung_noi_ra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    d = await zalo.gui_zns(sdt="0989862764", template_id="", du_lieu={})
    assert d["da_gui"] is False and d["ly_do"] == "CHUA_CAU_HINH"


def test_dang_bat_theo_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZALO_ZNS_ACCESS_TOKEN", raising=False)
    assert zalo.dang_bat() is False
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    assert zalo.dang_bat() is True


# ── Gọi thật ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gui_thanh_cong(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    da_gui = _gia_lap_post(
        monkeypatch,
        _TraLoi({"error": 0, "message": "Success", "data": {"msg_id": "m1"}}),
    )
    d = await zalo.gui_zns(
        sdt="0989862764", template_id="t1", du_lieu={"ten": "Lan"}, ma_theo_doi="bn1"
    )
    assert d["da_gui"] is True and d["msg_id"] == "m1"
    # Token đi ở HEADER `access_token` — không phải Bearer, không phải query.
    assert da_gui["headers"] == {"access_token": "tok"}
    assert da_gui["json"]["phone"] == "84989862764"
    assert da_gui["json"]["tracking_id"] == "bn1"


@pytest.mark.asyncio
async def test_zalo_tra_http_200_cho_loi_nghiep_vu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Đây là cái bẫy lớn nhất của API này.

    Zalo trả HTTP **200** kèm `error: -124`. Một `raise_for_status()` ở đây sẽ
    cho MỌI lỗi đi lọt, và hệ thống ghi "đã gửi" cho từng tin bị từ chối.
    """
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    _gia_lap_post(
        monkeypatch, _TraLoi({"error": -124, "message": "invalid token"}, 200)
    )
    d = await zalo.gui_zns(sdt="0989862764", template_id="t1", du_lieu={})
    assert d["da_gui"] is False
    assert d["ma_loi"] == -124
    # Và dịch sang tiếng Việt: người trực đọc "-124" thì phải đi hỏi kỹ thuật.
    assert "hết hạn" in d["chi_tiet"] or "không hợp lệ" in d["chi_tiet"]


@pytest.mark.asyncio
async def test_het_gio_noi_ro_la_chua_chac_da_gui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hết giờ KHÁC hẳn bị từ chối: tin có thể đã đi rồi.

    Nói "chưa gửi" ở đây là mời người dùng gửi lần hai cho một tin đã tới."""
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    _gia_lap_post(monkeypatch, httpx.TimeoutException("quá lâu"))
    d = await zalo.gui_zns(sdt="0989862764", template_id="t1", du_lieu={})
    assert d["da_gui"] is False and d["ly_do"] == "HET_GIO"
    assert "CHƯA CHẮC" in d["chi_tiet"]


@pytest.mark.asyncio
async def test_khong_ket_noi_va_tra_loi_la(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    _gia_lap_post(monkeypatch, httpx.ConnectError("đứt mạng"))
    d = await zalo.gui_zns(sdt="0989862764", template_id="t1", du_lieu={})
    assert d["ly_do"] == "KHONG_KET_NOI"

    _gia_lap_post(monkeypatch, _TraLoi(None, 502, hong_json=True))
    d = await zalo.gui_zns(sdt="0989862764", template_id="t1", du_lieu={})
    assert d["ly_do"] == "TRA_LOI_LA"


@pytest.mark.asyncio
async def test_khong_bao_gio_nem_ngoai_le(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mọi lời gọi nằm trong một thao tác của người dùng.

    Một ngoại lệ ở đây thành 500 trên màn — không nói được là Zalo từ chối hay
    mạng hỏng hay chưa cấu hình.
    """
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    for hong in (httpx.TimeoutException("x"), httpx.ConnectError("y")):
        _gia_lap_post(monkeypatch, hong)
        d = await zalo.gui_zns(sdt="0989862764", template_id="t1", du_lieu={})
        assert d["da_gui"] is False


# ── Rò rỉ ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nhat_ky_khong_mang_sdt_hay_noi_dung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = MagicMock()
    monkeypatch.setattr(zalo, "logger", fake)
    monkeypatch.setenv("ZALO_ZNS_ACCESS_TOKEN", "tok")
    _gia_lap_post(monkeypatch, _TraLoi({"error": 0, "data": {"msg_id": "m1"}}))

    await zalo.gui_zns(
        sdt="0989862764", template_id="t1", du_lieu={"ten": "Chị Lan đau bụng"}
    )

    moi_lan = fake.info.call_args_list + fake.warning.call_args_list
    for _args, kwargs in moi_lan:
        ghep = " ".join(str(v) for v in kwargs.values())
        assert "0989862764" not in ghep
        assert "84989862764" not in ghep
        assert "Lan" not in ghep


@pytest.mark.asyncio
async def test_duong_cu_thoi_noi_doi() -> None:
    """`send_zalo` từng trả ok=True cho một việc chưa hề xảy ra."""
    d = await zalo.send_zalo("0901234567", "Chị Lan đang đau bụng")
    assert d["ok"] is False
    assert d["da_gui"] is False


def test_template_doc_tu_moi_truong(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mã template do Zalo cấp cho TỪNG Official Account.

    Ghi cứng vào code là phòng khám thứ hai dùng hệ thống này sẽ gửi bằng
    template của phòng khám thứ nhất.
    """
    monkeypatch.delenv("ZALO_ZNS_TEMPLATE_NHAC_HEN", raising=False)
    assert zalo.template_cho("NHAC_HEN") is None
    monkeypatch.setenv("ZALO_ZNS_TEMPLATE_NHAC_HEN", "tpl-123")
    assert zalo.template_cho("NHAC_HEN") == "tpl-123"
    assert zalo.template_cho("KHONG_CO_LOAI_NAY") is None
