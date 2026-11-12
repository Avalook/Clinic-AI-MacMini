"""Chặng 4 — kết quả đối tác tự về từ Drive, chạy thật trên DB (Drive GIẢ, không mạng).

Ca biên kế hoạch mục 7: tự ghép đúng ống; gõ nhầm một số ⇒ hàng chờ, không gắn khách
khác; không mã; sai đối tác; quét lại không chép trùng; cùng tệp nội dung mới ⇒ bản 2;
ghép tay; từ chối ⇒ lượt sau bỏ qua; gán sang khi gán nhầm (tờ cũ thu hồi). Người tải
của tệp tự về: NULL + nguồn DRIVE + tên người thả lấy từ Drive.
"""

from __future__ import annotations

import pathlib
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem import (
    drive,
    drive_api,
    ghep_tay,
    ket_qua,
    mau,
    thu_ho,
)
from clinicai.services.xet_nghiem.drive_api import TepDrive, doc_gio
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca
from tests.services.test_xac_nhan_tep_ket_qua_db import PDF_DUMMY
from tests.services.test_xet_nghiem_nen_db import (
    _ca_doi_tac,
    _chi_dinh,
    _gan,
    _ma,
    _sp,
    _them_dt,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


class DriveGia:
    """Thay `drive_api.liet_ke` / `tai_ve`: tệp theo thư mục, nội dung theo file_id."""

    def __init__(self) -> None:
        # Mỗi test một cặp thư mục riêng: DB test dùng chung trong một lượt, hai đối
        # tác cùng thư mục thì đối tác quét trước "giữ" tệp (khoá theo phòng khám).
        duoi = uuid.uuid4().hex[:10]
        self.a = f"thuMucA_{duoi}"
        self.b = f"thuMucB_{duoi}"
        self.tep: dict[str, list[TepDrive]] = {}
        self.noi: dict[str, bytes] = {}

    def tha(self, thu_muc: str, file_id: str, ten: str, md5: str) -> None:
        ds = [t for t in self.tep.get(thu_muc, []) if t.file_id != file_id]
        ds.append(
            TepDrive(
                file_id=file_id,
                ten=ten,
                mime="application/pdf",
                md5=md5,
                so_byte=len(PDF_DUMMY),
                tao_luc=doc_gio("2026-11-05T08:00:00Z"),
                nguoi_tai="Lab Medlatec",
            )
        )
        self.tep[thu_muc] = ds
        # Mỗi bản một nội dung (md5 khác ⇒ byte khác), như đối tác tải bản mới thật.
        self.noi[file_id] = PDF_DUMMY + f"\n% {file_id} {md5}\n".encode()

    async def liet_ke(self, _kh: object, thu_muc: str) -> list[TepDrive]:
        return list(self.tep.get(thu_muc, []))

    async def tai_ve(self, _kh: object, file_id: str) -> bytes:
        return self.noi[file_id]


@pytest.fixture
def gia(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> DriveGia:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    g = DriveGia()
    monkeypatch.setattr(drive_api, "liet_ke", g.liet_ke)
    monkeypatch.setattr(drive_api, "tai_ve", g.tai_ve)
    monkeypatch.setattr(drive_api, "co_cau_hinh", lambda: True)
    return g


async def _lam(pool: asyncpg.Pool, ham: Any, ca: Ca, **d: object) -> Any:  # noqa: F811
    async with pool.acquire() as conn, conn.transaction():
        return await ham(conn, ca.bac_si, dict(d), hom_nay_vn())


async def _thu(pool: asyncpg.Pool, ca: Ca, oid: str) -> None:  # noqa: F811
    async with pool.acquire() as conn, conn.transaction():
        await thu_ho.ghi_nhan(conn, ca.bac_si, {"order_id": oid, "tien_mat": 300000})


async def _dung_ca(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
) -> tuple[Ca, str, str, str, str, str]:
    """Đối tác A (thư mục A) có HAI việc, mỗi việc MỘT ống; đối tác B (thư mục B)."""
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma(), hen_tra_so_ngay_mac_dinh=3)
    b = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))
    for dt_id, thu_muc in ((a, gia.a), (b, gia.b)):
        await pool.execute(
            "UPDATE doi_tac SET drive_folder_id = $2 WHERE id = $1::uuid",
            dt_id,
            thu_muc,
        )
    o1 = await _chi_dinh(pool, ca)
    o2 = await _chi_dinh(pool, ca)
    ma = []
    for o in (o1, o2):
        await _thu(pool, ca, o)
        ma.append((await _lam(pool, mau.lay_mau, ca, order_ids=[o]))["ma_mau"])
    return ca, a, o1, o2, ma[0], ma[1]


def _sai_so(ma: str) -> str:
    return ma[:-1] + str((int(ma[-1]) + 1) % 10)


async def _viec(pool: asyncpg.Pool, ca: Ca, oid: str) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        return await mau._mot_viec(conn, ca.bac_si, oid, hom_nay_vn())


async def _cho(pool: asyncpg.Pool) -> dict[str, dict[str, Any]]:  # noqa: F811
    async with pool.acquire() as conn:
        return {t["ten"]: t for t in await ghep_tay.ds_cho(conn, CLINIC)}


async def test_tu_ghep_va_hang_cho(pool: asyncpg.Pool, gia: DriveGia) -> None:  # noqa: F811
    ca, _a, o1, o2, ma1, ma2 = await _dung_ca(pool, gia)
    gia.tha(gia.a, "fileAAAAAAAA01", f"{ma1}_ket-qua.pdf", "1" * 32)
    gia.tha(gia.a, "fileAAAAAAAA02", f"{_sai_so(ma2)}.pdf", "2" * 32)
    gia.tha(gia.a, "fileAAAAAAAA03", "KQ_Mai_0211.pdf", "3" * 32)
    gia.tha(gia.b, "fileBBBBBBBB01", f"{ma2}.pdf", "4" * 32)
    kq = await drive.mot_vong(pool)
    assert kq["loi"] == 0 and kq["tep_moi"] >= 4

    # 1. Đúng mã ⇒ tự ghép vào o1; người tải NULL, nguồn DRIVE, tên người thả.
    v1 = await _viec(pool, ca, o1)
    assert v1["trang_thai"]["ma"] == "CO_KET_QUA" and v1["nut"]["gui"]
    assert v1["nguon_tep"] == "Drive · Lab Medlatec · tự ghép"
    tep = await pool.fetchrow(
        "SELECT tai_len_boi_staff_id, nguon, drive_nguoi_tai FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        v1["tep_id"],
    )
    assert tuple(tep) == (None, "DRIVE", "Lab Medlatec")
    # 2–4. Sai số kiểm / không mã ⇒ thử tên + SĐT (PDF giả không có khách khớp) ⇒
    # hàng chờ; sai đối tác giữ lý do mã (tín hiệu thật). KHÔNG gắn o2.
    cho = await _cho(pool)
    assert cho[f"{_sai_so(ma2)}.pdf"]["ly_do_cho"] == "KHONG_KHOP_KHACH"
    assert cho["KQ_Mai_0211.pdf"]["ly_do_cho"] == "KHONG_KHOP_KHACH"
    assert cho[f"{ma2}.pdf"]["ly_do_cho"] == "SAI_DOI_TAC"
    assert (await _viec(pool, ca, o2))["tep_id"] is None
    # Quét lại không chép trùng.
    assert (await drive.mot_vong(pool))["tep_moi"] == 0


async def test_tu_ghep_theo_ten_va_sdt_trong_pdf(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
) -> None:
    """Tuyền 05/11: đối tác không biết mã ống ⇒ tệp ghi đúng tên + SĐT khách thì ghép
    luôn; chỉ đúng tên (sai SĐT) thì không."""
    from tests.unit.test_xet_nghiem_ghep_khach import pdf_co_chu

    ca, _a, o1, o2, *_ = await _dung_ca(pool, gia)
    for oid, ten, sdt in (
        (o1, "Nguyễn Thị Hoa", "0901112223"),
        (o2, "Lê Thị Mai", "0903334445"),
    ):
        await pool.execute(
            "UPDATE patient p SET full_name = $2, phone_primary = $3"
            "  FROM service_order o JOIN visit v ON v.visit_id = o.visit_id"
            " WHERE o.id = $1::uuid AND p.clinic_patient_id = v.clinic_patient_id",
            oid,
            ten,
            sdt,
        )
    gia.tha(gia.a, "fileFFFFFFFF01", "KQ_0511_a.pdf", "5" * 32)
    gia.noi["fileFFFFFFFF01"] = pdf_co_chu(["Ho ten: LE THI MAI", "SDT: 0903 334 445"])
    gia.tha(gia.a, "fileFFFFFFFF02", "KQ_0511_b.pdf", "6" * 32)
    gia.noi["fileFFFFFFFF02"] = pdf_co_chu(
        ["Ho ten: NGUYEN THI HOA", "SDT: 0999999999"]
    )
    await drive.mot_vong(pool)
    v2 = await _viec(pool, ca, o2)
    assert v2["tep_id"] and v2["nguon_tep"] == "Drive · Lab Medlatec · tự ghép"
    assert (await _viec(pool, ca, o1))["tep_id"] is None
    assert (await _cho(pool))["KQ_0511_b.pdf"]["ly_do_cho"] == "KHONG_KHOP_KHACH"


async def test_ban_2_ghep_tay_tu_choi_gan_sang(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
) -> None:
    ca, _a, o1, o2, ma1, ma2 = await _dung_ca(pool, gia)
    gia.tha(gia.a, "fileCCCCCCCC01", f"{ma1}.pdf", "a" * 32)
    gia.tha(gia.a, "fileCCCCCCCC02", "KQ_khach_2.pdf", "b" * 32)
    gia.tha(gia.a, "fileCCCCCCCC03", f"{_sai_so(ma2)}.pdf", "c" * 32)
    await drive.mot_vong(pool)
    # Bản 2: cùng file_id, nội dung mới ⇒ tờ mới cho o1.
    gia.tha(gia.a, "fileCCCCCCCC01", f"{ma1}.pdf", "d" * 32)
    await drive.mot_vong(pool)
    assert (await _viec(pool, ca, o1))["so_ban"] == 2

    cho = await _cho(pool)
    # Ghép tay tệp không mã vào o2 ⇒ người bấm là người ghép.
    await ghep_tay.ghep(
        pool,
        ca.bac_si,
        {"drive_tep_id": cho["KQ_khach_2.pdf"]["id"], "order_id": o2},
        hom_nay_vn(),
    )
    v2 = await _viec(pool, ca, o2)
    assert v2["tep_id"] and v2["nguon_tep"].startswith(
        "Drive · Lab Medlatec · ghép bởi"
    )
    with pytest.raises(ConflictError):
        await ghep_tay.ghep(
            pool,
            ca.bac_si,
            {"drive_tep_id": cho["KQ_khach_2.pdf"]["id"], "order_id": o2},
            hom_nay_vn(),
        )
    # Từ chối ⇒ rời hàng chờ, quét lại không vào lại.
    sai = cho[f"{_sai_so(ma2)}.pdf"]["id"]
    await ghep_tay.tu_choi(
        pool, ca.bac_si, {"drive_tep_id": sai, "ly_do": "không phải của phòng khám"}
    )
    await drive.mot_vong(pool)
    assert f"{_sai_so(ma2)}.pdf" not in await _cho(pool)

    # Gán sang: tờ của o1 gán nhầm ⇒ sang o2; tờ cũ bị bù, o2 có tờ mới.
    cu = (await _viec(pool, ca, o1))["tep_id"]
    await ghep_tay.gan_sang(
        pool,
        ca.bac_si,
        {"order_id": o1, "order_id_moi": o2, "ly_do": "gán nhầm khách"},
        hom_nay_vn(),
    )
    assert (
        await pool.fetchval(
            "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid", cu
        )
        # Tờ máy nhận Hợp lệ ngay (12/11, bỏ bước Xác nhận) ⇒ lệnh bù là Thu hồi.
        == "THU_HOI"
    )
    assert (await _viec(pool, ca, o2))["so_ban"] == 2
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM drive_tep WHERE tep_ket_qua_id = $1::uuid", cu
        )
        == 0
    )


async def test_gan_sang_khac_doi_tac_bi_chan(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
) -> None:
    ca, _a, o1, _o2, ma1, _ma2 = await _dung_ca(pool, gia)
    gia.tha(gia.a, "fileDDDDDDDD01", f"{ma1}.pdf", "e" * 32)
    await drive.mot_vong(pool)
    with pytest.raises(ConflictError, match="KHÁC"):
        await ghep_tay.gan_sang(
            pool,
            ca.bac_si,
            {"order_id": o1, "order_id_moi": o1, "ly_do": "thử"},
            hom_nay_vn(),
        )


async def test_drive_loi_ghi_nhip_va_canh_gac_bao(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kế hoạch mục 7: Drive không đọc được ⇒ nhịp ghi lỗi mỗi lượt; quá 1 giờ không
    quét được ⇒ canh gác mở cảnh báo cho quản lý."""
    from clinicai.services import canh_gac

    ca, a, *_ = await _dung_ca(pool, gia)

    async def hong(_kh: object, _thu_muc: str) -> list[TepDrive]:
        raise drive_api.DriveError("Drive không liệt kê được thư mục (403).")

    monkeypatch.setattr(drive_api, "liet_ke", hong)
    kq = await drive.mot_vong(pool)
    assert kq["loi"] >= 1
    async with pool.acquire() as conn:
        nhip = {n["doi_tac_id"]: n for n in await ghep_tay.ds_nhip(conn, CLINIC)}
        assert "403" in (nhip[str(a)]["loi_cuoi"] or "") and nhip[str(a)]["tre"]
        truoc = (await canh_gac.do_so(conn))["drive_khong_nhip"]
        # Đối tác nối thư mục từ 2 giờ trước, chưa lượt nào thành công ⇒ bị đếm.
        await conn.execute(
            "UPDATE doi_tac SET sua_luc = now() - interval '2 hours'"
            " WHERE id = $1::uuid",
            a,
        )
        so = await canh_gac.do_so(conn)
    assert so["drive_khong_nhip"] == truoc + 1
    assert any(
        k.ma == "DRIVE_KHONG_NHIP" and k.co_chuyen for k in canh_gac.danh_gia(so)
    )
    assert ca


async def test_xem_truoc_chi_anh_pdf_theo_byte_that(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
) -> None:
    """Drive nói mime gì cũng không tin: tệp HTML khai `application/pdf` vẫn bị
    từ chối xem trước (chạy mã trên origin màn); PDF thật thì trả kiểu đã sniff."""
    ca, *_ = await _dung_ca(pool, gia)
    gia.tha(gia.a, "fileEEEEEEEE01", "KQ_khong_ma.pdf", "f" * 32)
    gia.tha(gia.a, "fileEEEEEEEE02", "KQ_html.pdf", "9" * 32)
    gia.noi["fileEEEEEEEE02"] = b"<html><script>alert(1)</script></html>"
    await drive.mot_vong(pool)
    cho = await _cho(pool)
    noi, mime = await ghep_tay.noi_dung_cho(
        pool, ca.bac_si, cho["KQ_khong_ma.pdf"]["id"]
    )
    assert mime == "application/pdf" and noi.startswith(b"%PDF")
    with pytest.raises(ConflictError, match="không xem trước"):
        await ghep_tay.noi_dung_cho(pool, ca.bac_si, cho["KQ_html.pdf"]["id"])


async def test_tien_thu_ho_loc_theo_doi_tac(
    pool: asyncpg.Pool,  # noqa: F811
    gia: DriveGia,
) -> None:
    """Tuyền 05/11: ô lọc đối tác phải lọc cả tab Tiền thu hộ (dòng + tổng)."""
    _ca, a, o1, o2, *_ = await _dung_ca(pool, gia)
    b = await pool.fetchval(
        "SELECT id::text FROM doi_tac WHERE drive_folder_id = $1", gia.b
    )
    hom_nay = hom_nay_vn()
    tat_ca = await thu_ho.so_ngay(pool, CLINIC, hom_nay)
    cua_a = await thu_ho.so_ngay(pool, CLINIC, hom_nay, str(a))
    cua_b = await thu_ho.so_ngay(pool, CLINIC, hom_nay, b)
    ids_a = {d["id"] for d in cua_a["dong"]}
    assert len(ids_a) >= 2 and ids_a <= {d["id"] for d in tat_ca["dong"]}
    assert cua_b["dong"] == [] and cua_b["tong"] == 0
    assert cua_a["tong"] == sum(d["so_tien"] for d in cua_a["dong"])
    assert thu_ho.doc_doi_tac("rác") is None and thu_ho.doc_doi_tac(None) is None
    assert o1 and o2


async def test_khong_khoa_thi_bo_qua(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drive_api, "co_cau_hinh", lambda: False)
    assert await drive.mot_vong(pool) == {"bo_qua": 1}


async def test_ban_tra_doi_tac_lien_quan(pool: asyncpg.Pool, gia: DriveGia) -> None:  # noqa: F811
    """Nhịp quét ghi sau mỗi lượt (đèn trên thẻ đối tác đọc ở đây)."""
    ca, a, *_ = await _dung_ca(pool, gia)
    await drive.mot_vong(pool)
    async with pool.acquire() as conn:
        nhip = {n["doi_tac_id"]: n for n in await ghep_tay.ds_nhip(conn, CLINIC)}
    assert str(a) in nhip and nhip[str(a)]["loi_cuoi"] is None
    assert nhip[str(a)]["tre"] is False
    _ = ket_qua  # cùng nhóm module bàn XN (nhập để chắc import không vòng)
    assert ca
