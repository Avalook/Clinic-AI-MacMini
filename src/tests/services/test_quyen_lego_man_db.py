"""Tài khoản CHỈ có một lego gọi được mọi API ĐỌC mà màn của lego ấy gọi — và
không có lego thì bị chặn ở lệnh ghi (đợt 3, 27/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        .venv/bin/pytest src/tests/services/test_quyen_lego_man_db.py

Bảng việc Tuyền giao: "Review lại back-end cho thao tác thêm bớt nút của mỗi tài
khoản — thừa thiếu nút như ở bác sĩ tư vấn". Nguyên nhân gốc: hai hệ gác song
song — lệnh hỏi capability, còn bảng đọc hỏi VAI. Tài khoản bác sĩ chỉ bật lego
Khám tư vấn (tắt Bàn khám → mất vai Bác sĩ theo lego) nhận khách được mà hàng
chờ tư vấn 403, màn đứng "Đang tải hàng chờ…" mãi.

Mỗi tài khoản thử có ĐÚNG các khối của lego được bật (không gói mẫu), danh tính
dựng bằng chính hàm máy chủ dùng (`doc_vai_theo_lego`) — y như đăng nhập thật.
Gọi qua HTTP thật của FastAPI (router + service + SQL), chỉ thay bước JWT.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import httpx
import pytest
import pytest_asyncio

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    _resolve_identity,
    doc_vai_theo_lego,
)
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.permissions import cache
from clinicai.permissions.catalogue import MAN, quyen_cua_khoi

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

HIEN_TAI: dict[str, StaffIdentity] = {}


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=6)
    app.dependency_overrides[get_db_pool] = lambda: p
    app.dependency_overrides[_resolve_identity] = lambda: HIEN_TAI["ai"]
    try:
        yield p
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
        await p.close()


@pytest_asyncio.fixture
async def http(pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://lego"
    ) as c:
        yield c


async def _nguoi(pool: asyncpg.Pool, vai: str, legos: list[str]) -> StaffIdentity:
    """Tài khoản vai `vai` có ĐÚNG các khối của `legos` (toàn phòng khám)."""
    khoi = sorted({k for m in legos for k in MAN[m].khoi})
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        ten = f"Lego {vai} {'+'.join(legos) or 'rong'} {uuid.uuid4().hex[:5]}"
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
            ten,
            vai,
            loc,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, $3, true)"
            " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
            CLINIC,
            sid,
            vai,
        )
        for k in khoi:
            for q in quyen_cua_khoi(k):
                await conn.execute(
                    "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                    " tu_khoi) VALUES ($1::uuid, $2::uuid, $3, $4)"
                    " ON CONFLICT DO NOTHING",
                    CLINIC,
                    sid,
                    q,
                    k,
                )
    cache.quen(CLINIC, sid)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=vai,
        role=ClinicRole(vai),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
        # Y như đăng nhập thật: vai do lego quyết tính bằng hàm của máy chủ.
        vai_theo_lego=await doc_vai_theo_lego(pool, CLINIC, sid, ClinicRole(vai)),
    )


async def _luot(pool: asyncpg.Pool, ghi_chu: str | None = None) -> str:
    """Một lượt hôm nay, có một ghi chú khám (nội dung lâm sàng) để thử cắt."""
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN thử lego', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"LG-{uuid.uuid4().hex[:10]}",
            loc,
        )
        return str(
            await conn.fetchval(
                "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
                " checked_in_at) VALUES ($1::uuid, $2::uuid, 'OPEN', now())"
                " RETURNING visit_id::text",
                CLINIC,
                pid,
            )
        )


async def _phong(pool: asyncpg.Pool) -> str:
    return str(
        await pool.fetchval(
            "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn"
            "  ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id"
            " WHERE r.clinic_id = $1::uuid AND rn.node_code = 'DICHVU-SIEUAM'"
            "   AND r.is_active ORDER BY r.sort LIMIT 1",
            CLINIC,
        )
    )


async def _goi(
    http: httpx.AsyncClient, ai: StaffIdentity, method: str, path: str, **kw: Any
) -> httpx.Response:
    HIEN_TAI["ai"] = ai
    headers = kw.pop("headers", {})
    headers.setdefault("Idempotency-Key", "lego-" + uuid.uuid4().hex)
    return await http.request(method, "/api/v1" + path, headers=headers, **kw)


def _ma() -> str:
    return str(uuid.uuid4())


# ── Màn → các API ĐỌC mà màn ấy gọi (theo mã frontend, 27/09/2026) ──────────
#
# `{phong}` / `{luot}` được thay lúc chạy. Hành trình + Xem lượt là màn LUÔN BẬT
# — mọi lego đều phải đọc được.
LUON_BAT = ["/hanh-trinh/hom-nay", "/xem-luot/{luot}"]
DOC_THEO_LEGO: dict[tuple[str, str], list[str]] = {
    # (lego, vai tài khoản): vai cố ý KHÁC vai "mặc định" của lego khi có thể —
    # chứng minh lego, không phải vai, là thứ quyết.
    ("tu_van", "DOCTOR"): [
        "/luot-kham/phong-hom-nay",
        "/luot-kham/bang",
        "/luot-kham/hang-cho?tu_van=true",
    ],
    ("ban_kham", "NURSE_ULTRASOUND"): [
        "/luot-kham/phong-hom-nay",
        "/luot-kham/bang",
        "/luot-kham/hang-cho",
        "/luot-kham/hang-cho?phong={phong}",
        "/luot-kham/cho-quyet",
    ],
    ("phong", "RECEPTION"): [
        "/luot-kham/phong-hom-nay",
        "/luot-kham/hang-cho?phong={phong}",
    ],
    ("do_sinh_hieu", "RECEPTION"): ["/luot-kham/bang"],
    ("tiep_don", "NURSE_ULTRASOUND"): ["/luot-kham/bang"],
    ("thu_tien_dv", "RECEPTION"): ["/cashier/board?modes=dich_vu"],
    ("thu_tien_thuoc", "PHARMACIST"): ["/cashier/board?modes=thuoc"],
    ("cham_soc_khach", "RECEPTION"): ["/cskh/danh-sach-khach"],
    ("dieu_phoi", "RECEPTION"): [
        "/luot-kham/bang",
        "/luot-kham/hang-cho?tu_van=true",
        "/luot-kham/chi-dinh-hom-nay",
        "/dispatch/overview",
    ],
    ("viec_can_xu_ly", "RECEPTION"): ["/work-items?workspace=khu_van_hanh"],
    # "Chỉ dùng lego" (27/09): hàng đợi tiếp đón theo lego, vai nào cũng được.
    ("tiep_don", "CASHIER"): ["/work-items?workspace=bang_dieu_phoi"],
    ("dieu_phoi", "CSKH"): ["/luot-kham/chi-dinh-hom-nay"],
}


async def test_chi_mot_lego_doc_duoc_moi_api_cua_man(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    phong = await _phong(pool)
    luot = await _luot(pool)
    hong: list[str] = []
    for (lego, vai), ds in DOC_THEO_LEGO.items():
        ai = await _nguoi(pool, vai, [lego])
        for duong in [*ds, *LUON_BAT]:
            p = duong.format(phong=phong, luot=luot)
            r = await _goi(http, ai, "GET", p)
            if r.status_code != 200:
                hong.append(f"{lego} ({vai}) GET {p} → {r.status_code} {r.text[:160]}")
    assert not hong, "\n".join(hong)


async def test_khong_lego_nao_van_vao_hanh_trinh_va_xem_luot(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    """Lễ tân tắt lego Tiếp đón (và mọi lego mang vai): Hành trình LUÔN BẬT."""
    luot = await _luot(pool)
    for vai in ("RECEPTION", "DOCTOR", "CASHIER", "NURSE_ULTRASOUND"):
        ai = await _nguoi(pool, vai, ["lich_lam_viec"])
        assert ai.cac_vai() == frozenset(), "lego mang vai đã tắt hết"
        for p in ("/hanh-trinh/hom-nay", f"/xem-luot/{luot}"):
            r = await _goi(http, ai, "GET", p)
            assert r.status_code == 200, f"{vai} GET {p} → {r.status_code} {r.text}"


async def test_doi_tac_va_tv_van_bi_chan(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    luot = await _luot(pool)
    for vai in ("PARTNER", "DISPLAY"):
        ai = await _nguoi(pool, vai, [])
        for p in (
            "/hanh-trinh/hom-nay",
            f"/xem-luot/{luot}",
            "/luot-kham/bang",
            "/luot-kham/hang-cho?tu_van=true",
            "/work-items?workspace=khu_van_hanh",
        ):
            r = await _goi(http, ai, "GET", p)
            assert r.status_code == 403, f"{vai} GET {p} → {r.status_code}"


async def test_lego_khac_khong_doc_duoc_hang_cua_lego_nay(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    """Chiều CHẶN: không có lego của màn thì hàng chờ / bảng của màn ấy đóng."""
    phong = await _phong(pool)
    cskh = await _nguoi(pool, "DOCTOR", ["cham_soc_khach"])  # vai BS, không lego khám
    for p in (
        "/luot-kham/bang",
        "/luot-kham/hang-cho",
        "/luot-kham/hang-cho?tu_van=true",
        f"/luot-kham/hang-cho?phong={phong}",
        "/luot-kham/cho-quyet",
        "/work-items?workspace=khu_van_hanh",
    ):
        r = await _goi(http, cskh, "GET", p)
        assert r.status_code == 403, f"GET {p} → {r.status_code} {r.text}"
    # Vai Lễ tân / Trưởng ca mà KHÔNG có lego Tiếp đón / Điều phối → đóng
    # (trước 27/09 vai của node / vai Trưởng ca mở cửa).
    le_tan = await _nguoi(pool, "NURSE_ULTRASOUND", ["do_sinh_hieu"])
    r = await _goi(http, le_tan, "GET", "/work-items?workspace=bang_dieu_phoi")
    assert r.status_code == 403, r.text
    truong_ca = await _nguoi(pool, "TRUONG_CA", ["tiep_don"])
    r = await _goi(http, truong_ca, "GET", "/luot-kham/chi-dinh-hom-nay")
    assert r.status_code == 403, r.text
    # Lego Tư vấn không mở hàng KHÁM chính; Bàn khám không mở hàng TƯ VẤN.
    tu_van = await _nguoi(pool, "DOCTOR", ["tu_van"])
    r = await _goi(http, tu_van, "GET", "/luot-kham/hang-cho")
    assert r.status_code == 403
    ban_kham = await _nguoi(pool, "DOCTOR", ["ban_kham"])
    r = await _goi(http, ban_kham, "GET", "/luot-kham/hang-cho?tu_van=true")
    assert r.status_code == 403


# ── Lệnh GHI: có lego → qua cửa quyền (rồi mới vấp "không tìm thấy");
#    không lego → 403. Mã giả để không đụng dữ liệu thật. ────────────────────
LENH: list[tuple[str, str, str, dict[str, Any] | None]] = [
    ("tu_van", "POST", "/luot-kham/consultations/{ma}/xong-tu-van", None),
    ("ban_kham", "POST", "/luot-kham/consultations/{ma}/start", None),
    ("ban_kham", "POST", "/luot-kham/consultations/{ma}/kham-xong", {}),
    (
        "phong",
        "POST",
        "/luot-kham/orders/{ma}/execution/bat-dau",
        {"expected_execution_revision": 1, "expected_routing_revision": 1},
    ),
    ("do_sinh_hieu", "POST", "/luot-kham/visits/{ma}/vitals/start", None),
    (
        "dieu_phoi",
        "POST",
        "/luot-kham/orders/{ma}/dispatch",
        {"room_id": "00000000-0000-4000-8000-000000000000"},
    ),
    # Việc cần xử lý: lệnh tìm đầu việc TRƯỚC (mã giả → 404 cho mọi người) —
    # kiểm trên việc thật ở `test_viec_can_xu_ly_ten_khach_va_dong_viec_chi_bang_lego`.
]


@pytest.mark.parametrize(("lego", "method", "duong", "than"), LENH)
async def test_lenh_ghi_theo_lego(
    pool: asyncpg.Pool,
    http: httpx.AsyncClient,
    lego: str,
    method: str,
    duong: str,
    than: dict[str, Any] | None,
) -> None:
    co = await _nguoi(pool, "CSKH", [lego])
    khong = await _nguoi(pool, "DOCTOR", ["cham_soc_khach"])
    p = duong.format(ma=_ma())
    kw: dict[str, Any] = {} if than is None else {"json": than}
    r = await _goi(http, khong, method, p, **kw)
    assert r.status_code == 403, f"không lego {lego}: {p} → {r.status_code} {r.text}"
    r = await _goi(http, co, method, p, **kw)
    assert r.status_code != 403, f"có lego {lego}: {p} → 403 {r.text}"


async def test_xem_luot_khong_quyen_y_khoa_khong_lo_lam_sang(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    luot = await _luot(pool)
    thu_ngan = await _nguoi(pool, "DOCTOR", ["thu_tien_dv"])  # vai BS, lego thu tiền
    r = await _goi(http, thu_ngan, "GET", f"/xem-luot/{luot}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert "lam_sang" not in d and not d["muc"]["lam_sang"]
    assert "tai_chinh" in d
    assert all(dv.get("ket_qua_ghi") is None for dv in d["dich_vu"])
    bac_si = await _nguoi(pool, "NURSE_ULTRASOUND", ["ban_kham"])
    d = (await _goi(http, bac_si, "GET", f"/xem-luot/{luot}")).json()
    assert "lam_sang" in d and d["muc"]["lam_sang"]


async def test_viec_can_xu_ly_ten_khach_va_dong_viec_chi_bang_lego(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    """Lễ tân CHỈ có lego Việc cần xử lý (mọi lego mang vai tắt → `cac_vai()`
    rỗng) vẫn thấy tên khách và đóng được việc."""
    import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
    from clinicai.events.catalogue import TRACH_NHIEM_DICH_VU, DichVuKhongLam
    from clinicai.events.emit import HE_THONG, emit_event
    from clinicai.events.worker import lam_mot_dong

    luot = await _luot(pool)
    order_id = _ma()
    async with pool.acquire() as conn, conn.transaction():
        await emit_event(
            conn,
            ten="service.not_performed",
            clinic_id=CLINIC,
            aggregate_id=order_id,
            aggregate_version=1,
            payload=DichVuKhongLam(
                visit_id=luot,
                service_order_id=order_id,
                ly_do="STAFF_UNAVAILABLE",
                execution_revision=1,
                da_thu_tien=True,
            ),
            boi=HE_THONG,
        )
    for _ in range(50_000):
        if not await lam_mot_dong(pool, TRACH_NHIEM_DICH_VU):
            break

    ai = await _nguoi(pool, "RECEPTION", ["viec_can_xu_ly"])
    assert ai.cac_vai() == frozenset()
    r = await _goi(http, ai, "GET", "/work-items?workspace=khu_van_hanh")
    assert r.status_code == 200, r.text
    [viec] = [v for v in r.json() if v["visit_id"] == luot]
    assert viec["node_code"] == "OPS-FINANCIAL-RESOLUTION"
    assert viec["patient"]["full_name"] == "BN thử lego"
    assert viec["patient"]["patient_code"].startswith("LG-")
    assert viec["actionable_by_me"] is True
    # Không có lego Việc cần xử lý → không đọc, không đóng được (bất kể vai).
    khong = await _nguoi(pool, "CASHIER", ["thu_tien_dv", "thu_tien_thuoc"])
    r = await _goi(http, khong, "GET", "/work-items?workspace=khu_van_hanh")
    assert r.status_code == 403, r.text
    # Việc mới mở ở PENDING: "Đã xử lý" = start rồi complete (máy trạng thái
    # kernel — complete chỉ từ IN_PROGRESS). Người không lego bị chặn ở start.
    r = await _goi(
        http,
        khong,
        "POST",
        f"/work-items/{viec['id']}/commands/start",
        json={"expected_version": viec["version"]},
    )
    assert r.status_code == 403, r.text
    r = await _goi(
        http,
        ai,
        "POST",
        f"/work-items/{viec['id']}/commands/start",
        json={"expected_version": viec["version"]},
    )
    assert r.status_code == 200, r.text
    r = await _goi(
        http,
        ai,
        "POST",
        f"/work-items/{viec['id']}/commands/complete",
        json={"expected_version": r.json()["version"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"
