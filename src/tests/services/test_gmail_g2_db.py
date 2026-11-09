"""Gmail G2 — vòng quét thư kết quả đối tác, chạy thật trên DB (Gmail GIẢ, không mạng).

Ca biên kế hoạch mục 4: thư vào Kho `LUU_TRU` với byte trên ổ VPS (không vào hàng ghép
tay); quét lại không tạo gì; người gửi khác (header From thật) ⇒ bỏ; phần không phải PDF
⇒ bỏ; một PDF tải lỗi ⇒ CẢ thư để lượt sau (không lưu dở); lịch sử theo con trỏ, mỗi
vòng một trang, hết ⇒ không gọi lại; lỗi Gmail ⇒ nhịp lỗi, giữ con trỏ; không khoá ⇒ bỏ
qua; gợi ý khách chỉ khi tên + SĐT khớp đúng một khách; `day_tep` đẩy PDF Gmail lên CFS.
"""

from __future__ import annotations

import hashlib
import pathlib
import random
import stat
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from clinicai.services import day_tep
from clinicai.services.xet_nghiem import ghep_tay, gmail, gmail_api
from clinicai.services.xet_nghiem.gmail_api import PhanPdf, ThuGmail
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g1_db import _dt

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


class GmailGia:
    """Hộp thư giả: thư theo id, trang lịch sử theo con trỏ, lỗi tải theo partId."""

    def __init__(self, email: str) -> None:
        self.email = email
        self.thu: dict[str, ThuGmail] = {}
        self.noi: dict[tuple[str, str], bytes] = {}
        self.trang: dict[str | None, tuple[list[str], str | None]] = {}
        self.moi: list[str] = []
        self.loi_tai: set[str] = set()
        self.goi_lich_su = 0

    def tha(
        self, *, tu: str | None = None, than: str = "", pdf: int = 1, noi: bytes = b""
    ) -> str:
        mid = uuid.uuid4().hex[:16]
        phan = []
        for i in range(1, pdf + 1):
            ten = f"KHACH_THU_081126-50{random.randint(1000, 9999)}_HPV_TMD.pdf"
            phan.append(PhanPdf(str(i), ten, 100, f"att{i}", None))
            self.noi[(mid, str(i))] = noi or b"%PDF-1.4 gia " + f"{mid}:{i}".encode()
        self.thu[mid] = ThuGmail(
            id=mid,
            nhan_luc=datetime(2026, 11, 9, 1, tzinfo=UTC),
            tu=tu or self.email,
            tieu_de="Kết quả xét nghiệm",
            than=than,
            pdf=phan,
        )
        return mid

    async def liet_ke(
        self, _kh: object, q: str, trang: str | None = None, so: int = 100
    ) -> tuple[list[str], str | None, int]:
        assert q.startswith(f"from:{self.email} has:attachment")
        if "after:" in q:
            return list(self.moi), None, len(self.moi)
        self.goi_lich_su += 1
        ids, sau = self.trang.get(trang, ([], None))
        return ids, sau, sum(len(v[0]) for v in self.trang.values())

    async def doc_thu(self, _kh: object, mid: str) -> ThuGmail | None:
        return self.thu.get(mid)

    async def tai_phan(self, _kh: object, mid: str, p: PhanPdf) -> bytes:
        if p.part_id in self.loi_tai:
            raise gmail_api.GmailError("Gmail lỗi HTTP 503 (backendError).")
        return self.noi[(mid, p.part_id)]


@pytest.fixture
async def gia(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> tuple[GmailGia, str]:
    import clinicai.services.media_service as media

    monkeypatch.setattr(media, "MEDIA_LOCAL_ROOT", tmp_path)
    email = f"kq_{uuid.uuid4().hex[:8]}@lab-thu.vn"
    dt_id = await _dt(pool, email)
    # DB test dùng chung trong một lượt: chỉ quét đối tác của test này.
    await pool.execute(
        "UPDATE doi_tac SET email_gui_ket_qua = NULL"
        " WHERE email_gui_ket_qua IS NOT NULL AND id <> $1::uuid",
        dt_id,
    )
    g = GmailGia(email)
    monkeypatch.setattr(gmail_api, "co_cau_hinh", lambda: True)
    monkeypatch.setattr(gmail_api, "liet_ke", g.liet_ke)
    monkeypatch.setattr(gmail_api, "doc_thu", g.doc_thu)
    monkeypatch.setattr(gmail_api, "tai_phan", g.tai_phan)
    return g, dt_id


async def _dong(pool: asyncpg.Pool, dt_id: str) -> list[Any]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT * FROM drive_tep WHERE doi_tac_id = $1::uuid ORDER BY file_id",
            dt_id,
        )
    )


async def _nhip(pool: asyncpg.Pool, dt_id: str) -> Any:  # noqa: F811
    return await pool.fetchrow(
        "SELECT * FROM drive_nhip WHERE doi_tac_id = $1::uuid AND nguon = 'GMAIL'",
        dt_id,
    )


async def test_thu_vao_kho_luu_tru_va_byte_tren_o_vps(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
    tmp_path: pathlib.Path,
) -> None:
    g, dt_id = gia
    mid = g.tha()
    g.trang[None] = ([mid], None)
    assert (await gmail.mot_vong(pool))["tep_moi"] == 1
    (d,) = await _dong(pool, dt_id)
    noi = g.noi[(mid, "1")]
    assert (d["nguon"], d["ly_do_cho"], d["vi_tri"]) == ("GMAIL", "LUU_TRU", "vps")
    assert d["file_id"] == f"gmail:{mid}:1" and d["email_message_id"] == mid
    assert d["sha256"] == hashlib.sha256(noi).hexdigest() and d["so_byte"] == len(noi)
    assert d["ma_ben_doi_tac_tep"] and d["tep_ket_qua_id"] is None
    tep = tmp_path / d["khoa"]
    assert tep.read_bytes() == noi
    assert stat.S_IMODE(tep.stat().st_mode) == 0o600
    assert d["khoa"].startswith(f"{CLINIC}/gmail/{mid}/")
    # Thư Lưu trữ chỉ ở Kho — không vào hàng ghép tay.
    async with pool.acquire() as conn:
        cho = {str(t["id"]) for t in await ghep_tay.ds_cho(conn, CLINIC)}
    assert str(d["id"]) not in cho
    n = await _nhip(pool, dt_id)
    assert n["loi_cuoi"] is None and n["ok_cuoi"] is not None
    assert (n["con_tro_lich_su"], n["so_lich_su_con"]) == (None, 0)


async def test_quet_lai_khong_tao_gi(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
    tmp_path: pathlib.Path,
) -> None:
    g, dt_id = gia
    mid = g.tha(pdf=2)  # thư 2 PDF ⇒ hai dòng
    g.trang[None] = ([mid], None)
    await gmail.mot_vong(pool)
    g.moi = [mid]  # lượt sau thư vẫn nằm trong khung "thư mới"
    assert (await gmail.mot_vong(pool))["tep_moi"] == 0
    assert len(await _dong(pool, dt_id)) == 2
    assert len(list((tmp_path / CLINIC / "gmail" / mid).iterdir())) == 2


async def test_nguoi_gui_khac_va_khong_phai_pdf_bo_qua(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
) -> None:
    g, dt_id = gia
    gia_mao = g.tha(tu="ke.gia@lua-dao.vn")  # `from:` của Gmail khớp nhưng header khác
    anh = g.tha(noi=b"\x89PNG anh dat ten .pdf")
    g.trang[None] = ([gia_mao, anh], None)
    await gmail.mot_vong(pool)
    assert await _dong(pool, dt_id) == []


async def test_mot_pdf_loi_ca_thu_de_luot_sau(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
) -> None:
    g, dt_id = gia
    mid = g.tha(pdf=2)
    g.trang[None] = ([mid], None)
    g.loi_tai = {"2"}
    ket = await gmail.mot_vong(pool)
    assert ket["loi"] == 1
    assert await _dong(pool, dt_id) == []  # không lưu dở PDF 1
    n = await _nhip(pool, dt_id)
    assert "503" in n["loi_cuoi"] and n["ok_cuoi"] is None
    g.loi_tai = set()
    await gmail.mot_vong(pool)
    assert [d["file_id"] for d in await _dong(pool, dt_id)] == [
        f"gmail:{mid}:1",
        f"gmail:{mid}:2",
    ]


async def test_lich_su_theo_con_tro_moi_vong_mot_trang(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
) -> None:
    g, dt_id = gia
    a, b, c = g.tha(), g.tha(), g.tha()
    g.trang = {None: ([a, b], "TRANG2"), "TRANG2": ([c], None)}
    await gmail.mot_vong(pool)
    n = await _nhip(pool, dt_id)
    assert n["con_tro_lich_su"] == "TRANG2" and n["so_lich_su_con"] == 1
    assert len(await _dong(pool, dt_id)) == 2
    # Gmail lỗi giữa chừng ⇒ giữ con trỏ (không nhảy trang).
    g.loi_tai = {"1"}
    await gmail.mot_vong(pool)
    assert (await _nhip(pool, dt_id))["con_tro_lich_su"] == "TRANG2"
    g.loi_tai = set()
    await gmail.mot_vong(pool)
    n = await _nhip(pool, dt_id)
    assert (n["con_tro_lich_su"], n["so_lich_su_con"]) == (None, 0)
    assert len(await _dong(pool, dt_id)) == 3
    truoc = g.goi_lich_su
    await gmail.mot_vong(pool)
    assert g.goi_lich_su == truoc, "lịch sử đã hết thì không đọc lại"


async def test_khong_khoa_thi_bo_qua(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gmail_api, "co_cau_hinh", lambda: False)
    assert await gmail.mot_vong(pool) == {"bo_qua": 1}


async def _khach(pool: asyncpg.Pool, ten: str, sdt: str) -> str:  # noqa: F811
    loc = await pool.fetchval(
        "SELECT id FROM clinic_location WHERE clinic_id = $1::uuid ORDER BY created_at"
        " LIMIT 1",
        CLINIC,
    )
    return str(
        await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary) VALUES ($1::uuid, $2, $3, $4, $5)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"GM-{uuid.uuid4().hex[:10]}",
            ten,
            loc,
            sdt,
        )
    )


def _sdt() -> str:
    return "09" + "".join(random.choices("0123456789", k=8))


async def test_goi_y_khach_chi_khi_ten_va_sdt_khop_dung_mot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    sdt = _sdt()
    me = await _khach(pool, "Trần Thị Mẫu Gmail", sdt)
    con = await _khach(pool, "Lê Thị Con Gmail", sdt)  # mẹ con chung số
    async with pool.acquire() as conn:
        assert await gmail.goi_y_khach(conn, CLINIC, f"TRAN THI MAU GMAIL {sdt}") == me
        assert (
            await gmail.goi_y_khach(
                conn, CLINIC, f"Họ tên: Lê Thị Con Gmail SĐT: {sdt}"
            )
            == con
        )
        # Chỉ SĐT, không tên ⇒ không gợi ý; chỉ tên ⇒ không gợi ý; rác ⇒ None.
        assert await gmail.goi_y_khach(conn, CLINIC, f"SĐT {sdt}") is None
        assert await gmail.goi_y_khach(conn, CLINIC, "Trần Thị Mẫu Gmail") is None
        assert await gmail.goi_y_khach(conn, CLINIC, "") is None
        # +84 cũng nhận ra.
        assert (
            await gmail.goi_y_khach(conn, CLINIC, f"Tran Thi Mau Gmail +84{sdt[1:]}")
            == me
        )


async def test_goi_y_ghi_vao_dong_kho(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
) -> None:
    g, dt_id = gia
    sdt = _sdt()
    kh = await _khach(pool, "Phạm Thị Gợi Ý", sdt)
    mid = g.tha(than=f"Họ tên: PHẠM THỊ GỢI Ý, SĐT {sdt}")
    g.trang[None] = ([mid], None)
    await gmail.mot_vong(pool)
    (d,) = await _dong(pool, dt_id)
    assert str(d["goi_y_clinic_patient_id"]) == kh
    assert d["ly_do_cho"] == "LUU_TRU" and d["tep_ket_qua_id"] is None  # chỉ gợi ý


async def test_day_tep_dua_pdf_gmail_len_cfs(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
    tmp_path: pathlib.Path,
) -> None:
    g, dt_id = gia
    mid = g.tha()
    g.trang[None] = ([mid], None)
    await gmail.mot_vong(pool)
    cfs = tmp_path.parent / f"cfs-{uuid.uuid4().hex[:6]}"
    cfs.mkdir()
    await day_tep.day_mot_lo(
        pool, goc_vps=tmp_path, goc_cfs=cfs, gioi_han=500, bang="drive_tep"
    )
    (d,) = await _dong(pool, dt_id)
    assert d["vi_tri"] == "cfs" and d["da_day_luc"] is not None
    assert (cfs / d["khoa"]).read_bytes() == g.noi[(mid, "1")]


async def test_mat_quyen_gmail_qua_mot_gio_thi_canh_gac_bao(
    pool: asyncpg.Pool,  # noqa: F811
    gia: tuple[GmailGia, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinicai.services import canh_gac

    _g, dt_id = gia

    async def mat_quyen(*_a: object, **_k: object) -> object:
        raise gmail_api.GmailError("Mất quyền đọc Gmail — cấp lại quyền.")

    monkeypatch.setattr(gmail_api, "liet_ke", mat_quyen)
    assert (await gmail.mot_vong(pool))["loi"] == 1
    assert "cấp lại quyền" in (await _nhip(pool, dt_id))["loi_cuoi"]
    async with pool.acquire() as conn:
        truoc = (await canh_gac.do_so(conn))["gmail_khong_nhip"]
        # Đặt email từ 2 giờ trước, chưa lượt nào thành công ⇒ bị đếm.
        await conn.execute(
            "UPDATE doi_tac SET sua_luc = now() - interval '2 hours'"
            " WHERE id = $1::uuid",
            dt_id,
        )
        so = await canh_gac.do_so(conn)
    assert so["gmail_khong_nhip"] == truoc + 1
    assert any(
        k.ma == "GMAIL_KHONG_NHIP" and k.co_chuyen for k in canh_gac.danh_gia(so)
    )
