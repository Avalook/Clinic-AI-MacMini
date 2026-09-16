"""Tệp kết quả khám — kiểu, trần, và quyền đọc.

Ba luật đắt nhất ở đây, cả ba đã có tiền lệ hỏng ở nơi khác:

  · KIỂU KIỂM BẰNG NỘI DUNG. Một tệp "kq.mp4" chứa HTML sẽ được trình duyệt
    chạy nếu phục vụ sai kiểu. Đuôi tệp là thứ người tải lên tự đặt.
  · TRẦN THEO TỪNG LOẠI. Một con số chung buộc phải lấy theo cái lớn nhất, và
    khi đó ô "chọn ảnh" cũng nhận một video 80MB.
  · ĐỌC LẠI PHẢI CHỨNG MINH QUYỀN. Đoán một UUID không đủ để mở tệp của bệnh
    nhân khác.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.requests import Request

from clinicai.api.exceptions import ValidationError
from clinicai.services.media_service import (
    MAX_BYTES_THEO_LOAI,
    sniff_ket_qua,
)

# Mấy byte đầu THẬT của từng định dạng — không phải đuôi tên tệp.
JPG = b"\xff\xd8\xff" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 32
MOV = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32


@pytest.mark.parametrize(
    ("data", "loai"),
    [
        (JPG, "ANH"),
        (PNG, "ANH"),
        (PDF, "PDF"),
        (MP4, "VIDEO"),
        (MOV, "VIDEO"),
        (WEBM, "VIDEO"),
    ],
)
def test_nhan_dung_loai_theo_noi_dung(data: bytes, loai: str) -> None:
    _mime, _ext, thuc_te = sniff_ket_qua(data)
    assert thuc_te == loai


def test_mp4_va_mov_co_chu_ky_o_byte_thu_tu() -> None:
    """`ftyp` KHÔNG ở đầu tệp — cùng kiểu bẫy như DICOM ở byte 128.

    Kiểm bằng `data.startswith(b"ftyp")` sẽ từ chối mọi video MP4 thật, và
    người dùng sẽ đi chép tay qua USB.
    """
    assert sniff_ket_qua(MP4)[0] == "video/mp4"
    assert sniff_ket_qua(MOV)[0] == "video/quicktime"


def test_dicom_van_nhan_duoc() -> None:
    """Máy siêu âm xuất thẳng DICOM là chuyện thường."""
    dicom = b"\x00" * 128 + b"DICM" + b"\x00" * 32
    assert sniff_ket_qua(dicom) == ("application/dicom", ".dcm", "ANH")


@pytest.mark.parametrize(
    "rac",
    [
        b"<html><script>alert(1)</script></html>",
        # GIF nay NHẬN (16/09/2026 — ảnh hợp lệ, trình duyệt hiển thị được).
        # BMP vẫn không: nặng, máy siêu âm không xuất, nói ra cho người dùng.
        b"BM" + b"\x00" * 32,
        b"",
    ],
)
def test_tu_choi_thu_khong_phai_ket_qua(rac: bytes) -> None:
    with pytest.raises(ValidationError):
        sniff_ket_qua(rac)


def test_mac_dinh_khong_gioi_han_dung_luong(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tuyền chốt 16/09/2026: không giới hạn dung lượng tệp tải lên.

    Trần vẫn đặt được qua env (MEDIA_MAX_BYTES_<LOẠI>) nếu sau này cần; 0 = không.
    """
    from clinicai.services.media_service import vuot_tran

    assert set(MAX_BYTES_THEO_LOAI) == {"ANH", "VIDEO", "PDF", "TAI_LIEU"}
    assert all(v == 0 for v in MAX_BYTES_THEO_LOAI.values())
    assert vuot_tran("VIDEO", 50 * 1024**3) is None
    monkeypatch.setitem(MAX_BYTES_THEO_LOAI, "ANH", 100)
    assert vuot_tran("ANH", 101) == 100
    assert vuot_tran("ANH", 100) is None


def test_khoa_tep_luon_bat_dau_bang_clinic_id() -> None:
    """Hai phòng khám không đọc được tệp của nhau kể cả khi một truy vấn sai."""
    from clinicai.services.media_service import duong_dan_ket_qua

    _path, khoa = duong_dan_ket_qua(
        clinic_id="a0000000-0000-4000-8000-000000000001",
        clinic_patient_id="b0000000-0000-4000-8000-000000000002",
        ext=".mp4",
    )
    assert khoa.startswith("a0000000-0000-4000-8000-000000000001/ket-qua/")
    assert khoa.endswith(".mp4")
    # Không một mảnh nào của tên đến từ người dùng.
    assert ".." not in khoa


def test_hai_lan_goi_ra_hai_khoa_khac_nhau() -> None:
    """Trùng khoá là một tệp ghi đè lên tệp của lần khám trước."""
    from clinicai.services.media_service import duong_dan_ket_qua

    args = {
        "clinic_id": "a0000000-0000-4000-8000-000000000001",
        "clinic_patient_id": "b0000000-0000-4000-8000-000000000002",
        "ext": ".jpg",
    }
    assert duong_dan_ket_qua(**args)[1] != duong_dan_ket_qua(**args)[1]


# ── Service: quyền và vòng đời "đã gửi" ────────────────────────────────────

from typing import Any  # noqa: E402

from clinicai.api.exceptions import NotFoundError  # noqa: E402
from clinicai.api.identity import ClinicRole, StaffIdentity  # noqa: E402
from clinicai.services.tep_ket_qua_service import TepKetQuaService  # noqa: E402

CLINIC = "a0000000-0000-4000-8000-000000000001"
BN = "b0000000-0000-4000-8000-000000000002"


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Chị Điều",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=CLINIC,
        location_id="l1",
        location_name="Kim Ngưu",
    )


class FakePool:
    def __init__(self, *kq: Any) -> None:
        self._kq = list(kq)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _lay(self) -> Any:
        return self._kq.pop(0) if self._kq else None

    async def fetchval(self, sql: str, *a: Any) -> Any:
        self.calls.append((sql, a))
        return self._lay()

    async def fetchrow(self, sql: str, *a: Any) -> Any:
        self.calls.append((sql, a))
        return self._lay()

    async def fetch(self, sql: str, *a: Any) -> Any:
        self.calls.append((sql, a))
        return self._lay() or []

    async def execute(self, sql: str, *a: Any) -> None:
        self.calls.append((sql, a))

    def acquire(self) -> "FakePool":
        return self

    def transaction(self) -> "FakePool":
        return self

    async def __aenter__(self) -> "FakePool":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.mark.asyncio
async def test_video_ket_qua_bi_tu_choi_khi_chua_bat_kho_luu() -> None:
    """UI nói video chưa nhận thì API trực tiếp cũng phải nói đúng như vậy."""
    with pytest.raises(ValidationError, match="Video.*chưa được bật"):
        await TepKetQuaService(FakePool()).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=MP4
        )


@pytest.mark.asyncio
async def test_quota_clinic_chan_upload_lap_lai_truoc_khi_ghi_tep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clinicai.services import tep_ket_qua_service as mod

    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(mod, "MEDIA_CLINIC_QUOTA_BYTES", 64)
    pool = FakePool(1, False, 60)  # patient, chưa TRA_KQ, gần hết quota

    with pytest.raises(ValidationError, match="hạn mức lưu trữ"):
        await mod.TepKetQuaService(pool).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=PNG
        )

    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.asyncio
async def test_o_dia_sap_day_thi_fail_closed_truoc_khi_ghi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil
    from collections import namedtuple

    from clinicai.services import tep_ket_qua_service as mod

    Disk = namedtuple("Disk", "total used free")
    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(mod, "MEDIA_MIN_FREE_BYTES", 1024)
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: Disk(2048, 1536, 512))
    pool = FakePool(1, 0)

    with pytest.raises(ValidationError, match="dung lượng trống an toàn"):
        await mod.TepKetQuaService(pool).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=PNG
        )

    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.asyncio
async def test_khong_upload_them_sau_khi_da_xac_nhan_tra_ket_qua(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clinicai.services import tep_ket_qua_service as mod

    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    pool = FakePool(1, True)  # patient hợp lệ, TRA_KQ vẫn đang hiệu lực

    with pytest.raises(ValidationError, match="đã xác nhận trả kết quả"):
        await mod.TepKetQuaService(pool).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=PNG
        )

    lock_call = next(call for call in pool.calls if "pg_advisory_xact_lock" in call[0])
    assert lock_call[1] == (f"cskh-ket-qua:{CLINIC}:{BN}",)
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


# ── Nhận multipart theo luồng, ghi thẳng vào kho ──────────────────────────────


def _than_multipart(
    truong: dict[str, str], tep: tuple[str, bytes] | None, bd: str = "ranhgioiXYZ"
) -> bytes:
    out = b""
    for k, v in truong.items():
        out += (
            f'--{bd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
        ).encode()
    if tep:
        ten, data = tep
        out += (
            (
                f'--{bd}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{ten}"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode()
            + data
            + b"\r\n"
        )
    return out + f"--{bd}--\r\n".encode()


def _request(than: bytes, *, khuc: int = 7777, dut_giua: bool = False) -> Any:
    from starlette.requests import Request

    phan = [than[i : i + khuc] for i in range(0, len(than), khuc)]
    if dut_giua:
        phan = phan[: len(phan) // 2]

    async def receive() -> dict[str, Any]:
        if phan:
            return {"type": "http.request", "body": phan.pop(0), "more_body": True}
        if dut_giua:
            return {"type": "http.disconnect"}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [
            (b"content-type", b"multipart/form-data; boundary=ranhgioiXYZ"),
            (b"content-length", str(len(than)).encode()),
        ],
    }
    return Request(scope, receive)


@pytest.fixture
def kho(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from clinicai.services import nhan_tep_luong as mod

    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    return tmp_path


def _con_part(kho: Path) -> list[Path]:
    return [p for p in kho.rglob("*") if p.is_file()]


@pytest.mark.asyncio
async def test_nhan_luong_ghi_dung_tung_byte_va_doc_truong(kho: Path) -> None:
    """Tệp 9MB đi theo khúc lẻ: trên kho khớp từng byte, sha đúng, trường đủ."""
    import hashlib

    from clinicai.services.nhan_tep_luong import nhan_multipart

    data = PNG + bytes(range(256)) * (9 * 1024 * 4)
    truong, tep = await nhan_multipart(
        _request(
            _than_multipart(
                {"clinic_patient_id": BN, "service_order_id": "x"}, ("a.png", data)
            )
        )
    )
    assert truong == {"clinic_patient_id": BN, "service_order_id": "x"}
    assert tep.duong.parent == kho / ".tam"
    assert tep.duong.read_bytes() == data
    assert tep.so_byte == len(data)
    assert tep.sha256 == hashlib.sha256(data).hexdigest()
    assert tep.dau == data[:8192]
    assert tep.ten == "a.png"


@pytest.mark.asyncio
async def test_nhan_luong_tep_nho_hon_khuc_dau(kho: Path) -> None:
    from clinicai.services.nhan_tep_luong import nhan_multipart

    _, tep = await nhan_multipart(_request(_than_multipart({}, ("p.pdf", PDF))))
    assert tep.duong.read_bytes() == PDF
    assert tep.dau == PDF


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("truong", "tep", "cau"),
    [
        ({}, ("x.exe", b"MZ\x90\x00" + b"\x00" * 20000), "không"),
        ({"a": "b"}, None, "rỗng"),
        ({}, ("r.png", b""), "rỗng"),
    ],
)
async def test_nhan_luong_tu_choi_va_khong_de_lai_rac(
    kho: Path, truong: dict[str, str], tep: tuple[str, bytes] | None, cau: str
) -> None:
    from clinicai.services.nhan_tep_luong import nhan_multipart

    with pytest.raises(ValidationError):
        await nhan_multipart(_request(_than_multipart(truong, tep)))
    assert _con_part(kho) == []


@pytest.mark.asyncio
async def test_nhan_luong_hai_tep_bi_tu_choi(kho: Path) -> None:
    from clinicai.services.nhan_tep_luong import nhan_multipart

    than = _than_multipart({}, ("a.png", PNG)).replace(b"--ranhgioiXYZ--\r\n", b"")
    than += _than_multipart({}, ("b.png", PNG))
    with pytest.raises(ValidationError, match="một tệp"):
        await nhan_multipart(_request(than))
    assert _con_part(kho) == []


@pytest.mark.asyncio
async def test_nhan_luong_mat_ket_noi_giua_chung_thi_don(kho: Path) -> None:
    from clinicai.services.nhan_tep_luong import nhan_multipart

    than = _than_multipart({}, ("v.png", PNG + b"x" * (12 * 1024 * 1024)))
    with pytest.raises(ValidationError, match="Mất kết nối"):
        await nhan_multipart(_request(than, khuc=1024 * 1024, dut_giua=True))
    assert _con_part(kho) == []


@pytest.mark.asyncio
async def test_nhan_luong_tran_dat_qua_env_van_chan(
    kho: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from clinicai.services.media_service import MAX_BYTES_THEO_LOAI
    from clinicai.services.nhan_tep_luong import nhan_multipart

    monkeypatch.setitem(MAX_BYTES_THEO_LOAI, "ANH", 5 * 1024 * 1024)
    than = _than_multipart({}, ("a.png", PNG + b"x" * (9 * 1024 * 1024)))
    with pytest.raises(ValidationError, match="quá lớn"):
        await nhan_multipart(_request(than, khuc=512 * 1024))
    assert _con_part(kho) == []


@pytest.mark.asyncio
async def test_nhan_luong_khong_phai_multipart(kho: Path) -> None:
    from starlette.requests import Request

    from clinicai.services.nhan_tep_luong import nhan_multipart

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"{}", "more_body": False}

    req = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
    )
    with pytest.raises(ValidationError, match="multipart"):
        await nhan_multipart(req)


@pytest.mark.asyncio
async def test_service_doi_ten_tep_da_nhan_khong_chep_lai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tệp đã nằm trên kho → service chỉ đổi tên; tệp tạm biến mất."""
    import hashlib

    from clinicai.services import tep_ket_qua_service as mod
    from clinicai.services.nhan_tep_luong import TepDaNhan

    monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr("clinicai.services.media_service.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_chep_luong", lambda *_a: pytest.fail("không được chép"))
    part = tmp_path / ".tam" / "x.part"
    part.parent.mkdir()
    part.write_bytes(PNG)
    tep = TepDaNhan(
        duong=part,
        so_byte=len(PNG),
        sha256=hashlib.sha256(PNG).hexdigest(),
        dau=PNG,
        ten="a.png",
    )
    pool = FakePool(1, False, "tep-1")
    d = await mod.TepKetQuaService(pool).tai_len(
        identity=_ai(), clinic_patient_id=BN, tep_da_nhan=tep, ten_hien_thi=tep.ten
    )
    assert d["so_byte"] == len(PNG)
    assert not part.exists()
    tren_dia = [p for p in tmp_path.rglob("*.png")]
    assert len(tren_dia) == 1 and tren_dia[0].read_bytes() == PNG


@pytest.mark.asyncio
@pytest.mark.parametrize("range_header", [None, "bytes=0-9", "bytes=9999-10000"])
async def test_response_tep_phi_luon_no_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    range_header: str | None,
) -> None:
    from clinicai.api.v1.routers.cskh import doc_tep_ket_qua

    path = tmp_path / "ket-qua.pdf"
    path.write_bytes(PDF)

    async def fake_path(*_args: Any, **_kwargs: Any) -> tuple[Path, str, int, str]:
        return path, "application/pdf", len(PDF), "ket-qua.pdf"

    monkeypatch.setattr(TepKetQuaService, "duong_dan_de_doc", fake_path)
    headers = [] if range_header is None else [(b"range", range_header.encode())]
    request = Request(
        {"type": "http", "method": "GET", "path": "/", "headers": headers}
    )

    response = await doc_tep_ket_qua(
        tep_id="00000000-0000-4000-8000-000000000001",  # type: ignore[arg-type]
        request=request,
        identity=_ai(),
        pool=FakePool(),
    )

    assert "no-store" in response.headers["cache-control"]


@pytest.mark.asyncio
async def test_tep_rong_va_tep_qua_lon_bi_tu_choi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError):
        await TepKetQuaService(FakePool()).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=b""
        )
    monkeypatch.setitem(MAX_BYTES_THEO_LOAI, "ANH", 1024)
    qua_lon = JPG + b"\x00" * 1025
    with pytest.raises(ValidationError) as e:
        await TepKetQuaService(FakePool()).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=qua_lon
        )
    assert "quá lớn" in str(e.value)


@pytest.mark.asyncio
async def test_khach_phong_kham_khac_thi_khong_tai_len_duoc() -> None:
    """RLS chỉ GIẤU dòng đi, không ngăn nó ra đời — phải kiểm ở service."""
    with pytest.raises(NotFoundError):
        await TepKetQuaService(FakePool(None)).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=JPG
        )


@pytest.mark.asyncio
async def test_doc_tep_khong_thuoc_phong_kham_thi_tu_choi() -> None:
    """Khoá phải bắt đầu bằng đúng clinic_id của người đang đăng nhập.

    Chốt thứ hai này là THỪA về logic (câu truy vấn đã lọc clinic_id) — nhưng
    backend chạy bằng service role và BỎ QUA RLS, nên một lần sửa sau này làm
    hỏng bộ lọc sẽ biến đây thành lỗ thật.
    """
    pool = FakePool(
        {
            "khoa": "PHONG-KHAM-KHAC/ket-qua/x/y.jpg",
            "mime": "image/jpeg",
            "so_byte": 10,
            "ten_hien_thi": "a.jpg",
        }
    )
    with pytest.raises(ValidationError):
        await TepKetQuaService(pool).duong_dan_de_doc(identity=_ai(), tep_id="t1")


@pytest.mark.asyncio
async def test_danh_dau_da_gui_can_kenh_hop_le() -> None:
    with pytest.raises(ValidationError):
        await TepKetQuaService(FakePool()).danh_dau_da_gui(
            identity=_ai(), tep_id="t1", kenh="BO_CAU"
        )


@pytest.mark.asyncio
async def test_gui_lan_hai_thi_bao_da_gui_roi() -> None:
    """Câu UPDATE có `AND gui_luc IS NULL`, nên lần hai không khớp dòng nào.

    Nói ra "đã gửi rồi" thay vì im lặng ghi đè: hai dòng "đã gửi" cho cùng một
    tệp là hai lần gửi trong báo cáo, và người đọc sau không biết cái nào thật.
    """
    with pytest.raises(NotFoundError):
        await TepKetQuaService(FakePool(None)).danh_dau_da_gui(
            identity=_ai(), tep_id="t1", kenh="ZALO"
        )


# ── HTTP Range: điều kiện để video tua được ────────────────────────────────


def test_range_cac_dang_hop_le() -> None:
    from clinicai.services.media_service import phan_tich_range

    assert phan_tich_range("bytes=0-99", 1000) == (0, 99)
    # END thiếu = "tới hết tệp".
    assert phan_tich_range("bytes=500-", 1000) == (500, 999)
    # `bytes=-500` = 500 byte CUỐI. Trình phát dùng dạng này để đọc chỉ mục MP4
    # nằm ở đuôi tệp; hiểu nhầm thành "từ byte 0" là tải cả video.
    assert phan_tich_range("bytes=-200", 1000) == (800, 999)
    # Vượt cuối tệp thì kẹp lại, không trả byte không tồn tại.
    assert phan_tich_range("bytes=900-99999", 1000) == (900, 999)


def test_range_khong_hop_le_thi_tra_tron_tep() -> None:
    from clinicai.services.media_service import phan_tich_range

    for xau in [None, "", "items=0-1", "bytes=abc-def", "bytes=-"]:
        assert phan_tich_range(xau, 1000) is None


def test_range_ngoai_tep_bao_khoang_rong() -> None:
    """Lời gọi thấy đầu > cuối thì trả 416 — không trả 200 kèm trọn tệp.

    Trả 200 cho một câu hỏi vượt cuối tệp là bắt trình duyệt tải lại từ đầu mỗi
    lần người xem kéo thanh tua tới cuối.
    """
    from clinicai.services.media_service import phan_tich_range

    dau, cuoi = phan_tich_range("bytes=5000-6000", 1000) or (0, 0)
    assert dau > cuoi


@pytest.mark.asyncio
async def test_tai_len_ghi_dung_nhung_gi_da_nhan() -> None:
    """Kiểu, kích thước, mã băm và NGƯỜI TẢI đều lấy từ nguồn đáng tin.

    `ten_hien_thi` là thứ DUY NHẤT đến từ client, và nó chỉ là nhãn — tên trên
    đĩa do hệ thống sinh.
    """
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as thu_muc:
        with (
            patch("clinicai.services.media_service.MEDIA_ROOT", Path(thu_muc)),
            patch("clinicai.services.tep_ket_qua_service.MEDIA_ROOT", Path(thu_muc)),
        ):
            # patient → chưa TRA_KQ → id mới (không hạn mức = không
            # đếm tổng dung lượng)
            pool = FakePool(1, False, "tep-1")
            d = await TepKetQuaService(pool).tai_len(
                identity=_ai(),
                clinic_patient_id=BN,
                data=PNG,
                ten_hien_thi="../../../etc/passwd",
            )
            assert d["loai_tep"] == "ANH"
            assert d["so_byte"] == len(PNG)

            sql, args = pool.calls[3]
            assert "INSERT INTO public.tep_ket_qua" in sql
            assert "s1" in args  # người tải = phiên đăng nhập
            assert "image/png" in args
            # Tên hiểm chỉ nằm ở cột nhãn; KHOÁ tệp không mang một mảnh nào của nó.
            khoa = next(a for a in args if isinstance(a, str) and "/ket-qua/" in a)
            assert ".." not in khoa
            assert khoa.startswith(f"{CLINIC}/")

            # Và tệp thật sự nằm trên đĩa, đúng chỗ khoá nói.
            tren_dia = Path(thu_muc) / khoa
            assert tren_dia.exists()
            assert tren_dia.read_bytes() == PNG
            # Không để lại tệp tạm nào: ghi .tmp rồi đổi tên là để một lần ghi
            # đứt quãng không thành một tệp hỏng mà database vẫn khai là có.
            assert not list(Path(thu_muc).rglob("*.tmp"))


@pytest.mark.asyncio
async def test_danh_sach_tra_du_cot_man_hinh_can() -> None:
    """Bốn câu `image_refs` không trả lời được — và là lý do bảng này tồn tại."""
    pool = FakePool(
        [
            {
                "id": "t1",
                "ten_hien_thi": "sieu-am.mp4",
                "loai_tep": "VIDEO",
                "mime": "video/mp4",
                "so_byte": 1234,
                "tai_len_luc": "2026-08-08T10:00:00+07:00",
                "gui_luc": None,
                "gui_kenh": None,
                "tai_len_boi": "Chị Điều",
                "gui_boi": None,
            }
        ]
    )
    rows = await TepKetQuaService(pool).danh_sach(identity=_ai(), clinic_patient_id=BN)
    assert rows[0]["loai_tep"] == "VIDEO"  # ảnh hay video — hiển thị khác hẳn
    assert rows[0]["so_byte"] == 1234  # đếm được đĩa đang dùng bao nhiêu
    assert rows[0]["tai_len_boi"] == "Chị Điều"  # ai tải
    assert rows[0]["gui_luc"] is None  # đã gửi chưa


@pytest.mark.asyncio
async def test_lich_hen_khong_phai_cua_khach_thi_tu_choi() -> None:
    """Gắn tệp vào lịch của người khác là gắn kết quả vào sai hồ sơ."""
    pool = FakePool(1, None)  # patient OK, appointment KHÔNG thuộc khách này
    with pytest.raises(ValidationError):
        await TepKetQuaService(pool).tai_len(
            identity=_ai(),
            clinic_patient_id=BN,
            data=JPG,
            appointment_id="c0000000-0000-4000-8000-000000000003",
        )


@pytest.mark.asyncio
async def test_tep_bien_mat_khoi_dia_thi_noi_ro() -> None:
    """Database khai có mà đĩa không có — nói "báo kỹ thuật", đừng trả 500.

    Đây chính là cảnh sau một lần khôi phục database mà quên khôi phục tệp.
    """
    pool = FakePool(
        {
            "khoa": f"{CLINIC}/ket-qua/x/khong-ton-tai.jpg",
            "mime": "image/jpeg",
            "so_byte": 10,
            "ten_hien_thi": "a.jpg",
        }
    )
    with pytest.raises(NotFoundError):
        await TepKetQuaService(pool).duong_dan_de_doc(identity=_ai(), tep_id="t1")


# ---------------------------------------------------------------------------
# Tự kiểm 16/09/2026: đủ loại tệp người dùng thật sẽ kéo vào ô
# ---------------------------------------------------------------------------


def _zip_office(ten_ben_trong: bytes) -> bytes:
    # Đầu tệp ZIP thật: chữ ký + tiêu đề cục bộ + tên mục đầu tiên.
    return (
        b"PK\x03\x04"
        + b"\x00" * 26
        + b"[Content_Types].xml"
        + b"\x00" * 64
        + ten_ben_trong
        + b"\x00" * 64
    )


def test_heic_iphone_bi_tu_choi_ro_rang_khong_thanh_video() -> None:
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 40
    with pytest.raises(ValidationError, match="HEIC"):
        sniff_ket_qua(heic)


def test_webp_gif_la_anh() -> None:
    assert sniff_ket_qua(b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 20)[2] == "ANH"
    assert sniff_ket_qua(b"GIF89a" + b"\x00" * 20)[0] == "image/gif"


def test_avi_khong_nhan() -> None:
    with pytest.raises(ValidationError):
        sniff_ket_qua(b"RIFF\x10\x00\x00\x00AVI LIST" + b"\x00" * 20)


def test_docx_xlsx_la_tai_lieu() -> None:
    assert sniff_ket_qua(_zip_office(b"word/document.xml"))[1:] == (".docx", "TAI_LIEU")
    assert sniff_ket_qua(_zip_office(b"xl/workbook.xml"))[1:] == (".xlsx", "TAI_LIEU")


def test_zip_thuong_khong_nhan() -> None:
    zip_rac = b"PK\x03\x04" + b"\x00" * 26 + b"virus.exe" + b"\x00" * 9000
    with pytest.raises(ValidationError, match="ZIP"):
        sniff_ket_qua(zip_rac)


def test_exe_doi_duoi_jpg_van_bi_tu_choi() -> None:
    with pytest.raises(ValidationError):
        sniff_ket_qua(b"MZ\x90\x00" + b"\x00" * 100)
