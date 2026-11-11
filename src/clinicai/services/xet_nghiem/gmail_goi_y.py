"""Gmail G9 — thư "không khớp khách" vì tên HOẶC SĐT lệch hồ sơ (Tuyền 11/11/2026).

Soát prod 11/11 (56 thư KHONG_KHOP_KHACH): 31 thư tên đúng mà SĐT khác (lệch 1–2 số
hoặc khách dùng số khác), 9 thư SĐT đúng mà tên gõ lệch / thiếu tên đệm. Máy KHÔNG tự
gán những thư này (nhầm là kết quả vào hồ sơ người khác) — chỉ GỢI Ý khi ra đúng MỘT
khách, và cho nút "Gán cho khách này".

Nút gán không cần Bàn XN (prod 11/11: 0 việc Bàn XN cho cả 3 lab Gmail ⇒ ô "Gán cho
khách" ở tab Kết quả trống): khách gợi ý có đúng MỘT chỉ định đúng loại đang chờ ⇒ gán
vào chỉ định; không có ⇒ vào hồ sơ theo lượt khám gần nhất (luật G8). Người bấm = xác
nhận cùng bước (như Gán tay).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.xet_nghiem import drive, ghep_khach, ghep_tay, gmail_doc
from clinicai.services.xet_nghiem.ghep_khach import UngVien, chuan
from clinicai.services.xet_nghiem.gmail_doc import DocThu


def ten_gan_giong(a: object, b: object) -> bool:
    """HÀM THUẦN: hai tên (bỏ dấu) gần giống — chung ≥ nửa số chữ, hoặc trùng hai chữ
    cuối (tên đệm + tên). Bắt "Nguyễn Thị Lan" ↔ "Nguyễn Lan", lỗi gõ một chữ."""
    ta, tb = chuan(a).split(), chuan(b).split()
    if not ta or not tb:
        return False
    sa, sb = set(ta), set(tb)
    return len(sa & sb) / len(sa | sb) >= 0.5 or (
        len(ta) >= 2 and len(tb) >= 2 and ta[-2:] == tb[-2:]
    )


def goi_y_lech(
    ten: str | None, sdt: str | None, ung_vien: Sequence[UngVien]
) -> str | None:
    """HÀM THUẦN: khách gợi ý cho thư không khớp cả tên lẫn SĐT. Gợi ý khi ĐÚNG MỘT
    khách (a) trùng nguyên tên (SĐT khác / thư không có SĐT), hoặc (b) mang SĐT của
    thư VÀ tên gần giống. `ung_vien` = khách có chỉ định của lab trong cửa sổ + khách
    mang SĐT thư. Không ai / nhiều người ⇒ None (không đoán)."""
    t = chuan(ten)
    if not t:
        return None
    khach = {u.clinic_patient_id for u in ung_vien if chuan(u.ten) == t}
    if sdt:
        khach |= {
            u.clinic_patient_id
            for u in ung_vien
            if sdt in ghep_khach._sdt_cua(u.sdt) and ten_gan_giong(u.ten, ten)
        }
    return next(iter(khach)) if len(khach) == 1 else None


async def tim(
    conn: asyncpg.Connection, cid: str, d: DocThu, viec: list[UngVien]
) -> str | None:
    """Gợi ý cho MỘT PDF (lúc nạp / xét lại). Tên trùng chỉ xét trong khách CÓ chỉ định
    của lab (tên phổ biến trùng hàng chục hồ sơ toàn phòng khám)."""
    from clinicai.services.xet_nghiem import gmail_luu

    theo_sdt = await gmail_luu.khach_theo_sdt(conn, cid, {d.sdt} if d.sdt else set())
    return goi_y_lech(d.ten, d.sdt, [*viec, *theo_sdt])


async def gan_cho_khach_goi_y(
    pool: asyncpg.Pool, identity: StaffIdentity, data: dict[str, Any]
) -> dict[str, Any]:
    """Nút "Gán cho khách này": giữ CÙNG khoá của Gán tay / Từ chối / tự ghép."""
    async with ghep_tay.khoa_tep(pool, data.get("drive_tep_id")):
        return await _gan(pool, identity, data.get("drive_tep_id"))


async def _gan(
    pool: asyncpg.Pool, identity: StaffIdentity, drive_tep_id: object
) -> dict[str, Any]:
    cid = identity.clinic_id
    r = await ghep_tay._dong_cho(pool, cid, drive_tep_id)
    kh = r["goi_y_kh"]
    if not ghep_tay.gan_goi_y_duoc(r["nguon"], r["ly_do_cho"], kh):
        raise ConflictError("Tệp này không có khách gợi ý — tải lại màn.")
    noi = await ghep_tay._byte(r)
    loai = gmail_doc.loai_ket_qua(ghep_khach.chu_pdf(noi))
    order_id, visit_id, appointment_id = await _dich(
        pool, cid, r["doi_tac_id"], kh, r["email_nhan_luc"], loai
    )
    kq = await TepKetQuaService(pool).tai_len(
        identity=identity,
        clinic_patient_id=kh,
        data=noi,
        ten_hien_thi=r["ten"],
        service_order_id=order_id,
        appointment_id=None if order_id else appointment_id,
        la_tep_doi_tac=True,
        tu_drive=True,
        tu_gmail=True,
    )
    await ghep_tay.ghi_da_ghep(pool, identity, r["id"], kq["id"])
    if order_id is not None:
        await drive._phat_den(pool, cid, drive.Quyet(order_id, kh, visit_id, None))
    return {"tep_id": kq["id"], "vao_chi_dinh": order_id is not None}


async def _dich(
    pool: asyncpg.Pool,
    cid: str,
    dt: str,
    kh: str,
    nhan_luc: Any,
    loai: frozenset[str],
) -> tuple[str | None, str | None, str | None]:
    """(order_id, visit_id, appointment_id) — đúng luật tự gán (G5–G8) nhưng khách do
    người chọn: đúng 1 chỉ định đúng loại chưa có tờ ⇒ chỉ định; không ⇒ lượt khám."""
    from clinicai.services.xet_nghiem.gmail_ghep import dung_loai

    async with pool.acquire() as conn:
        viec = [
            v
            for v in await ghep_khach.doc_chi_dinh(conn, cid, dt, nhan_luc)
            if v.clinic_patient_id == kh
        ]
        cho = [v for v in dung_loai(loai, viec) if not v.co_tep]
        if len(cho) > 1:
            raise ConflictError(
                f"Khách có {len(cho)} xét nghiệm cùng loại đang chờ kết quả — mở hồ sơ"
                " khách, gán tờ vào đúng chỉ định."
            )
        if cho:
            return cho[0].order_id, cho[0].visit_id, None
        luot = await ghep_khach.luot_gan_nhat(conn, cid, kh, nhan_luc)
    if luot is None:
        raise ConflictError(
            "Khách không có lượt khám nào trong 60 ngày trước thư — kiểm lại khách,"
            " hoặc Từ chối tệp."
        )
    return None, luot[0], luot[1]
