"""Gmail G9 — thư "không khớp khách" vì tên HOẶC SĐT lệch hồ sơ (Tuyền 11/11/2026).

Soát prod 11/11 (56 thư KHONG_KHOP_KHACH): 31 thư tên đúng mà SĐT khác (lệch 1–2 số
hoặc khách dùng số khác), 9 thư SĐT đúng mà tên gõ lệch / thiếu tên đệm. Máy KHÔNG tự
gán những thư này (nhầm là kết quả vào hồ sơ người khác) — chỉ GỢI Ý khi ra đúng MỘT
khách, và cho nút "Gán cho khách này".

Nút gán không cần Bàn XN (prod 11/11: 0 việc Bàn XN cho cả 3 lab Gmail ⇒ ô "Gán cho
khách" ở tab Kết quả trống). Tờ vào đâu = ĐÚNG luật tự ghép (`gmail_ghep.
quyet_mot_khach`) với khách do người chọn; không có chỉ định ⇒ hồ sơ theo lượt khám
(G8). Người bấm = xác nhận cùng bước (như Gán tay).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import asyncpg

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.xet_nghiem import drive, ghep_khach, ghep_tay, gmail_doc
from clinicai.services.xet_nghiem.ghep_khach import UngVien, chuan
from clinicai.services.xet_nghiem.gmail_doc import DocThu

#: Chữ đệm quá phổ biến — không đủ làm căn cứ "cùng người".
_DEM_PHO_BIEN: Final = frozenset({"thi", "van"})


def ten_gan_giong(a: object, b: object) -> bool:
    """HÀM THUẦN: hai tên (bỏ dấu) là cùng người viết thiếu / thừa chữ — TRÙNG tên gọi
    (chữ cuối) VÀ chữ của tên ngắn hơn nằm hết trong tên dài hơn (thiếu tên đệm / thiếu
    họ: "Trần Mỹ Duyên" ↔ "Trần Thị Mỹ Duyên"). Khác tên gọi ("Lan" ↔ "Hoa") hay khác
    họ ("Trần Thị Lan" ↔ "Nguyễn Thị Lan") ⇒ KHÔNG (người nhà dùng chung SĐT)."""
    ta, tb = chuan(a).split(), chuan(b).split()
    if not ta or not tb or ta == tb or ta[-1] != tb[-1]:
        return bool(ta) and ta == tb
    ngan, dai = sorted((set(ta), set(tb)), key=len)
    return ngan <= dai and len(ngan - _DEM_PHO_BIEN) >= 2


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
    """Nút "Gán cho khách này": giữ CÙNG khoá của Gán tay / Từ chối / tự ghép. Màn gửi
    kèm khách nó đang hiện — gợi ý đổi giữa lúc vẽ và lúc bấm (xét lại) ⇒ 409."""
    async with ghep_tay.khoa_tep(pool, data.get("drive_tep_id")):
        return await _gan(
            pool, identity, data.get("drive_tep_id"), data.get("clinic_patient_id")
        )


async def _gan(
    pool: asyncpg.Pool, identity: StaffIdentity, drive_tep_id: object, thay: object
) -> dict[str, Any]:
    cid = identity.clinic_id
    r = await ghep_tay._dong_cho(pool, cid, drive_tep_id)
    kh = r["goi_y_kh"]
    if not ghep_tay.gan_goi_y_duoc(r["nguon"], r["ly_do_cho"], kh):
        raise ConflictError("Tệp này không có khách gợi ý — tải lại màn.")
    if str(thay or "") != kh:
        raise ConflictError("Khách gợi ý vừa đổi — tải lại màn rồi kiểm lại.")
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
    """(order_id, visit_id, appointment_id) theo ĐÚNG `quyet_mot_khach` + `gan_ho_so`
    của đường tự ghép; lý do khác "ghép được" ⇒ 409 với đúng câu lý do đó."""
    from clinicai.services.xet_nghiem import gmail_ghep

    async with pool.acquire() as conn:
        viec = [
            v
            for v in await ghep_khach.doc_chi_dinh(conn, cid, dt, nhan_luc)
            if v.clinic_patient_id == kh
        ]
        q = gmail_ghep.quyet_mot_khach(loai, viec, kh, nhan_luc)
        if q.ly_do == "KHONG_THAY_CHI_DINH":
            luot = await ghep_khach.luot_gan_nhat(conn, cid, kh, nhan_luc)
            q = gmail_ghep.gan_ho_so(q, luot)
    if q.ly_do is not None:
        if q.ly_do == "KHONG_THAY_CHI_DINH":
            raise ConflictError(
                "Khách không có chỉ định loại này, cũng không có lượt khám nào trong 60"
                " ngày trước thư — kiểm lại khách, hoặc Từ chối tệp."
            )
        raise ConflictError(
            "Chưa gán được: " + ghep_tay.vi_sao_cho(q.ly_do, q.luu_tru_vi_sao) + "."
        )
    return q.order_id, q.visit_id, q.appointment_id
