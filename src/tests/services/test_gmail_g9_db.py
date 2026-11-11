"""Gmail G9 (11/11/2026) — thư "không khớp khách" vì tên / SĐT lệch hồ sơ: máy gợi ý
đúng một khách, KHÔNG tự gán; nút "Gán cho khách này" chạy không cần Bàn XN, tờ vào
đâu theo ĐÚNG luật tự ghép (`gmail_ghep.quyet_mot_khach`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.xet_nghiem import ghep_tay, gmail, gmail_goi_y, gmail_xet_lai
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g3_db import (  # noqa: F401
    Ca3,
    _dong,
    _to_cua,
    c3,
)
from tests.services.test_xac_nhan_tep_ket_qua_db import PDF_DUMMY, _tao_staff

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _nguoi(pool: asyncpg.Pool) -> StaffIdentity:  # noqa: F811
    async with pool.acquire() as conn:
        return await _tao_staff(conn, CLINIC, "NURSE")


async def _cho(pool: asyncpg.Pool, dong_id: str) -> dict[str, Any]:  # noqa: F811
    async with pool.acquire() as conn:
        return next(
            t for t in await ghep_tay.ds_cho(conn, CLINIC) if t["id"] == dong_id
        )


async def _gan(
    pool: asyncpg.Pool,  # noqa: F811
    d: Any,
    kh: str | None = None,
) -> dict[str, Any]:
    """Như màn: gửi kèm khách gợi ý ĐANG HIỆN."""
    return await gmail_goi_y.gan_cho_khach_goi_y(
        pool,
        await _nguoi(pool),
        {
            "drive_tep_id": d["id"],
            "clinic_patient_id": kh or d["goi_y_clinic_patient_id"],
        },
    )


async def _thu_lech_sdt(pool: asyncpg.Pool, c3: Ca3, v: dict[str, Any]) -> Any:  # noqa: F811
    mid = c3.thu(v["ten"], "0988" + v["sdt"][-6:])
    await gmail.mot_vong(pool)
    return await _dong(pool, mid)


async def test_ten_dung_sdt_khac_thi_goi_y_roi_gan_vao_chi_dinh(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Tên đúng, SĐT trong thư khác hồ sơ ⇒ KHÔNG tự gán, gợi ý khách; bấm "Gán cho
    khách này" ⇒ tờ vào đúng chỉ định đang chờ, người bấm = xác nhận (HOP_LE)."""
    v = await c3.viec(pool, ban_xn=False)  # không có việc Bàn XN (như prod 11/11)
    d = await _thu_lech_sdt(pool, c3, v)
    assert d["tep_ket_qua_id"] is None and d["ly_do_cho"] == "KHONG_KHOP_KHACH"
    assert d["goi_y_clinic_patient_id"] == v["kh"]
    t = await _cho(pool, d["id"])
    assert t["gan_goi_y_duoc"] is True and t["goi_y_ten"] == v["ten"]
    assert t["vi_sao"] == ghep_tay.LECH_CO_GOI_Y
    kq = await _gan(pool, d)
    assert kq["vao_chi_dinh"] is True
    assert [tuple(r) for r in await _to_cua(pool, v["oid"])] == [("GMAIL", "HOP_LE")]
    sau = await pool.fetchrow(
        "SELECT tep_ket_qua_id, ghep_boi FROM drive_tep WHERE id = $1::uuid", d["id"]
    )
    assert sau["tep_ket_qua_id"] is not None and sau["ghep_boi"] is not None
    with pytest.raises(ConflictError):  # bấm lần hai: đã ghép
        await _gan(pool, d)


async def test_goi_y_doi_giua_luc_ve_va_luc_bam_thi_409(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Màn đang hiện khách A, xét lại đổi gợi ý ⇒ bấm gán phải bị từ chối, không tờ."""
    v = await c3.viec(pool, ban_xn=False)
    d = await _thu_lech_sdt(pool, c3, v)
    khac = await c3.viec(pool, ban_xn=False)
    with pytest.raises(ConflictError, match="vừa đổi"):
        await _gan(pool, d, khac["kh"])
    assert await _to_cua(pool, v["oid"]) == []


async def test_chi_dinh_chi_co_to_tay_thi_gan_song_song(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Đúng luật tự ghép: chỉ định CHỈ có tờ tải tay ⇒ tờ email vào cùng chỉ định."""
    v = await c3.viec(pool, ban_xn=False)
    await TepKetQuaService(pool).tai_len(
        identity=await _nguoi(pool),
        clinic_patient_id=v["kh"],
        data=PDF_DUMMY,
        ten_hien_thi="tai-tay.pdf",
        service_order_id=v["oid"],
        la_tep_doi_tac=True,
    )
    d = await _thu_lech_sdt(pool, c3, v)
    assert (await _gan(pool, d))["vao_chi_dinh"] is True
    assert len(await _to_cua(pool, v["oid"])) == 2


async def test_chi_dinh_da_co_to_email_thi_khong_gan_trung(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Chỉ định đã có tờ TỪ EMAIL (bản trước) ⇒ như tự ghép: "bản mới", không tạo tờ
    thứ hai gắn vào lượt."""
    v = await c3.viec(pool, ban_xn=False)
    c3.thu(v["ten"], v["sdt"])
    await gmail.mot_vong(pool)  # bản 1 tự ghép
    d = await _thu_lech_sdt(pool, c3, v)
    with pytest.raises(ConflictError, match="Chưa gán được"):
        await _gan(pool, d)
    assert len(await _to_cua(pool, v["oid"])) == 1


async def test_sdt_dung_ten_thieu_ten_dem_khong_chi_dinh_thi_vao_ho_so(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """SĐT đúng, tên thiếu tên đệm; khách không có chỉ định đúng loại (chỉ định quá 60
    ngày) ⇒ gợi ý; bấm gán ⇒ vào hồ sơ theo lượt khám (luật G8), HOP_LE."""
    v = await c3.viec(pool)
    await pool.execute(
        "UPDATE service_order SET created_at = now() - interval '61 days'"
        " WHERE id = $1::uuid",
        v["oid"],
    )
    await pool.execute(
        "UPDATE patient SET full_name = $2 WHERE clinic_patient_id = $1::uuid",
        v["kh"],
        "Trần Thị Mỹ Duyên",
    )
    mid = c3.thu("Trần Mỹ Duyên", v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] == "KHONG_KHOP_KHACH"
    assert d["goi_y_clinic_patient_id"] == v["kh"]
    kq = await _gan(pool, d)
    assert kq["vao_chi_dinh"] is False
    to = await pool.fetchrow(
        "SELECT service_order_id, appointment_id, clinic_patient_id::text AS kh,"
        "       xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid",
        kq["tep_id"],
    )
    assert to["service_order_id"] is None and to["appointment_id"] is not None
    assert (to["kh"], to["xac_nhan_trang_thai"]) == (v["kh"], "HOP_LE")


async def test_khong_chi_dinh_khong_luot_thi_409(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    v = await c3.viec(pool, ban_xn=False)
    d = await _thu_lech_sdt(pool, c3, v)
    await pool.execute(
        "UPDATE service_order SET created_at = now() - interval '61 days'"
        " WHERE id = $1::uuid",
        v["oid"],
    )
    await pool.execute(
        "UPDATE visit SET checked_in_at = now() - interval '70 days',"
        "       created_at = now() - interval '70 days'"
        " WHERE clinic_patient_id = $1::uuid",
        v["kh"],
    )
    with pytest.raises(ConflictError, match="lượt khám"):
        await _gan(pool, d)


async def test_hai_khach_cung_ten_khong_goi_y_va_khong_gan_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Hai khách có chỉ định cùng trùng tên thư, SĐT không khớp ai ⇒ không đoán."""
    v1 = await c3.viec(pool, ban_xn=False)
    v2 = await c3.viec(pool, ban_xn=False)
    await pool.execute(
        "UPDATE patient SET full_name = $2 WHERE clinic_patient_id = ANY($1::uuid[])",
        [v1["kh"], v2["kh"]],
        "Lê Thị Trùng Tên",
    )
    mid = c3.thu("Lê Thị Trùng Tên", "0977123456")
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] == "KHONG_KHOP_KHACH" and d["goi_y_clinic_patient_id"] is None
    assert (await _cho(pool, d["id"]))["gan_goi_y_duoc"] is False
    with pytest.raises(ConflictError):
        await _gan(pool, d, v1["kh"])


async def test_thu_luu_tru_khong_di_cua_gan_goi_y(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Thư trước mốc (Lưu trữ, chỉ Kho email) ⇒ cửa gán theo id nói "không thấy"."""
    v = await c3.viec(pool, ban_xn=False)
    mid = c3.thu(v["ten"], v["sdt"], nhan=datetime.now(UTC) - timedelta(days=30))
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["ly_do_cho"] == "LUU_TRU"
    with pytest.raises(NotFoundError):
        await _gan(pool, d, v["kh"])


async def test_xet_lai_ghi_va_xoa_goi_y_cho_dong_khong_khop(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Dòng "không khớp" nạp TRƯỚC G9 (không gợi ý) ⇒ xét lại ghi gợi ý, lý do giữ;
    gợi ý cũ sai (người khác) ⇒ ghi lại đúng; gọi lại không ghi nữa."""
    v = await c3.viec(pool, ban_xn=False)
    d = await _thu_lech_sdt(pool, c3, v)
    await pool.execute(
        "UPDATE drive_tep SET goi_y_clinic_patient_id = NULL WHERE id = $1::uuid",
        d["id"],
    )
    dem = await gmail_xet_lai.xet_lai(pool, None, CLINIC)  # type: ignore[arg-type]
    assert dem.get("goi_y_moi") == 1
    sau = await pool.fetchrow(
        "SELECT ly_do_cho, goi_y_clinic_patient_id::text AS kh FROM drive_tep"
        " WHERE id = $1::uuid",
        d["id"],
    )
    assert (sau["ly_do_cho"], sau["kh"]) == ("KHONG_KHOP_KHACH", v["kh"])
    dem = await gmail_xet_lai.xet_lai(pool, None, CLINIC)  # type: ignore[arg-type]
    assert dem.get("van_khong_khop_khach") == 1  # gọi lại: không ghi nữa
