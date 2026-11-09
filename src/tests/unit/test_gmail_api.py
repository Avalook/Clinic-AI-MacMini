"""Gmail G2 — đọc thư bằng Gmail API (mạng giả httpx.MockTransport, không gọi Google).

Ca biên: bóc thư lồng nhiều tầng; chỉ giữ PDF có partId; thân text/plain trước html; cắt
độ dài theo CHECK của `drive_tep`; đầu vào rác ⇒ rỗng / None, không ném; token mất quyền
⇒ câu dễ hiểu, không lộ token; 401 ⇒ xin token mới đúng một lần; tệp quá trần ⇒ từ chối.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from clinicai.services.xet_nghiem import gmail, gmail_api, gmail_luu
from clinicai.services.xet_nghiem.gmail_api import PhanPdf, thanh_thu


def _b(s: str | bytes) -> str:
    raw = s.encode() if isinstance(s, str) else s
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _thu(**them: Any) -> dict[str, Any]:
    return {
        "id": "18c0ffee12345678",
        "internalDate": "1762650000000",
        "payload": {
            "headers": [
                {"name": "From", "value": "True Med <TrueMedicine.LayMau@Gmail.com>"},
                {"name": "Subject", "value": "Kết quả   xét nghiệm:  VŨ THỊ A"},
            ],
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "partId": "0",
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"partId": "0.0", "mimeType": "text/html",
                         "body": {"data": _b("<p>HTML <b>bỏ</b></p>")}},
                        {"partId": "0.1", "mimeType": "text/plain",
                         "body": {"data": _b("Họ tên: VŨ THỊ A,\n NS: 1981")}},
                    ],
                },
                {"partId": "1", "filename": "VU_THI_A_081126-501726_HPV_TMD.pdf",
                 "mimeType": "application/pdf",
                 "body": {"attachmentId": "ANGjdJ", "size": 1234}},
                {"partId": "2", "filename": "logo.png", "mimeType": "image/png",
                 "body": {"attachmentId": "x", "size": 10}},
                {"filename": "khong_part_id.pdf", "mimeType": "application/pdf",
                 "body": {"attachmentId": "y", "size": 5}},
            ],
        },
        **them,
    }  # fmt: skip


def test_boc_thu_day_du() -> None:
    t = thanh_thu(_thu())
    assert t is not None
    assert t.id == "18c0ffee12345678"
    assert t.tu == "truemedicine.laymau@gmail.com"  # chữ thường, bỏ tên hiển thị
    assert t.tieu_de == "Kết quả xét nghiệm: VŨ THỊ A"  # gộp khoảng trắng
    assert t.than == "Họ tên: VŨ THỊ A, NS: 1981"  # text/plain thắng html
    assert t.nhan_luc == datetime.fromtimestamp(1762650000, UTC)
    # Chỉ PDF có partId (ảnh logo và phần thiếu partId bị bỏ).
    assert [(p.part_id, p.ten, p.so_byte) for p in t.pdf] == [
        ("1", "VU_THI_A_081126-501726_HPV_TMD.pdf", 1234)
    ]


def test_chi_co_html_thi_bo_the() -> None:
    r = _thu()
    r["payload"]["parts"][0]["parts"] = [
        {
            "mimeType": "text/html",
            "body": {"data": _b("<p>Kính gửi&nbsp;<b>PK</b></p>")},
        }
    ]
    t = thanh_thu(r)
    assert t is not None and t.than == "Kính gửi PK"


def test_cat_do_dai_theo_check_drive_tep() -> None:
    r = _thu()
    r["payload"]["headers"][1]["value"] = "T" * 900
    r["payload"]["parts"][0]["parts"][1]["body"]["data"] = _b("x" * 5000)
    r["payload"]["parts"][1]["filename"] = "A" * 400 + ".pdf"
    t = thanh_thu(r)
    assert t is not None
    assert len(t.tieu_de) == gmail_api.TRAN_TIEU_DE
    assert len(t.than) == gmail_api.TRAN_THAN
    assert len(t.pdf[0].ten) == gmail_api.TRAN_TEN


@pytest.mark.parametrize(
    "rac",
    [
        None,
        "chuỗi",
        42,
        [],
        {},
        {"id": ""},
        {"payload": {}},
        {"id": "abc"},  # quá ngắn so với CHECK
        {"id": "../../etc/x"},  # id đi vào đường dẫn ổ ⇒ phải bỏ
        {"id": "a" * 65},
    ],
)
def test_rac_tra_none(rac: object) -> None:
    assert thanh_thu(rac) is None


def test_thu_chi_la_mot_pdf_o_goc() -> None:
    """Cả thư chỉ là một PDF: Gmail để partId "" ở gốc ⇒ dùng "goc", không bỏ sót."""
    t = thanh_thu(
        {
            "id": "abcdef1234",
            "payload": {
                "partId": "",
                "filename": "KQ.pdf",
                "mimeType": "application/pdf",
                "body": {"attachmentId": "a1", "size": 9},
            },
        }
    )
    assert t is not None and [p.part_id for p in t.pdf] == ["goc"]


def test_phong_kham_cua_khoa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(gmail.BIEN_PHONG_KHAM, raising=False)
    assert gmail.phong_kham_cua_khoa() is None
    for rac in ("", "khong-phai-uuid", "a0000000-0000-4000-8000-00000000000"):
        monkeypatch.setenv(gmail.BIEN_PHONG_KHAM, rac)
        assert gmail.phong_kham_cua_khoa() is None
    monkeypatch.setenv(gmail.BIEN_PHONG_KHAM, " A0000000-0000-4000-8000-000000000001 ")
    assert gmail.phong_kham_cua_khoa() == "a0000000-0000-4000-8000-000000000001"


def test_truong_hong_thi_rong_khong_nem() -> None:
    t = thanh_thu(
        {
            "id": "abcdef12",
            "internalDate": "không-phải-số",
            "payload": {
                "headers": ["rác", {"name": "From"}],
                "parts": ["rác", {"partId": "1", "filename": "a.pdf", "body": "rác"}],
            },
        }
    )
    assert t is not None
    assert (t.tu, t.tieu_de, t.than) == ("", "", "")
    assert t.nhan_luc == datetime.fromtimestamp(0, UTC)
    assert [(p.part_id, p.so_byte, p.attachment_id) for p in t.pdf] == [("1", 0, None)]


@pytest.mark.parametrize(
    ("ten", "ma"),
    [
        ("VU_THI_A_081126-501726_HPV_TMD.pdf", "081126-501726"),
        ("khong-co-ma.pdf", None),
        ("A_081126-501726_B_091126-000001.pdf", None),  # hai mã khác nhau ⇒ không đoán
        ("A_081126-501726_081126-501726.pdf", "081126-501726"),
        ("1081126-501726.pdf", None),  # dính số trước
        (None, None),
        (123, None),
    ],
)
def test_ma_tep(ten: object, ma: str | None) -> None:
    assert gmail_luu.ma_tep(ten) == ma


def test_cau_tim() -> None:
    # Chỉ thư có PDF, bỏ Spam (thư giả mạo người gửi bị Gmail xếp vào đó).
    assert (
        gmail.q_thu("lab@x.vn") == "from:lab@x.vn has:attachment filename:pdf -in:spam"
    )
    sau = datetime(2026, 11, 9, tzinfo=UTC)
    assert gmail.q_thu("lab@x.vn", sau).endswith(f"after:{int(sau.timestamp())}")


def test_co_cau_hinh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(gmail_api.BIEN_KHOA, raising=False)
    assert gmail_api.co_cau_hinh() is False
    rong = tmp_path / "rong"
    rong.write_bytes(b"")
    monkeypatch.setenv(gmail_api.BIEN_KHOA, str(rong))
    assert gmail_api.co_cau_hinh() is False  # tệp giữ chỗ của compose
    monkeypatch.setenv(gmail_api.BIEN_KHOA, str(tmp_path / "khong-co"))
    assert gmail_api.co_cau_hinh() is False
    co = tmp_path / "khoa.json"
    co.write_text("{}")
    monkeypatch.setenv(gmail_api.BIEN_KHOA, str(co))
    assert gmail_api.co_cau_hinh() is True


# ── Mạng giả ────────────────────────────────────────────────────────────────


@pytest.fixture
def khoa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "gmail-oauth.json"
    p.write_text(
        json.dumps(
            {"client_id": "id", "client_secret": "bi-mat", "refresh_token": "rt"}
        )
    )
    monkeypatch.setenv(gmail_api.BIEN_KHOA, str(p))
    monkeypatch.setattr(gmail_api, "_token", {"gia_tri": None, "het": 0.0})


@pytest.mark.asyncio
@pytest.mark.usefixtures("khoa")
async def test_mat_quyen_thi_cau_de_hieu_khong_lo_token() -> None:
    def tra(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(tra)) as kh:
        with pytest.raises(gmail_api.GmailError) as loi:
            await gmail_api.liet_ke(kh, "from:a@b.vn")
    assert "cấp lại quyền" in str(loi.value)
    assert "rt" not in str(loi.value) and "bi-mat" not in str(loi.value)


@pytest.mark.asyncio
@pytest.mark.usefixtures("khoa")
async def test_401_thi_xin_token_moi_dung_mot_lan() -> None:
    dem = {"token": 0, "gmail": 0}

    def tra(req: httpx.Request) -> httpx.Response:
        if req.url.host == "oauth2.googleapis.com":
            dem["token"] += 1
            return httpx.Response(
                200, json={"access_token": f"tk{dem['token']}", "expires_in": 3600}
            )
        dem["gmail"] += 1
        if req.headers["Authorization"] == "Bearer tk1":
            return httpx.Response(401, json={"error": {"status": "UNAUTHENTICATED"}})
        assert req.url.params["includeSpamTrash"] == "true"  # đọc cả Thùng rác
        return httpx.Response(
            200,
            json={
                "messages": [{"id": "m1"}, {"id": "m2"}],
                "nextPageToken": "T2",
                "resultSizeEstimate": 7,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(tra)) as kh:
        assert await gmail_api.liet_ke(kh, "q") == (["m1", "m2"], "T2", 7)
    assert dem == {"token": 2, "gmail": 2}


@pytest.mark.asyncio
@pytest.mark.usefixtures("khoa")
async def test_gioi_han_toc_do_thi_nem_de_luot_sau_thu_lai() -> None:
    def tra(req: httpx.Request) -> httpx.Response:
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "tk", "expires_in": 3600})
        return httpx.Response(
            403, json={"error": {"errors": [{"reason": "rateLimitExceeded"}]}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(tra)) as kh:
        with pytest.raises(gmail_api.GmailError, match="rateLimitExceeded"):
            await gmail_api.liet_ke(kh, "q")


@pytest.mark.asyncio
async def test_tai_phan_nhung_thang_va_tran() -> None:
    async with httpx.AsyncClient() as kh:
        p = PhanPdf("1", "a.pdf", 8, None, _b(b"%PDF-1.4"))
        assert await gmail_api.tai_phan(kh, "m", p) == b"%PDF-1.4"
        # Lỗi riêng một thư ⇒ ThuBoQua (bỏ thư), KHÔNG phải GmailError (chặn đối tác).
        to = PhanPdf("1", "a.pdf", gmail_api.TRAN_BYTE + 1, "att", None)
        with pytest.raises(gmail_api.ThuBoQua, match="tep_qua_lon"):
            await gmail_api.tai_phan(kh, "m", to)
        with pytest.raises(gmail_api.ThuBoQua, match="khong_du_lieu"):
            await gmail_api.tai_phan(kh, "m", PhanPdf("1", "a.pdf", 1, None, None))
        with pytest.raises(gmail_api.ThuBoQua, match="du_lieu_hong"):
            await gmail_api.tai_phan(kh, "m", PhanPdf("1", "a.pdf", 1, None, "A"))
