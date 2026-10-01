"""Thu nhiều hình thức + hoàn tác lần thu + ảnh chuyển khoản (01/10/2026), DB thật.

Kịch bản: lượt 150k thu = 100k TIỀN MẶT (khách đưa 200k) + 50k CHUYỂN KHOẢN →
lần thu chờ xác minh → đã nhận tiền → phiếu in thấy 2 phần + "trả lại 100k".
Postgres chặn tổng các phần lệch số tiền lần thu. QR cũ đọc ra Chuyển khoản.
Hoàn tác lần thu (đã thu / đang chờ xác minh) đưa lượt về chưa thu, thu lại được.
Ảnh chuyển khoản tải lên, đọc lại đúng byte, gỡ thì ẩn.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services import media_service
from clinicai.services.anh_chuyen_khoan_service import (
    AnhChuyenKhoanService,
    anh_cua_cac_lan_thu,
)
from clinicai.services.doi_hinh_thuc_service import DoiHinhThucService
from clinicai.services.nhan_tep_luong import TepDaNhan
from clinicai.services.payment_service import CHO_XAC_MINH, PaymentService
from clinicai.services.quay_thu_service import QuayThuService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _hd, tao_quay
from tests.services.test_tien_thuoc_cp2_db import _rev, _thu_pt, _xm

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: PNG 1×1 hợp lệ (đủ byte đầu cho sniff_ket_qua).
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6300010000000500010d0a2db40000"
    "000049454e44ae426082"
)


async def _thu_chia(q: Quay) -> dict[str, object]:
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=await _rev(q),
        method="CASH",
        phan=[
            {"hinh_thuc": "CASH", "so_tien": 100_000, "khach_dua": 200_000},
            {"hinh_thuc": "TRANSFER", "so_tien": 50_000},
        ],
    )


async def _phan_db(q: Quay, cid: str) -> list[dict[str, object]]:
    raw = await q.pool.fetchval(
        "SELECT phan_thu_hieu_luc(clinic_id, payment_cycle_id, method, amount)"
        " FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
        cid,
    )
    ds: list[dict[str, object]] = json.loads(raw)
    return ds


async def test_thu_chia_tong_dung_va_phieu_in_hai_dong(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    kq = await _thu_chia(q)
    cid = str(kq["payment_cycle_id"])
    lan = await pool.fetchrow(
        "SELECT status, method, amount FROM payment_cycle"
        " WHERE payment_cycle_id = $1::uuid",
        cid,
    )
    assert lan is not None
    # Có phần chuyển khoản → chờ xác minh như contract A2.
    assert (lan["status"], lan["method"], lan["amount"]) == (
        CHO_XAC_MINH,
        "TRANSFER",
        150_000,
    )
    await _xm(q, cid, "")
    phan = await _phan_db(q, cid)
    assert [(p["hinh_thuc"], p["so_tien"]) for p in phan] == [
        ("CASH", 100_000),
        ("TRANSFER", 50_000),
    ]
    assert sum(int(str(p["so_tien"])) for p in phan) == 150_000

    phieu = await QuayThuService(pool).phieu(identity=q.thu_ngan, id_=cid)
    assert [(p["hinh_thuc"], p["so_tien"]) for p in phieu["phan"]] == [
        ("CASH", 100_000),
        ("TRANSFER", 50_000),
    ]
    assert phieu["tra_lai"] == 100_000


async def test_tong_lech_bi_chan_o_dich_vu_va_postgres(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    with pytest.raises(ValidationError, match="khác số cần thu"):
        await PaymentService(pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            idempotency_key=f"test-{uuid.uuid4().hex}",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
            bill_revision=await _rev(q),
            phan=[
                {"hinh_thuc": "CASH", "so_tien": 100_000},
                {"hinh_thuc": "TRANSFER", "so_tien": 10_000},
            ],
        )
    # Lách tầng dịch vụ: Postgres vẫn chặn lúc COMMIT (trigger hoãn).
    kq = await _thu_pt(q, "CASH")
    cid = str(kq["payment_cycle_id"])
    with pytest.raises(asyncpg.CheckViolationError, match="Tổng các phần"):
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO payment_cycle_phan (clinic_id, cycle_id, hinh_thuc,"
                " so_tien) VALUES ($1::uuid, $2::uuid, 'TRANSFER', 1)",
                CLINIC,
                cid,
            )


async def test_qr_cu_doc_ra_chuyen_khoan(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    cid = str((await _thu_pt(q, "CASH"))["payment_cycle_id"])
    # Lần thu cũ trước 01/10 không có dòng phần: (method gốc 'QR', amount).
    raw = await pool.fetchval(
        "SELECT phan_thu_hieu_luc($1::uuid, $2::uuid, 'QR', 90000)",
        CLINIC,
        str(uuid.uuid4()),
    )
    assert json.loads(raw) == [{"hinh_thuc": "TRANSFER", "so_tien": 90_000}]
    # Máy cũ còn gửi "QR" → ghi thành Chuyển khoản.
    q2 = await tao_quay(pool)
    kq = await _thu_pt(q2, "QR")
    assert (
        await pool.fetchval(
            "SELECT method FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
            kq["payment_cycle_id"],
        )
        == "TRANSFER"
    )
    assert cid


async def test_hoan_tac_da_thu_dua_luot_ve_chua_thu(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    cid = str((await _thu_pt(q, "CASH"))["payment_cycle_id"])
    assert (await _hd(q, "dich_vu")).dong == []
    kq = await PaymentService(pool).hoan_tac(
        payment_cycle_id=cid, ly_do=None, identity=q.thu_ngan
    )
    assert kq["visit_id"] == q.visit_id
    st = await pool.fetchrow(
        "SELECT status FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
        cid,
    )
    assert st is not None and st["status"] == "VOIDED"
    # Lượt về CHƯA THU: hoá đơn có lại tiền khám, thu lại được.
    assert [d.source_type for d in (await _hd(q, "dich_vu")).dong] == ["exam"]
    lai = await _thu_pt(q, "CASH")
    assert lai["payment_cycle_id"] != cid
    # Dòng thời gian có sự kiện hoàn tác.
    assert await pool.fetchval(
        "SELECT count(*) FROM domain_event"
        " WHERE event_type = 'payment.collection_undone' AND aggregate_id = $1::uuid",
        cid,
    )
    # Gửi lại → thành công như cũ, không nhân đôi.
    await PaymentService(pool).hoan_tac(
        payment_cycle_id=cid, ly_do="bấm lại", identity=q.thu_ngan
    )


async def test_hoan_tac_lan_cho_xac_minh(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    cid = str((await _thu_chia(q))["payment_cycle_id"])
    await PaymentService(pool).hoan_tac(
        payment_cycle_id=cid, ly_do="", identity=q.thu_ngan
    )
    assert (
        await pool.fetchval(
            "SELECT status FROM payment_cycle WHERE payment_cycle_id = $1::uuid", cid
        )
        == "CANCELLED"
    )
    assert [d.source_type for d in (await _hd(q, "dich_vu")).dong] == ["exam"]
    again = await PaymentService(pool).hoan_tac(
        payment_cycle_id=cid, ly_do=None, identity=q.thu_ngan
    )
    assert again["status"] == "CANCELLED"


async def test_doi_hinh_thuc_sang_chia(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    cid = str((await _thu_pt(q, "CASH"))["payment_cycle_id"])
    await DoiHinhThucService(pool).doi(
        identity=q.thu_ngan,
        payment_cycle_id=cid,
        hinh_thuc=None,
        tien_mat=100_000,
        chuyen_khoan=50_000,
        ly_do="Khách chuyển một phần",
    )
    assert [(p["hinh_thuc"], p["so_tien"]) for p in await _phan_db(q, cid)] == [
        ("CASH", 100_000),
        ("TRANSFER", 50_000),
    ]


async def test_anh_chuyen_khoan_luu_doc_go(
    pool: asyncpg.Pool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vps = tmp_path / "vps"
    (vps / ".tam").mkdir(parents=True)
    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", vps)
    monkeypatch.setattr(media_service, "MEDIA_ROOT", tmp_path / "cfs")
    q = await tao_quay(pool)
    cid = str((await _thu_chia(q))["payment_cycle_id"])
    tam = vps / ".tam" / "x.part"
    tam.write_bytes(PNG)
    svc = AnhChuyenKhoanService(pool)
    kq = await svc.tai_len(
        identity=q.thu_ngan,
        payment_cycle_id=cid,
        tep=TepDaNhan(
            duong=tam,
            so_byte=len(PNG),
            sha256=hashlib.sha256(PNG).hexdigest(),
            dau=PNG[:64],
            ten="ck.png",
        ),
    )
    noi_dung, mime = await svc.doc(identity=q.thu_ngan, anh_id=str(kq["id"]))
    assert noi_dung == PNG and mime == "image/png"
    async with pool.acquire() as conn:
        assert [
            a["id"] for a in (await anh_cua_cac_lan_thu(conn, CLINIC, [cid]))[cid]
        ] == [kq["id"]]
    # Không phải ảnh → 422.
    rac = vps / ".tam" / "y.part"
    rac.write_bytes(b"%PDF-1.4 khong phai anh")
    with pytest.raises(ValidationError):
        await svc.tai_len(
            identity=q.thu_ngan,
            payment_cycle_id=cid,
            tep=TepDaNhan(duong=rac, so_byte=24, sha256="", dau=b"%PDF-1.4", ten=None),
        )
    await svc.go(identity=q.thu_ngan, anh_id=str(kq["id"]))
    async with pool.acquire() as conn:
        assert await anh_cua_cac_lan_thu(conn, CLINIC, [cid]) == {}
