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

import pytest

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
        b"GIF89a" + b"\x00" * 32,  # GIF: không nhận, và phải nói ra
        b"",
    ],
)
def test_tu_choi_thu_khong_phai_ket_qua(rac: bytes) -> None:
    with pytest.raises(ValidationError):
        sniff_ket_qua(rac)


def test_tran_video_rong_hon_tran_anh() -> None:
    """Gộp một trần chung là mở cửa cho video 80MB vào ô chọn ảnh."""
    assert MAX_BYTES_THEO_LOAI["VIDEO"] > MAX_BYTES_THEO_LOAI["ANH"]
    assert MAX_BYTES_THEO_LOAI["ANH"] == 12 * 1024 * 1024
    assert set(MAX_BYTES_THEO_LOAI) == {"ANH", "VIDEO", "PDF"}


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

    def acquire(self) -> "FakePool":
        return self

    def transaction(self) -> "FakePool":
        return self

    async def __aenter__(self) -> "FakePool":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


@pytest.mark.asyncio
async def test_tep_rong_va_tep_qua_lon_bi_tu_choi() -> None:
    with pytest.raises(ValidationError):
        await TepKetQuaService(FakePool()).tai_len(
            identity=_ai(), clinic_patient_id=BN, data=b""
        )
    qua_lon = JPG + b"\x00" * (MAX_BYTES_THEO_LOAI["ANH"] + 1)
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
            pool = FakePool(1, "tep-1")  # patient tồn tại → id dòng mới
            d = await TepKetQuaService(pool).tai_len(
                identity=_ai(),
                clinic_patient_id=BN,
                data=MP4,
                ten_hien_thi="../../../etc/passwd",
            )
            assert d["loai_tep"] == "VIDEO"
            assert d["so_byte"] == len(MP4)

            sql, args = pool.calls[1]
            assert "INSERT INTO public.tep_ket_qua" in sql
            assert "s1" in args  # người tải = phiên đăng nhập
            assert "video/mp4" in args
            # Tên hiểm chỉ nằm ở cột nhãn; KHOÁ tệp không mang một mảnh nào của nó.
            khoa = next(a for a in args if isinstance(a, str) and "/ket-qua/" in a)
            assert ".." not in khoa
            assert khoa.startswith(f"{CLINIC}/")

            # Và tệp thật sự nằm trên đĩa, đúng chỗ khoá nói.
            tren_dia = Path(thu_muc) / khoa
            assert tren_dia.exists()
            assert tren_dia.read_bytes() == MP4
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
