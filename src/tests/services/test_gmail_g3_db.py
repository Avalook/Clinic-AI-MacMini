"""Gmail G3 — tự ghép thư kết quả Gmail vào đúng việc, chạy thật trên DB (Gmail GIẢ).

Ca biên: thư sau mốc, xác thực đúng miền, tên + SĐT khớp một khách có MỘT việc đang
chờ ⇒ tờ kết quả tự gắn (nguồn GMAIL, chờ xác nhận) + `lab.result_arrived`; trước mốc /
chưa có mốc / không xác thực / Greenlab "Chưa đủ kết quả" ⇒ Lưu trữ (Kho), không ghép;
SĐT không khớp ⇒ hàng ghép tay, Gán tay đọc byte đã lưu ⇒ tờ nguồn GMAIL; khách đã có
tờ ⇒ CO_BAN_MOI + gợi ý việc.
"""

from __future__ import annotations

import asyncio
import pathlib
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem import ghep_tay, gmail, gmail_api, mau
from clinicai.services.xet_nghiem.gmail_api import PhanPdf, ThuGmail
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g2_db import GmailGia
from tests.services.test_xac_nhan_tep_ket_qua_db import PDF_DUMMY
from tests.services.test_xet_nghiem_drive_db import _lam
from tests.services.test_xet_nghiem_drive_db import _thu as _thu_tien
from tests.services.test_xet_nghiem_nen_db import (  # noqa: F401
    _ca_doi_tac,
    _chi_dinh,
    _gan,
    _ma,
    _sp,
    _them_dt,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

XAC_THUC = "mx.google.com; dkim=pass header.i=@lab-thu.vn; spf=pass; dmarc=pass"


class Ca3:
    def __init__(self, g: GmailGia, dt: str, ca: Any) -> None:
        self.g, self.dt, self.ca = g, dt, ca

    async def viec(
        self,
        pool: asyncpg.Pool,  # noqa: F811
        *,
        lay_mau: bool = True,
        ban_xn: bool = True,
    ) -> dict[str, Any]:
        if not ban_xn:
            # Chỉ định KHÔNG có việc Bàn XN (như HPV trên prod 10–11/2026): gán dịch vụ
            # còn đó nhưng không mặc định ⇒ `chup` không tạo việc.
            await pool.execute(
                "UPDATE doi_tac_dich_vu SET mac_dinh = false"
                " WHERE doi_tac_id = $1::uuid",
                self.dt,
            )
        oid = await _chi_dinh(pool, self.ca)
        if ban_xn:
            await _thu_tien(pool, self.ca, oid)
        if ban_xn and lay_mau:
            await _lam(pool, mau.lay_mau, self.ca, order_ids=[oid])
        sdt = "09" + "".join(random.choices("0123456789", k=8))
        r = await pool.fetchrow(
            "UPDATE patient p SET phone_primary = $2 FROM service_order o, visit v"
            " WHERE o.id = $1::uuid AND v.visit_id = o.visit_id"
            "   AND p.clinic_patient_id = v.clinic_patient_id"
            " RETURNING p.clinic_patient_id::text AS kh, p.full_name AS ten",
            oid,
            sdt,
        )
        return {"oid": oid, "kh": r["kh"], "ten": r["ten"], "sdt": sdt}

    def thu(
        self,
        ten: str,
        sdt: str,
        *,
        xac_thuc: str = XAC_THUC,
        nhan: datetime | None = None,
        than: str = "Trạng thái : Đủ kết quả",
    ) -> str:
        mid = uuid.uuid4().hex[:16]
        self.thu_raw = ThuGmail(
            id=mid,
            nhan_luc=nhan or datetime.now(UTC),
            tu=self.g.email,
            tieu_de=f"KQ xét nghiệm KH {ten.upper()} (SID: 091126-1234567) - {sdt}",
            than=than,
            pdf=[PhanPdf("1", "091126-1234567_1.pdf", 100, "att1", None)],
            xac_thuc=xac_thuc,
        )
        self.g.thu[mid] = self.thu_raw
        self.g.noi[(mid, "1")] = PDF_DUMMY + f"\n% {mid}\n".encode()
        # Thư mới: thấy qua trang lịch sử (lượt đầu) VÀ khung "thư mới" (lượt sau,
        # khi lịch sử đã hết) — như Gmail thật.
        self.g.trang[None] = ([mid], None)
        self.g.moi.append(mid)
        return mid


@pytest.fixture
async def c3(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> Ca3:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    for m, ten in (
        (media, "MEDIA_LOCAL_ROOT"),
        (media, "MEDIA_ROOT"),
        (tep_mod, "MEDIA_ROOT"),
    ):
        monkeypatch.setattr(m, ten, tmp_path)
    ca = await _ca_doi_tac(pool)
    email = f"kq_{uuid.uuid4().hex[:8]}@lab-thu.vn"
    dt = await _them_dt(pool, ca.bac_si, _ma(), email_gui_ket_qua=email)
    await _gan(pool, ca.bac_si, dt, await _sp(pool, ca.ma_dv))
    await pool.execute(
        "UPDATE doi_tac SET email_gui_ket_qua = NULL"
        " WHERE email_gui_ket_qua IS NOT NULL AND id <> $1::uuid",
        dt,
    )
    await pool.execute(
        "INSERT INTO xet_nghiem_cai_dat (clinic_id, gmail_tu_ngay)"
        " VALUES ($1::uuid, $2) ON CONFLICT (clinic_id)"
        " DO UPDATE SET gmail_tu_ngay = EXCLUDED.gmail_tu_ngay",
        CLINIC,
        hom_nay_vn(),
    )
    g = GmailGia(email)
    monkeypatch.setenv(gmail.BIEN_PHONG_KHAM, CLINIC)
    monkeypatch.setattr(gmail_api, "co_cau_hinh", lambda: True)
    monkeypatch.setattr(gmail_api, "liet_ke", g.liet_ke)
    monkeypatch.setattr(gmail_api, "doc_thu", g.doc_thu)
    monkeypatch.setattr(gmail_api, "tai_phan", g.tai_phan)
    return Ca3(g, dt, ca)


async def _dong(pool: asyncpg.Pool, mid: str) -> Any:  # noqa: F811
    return await pool.fetchrow(
        "SELECT id::text, ly_do_cho, tep_ket_qua_id::text, goi_y_order_id::text,"
        " goi_y_clinic_patient_id::text, luu_tru_vi_sao"
        " FROM drive_tep WHERE email_message_id = $1",
        mid,
    )


async def test_thu_sau_moc_khop_mot_viec_thi_tu_ghep(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    v = await c3.viec(pool)
    mid = c3.thu(v["ten"], v["sdt"])
    assert (await gmail.mot_vong(pool))["tep_moi"] == 1
    d = await _dong(pool, mid)
    assert d["tep_ket_qua_id"] is not None and d["ly_do_cho"] is None
    tep = await pool.fetchrow(
        "SELECT nguon, service_order_id::text, xac_nhan_trang_thai FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        d["tep_ket_qua_id"],
    )
    assert (tep["nguon"], tep["service_order_id"]) == ("GMAIL", v["oid"])
    assert (
        tep["xac_nhan_trang_thai"] == "CHO_XAC_NHAN"
    )  # người vẫn bấm "Đúng người, gửi"
    den = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type = 'lab.result_arrived'"
        " AND aggregate_id = $1::uuid",
        v["oid"],
    )
    assert den == 1


@pytest.mark.parametrize(
    "ca_hong", ["khong_xac_thuc", "truoc_moc", "chua_du", "khong_moc"]
)
async def test_khong_du_dieu_kien_thi_luu_tru(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
    ca_hong: str,
) -> None:
    v = await c3.viec(pool)
    if ca_hong == "khong_xac_thuc":
        mid = c3.thu(
            v["ten"], v["sdt"], xac_thuc="mx.google.com; dkim=fail; dmarc=fail"
        )
    elif ca_hong == "truoc_moc":
        mid = c3.thu(v["ten"], v["sdt"], nhan=datetime.now(UTC) - timedelta(days=3))
    elif ca_hong == "chua_du":
        mid = c3.thu(v["ten"], v["sdt"], than="Trạng thái : Chưa đủ kết quả")
    else:
        await pool.execute(
            "UPDATE xet_nghiem_cai_dat SET gmail_tu_ngay = NULL"
            " WHERE clinic_id = $1::uuid",
            CLINIC,
        )
        mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert (d["ly_do_cho"], d["tep_ket_qua_id"]) == ("LUU_TRU", None)
    # G5: Lưu trữ phải nói được VÌ SAO.
    assert (
        d["luu_tru_vi_sao"]
        == {
            "khong_xac_thuc": "KHONG_XAC_THUC",
            "truoc_moc": "TRUOC_MOC",
            "chua_du": "CHUA_DU_KET_QUA",
            "khong_moc": "CHUA_DAT_MOC",
        }[ca_hong]
    )


async def test_sdt_khong_khop_vao_hang_ghep_tay_va_gan_tay_doc_byte_da_luu(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    v = await c3.viec(pool)
    mid = c3.thu(v["ten"], "0911000000")
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert (d["ly_do_cho"], d["tep_ket_qua_id"]) == ("KHONG_KHOP_KHACH", None)
    async with pool.acquire() as conn:
        cho = {t["id"]: t for t in await ghep_tay.ds_cho(conn, CLINIC)}
    assert cho[d["id"]]["nguon"] == "GMAIL"
    kq = await ghep_tay.ghep(
        pool,
        c3.ca.bac_si,
        {"drive_tep_id": d["id"], "order_id": v["oid"]},
        hom_nay_vn(),
    )
    assert (
        await pool.fetchval(
            "SELECT nguon FROM tep_ket_qua WHERE id = $1::uuid", kq["tep_id"]
        )
        == "GMAIL"
    )


async def test_khach_da_co_to_thi_co_ban_moi_va_goi_y_viec(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    v = await c3.viec(pool)
    c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)  # bản 1 tự ghép
    mid2 = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid2)
    assert d["ly_do_cho"] == "CO_BAN_MOI" and d["tep_ket_qua_id"] is None
    assert (d["goi_y_order_id"], d["goi_y_clinic_patient_id"]) == (v["oid"], v["kh"])


async def test_tu_ghep_cho_khoa_va_doc_lai_dong_khong_tao_to_thu_hai(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dòng thư hiện ở hàng ghép tay ngay khi commit. Người Từ chối (giữ khoá tệp)
    trong lúc tự ghép đang chờ ⇒ tự ghép đọc lại dòng trong khoá, thôi, không tờ."""
    from clinicai.services.xet_nghiem import gmail_ghep

    goc = gmail_ghep.gan_tu_dong

    async def chua_gan(*_a: object, **_k: object) -> bool:
        return False

    monkeypatch.setattr(gmail_ghep, "gan_tu_dong", chua_gan)
    v = await c3.viec(pool)
    mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert (d["ly_do_cho"], d["tep_ket_qua_id"]) == (None, None)
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM service_order WHERE id = $1::uuid", v["oid"]
    )
    q = gmail_ghep.QuyetGmail(None, v["oid"], v["kh"], vid)
    async with ghep_tay.khoa_tep(pool, d["id"]):
        viec = asyncio.create_task(goc(pool, CLINIC, d["id"], q, PDF_DUMMY, "kq.pdf"))
        await asyncio.sleep(0.3)
        assert not viec.done()  # tự ghép phải CHỜ khoá
        # Đúng thân lệnh Từ chối (`tu_choi` = khoá + `_tu_choi`; khoá test đang giữ).
        await ghep_tay._tu_choi(pool, c3.ca.bac_si, d["id"], "nhầm thư")
    assert await viec is False
    so_to = await pool.fetchval(
        "SELECT count(*) FROM tep_ket_qua WHERE service_order_id = $1::uuid", v["oid"]
    )
    assert so_to == 0


async def _to_cua(pool: asyncpg.Pool, oid: str) -> list[Any]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT nguon, xac_nhan_trang_thai FROM tep_ket_qua"
            " WHERE service_order_id = $1::uuid AND da_xoa_luc IS NULL",
            oid,
        )
    )


async def test_g5_chua_bam_lay_mau_van_tu_gan(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    v = await c3.viec(pool, lay_mau=False)
    mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] is None and d["tep_ket_qua_id"] is not None
    assert [tuple(r) for r in await _to_cua(pool, v["oid"])] == [
        ("GMAIL", "CHO_XAC_NHAN")
    ]


async def test_g5_chi_dinh_khong_o_ban_xn_van_tu_gan_theo_gan_dich_vu(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    """HPV trên prod: chỉ định tạo trước khi gán dịch vụ cho lab ⇒ không có việc Bàn XN.
    Dịch vụ được gán cho lab này ⇒ vẫn là ứng viên, tự gán vào đúng chỉ định."""
    v = await c3.viec(pool, ban_xn=False)
    assert await pool.fetchval(
        "SELECT count(*) FROM xet_nghiem_viec WHERE service_order_id = $1::uuid",
        v["oid"],
    ) == 0  # fmt: skip
    mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] is None and d["tep_ket_qua_id"] is not None
    assert [tuple(r) for r in await _to_cua(pool, v["oid"])] == [
        ("GMAIL", "CHO_XAC_NHAN")
    ]


async def test_g5_to_tai_tay_va_to_gmail_hien_song_song(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    """Tuyền 11/11: chỉ định nhân viên đã tải tờ tay (trước khi có tính năng) ⇒ thư
    Gmail vẫn gắn THÊM vào đúng chỉ định đó — hai tờ cùng hiện, không thay nhau."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    v = await c3.viec(pool, ban_xn=False)
    await TepKetQuaService(pool).tai_len(
        identity=c3.ca.bac_si,
        clinic_patient_id=v["kh"],
        data=PDF_DUMMY + b"\n% tai tay\n",
        ten_hien_thi="anh-tai-tay.pdf",
        service_order_id=v["oid"],
    )
    mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] is None and d["tep_ket_qua_id"] is not None
    assert sorted(r["nguon"] for r in await _to_cua(pool, v["oid"])) == [
        "GMAIL",
        "TAI_LEN",
    ]


async def test_g5_chi_dinh_qua_60_ngay_thi_khong_thay_chi_dinh(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    v = await c3.viec(pool)
    await pool.execute(
        "UPDATE service_order SET created_at = now() - interval '61 days'"
        " WHERE id = $1::uuid",
        v["oid"],
    )
    mid = c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    # Khách có thật (tên + SĐT khớp hồ sơ) nhưng không có chỉ định trong 60 ngày.
    assert (d["ly_do_cho"], d["goi_y_clinic_patient_id"]) == (
        "KHONG_THAY_CHI_DINH",
        v["kh"],
    )
    assert await _to_cua(pool, v["oid"]) == []


async def test_g5_thu_cu_hon_to_da_co_thi_da_co_ket_qua(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    """Gán ngược: tờ đã có (tải tay sau khi nhận thư, hoặc thư trùng) KHÔNG cũ hơn thư
    ⇒ thư đã được xử lý ⇒ chỉ cất ở Kho, không làm đầy hàng chưa gán."""
    await pool.execute(
        "UPDATE xet_nghiem_cai_dat SET gmail_tu_ngay = $2 WHERE clinic_id = $1::uuid",
        CLINIC,
        hom_nay_vn() - timedelta(days=3),
    )
    v = await c3.viec(pool)
    await pool.execute(  # chỉ định từ 4 ngày trước — trước cả hai thư
        "UPDATE service_order SET created_at = now() - interval '4 days'"
        " WHERE id = $1::uuid",
        v["oid"],
    )
    c3.thu(v["ten"], v["sdt"])  # thư mới ⇒ tự gán, tờ mang giờ thư này
    await gmail.mot_vong(pool)
    cu = c3.thu(v["ten"], v["sdt"], nhan=datetime.now(UTC) - timedelta(hours=30))
    await gmail.mot_vong(pool)
    d = await _dong(pool, cu)
    assert (d["ly_do_cho"], d["luu_tru_vi_sao"]) == ("LUU_TRU", "DA_CO_KET_QUA")
    assert len(await _to_cua(pool, v["oid"])) == 1


async def test_g5_ung_vien_dung_lab_dung_cua_so_ngay(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,
) -> None:
    """`doc_chi_dinh`: lab KHÔNG được gán dịch vụ và không phải lab của việc Bàn XN ⇒
    không phải ứng viên. Lab thứ hai CÓ gán dịch vụ (không mặc định — HPV nhiều lab làm)
    ⇒ vẫn là ứng viên dù Bàn XN chụp lab mặc định. Chỉ định SAU giờ nhận thư / quá 60
    ngày / đã huỷ không phải ứng viên."""
    from clinicai.services.xet_nghiem.ghep_khach import doc_chi_dinh

    v = await c3.viec(pool)  # việc Bàn XN chụp c3.dt (lab mặc định)
    la = await _them_dt(pool, c3.ca.bac_si, _ma())  # không gán dịch vụ này
    hai = await _them_dt(pool, c3.ca.bac_si, _ma())
    await _gan(pool, c3.ca.bac_si, hai, await _sp(pool, c3.ca.ma_dv), mac_dinh=False)
    bay_gio = datetime.now(UTC)

    async def ids(conn: Any, dt: str, luc: datetime) -> set[str]:
        return {u.order_id for u in await doc_chi_dinh(conn, CLINIC, dt, luc)}

    async with pool.acquire() as conn:
        assert v["oid"] in await ids(conn, c3.dt, bay_gio)
        # G7: ứng viên mang tên dịch vụ (để suy loại xét nghiệm).
        uv = {u.order_id: u for u in await doc_chi_dinh(conn, CLINIC, c3.dt, bay_gio)}
        assert uv[v["oid"]].ten_dich_vu
        assert v["oid"] in await ids(conn, hai, bay_gio)
        assert v["oid"] not in await ids(conn, la, bay_gio)
        truoc = bay_gio - timedelta(hours=1)  # thư nhận TRƯỚC khi chỉ định
        assert v["oid"] not in {
            u.order_id for u in await doc_chi_dinh(conn, CLINIC, c3.dt, truoc)
        }
        sau_61 = bay_gio + timedelta(days=61)
        assert v["oid"] not in {
            u.order_id for u in await doc_chi_dinh(conn, CLINIC, c3.dt, sau_61)
        }
    await pool.execute(
        "UPDATE service_order SET exec_status = 'cancelled' WHERE id = $1::uuid",
        v["oid"],
    )
    async with pool.acquire() as conn:
        assert v["oid"] not in {
            u.order_id for u in await doc_chi_dinh(conn, CLINIC, c3.dt, bay_gio)
        }
