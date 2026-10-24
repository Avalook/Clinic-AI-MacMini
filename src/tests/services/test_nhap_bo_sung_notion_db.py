"""Gói PHỤ lịch sử Notion (06/10/2026): lịch sử chăm sóc + nguồn khách + người nhà +
dự kiến sinh. Nạp SAU gói chính, cùng khuôn: thử khô không ghi gì, nạp lại không
trùng, gỡ được — và KHÔNG sinh việc CSKH nào (dữ liệu giả, không có khách thật)."""

from __future__ import annotations

import json
import random
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from clinicai.services.danh_sach_khach_cskh import COT_KENH_DOI_HUY
from clinicai.services.lich_su_notion_service import lich_su_cham_soc
from clinicai.services.nhap_bo_sung_notion import nap as nap_phu
from clinicai.services.nhap_lich_su_notion import nap as nap_chinh
from tests.services.test_lich_su_notion_db import _ghi, _goi, _khach_he_thong, _sdt
from tests.services.test_luot_kham_service_db import CLINIC, KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

HOAN_TAC = Path(__file__).resolve().parents[3] / "scripts/hoan-tac-bo-sung-notion.sql"


def _goi_phu(tmp: Path, **bang: list[dict[str, Any]]) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "manifest.json").write_text(json.dumps({"goi": "phu-test"}))
    for ten in ("cham_soc", "nguon_khach", "nguoi_nha", "du_kien_sinh"):
        _ghi(tmp, ten, bang.get(ten, []))
    return tmp


def _cs(key: str, luc: str, buoc: str, **kw: Any) -> dict[str, Any]:
    return {
        "notion_id": str(uuid.uuid4()),
        "nguoi_key": key,
        "ma": f"ACT-T{random.randint(1, 10**6)}",
        "luc": luc,
        "buoc": buoc,
        "phan_loai": "Đặt hẹn",
        "kich_ban": "Đặt hẹn - Nhắc lịch / Thành công ✅",
        "nguoi_lam": "CSKH Thử",
        **kw,
    }


async def _so_viec_cskh(conn: asyncpg.Connection, bn: list[str]) -> dict[str, int]:
    """Mọi chỗ sinh / chứa việc CSKH của các khách thử."""
    so = {}
    for bang in ("tuong_tac_cskh", "nhac_tai_kham", "hen_goi_lai", "v_viec_cskh"):
        so[bang] = await conn.fetchval(
            f"SELECT count(*) FROM public.{bang}"
            " WHERE clinic_patient_id = ANY($1::uuid[])",
            bn,
        )
    return so


async def test_goi_phu_thu_kho_nap_lai_go_va_khong_sinh_viec(
    kb: KichBan, tmp_path: Path
) -> None:
    sdt_a, sdt_b = _sdt(), _sdt()
    async with kb.pool.acquire() as conn:
        a = await _khach_he_thong(conn, kb.location_id, "Nguyễn Thị Bổ Sung A", sdt_a)
        b = await _khach_he_thong(conn, kb.location_id, "Trần Thị Bổ Sung B", sdt_b)
        # B đã có lịch hẹn kênh Zalo trên hệ thống → nguồn cũ KHÔNG được đè.
        st = await conn.fetchval(
            "SELECT id FROM service_type WHERE clinic_id = $1::uuid LIMIT 1", CLINIC
        )
        await conn.execute(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, booking_channel, slot_start, slot_end, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'ZALO_PK',"
            " '2026-05-01 09:00+07', '2026-05-01 09:30+07', 'COMPLETED')",
            CLINIC,
            b,
            kb.location_id,
            st,
        )
    ka, kb_, kc = (f"hc:{uuid.uuid4()}" for _ in range(3))
    hen_a = str(uuid.uuid4())
    goi = _goi(
        tmp_path / "goi",
        nguoi=[
            {"nguoi_key": ka, "ten": "Nguyễn Thị Bổ Sung A", "sdt": sdt_a, "ma": "X"},
            {"nguoi_key": kb_, "ten": "Trần Thị Bổ Sung B", "sdt": sdt_b, "ma": "Y"},
            {
                "nguoi_key": kc,
                "ten": "Lê Thị Bổ Sung C",
                "sdt": _sdt(),
                "ma": f"KHACH-T{random.randint(1, 10**6)}",
            },
        ],
        luot=[],
    )
    _ghi(
        goi,
        "lich_hen",
        [
            {
                "notion_id": hen_a,
                "nguoi_key": ka,
                "ma": "REG-T",
                "ngay_hen": "2026-01-21",
                "gio_hen": "13:00",
                "loai_kham_goc": "Sản 1",
                "trang_thai": "COMPLETED",
            }
        ],
    )
    await nap_chinh(kb.pool, goi, that=True, clinic_id=CLINIC)
    async with kb.pool.acquire() as conn:
        c = await conn.fetchval(
            "SELECT clinic_patient_id::text FROM lich_su_notion.nguoi"
            " WHERE nguoi_key = $1",
            kc,
        )
        truoc = await _so_viec_cskh(conn, [a, b, c])

    ngay_sau = (date.today() + timedelta(days=60)).isoformat()
    yeu_cau = _cs(
        ka,
        "2026-01-10T03:00:00Z",
        "yeu_cau",
        tinh_trang="Kết thúc · Đã xác nhận lịch hẹn / Đã nhắc",
        lich_hen_id=hen_a,
    )
    phu = _goi_phu(
        tmp_path / "phu",
        cham_soc=[
            yeu_cau,
            _cs(
                ka,
                "2026-01-20T02:15:00Z",
                "thuc_hien",
                cha_id=yeu_cau["notion_id"],
                noi_dung="Khách hẹn gọi lại buổi chiều",
                # lịch hẹn không có trong lịch sử → bỏ liên kết, giữ dòng.
                lich_hen_id=str(uuid.uuid4()),
            ),
            _cs(kc, "2026-02-01T08:00:00Z", "ghi_chu"),
            _cs(f"hc:{uuid.uuid4()}", "2026-02-01T08:00:00Z", "thuc_hien"),
        ],
        nguon_khach=[
            {"nguoi_key": ka, "kenh": "FB_DR4WOMEN"},
            {"nguoi_key": kb_, "kenh": "HOTLINE"},
        ],
        nguoi_nha=[
            {"nguoi_key_a": ka, "nguoi_key_b": kc},
            {"nguoi_key_a": ka, "nguoi_key_b": f"hc:{uuid.uuid4()}"},
        ],
        du_kien_sinh=[
            {"nguoi_key": ka, "du_kien_sinh": ngay_sau, "notion_id": str(uuid.uuid4())},
            {"nguoi_key": kc, "du_kien_sinh": "2026-03-01", "notion_id": str(uuid.uuid4())},
        ],
    )

    # ── Thử khô: không ghi gì ───────────────────────────────────────────────
    thu = await nap_phu(kb.pool, phu, that=False, clinic_id=CLINIC)
    assert thu["thu_kho"] is True
    assert thu["cham_soc_khong_co_ho_so"] == 1
    async with kb.pool.acquire() as conn:
        assert not await conn.fetchval(
            "SELECT count(*) FROM lich_su_notion.cham_soc"
            " WHERE clinic_patient_id = ANY($1::uuid[])",
            [a, c],
        )
        assert not await conn.fetchval(
            "SELECT count(*) FROM pregnancy WHERE clinic_patient_id = ANY($1::uuid[])",
            [a, c],
        )

    # ── Ghi thật ────────────────────────────────────────────────────────────
    kq = await nap_phu(kb.pool, phu, that=True, clinic_id=CLINIC)
    assert kq["nguoi_nha_lien_ket_moi"] == 1
    assert kq["nguoi_nha_thieu_ho_so"] == 1
    assert kq["du_kien_sinh_dang_theo_doi"] == 1 and kq["du_kien_sinh_da_qua"] == 1

    cs = await lich_su_cham_soc(kb.pool, identity=kb.bac_si, clinic_patient_id=a)
    assert cs["tong"] == 2
    moi, cu = cs["dong"]
    assert moi["buoc_nhan"] == "Thực hiện" and moi["noi_dung"] == "Khách hẹn gọi lại buổi chiều"
    assert moi["ngay_hen"] is None
    assert cu["ngay_hen"] == "2026-01-21" and cu["gio_hen"] == "13:00"
    assert cu["luc"].startswith("2026-01-10")

    async with kb.pool.acquire() as conn:
        kenh = {
            r["id"]: r["kenh_dat"]
            for r in await conn.fetch(
                f"SELECT p.clinic_patient_id::text AS id, {COT_KENH_DOI_HUY}"
                " FROM patient p WHERE p.clinic_patient_id = ANY($1::uuid[])",
                [a, b],
            )
        }
        assert kenh == {a: "FB_DR4WOMEN", b: "ZALO_PK"}, "nguồn cũ không đè kênh hệ thống"
        lk = await conn.fetch(
            "SELECT relation, created_by FROM patient_link"
            " WHERE clinic_id = $1::uuid AND $2::uuid IN (patient_a, patient_b)",
            CLINIC,
            a,
        )
        assert [r["relation"] for r in lk] == ["FAMILY"]
        tk = {
            str(r["clinic_patient_id"]): (r["outcome"], r["edd_nguon"])
            for r in await conn.fetch(
                "SELECT clinic_patient_id, outcome, edd_nguon FROM pregnancy"
                " WHERE clinic_patient_id = ANY($1::uuid[])",
                [a, c],
            )
        }
        assert tk == {a: ("ONGOING", "KHAC"), c: ("UNKNOWN", "KHAC")}

    # ── Nạp lại: không trùng ────────────────────────────────────────────────
    lai = await nap_phu(kb.pool, phu, that=True, clinic_id=CLINIC)
    assert lai["nguoi_nha_lien_ket_moi"] == 0
    assert lai["du_kien_sinh_dang_theo_doi"] == lai["du_kien_sinh_da_qua"] == 0
    async with kb.pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM lich_su_notion.cham_soc"
                " WHERE clinic_patient_id = ANY($1::uuid[])",
                [a, c],
            )
            == 3
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM pregnancy WHERE clinic_patient_id = ANY($1::uuid[])",
                [a, c],
            )
            == 2
        )
        # ── KHÔNG sinh việc CSKH nào ────────────────────────────────────────
        assert await _so_viec_cskh(conn, [a, b, c]) == truoc

        # ── Gỡ: thai kỳ bác sĩ đã sửa thì giữ, còn lại về như trước ─────────
        await conn.execute(
            "UPDATE pregnancy SET updated_by = $2::uuid"
            " WHERE clinic_patient_id = $1::uuid",
            c,
            kb.bac_si.staff_id,
        )
        await conn.execute(HOAN_TAC.read_text())
        assert not await conn.fetchval(
            "SELECT count(*) FROM lich_su_notion.cham_soc"
            " WHERE clinic_patient_id = ANY($1::uuid[])",
            [a, c],
        )
        assert not await conn.fetchval(
            "SELECT count(*) FROM patient_link WHERE $1::uuid IN (patient_a, patient_b)",
            a,
        )
        assert [
            str(r[0])
            for r in await conn.fetch(
                "SELECT clinic_patient_id FROM pregnancy"
                " WHERE clinic_patient_id = ANY($1::uuid[])",
                [a, c],
            )
        ] == [c]
        assert not await conn.fetchval(
            "SELECT count(*) FROM lich_su_notion.nguoi"
            " WHERE nguoi_key = ANY($1::text[]) AND kenh IS NOT NULL",
            [ka, kb_],
        )

    # Nạp lại sau khi gỡ: tạo lại đúng như cũ (thai kỳ C còn giữ → không tạo thêm).
    sau = await nap_phu(kb.pool, phu, that=True, clinic_id=CLINIC)
    assert sau["nguoi_nha_lien_ket_moi"] == 1
    assert sau["du_kien_sinh_dang_theo_doi"] == 1 and sau["du_kien_sinh_da_qua"] == 0


async def test_khach_khong_co_lich_su_cham_soc(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        a = await _khach_he_thong(conn, kb.location_id, "Phạm Thị Không Cũ", _sdt())
    assert await lich_su_cham_soc(kb.pool, identity=kb.le_tan, clinic_patient_id=a) == {
        "tong": 0,
        "dong": [],
    }
