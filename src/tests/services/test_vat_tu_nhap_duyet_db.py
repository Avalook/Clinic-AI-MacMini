"""G8b — Phiếu NHẬP vật tư thuộc loại "cần duyệt nhập" phải qua người duyệt.

    scripts/test-nhanh.sh src/tests/services/test_vat_tu_nhap_duyet_db.py

Mặt hàng có cờ `can_duyet_nhap_vat_tu` (Quản lý đặt ở danh mục): phiếu NHẬP có ít
nhất một dòng như vậy thành YÊU CẦU "chờ duyệt" — KHÔNG chạm sổ / tồn. Người có
lego Duyệt vật tư (`vat_tu.approve`: Quản lý, Trưởng ca được cấp) duyệt thì hệ
thống lập phiếu NHẬP thật (sổ chỉ thêm) đúng số đã xin; từ chối (bắt lý do) hoặc
người lập rút lại thì không có gì vào sổ. Người có lego tự lập = tự duyệt. Hoàn
tác một lần nhập đã duyệt = phiếu đảo như mọi phiếu.

BẤT BIẾN:
  N1  Yêu cầu CHỜ / TỪ CHỐI / RÚT LẠI không có phiếu, không đổi tồn dù một đồng;
      yêu cầu ĐÃ DUYỆT có đúng MỘT phiếu NHẬP, đúng số.
  N2  Tồn mỗi nơi chứa = cộng dồn sổ (như G8a) — kể cả sau duyệt / hoàn tác.
  N3  Chỉ người CÓ lego duyệt / từ chối được (Python + Postgres); một yêu cầu chỉ
      quyết MỘT lần; gửi lại không nhân đôi.
  N4  Hàng không cờ nhập → như cũ (ghi sổ ngay) — không làm vỡ G8a.
"""

from __future__ import annotations

import random
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ClinicAIBaseException, SafetyGateError
from clinicai.services.permission_service import PermissionService
from clinicai.services.vat_tu_kho_service import hoan_phieu, tao_phieu
from clinicai.services.vat_tu_nhap_duyet_service import (
    doc_cho_duyet,
    duyet,
    rut_lai,
    tu_choi,
)
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_permission_db import quan_ly  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


class Bo:
    def __init__(
        self,
        lap: StaffIdentity,
        ql: StaffIdentity,
        vt_can: str,
        vt_thuong: str,
        phong: str,
    ) -> None:
        self.lap, self.ql = lap, ql
        self.vt_can, self.vt_thuong, self.phong = vt_can, vt_thuong, phong


async def _bo(pool: asyncpg.Pool) -> Bo:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY id LIMIT 1",
            CLINIC,
        )
        lap = await _nguoi(conn, loc, "PHARMACIST")  # không có lego duyệt
        ql = await _nguoi(conn, loc, "MANAGEMENT")  # có sẵn lego duyệt
        vt_can = await conn.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " don_vi, gia_nhap_vat_tu, can_duyet_nhap_vat_tu)"
            " VALUES ($1::uuid, $2, 'Găng cần duyệt nhập', 'vat_tu', 'hộp', 50000,"
            " true) RETURNING id::text",
            CLINIC,
            f"VT_TEST_{uuid.uuid4().hex}",
        )
        vt_thuong = await conn.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " don_vi) VALUES ($1::uuid, $2, 'Gạc nhập thường', 'vat_tu', 'cái')"
            " RETURNING id::text",
            CLINIC,
            f"VT_TEST_{uuid.uuid4().hex}",
        )
        phong = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3, 'Phòng vật tư', 'DICHVU-SIEUAM')"
            " RETURNING id::text",
            CLINIC,
            loc,
            f"VT-{uuid.uuid4().hex}",
        )
    return Bo(lap, ql, vt_can, vt_thuong, phong)


def _dong(vt: str, so: Any = 5) -> dict[str, Any]:
    return {"vat_tu_id": vt, "so_luong": so}


async def _nhap(
    pool: asyncpg.Pool,  # noqa: F811
    ai: StaffIdentity,
    dong: list[dict[str, Any]],
    khoa: str | None = None,
) -> dict[str, Any]:
    return await tao_phieu(
        pool,
        identity=ai,
        khoa_gui=khoa or uuid.uuid4().hex,
        loai="NHAP",
        ghi_chu="Bài nhập chờ duyệt",
        dong=dong,
    )


async def _ton(pool: asyncpg.Pool, vt: str) -> Decimal:  # noqa: F811
    v = await pool.fetchval(
        "SELECT coalesce(sum(so_luong), 0) FROM vat_tu_ton"
        " WHERE clinic_id = $1::uuid AND vat_tu_id = $2::uuid",
        CLINIC,
        vt,
    )
    return Decimal(v)


async def _yc(pool: asyncpg.Pool, yc: str) -> asyncpg.Record:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT * FROM vat_tu_nhap_cho_duyet WHERE id = $1::uuid", yc
    )
    assert r is not None
    return r


# ── N4: hàng không cờ → như cũ ───────────────────────────────────────────────


async def test_hang_khong_co_co_nhap_ghi_so_ngay_nhu_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    kq = await _nhap(pool, b.lap, [_dong(b.vt_thuong, 4)])
    assert kq.get("cho_duyet") is not True and kq["loai"] == "NHAP"
    assert await _ton(pool, b.vt_thuong) == 4
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM vat_tu_nhap_cho_duyet WHERE tao_boi = $1::uuid",
            b.lap.staff_id,
        )
        == 0
    )


# ── Chờ duyệt: không chạm sổ ─────────────────────────────────────────────────


async def test_retry_sau_bo_co_duyet_khong_nhap_kho_hai_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    khoa = uuid.uuid4().hex
    dau = await _nhap(pool, b.lap, [_dong(b.vt_can, 7)], khoa)
    await pool.execute(
        "UPDATE service_price SET can_duyet_nhap_vat_tu = false WHERE id=$1::uuid",
        b.vt_can,
    )

    lai = await _nhap(pool, b.lap, [_dong(b.vt_can, 7)], khoa)
    assert lai["yeu_cau_id"] == dau["yeu_cau_id"]
    assert lai["cho_duyet"] is True and lai["gui_lai"] is True
    assert await _ton(pool, b.vt_can) == 0

    await duyet(pool, identity=b.ql, yeu_cau_id=dau["yeu_cau_id"])
    assert await _ton(pool, b.vt_can) == 7
    sau_duyet = await _nhap(pool, b.lap, [_dong(b.vt_can, 7)], khoa)
    assert sau_duyet["yeu_cau_id"] == dau["yeu_cau_id"]
    assert sau_duyet["trang_thai"] == "DA_DUYET"
    assert await _ton(pool, b.vt_can) == 7


async def test_phieu_nhap_hang_can_duyet_thanh_yeu_cau_cho_khong_doi_ton(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    khoa = uuid.uuid4().hex
    kq = await _nhap(pool, b.lap, [_dong(b.vt_can, 7)], khoa)
    assert kq["cho_duyet"] is True and kq["ok"] is True
    yc = await _yc(pool, kq["yeu_cau_id"])
    assert yc["trang_thai"] == "CHO_DUYET" and yc["phieu_id"] is None
    assert await _ton(pool, b.vt_can) == 0
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM vat_tu_txn WHERE vat_tu_id = $1::uuid", b.vt_can
        )
        == 0
    )
    # Gửi lại cùng khoá = cùng yêu cầu, không nhân đôi.
    lai = await _nhap(pool, b.lap, [_dong(b.vt_can, 7)], khoa)
    assert lai["yeu_cau_id"] == kq["yeu_cau_id"] and lai["gui_lai"] is True
    # Phiếu HỖN HỢP (một dòng cần duyệt, một dòng thường): cả phiếu chờ, dòng
    # thường cũng chưa vào sổ — không ghi nửa phiếu.
    hon = await _nhap(pool, b.lap, [_dong(b.vt_can, 2), _dong(b.vt_thuong, 3)])
    assert hon["cho_duyet"] is True
    assert await _ton(pool, b.vt_thuong) == 0
    ds = await doc_cho_duyet(pool, identity=b.ql)
    ids = {x["id"] for x in ds if x["trang_thai"] == "CHO_DUYET"}
    assert {kq["yeu_cau_id"], hon["yeu_cau_id"]} <= ids


async def test_dong_rac_bi_tu_choi_truoc_khi_ghi_yeu_cau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    truoc = await pool.fetchval("SELECT count(*) FROM vat_tu_nhap_cho_duyet")
    for so in (0, -3, "abc", "NaN", "Infinity", None, True, "1.0005"):
        with pytest.raises(ValidationError):
            await _nhap(pool, b.lap, [_dong(b.vt_can, so)])
    with pytest.raises(ValidationError):
        await _nhap(pool, b.lap, [_dong(b.vt_can, 1), _dong(b.vt_can, 2)])
    assert await pool.fetchval("SELECT count(*) FROM vat_tu_nhap_cho_duyet") == truoc


# ── Duyệt / từ chối / rút lại ───────────────────────────────────────────────


async def test_nguoi_co_lego_duyet_thi_lap_phieu_nhap_that_dung_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    kq = await _nhap(pool, b.lap, [_dong(b.vt_can, 7)])
    yc_id = kq["yeu_cau_id"]
    # Người lập không có lego → không tự duyệt được.
    with pytest.raises(SafetyGateError):
        await duyet(pool, identity=b.lap, yeu_cau_id=yc_id)
    assert await _ton(pool, b.vt_can) == 0

    ok = await duyet(pool, identity=b.ql, yeu_cau_id=yc_id)
    assert ok["ok"] is True and ok["phieu_id"]
    yc = await _yc(pool, yc_id)
    assert yc["trang_thai"] == "DA_DUYET" and str(yc["quyet_boi"]) == b.ql.staff_id
    assert str(yc["phieu_id"]) == ok["phieu_id"]
    assert await _ton(pool, b.vt_can) == 7
    phieu = await pool.fetchrow(
        "SELECT loai FROM vat_tu_phieu WHERE id = $1::uuid", ok["phieu_id"]
    )
    assert phieu is not None and phieu["loai"] == "NHAP"
    # Giá nhập là bản chụp lúc LẬP YÊU CẦU (danh mục đổi sau không đổi lịch sử).
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu = 99000 WHERE id = $1::uuid",
        b.vt_can,
    )
    gia = await pool.fetchval(
        "SELECT gia_nhap FROM vat_tu_txn WHERE phieu_id = $1::uuid", ok["phieu_id"]
    )
    assert gia == 50000
    # Duyệt lại / hai máy cùng bấm: không nhân đôi.
    lai = await duyet(pool, identity=b.ql, yeu_cau_id=yc_id)
    assert lai["already"] is True and lai["phieu_id"] == ok["phieu_id"]
    assert await _ton(pool, b.vt_can) == 7
    # Hoàn tác nhập đã duyệt = phiếu đảo, tồn về.
    await hoan_phieu(
        pool,
        identity=b.ql,
        phieu_id=ok["phieu_id"],
        khoa_gui=uuid.uuid4().hex,
        ghi_chu="Nhập nhầm",
    )
    assert await _ton(pool, b.vt_can) == 0


async def test_tu_choi_bat_ly_do_rut_lai_va_chi_quyet_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    kq = await _nhap(pool, b.lap, [_dong(b.vt_can, 3)])
    yc_id = kq["yeu_cau_id"]
    with pytest.raises(SafetyGateError):
        await tu_choi(pool, identity=b.lap, yeu_cau_id=yc_id, ly_do="Không đủ quyền")
    for ly in (None, "", "   ", "ab", "x" * 501, 123):
        with pytest.raises(ValidationError):
            await tu_choi(pool, identity=b.ql, yeu_cau_id=yc_id, ly_do=ly)
    ok = await tu_choi(
        pool, identity=b.ql, yeu_cau_id=yc_id, ly_do="Đặt nhầm số lượng so với đơn"
    )
    assert ok["ok"] is True
    yc = await _yc(pool, yc_id)
    assert yc["trang_thai"] == "TU_CHOI" and yc["phieu_id"] is None
    assert yc["quyet_ly_do"] == "Đặt nhầm số lượng so với đơn"
    # Đã quyết một lần → không duyệt / rút lại / từ chối nữa.
    with pytest.raises(ConflictError):
        await duyet(pool, identity=b.ql, yeu_cau_id=yc_id)
    with pytest.raises(ConflictError):
        await rut_lai(pool, identity=b.lap, yeu_cau_id=yc_id)
    assert await _ton(pool, b.vt_can) == 0

    # Người lập tự RÚT LẠI khi còn chờ (hoàn tác được); người lạ không lego thì không.
    kq2 = await _nhap(pool, b.lap, [_dong(b.vt_can, 3)])
    la = await _nguoi_la(pool)
    with pytest.raises(SafetyGateError):
        await rut_lai(pool, identity=la, yeu_cau_id=kq2["yeu_cau_id"])
    await rut_lai(pool, identity=b.lap, yeu_cau_id=kq2["yeu_cau_id"])
    assert (await _yc(pool, kq2["yeu_cau_id"]))["trang_thai"] == "RUT_LAI"
    with pytest.raises(ConflictError):
        await duyet(pool, identity=b.ql, yeu_cau_id=kq2["yeu_cau_id"])
    # Lập lại sau khi rút = yêu cầu MỚI (khoá khác) — làm lại được.
    kq3 = await _nhap(pool, b.lap, [_dong(b.vt_can, 3)])
    assert kq3["yeu_cau_id"] != kq2["yeu_cau_id"]
    with pytest.raises((NotFoundError, ValidationError)):
        await duyet(pool, identity=b.ql, yeu_cau_id=str(uuid.uuid4()))
    with pytest.raises(ValidationError):
        await duyet(pool, identity=b.ql, yeu_cau_id="không-phải-uuid")


async def _nguoi_la(pool: asyncpg.Pool) -> StaffIdentity:  # noqa: F811
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY id LIMIT 1",
            CLINIC,
        )
        return await _nguoi(conn, loc, "RECEPTION")


async def test_nguoi_co_lego_tu_lap_la_tu_duyet_ghi_so_ngay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    kq = await _nhap(pool, b.ql, [_dong(b.vt_can, 6)])
    assert kq.get("cho_duyet") is not True
    assert await _ton(pool, b.vt_can) == 6
    yc = await _yc(pool, kq["yeu_cau_id"])
    assert yc["trang_thai"] == "DA_DUYET" and str(yc["quyet_boi"]) == b.ql.staff_id
    assert str(yc["phieu_id"]) == kq["id"]


async def test_truong_ca_duoc_cap_lego_duyet_nhap_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    b = await _bo(pool)
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY id LIMIT 1",
            CLINIC,
        )
        tc = await _nguoi(conn, loc, "TRUONG_CA")
    kq = await _nhap(pool, b.lap, [_dong(b.vt_can, 2)])
    with pytest.raises(SafetyGateError):  # chưa có lego
        await duyet(pool, identity=tc, yeu_cau_id=kq["yeu_cau_id"])
    svc = PermissionService(pool)
    await svc.cap_khoi(staff_id=tc.staff_id, khoi="duyet_vat_tu", identity=quan_ly)
    await duyet(pool, identity=tc, yeu_cau_id=kq["yeu_cau_id"])
    assert await _ton(pool, b.vt_can) == 2
    # Thu lego → không duyệt thêm được nữa.
    kq2 = await _nhap(pool, b.lap, [_dong(b.vt_can, 2)])
    await svc.thu_khoi(staff_id=tc.staff_id, khoi="duyet_vat_tu", identity=quan_ly)
    with pytest.raises(SafetyGateError):
        await duyet(pool, identity=tc, yeu_cau_id=kq2["yeu_cau_id"])


async def test_postgres_gac_yeu_cau_da_quyet_va_nguoi_quyet(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    b = await _bo(pool)
    kq = await _nhap(pool, b.lap, [_dong(b.vt_can, 2)])
    yc_id = kq["yeu_cau_id"]
    # Ghi thẳng: người không có lego không "duyệt" / "từ chối" được.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE vat_tu_nhap_cho_duyet SET trang_thai = 'TU_CHOI',"
            " quyet_boi = $2::uuid, quyet_luc = now(),"
            " quyet_ly_do = 'Ghi thẳng không có quyền' WHERE id = $1::uuid",
            yc_id,
            b.lap.staff_id,
        )
    # Không xoá, không sửa dòng đã xin.
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "DELETE FROM vat_tu_nhap_cho_duyet WHERE id = $1::uuid", yc_id
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE vat_tu_nhap_cho_duyet SET dong = '[]'::jsonb WHERE id = $1::uuid",
            yc_id,
        )
    await tu_choi(pool, identity=b.ql, yeu_cau_id=yc_id, ly_do="Không cần nhập nữa")
    # Đã chốt: không lật lại bằng ghi thẳng.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE vat_tu_nhap_cho_duyet SET trang_thai = 'CHO_DUYET',"
            " quyet_boi = NULL, quyet_luc = NULL, quyet_ly_do = NULL"
            " WHERE id = $1::uuid",
            yc_id,
        )


# ── Bấm lộn xộn ──────────────────────────────────────────────────────────────


async def _bat_bien(pool: asyncpg.Pool, b: Bo) -> list[str]:  # noqa: F811
    vo: list[str] = []
    # N2: tồn = Σ sổ.
    for r in await pool.fetch(
        "SELECT t.id, t.so_luong, coalesce(sum(x.so_luong), 0) AS so"
        " FROM vat_tu_ton t LEFT JOIN vat_tu_txn x ON x.ton_id = t.id"
        " WHERE t.clinic_id = $1::uuid AND t.vat_tu_id = $2::uuid GROUP BY t.id",
        CLINIC,
        b.vt_can,
    ):
        if r["so_luong"] != r["so"]:
            vo.append(f"N2 tồn {r['so_luong']} ≠ Σ sổ {r['so']}")
    # N1: tồn hàng cần duyệt = Σ số của yêu cầu ĐÃ DUYỆT chưa bị đảo.
    mong = await pool.fetchval(
        """
        SELECT coalesce(sum((d->>'so_luong')::numeric), 0)
          FROM vat_tu_nhap_cho_duyet y
          CROSS JOIN LATERAL jsonb_array_elements(y.dong) d
         WHERE y.clinic_id = $1::uuid AND y.trang_thai = 'DA_DUYET'
           AND (d->>'vat_tu_id') = $2
           AND y.tao_boi IN ($3::uuid, $4::uuid)
           AND NOT EXISTS (SELECT 1 FROM vat_tu_phieu h
                            WHERE h.dao_phieu_id = y.phieu_id)
        """,
        CLINIC,
        b.vt_can,
        b.lap.staff_id,
        b.ql.staff_id,
    )
    if Decimal(mong) != await _ton(pool, b.vt_can):
        vo.append(f"N1 tồn {await _ton(pool, b.vt_can)} ≠ yêu cầu đã duyệt {mong}")
    for r in await pool.fetch(
        "SELECT id::text, trang_thai, phieu_id FROM vat_tu_nhap_cho_duyet"
        " WHERE tao_boi IN ($1::uuid, $2::uuid)",
        b.lap.staff_id,
        b.ql.staff_id,
    ):
        if (r["trang_thai"] == "DA_DUYET") != (r["phieu_id"] is not None):
            vo.append(f"N1 yêu cầu {r['id']} {r['trang_thai']}/phiếu {r['phieu_id']}")
    return vo


SO_HAT = 40
SO_BUOC = 10


async def test_bam_lon_xon_nhap_cho_duyet_40_luot_10_buoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lech: list[str] = []
    chay: Counter[str] = Counter()
    chan: Counter[str] = Counter()
    db_chan: list[str] = []
    for hat in range(SO_HAT):
        rnd = random.Random(hat)
        b = await _bo(pool)
        da: list[str] = []
        yc_cho: list[str] = []
        phieu_duyet: list[str] = []
        for _ in range(SO_BUOC):
            viec = rnd.choice(
                [
                    "lap_khong_lego",
                    "lap_khong_lego",
                    "lap_co_lego",
                    "lap_thuong",
                    "duyet",
                    "duyet_sai_nguoi",
                    "tu_choi",
                    "rut_lai",
                    "hoan_nhap_da_duyet",
                    "gui_lai_khoa",
                ]
            )
            try:
                if viec == "lap_khong_lego":
                    r = await _nhap(pool, b.lap, [_dong(b.vt_can, rnd.randint(1, 9))])
                    yc_cho.append(r["yeu_cau_id"])
                elif viec == "lap_co_lego":
                    r = await _nhap(pool, b.ql, [_dong(b.vt_can, rnd.randint(1, 9))])
                    phieu_duyet.append(r["id"])
                elif viec == "lap_thuong":
                    await _nhap(pool, b.lap, [_dong(b.vt_thuong, rnd.randint(1, 9))])
                elif viec == "duyet":
                    r = await duyet(pool, identity=b.ql, yeu_cau_id=rnd.choice(yc_cho))
                    if r.get("phieu_id") and r["phieu_id"] not in phieu_duyet:
                        phieu_duyet.append(r["phieu_id"])
                elif viec == "duyet_sai_nguoi":
                    await duyet(pool, identity=b.lap, yeu_cau_id=rnd.choice(yc_cho))
                    lech.append(f"hạt {hat}: {da} người không lego duyệt được")
                elif viec == "tu_choi":
                    await tu_choi(
                        pool,
                        identity=b.ql,
                        yeu_cau_id=rnd.choice(yc_cho),
                        ly_do="Không cần nhập nữa",
                    )
                elif viec == "rut_lai":
                    await rut_lai(pool, identity=b.lap, yeu_cau_id=rnd.choice(yc_cho))
                elif viec == "hoan_nhap_da_duyet":
                    await hoan_phieu(
                        pool,
                        identity=b.ql,
                        phieu_id=rnd.choice(phieu_duyet),
                        khoa_gui=uuid.uuid4().hex,
                    )
                else:
                    r = await _nhap(
                        pool, b.lap, [_dong(b.vt_can, 3)], khoa=f"khoa-{hat}-co-dinh"
                    )
                    if r.get("yeu_cau_id") and r["yeu_cau_id"] not in yc_cho:
                        yc_cho.append(r["yeu_cau_id"])
            except (ClinicAIBaseException, IndexError):
                chan[viec] += 1  # màn không cho — người thật cũng bị chặn
                continue
            except asyncpg.PostgresError as e:
                db_chan.append(f"hạt {hat}: {' → '.join([*da, viec])} ⇒ {e}")
                continue
            chay[viec] += 1
            da.append(viec)
            vo = await _bat_bien(pool, b)
            if vo:
                lech.append(f"hạt {hat}: {' → '.join(da)} ⇒ {'; '.join(vo)}")
                break
    print(
        f"\nCHẠY: {dict(chay)}\nBỊ CHẶN: {dict(chan)}\n"
        f"DB TỰ CHẶN: {db_chan or '(không)'}\nLỆCH: {lech or '(không)'}"
    )
    assert lech == [] and db_chan == []
    assert chay["duyet"] >= 10 and chay["tu_choi"] >= 5 and chay["rut_lai"] >= 5
    assert chay["hoan_nhap_da_duyet"] >= 3
