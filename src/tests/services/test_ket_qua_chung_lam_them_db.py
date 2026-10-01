"""KẾT QUẢ CHUNG cho dịch vụ chưa có mẫu — nhập ngay tại quầy (Tuyền 01/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_ket_qua_chung_lam_them_db.py

"Nước tiểu" tick ở bàn sinh hiệu không có mẫu kết quả nào → trước đây không có chỗ
nhập. Nay MÁY CHỦ chọn mẫu CHUNG (nhập tự do) khi chưa gắn mẫu; mẫu đã gắn thì
thắng; người đứng bàn nhập + tải ảnh que thử ngay tại đó, cùng vòng đời và cùng
sự kiện với mọi kết quả khác.
"""

from __future__ import annotations

import pathlib

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.phieu_kham.mau_goi_y import MAU_CHUNG, chon_mau, mau_cho_cac_dich_vu
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.mau_ket_qua_service import MauKetQuaService
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_lam_them_tai_quay_db import _nut, _san_sang, _tick
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _su_kien
from tests.services.test_xac_nhan_tep_ket_qua_db import PDF_DUMMY

pytestmark = [pytest.mark.db]
async_db = pytest.mark.asyncio

#: Ảnh PNG nhỏ nhất hợp lệ (đủ chữ ký để `sniff_ket_qua` nhận là ảnh).
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def kho(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    import clinicai.services.media_service as media

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path / "cfs")
    monkeypatch.setattr(media, "MEDIA_LOCAL_ROOT", tmp_path / "vps")
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    return tmp_path


def _o(gia_tri: str) -> dict:  # type: ignore[type-arg]
    return {"gia_tri": gia_tri, "nguon": "USER"}


# ── Luật chọn mẫu (hàm thuần) ───────────────────────────────────────────────


def test_chua_gan_mau_nao_may_chon_chung_mac_dinh() -> None:
    tat_ca = [
        {"ma": "SA_VU", "ten": "SÂ vú", "nhom": "Siêu âm"},
        {"ma": MAU_CHUNG, "ten": "Kết quả chung", "nhom": "Chung"},
    ]
    kq = chon_mau([], tat_ca, "DV_KHONG_CO_GOI_Y")
    assert kq["chon_san"] == MAU_CHUNG and kq["mac_dinh"] is True
    assert kq["mau"][0]["ma"] == MAU_CHUNG  # CHUNG đứng đầu, mẫu khác vẫn chọn được
    assert all(m["cua_dich_vu"] for m in kq["mau"])


def test_mau_da_gan_thang_chung() -> None:
    gan = [{"ma": "SA_GIAP", "ten": "SÂ giáp", "nhom": "Siêu âm"}]
    tat_ca = [*gan, {"ma": MAU_CHUNG, "ten": "Kết quả chung", "nhom": "Chung"}]
    kq = chon_mau(gan, tat_ca, "DV_X")
    assert kq["chon_san"] == "SA_GIAP" and kq["mac_dinh"] is False
    assert [m["ma"] for m in kq["mau"]] == ["SA_GIAP"]


# ── Trên Postgres thật ──────────────────────────────────────────────────────


@async_db
async def test_dich_vu_chua_gan_tra_chung_gan_roi_thi_mau_gan_thang(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, _ = await _san_sang(pool)
    async with pool.acquire() as conn:
        kq = (
            await mau_cho_cac_dich_vu(conn, clinic_id=CLINIC, service_codes=[ca.ma_dv])
        )[ca.ma_dv]
    assert kq["chon_san"] == MAU_CHUNG and kq["mac_dinh"] is True

    # API của màn Mẫu kết quả cũng trả CHUNG khi chưa gắn.
    dv = await MauKetQuaService(pool).mau_cua_dich_vu(
        service_code=ca.ma_dv, identity=ca.bac_si
    )
    assert dv["chon_san"] == MAU_CHUNG and dv["mac_dinh"] is True
    assert dv["mau"][0]["ma"] == MAU_CHUNG

    # Quản lý gắn mẫu riêng → mẫu đã gắn thắng, hết "mặc định".
    await pool.execute(
        "INSERT INTO dich_vu_mau_ket_qua (clinic_id, service_code, mau, gan_boi)"
        " VALUES ($1::uuid, $2, 'SA_GIAP', $3::uuid) ON CONFLICT DO NOTHING",
        CLINIC,
        ca.ma_dv,
        ca.bac_si.staff_id,
    )
    dv = await MauKetQuaService(pool).mau_cua_dich_vu(
        service_code=ca.ma_dv, identity=ca.bac_si
    )
    assert [m["ma"] for m in dv["mau"]] == ["SA_GIAP"]
    assert dv["chon_san"] == "SA_GIAP" and dv["mac_dinh"] is False


@async_db
async def test_tick_o_ban_sinh_hieu_co_cho_nhap_ket_qua_theo_quyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    # Chưa tick: không có gì để nhập.
    goi = await _nut(pool, ca, visit, noi="sinh_hieu")
    assert goi["luot"][visit][ca.ma_dv]["ket_qua"] is None

    kq = await _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd)
    goi = await _nut(pool, ca, visit, noi="sinh_hieu")
    k = goi["luot"][visit][ca.ma_dv]["ket_qua"]
    assert k["nhap_duoc"] is True  # điều dưỡng có quyền điền phiếu kết quả
    assert k["trang_thai"] == "CHUA_CO" and k["so_tep"] == 0
    assert k["mau_chon_san"] == MAU_CHUNG and k["mac_dinh"] is True
    assert k["clinic_patient_id"]
    assert kq["order_id"]

    # Theo QUYỀN, không theo vai: hôm nay lễ tân được mở full lego nên có nút;
    # tài khoản chỉ có gói cũ (không khối Kết quả) thì cờ nhap_duoc = False → màn
    # không hiện nút. Quyền không bị đổi bởi tính năng này.
    goi_lt = await _nut(pool, ca, visit, noi="tiep_don")
    assert goi_lt["luot"][visit][ca.ma_dv]["ket_qua"]["nhap_duoc"] is True
    await ve_goi_mau_cu(pool, ca.le_tan)
    goi_lt = await _nut(pool, ca, visit, noi="tiep_don")
    assert goi_lt["luot"][visit][ca.ma_dv]["ket_qua"]["nhap_duoc"] is False


@async_db
async def test_chung_nhap_hoan_tat_sua_huy_sua_cung_su_kien_nhu_ket_qua_khac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    oid = (await _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd))["order_id"]
    fe = FormEngineService(pool)

    # Tài khoản không có khối Kết quả → bị chặn ở lệnh (gác thật, không chỉ ẩn nút).
    await ve_goi_mau_cu(pool, ca.le_tan)
    with pytest.raises(SafetyGateError):
        await fe.mo_phieu(
            service_order_id=oid, form_id=f"KQ_{MAU_CHUNG}", identity=ca.le_tan
        )

    p = await fe.mo_phieu(
        service_order_id=oid, form_id=f"KQ_{MAU_CHUNG}", identity=ca.dd
    )
    assert p["trang_thai"] == "DRAFT"
    luu = await fe.luu_nhap(
        phieu_id=p["id"],
        du_lieu={"noi_dung": _o("Que thử: protein (+), hồng cầu (-)")},
        expected_revision=p["revision"],
        identity=ca.dd,
    )
    goi = await _nut(pool, ca, visit, noi="sinh_hieu")
    assert goi["luot"][visit][ca.ma_dv]["ket_qua"]["trang_thai"] == "DANG_NHAP"
    # Nháp không phát sự kiện, không phải kết quả.
    assert await _su_kien(pool, "result_form.completed", p["id"]) == []

    xong = await fe.hoan_tat(
        phieu_id=p["id"], expected_revision=luu["revision"], identity=ca.dd
    )
    assert xong["da_hoan_tat"] is True
    # CÙNG sự kiện như mọi kết quả khác → Hành trình khách / bàn bác sĩ cập nhật.
    assert len(await _su_kien(pool, "result_form.completed", p["id"])) == 1
    assert len(await _su_kien(pool, "result.ready", p["id"])) == 1
    goi = await _nut(pool, ca, visit, noi="sinh_hieu")
    assert goi["luot"][visit][ca.ma_dv]["ket_qua"]["trang_thai"] == "CO_KET_QUA"
    assert goi["luot"][visit][ca.ma_dv]["ket_qua"]["mau_chon_san"] == MAU_CHUNG

    # Hoàn tác: mở sửa → bỏ sửa; kết quả chính thức không đổi một chữ.
    sua = await fe.mo_sua(phieu_id=p["id"], identity=ca.dd)
    assert sua["dang_sua"] is True
    huy = await fe.huy_sua(
        phieu_id=p["id"], identity=ca.dd, expected_revision=sua["revision"]
    )
    assert huy["dang_sua"] is False
    ban = await fe.xem_ket_qua(service_order_id=oid, identity=ca.dd)
    assert "protein (+)" in str(ban)
    assert len(await _su_kien(pool, "result.corrected", p["id"])) == 0


@async_db
async def test_tai_anh_va_pdf_len_chi_dinh_lam_them(
    pool: asyncpg.Pool,  # noqa: F811
    kho: pathlib.Path,
) -> None:
    ca, visit = await _san_sang(pool)
    oid = (await _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd))["order_id"]
    pid = (await _nut(pool, ca, visit, noi="sinh_hieu"))["luot"][visit][ca.ma_dv][
        "ket_qua"
    ]["clinic_patient_id"]

    tep = TepKetQuaService(pool)
    a = await tep.tai_len(
        identity=ca.dd,
        clinic_patient_id=pid,
        data=PNG,
        ten_hien_thi="que-thu.png",
        service_order_id=oid,
    )
    b = await tep.tai_len(
        identity=ca.dd,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="phieu.pdf",
        service_order_id=oid,
    )
    assert a["loai_tep"] == "ANH" and b["loai_tep"] == "PDF"

    k = (await _nut(pool, ca, visit, noi="sinh_hieu"))["luot"][visit][ca.ma_dv][
        "ket_qua"
    ]
    assert k["so_tep"] == 2 and k["trang_thai"] == "CO_KET_QUA"
    # Cùng sự kiện tệp về của mọi kết quả khác.
    assert len(await _su_kien(pool, "result_file.uploaded", str(a["id"]))) == 1


@async_db
async def test_ban_bac_si_thay_mau_chon_san_cua_chi_dinh_lam_them(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bàn bác sĩ / phiếu khám: chỉ định chưa gắn mẫu vẫn có mẫu để điền (máy chủ
    chọn CHUNG), còn `mau_ket_qua` (mẫu ĐÃ GẮN) vẫn rỗng — chip không nói dối."""
    from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh

    ca, visit = await _san_sang(pool)
    oid = (await _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd))["order_id"]
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    d = next(x for x in ds if x["service_order_id"] == oid)
    assert d["mau_ket_qua"] == []
    assert d["mau_chon_san"] == MAU_CHUNG and d["mau_mac_dinh"] is True
    assert d["mau_chon_duoc"][0]["ma"] == MAU_CHUNG
