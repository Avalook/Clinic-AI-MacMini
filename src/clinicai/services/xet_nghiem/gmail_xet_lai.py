"""Xét lại thư Gmail đã xếp trước khi luật đổi — Gmail G6 + G7 (11/11/2026).

Các nhóm: `LUU_TRU / KHONG_XAC_THUC` (G6: SPF khớp miền), `ONG_NHIEU_VIEC` (G7: tách
HPV / STD theo loại đọc trong PDF), `KHONG_THAY_CHI_DINH` / `KHONG_KHOP_KHACH` (11/11:
SĐT phụ, chỉ định nhập muộn ≤ 7 ngày, khách đúng mà chưa có chỉ định ⇒ vào hồ sơ theo
lượt khám). Quyết lại ra đúng lý do cũ ⇒ để nguyên.

Vì sao có: luật xác thực G3 chỉ nhận DKIM / DMARC đúng miền; HighDetect (lab máu) gửi
qua Google Workspace không DKIM riêng, không DMARC ⇒ thư thật bị xếp oan `LUU_TRU /
KHONG_XAC_THUC` trước khi G6 nhận SPF khớp miền. Máy KHÔNG nạp lại thư đã có (khoá
`(file_id, md5)`), nên các dòng đó phải được xét lại một lần.

Làm gì: mỗi thư còn `LUU_TRU / KHONG_XAC_THUC` của đối tác đang có email ⇒ đọc lại
header từ Gmail (chỉ đọc), người gửi phải đúng email đối tác, chạy LẠI đúng đường quyết
của lúc nạp (`gmail.muc_ca_thu`) trên byte PDF đã lưu ⇒ cập nhật lý do / gợi ý của dòng
(chỉ khi dòng vẫn ở đúng trạng thái đó), quyết "tự ghép" ⇒ `gmail_ghep.gan_tu_dong`
(có khoá như Gán tay). Vẫn không xác thực ⇒ để nguyên. Gọi lại an toàn.

Chạy (Tuyền, trên VPS): `docker exec clinicai_prod-drive-xn-1 python -m
clinicai.services.xet_nghiem.gmail_xet_lai` — in con số, không in dữ liệu khách.
"""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from typing import Final

import asyncpg
import httpx
import structlog

from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.xet_nghiem import gmail, gmail_api, gmail_ghep, gmail_luu

logger = structlog.get_logger()

TRAN: Final = 2000

_DONG_SQL = f"""
SELECT t.id::text AS id, t.doi_tac_id::text AS dt, t.email_message_id AS mid,
       t.file_id, t.khoa, t.vi_tri, d.email_gui_ket_qua AS email,
       t.ly_do_cho, t.luu_tru_vi_sao
  FROM drive_tep t
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
 WHERE t.clinic_id = $1::uuid AND t.nguon = 'GMAIL'
   AND ((t.ly_do_cho = 'LUU_TRU' AND t.luu_tru_vi_sao = 'KHONG_XAC_THUC')
        OR t.ly_do_cho IN ('ONG_NHIEU_VIEC', 'KHONG_THAY_CHI_DINH',
                           'KHONG_KHOP_KHACH'))
   AND t.tep_ket_qua_id IS NULL AND t.tu_choi_luc IS NULL
   AND d.email_gui_ket_qua IS NOT NULL AND d.ngung_luc IS NULL
 ORDER BY t.email_nhan_luc, t.id
 LIMIT {TRAN}
"""

#: Chỉ dòng VẪN ở đúng lý do lúc đọc ($7/$8) — không đè người / lượt khác đã xử lý.
_CAP_NHAT_SQL = """
UPDATE drive_tep
   SET ly_do_cho = $3, luu_tru_vi_sao = $4, goi_y_order_id = $5::uuid,
       goi_y_clinic_patient_id = coalesce($6::uuid, goi_y_clinic_patient_id)
 WHERE clinic_id = $1::uuid AND id = $2::uuid
   AND ly_do_cho = $7 AND luu_tru_vi_sao IS NOT DISTINCT FROM $8
   AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL
"""


def _part_id(file_id: str, mid: str) -> str | None:
    """`gmail:<mid>:<part_id>` (gmail_luu) ⇒ part_id. Khác khuôn ⇒ None."""
    dau = f"gmail:{mid}:"
    return file_id[len(dau) :] if file_id.startswith(dau) else None


async def xet_lai(
    pool: asyncpg.Pool, kh: httpx.AsyncClient, cid: str
) -> dict[str, int]:
    rows = await pool.fetch(_DONG_SQL, cid)
    canh_bao_neu_day("drive_tep", len(rows), TRAN, clinic_id=cid)
    theo_thu: dict[str, list[asyncpg.Record]] = defaultdict(list)
    for r in rows:
        theo_thu[r["mid"]].append(r)
    dem: Counter[str] = Counter(dong=len(rows))
    for mid, dongs in theo_thu.items():
        try:
            await _mot_thu(pool, kh, cid, mid, dongs, dem)
        except gmail_api.GmailError as e:
            dem["loi_gmail"] += len(dongs)
            logger.warning("gmail_xet_lai_loi", message_id=mid, cau=str(e)[:200])
        except Exception as e:  # noqa: BLE001 — một thư lỗi không dừng cả lượt
            # Chỉ tên kiểu lỗi: chuỗi lỗi DB / tệp có thể chứa dữ liệu thư.
            dem["loi"] += len(dongs)
            logger.error("gmail_xet_lai_loi", message_id=mid, loai=type(e).__name__)
    logger.info("gmail_xet_lai_xong", clinic_id=cid, **dict(dem))
    return dict(dem)


async def _mot_thu(
    pool: asyncpg.Pool,
    kh: httpx.AsyncClient,
    cid: str,
    mid: str,
    dongs: list[asyncpg.Record],
    dem: Counter[str],
) -> None:
    thu = await gmail_api.doc_thu(kh, mid)
    if thu is None or thu.tu != dongs[0]["email"]:
        dem["bo_qua"] += len(dongs)  # thư mất / người gửi khác email đối tác
        return
    phan = {p.part_id: p for p in thu.pdf}
    tai: list[tuple[gmail_api.PhanPdf, bytes, asyncpg.Record]] = []
    for d in dongs:
        p = phan.get(_part_id(d["file_id"], mid) or "")
        if p is None:
            dem["bo_qua"] += 1
            continue
        try:
            data = await gmail_luu.doc_het(d["khoa"], d["vi_tri"])
        except Exception as e:  # noqa: BLE001 — byte mất ⇒ để nguyên dòng
            dem["mat_byte"] += 1
            logger.error(
                "gmail_xet_lai_mat_byte", drive_tep_id=d["id"], loai=type(e).__name__
            )
            continue
        tai.append((p, data, d))
    if not tai:
        return
    muc = await gmail.muc_ca_thu(
        pool, cid, dongs[0]["dt"], thu, [(p, b) for p, b, _ in tai]
    )
    for m, (_, _, d) in zip(muc, tai, strict=True):
        await _ap(pool, cid, d, m, dem)


async def _ap(
    pool: asyncpg.Pool,
    cid: str,
    d: asyncpg.Record,
    m: gmail_luu.Muc,
    dem: Counter[str],
) -> None:
    q, dong_id = m.q, d["id"]
    if (q.ly_do, q.luu_tru_vi_sao) == (d["ly_do_cho"], d["luu_tru_vi_sao"]):
        # Quyết lại vẫn như cũ ⇒ để nguyên.
        cu = d["luu_tru_vi_sao"] or d["ly_do_cho"]
        dem["van_" + str(cu).lower()] += 1
        return
    n = await pool.execute(
        _CAP_NHAT_SQL,
        cid,
        dong_id,
        q.ly_do,
        q.luu_tru_vi_sao,
        q.goi_y_order_id,
        q.goi_y_clinic_patient_id or q.clinic_patient_id,
        d["ly_do_cho"],
        d["luu_tru_vi_sao"],
    )
    if n != "UPDATE 1":
        dem["da_doi"] += 1  # dòng vừa được xử lý ở chỗ khác
        return
    if q.ly_do is None:
        try:
            ok = await gmail_ghep.gan_tu_dong(pool, cid, dong_id, q, m.data, m.p.ten)
        except Exception as e:  # noqa: BLE001 — như nhan_thu: dòng sang LOI_TEP
            # Dòng vừa thành "chờ tự gán" (ly_do NULL) — không để kẹt không lý do.
            logger.error(
                "gmail_xet_lai_gan_loi", drive_tep_id=dong_id, loai=type(e).__name__
            )
            await gmail_ghep.danh_loi_tep(pool, cid, dong_id)
            ok = False
        dem["tu_gan" if ok else "gan_loi"] += 1
    else:
        dem[
            f"ly_do:{q.ly_do}" + (f"/{q.luu_tru_vi_sao}" if q.luu_tru_vi_sao else "")
        ] += 1


async def _chay() -> None:
    from clinicai.core.database import close_pool, create_pool

    cid = gmail.phong_kham_cua_khoa()
    if not gmail_api.co_cau_hinh() or cid is None:
        print("Chưa bật Gmail (khoá / GMAIL_CLINIC_ID) — không làm gì.")
        return
    pool = await create_pool()
    try:
        async with httpx.AsyncClient(timeout=60) as kh:
            dem = await xet_lai(pool, kh, cid)
    finally:
        await close_pool(pool)
    print(
        "Xét lại thư 'không xác thực':",
        " · ".join(f"{k} {v}" for k, v in sorted(dem.items())),
    )


if __name__ == "__main__":
    asyncio.run(_chay())
