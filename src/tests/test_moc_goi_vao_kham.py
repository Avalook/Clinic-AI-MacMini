"""Mốc "gọi vào khám" của quầy — và đường lùi có chốt (Tuyền 20/08/2026).

Hai nút tròn trên thanh tiến độ phải bấm được, và bấm lại là hoàn tác. Nhưng
kernel quy trình KHÔNG có lệnh mở lại, nên đường lùi là một hành động bù — thứ
chỉ an toàn khi cái chốt của nó đúng. Các bài dưới chạy qua CHÍNH
``ReceptionService`` với connection giả: luật là HÀNH VI, không phải chuỗi ký tự.

Điều đáng canh nhất: *thứ tự* của hai việc trong ``goi_vao_kham``. Kernel phải
chạy TRƯỚC khi ghi mốc — ghi mốc trước rồi kernel từ chối là database có một giờ
khám cho người chưa được gọi.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.reception_service import ReceptionService

_LUC = datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc)
_VISIT = "11111111-1111-4111-8111-111111111111"


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s-le-tan",
        auth_user_id="u1",
        full_name="Lễ tân A",
        department="Tiếp đón",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _GiaoDich:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> bool:
        return False


class _Conn:
    """Định tuyến theo nội dung SQL, và GHI LẠI thứ tự các việc đã làm."""

    def __init__(self, chu: dict[str, Any]) -> None:
        self.chu = chu

    def transaction(self) -> _GiaoDich:
        return _GiaoDich()

    async def fetchval(self, sql: str, *args: Any) -> Any:
        if "UPDATE public.visit" in sql and "exam_started_at = now()" in sql:
            if self.chu["da_goi"] is not None:
                return None  # người khác vừa gọi trước
            self.chu["da_goi"] = _LUC
            self.chu["dau_vet"].append("ghi_moc")
            return _LUC
        if "UPDATE public.visit" in sql and "exam_started_at = NULL" in sql:
            cu = self.chu["da_goi"]
            self.chu["da_goi"] = None
            self.chu["dau_vet"].append("xoa_moc")
            return cu
        return None

    async def execute(self, sql: str, *args: Any) -> str:
        if "UPDATE public.work_item" in sql:
            self.chu["dau_vet"].append("mo_lai_viec")
        elif "work_item_event" in sql:
            self.chu["dau_vet"].append("vet_kernel")
        elif "event_log" in sql:
            self.chu["dau_vet"].append("so_su_kien")
        return "OK"


class _Acquire:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _Conn:
        return self._conn

    async def __aexit__(self, *_: object) -> bool:
        return False


class _Pool:
    def __init__(self, chu: dict[str, Any]) -> None:
        self.chu = chu

    def acquire(self) -> _Acquire:
        return _Acquire(_Conn(self.chu))

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        if "FROM public.visit" in sql:
            return {
                "visit_id": _VISIT,
                "clinic_patient_id": "p1",
                "appointment_id": "a1",
                "status": "IN_PROGRESS",
                "checked_in_at": _LUC - timedelta(minutes=10),
                "exam_started_at": self.chu["da_goi"],
            }
        if "node_definition" in sql and "workspace = $3" in sql:
            return self.chu["viec_quay"]
        return None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        if "n.workspace <> $3" in sql:
            return self.chu["buoc_khac"]
        if "clinical_record" in sql:
            return self.chu["co_ho_so"]
        return None


def _chu(**ghi_de: Any) -> dict[str, Any]:
    nen: dict[str, Any] = {
        "da_goi": None,
        "viec_quay": {
            "id": "w1",
            "status": "IN_PROGRESS",
            "version": 1,
            "node_code": "LUOTKHAM-02",
        },
        "buoc_khac": None,
        "co_ho_so": False,
        "dau_vet": [],
    }
    nen.update(ghi_de)
    return nen


def _svc(chu: dict[str, Any], *, kernel: list[str] | None = None) -> ReceptionService:
    svc = ReceptionService(_Pool(chu))

    class _Kernel:
        def __init__(self, _pool: Any) -> None:
            pass

        async def issue(self, **kw: Any) -> dict[str, object]:
            chu["dau_vet"].append(f"kernel:{kw['command']}")
            if kernel is not None:
                kernel.append(str(kw["command"]))
            return {"status": "COMPLETED"}

    import clinicai.services.reception_service as mod

    setattr(mod, "WorkItemService", _Kernel)
    return svc


def test_goi_vao_kham_chay_kernel_truoc_roi_moi_ghi_moc() -> None:
    """Thứ tự này là chốt an toàn, không phải chuyện thẩm mỹ."""
    chu = _chu()
    ket = asyncio.run(_svc(chu).goi_vao_kham(visit_id=_VISIT, identity=_identity()))
    assert ket["ok"] is True
    assert chu["dau_vet"].index("kernel:complete") < chu["dau_vet"].index("ghi_moc")
    assert "so_su_kien" in chu["dau_vet"], "phải để lại vết trong sổ sự kiện"


def test_bam_lai_lan_hai_khong_phai_loi() -> None:
    """Hai người cùng bấm, hoặc bấm lại sau khi mạng lag."""
    chu = _chu(da_goi=_LUC)
    ket = asyncio.run(_svc(chu).goi_vao_kham(visit_id=_VISIT, identity=_identity()))
    assert ket["da_goi_truoc_do"] is True
    assert "kernel:complete" not in chu["dau_vet"], "không được gọi kernel lần hai"


def test_hoan_tac_mo_lai_viec_va_de_lai_hai_vet() -> None:
    chu = _chu(da_goi=_LUC)
    chu["viec_quay"] = {
        "id": "w1",
        "status": "COMPLETED",
        "version": 2,
        "node_code": "LUOTKHAM-02",
    }
    ket = asyncio.run(
        _svc(chu).hoan_tac_goi_vao_kham(visit_id=_VISIT, identity=_identity())
    )
    assert ket["da_rut_lai"] is True
    assert chu["da_goi"] is None
    # Hành động bù phải để lại vết ở CẢ HAI nơi: nhật ký kernel và sổ sự kiện.
    for vet in ("mo_lai_viec", "vet_kernel", "so_su_kien"):
        assert vet in chu["dau_vet"], f"thiếu vết {vet}"


def test_bac_si_da_bat_dau_thi_khong_lui_duoc() -> None:
    """Chốt Tuyền chọn: chỉ lùi khi bác sĩ chưa động vào."""
    chu = _chu(da_goi=_LUC, buoc_khac="Sinh hiệu")
    with pytest.raises(ValidationError) as loi:
        asyncio.run(
            _svc(chu).hoan_tac_goi_vao_kham(visit_id=_VISIT, identity=_identity())
        )
    # Câu lỗi phải NÓI RÕ vướng ai — "không được" thì người dùng bấm lại lần nữa.
    assert "Sinh hiệu" in str(loi.value)
    assert chu["da_goi"] == _LUC, "không được xoá mốc khi đã từ chối"


def test_ho_so_kham_da_co_du_lieu_thi_khong_lui_duoc() -> None:
    chu = _chu(da_goi=_LUC, co_ho_so=True)
    with pytest.raises(ValidationError) as loi:
        asyncio.run(
            _svc(chu).hoan_tac_goi_vao_kham(visit_id=_VISIT, identity=_identity())
        )
    assert "hồ sơ" in str(loi.value).lower()


def test_chua_check_in_thi_khong_goi_vao_kham_duoc() -> None:
    """Gọi vào khám một người chưa tới = một giờ khám cho người vắng mặt."""
    chu = _chu()

    class _PoolChuaDen(_Pool):
        async def fetchrow(self, sql: str, *args: Any) -> Any:
            row = await super().fetchrow(sql, *args)
            if row and "checked_in_at" in row:
                return {**row, "checked_in_at": None}
            return row

    svc = ReceptionService(_PoolChuaDen(chu))
    with pytest.raises(ValidationError):
        asyncio.run(svc.goi_vao_kham(visit_id=_VISIT, identity=_identity()))


def test_hoan_tac_khi_chua_tung_goi_la_vo_hai() -> None:
    chu = _chu()
    ket = asyncio.run(
        _svc(chu).hoan_tac_goi_vao_kham(visit_id=_VISIT, identity=_identity())
    )
    assert ket["chua_tung_goi"] is True


def test_viec_dang_cho_thi_phai_start_truoc_roi_moi_complete() -> None:
    """Kernel không cho nhảy thẳng từ 'chờ' sang 'xong'.

    Lễ tân không quan tâm chuyện đó — họ chỉ bấm một nút. Service phải tự đi
    đủ hai bước thay vì bắt người dùng bấm 'Bắt đầu xử lý' rồi mới bấm 'Xong'.
    """
    chu = _chu()
    chu["viec_quay"] = {
        "id": "w1",
        "status": "PENDING",
        "version": 1,
        "node_code": "LUOTKHAM-02",
    }
    lenh: list[str] = []
    asyncio.run(
        _svc(chu, kernel=lenh).goi_vao_kham(visit_id=_VISIT, identity=_identity())
    )
    assert lenh == ["start", "complete"], f"phải đi đủ hai bước, thấy {lenh}"


def test_hai_nguoi_cung_bam_thi_nguoi_sau_nhan_cau_noi_ro() -> None:
    """Tranh chấp: giữa lúc đọc và lúc ghi, người khác đã gọi mất.

    Câu UPDATE có `AND exam_started_at IS NULL` nên nó trả rỗng — và đó là lúc
    duy nhất được phép báo lỗi, vì hai người vừa làm hai việc mâu thuẫn.
    """
    chu = _chu()

    class _PoolTranhChap(_Pool):
        def acquire(self) -> Any:
            # Người khác chen vào NGAY TRƯỚC câu UPDATE của mình.
            self.chu["da_goi"] = _LUC
            return super().acquire()

    svc = ReceptionService(_PoolTranhChap(chu))

    class _K:
        def __init__(self, _p: Any) -> None:
            pass

        async def issue(self, **_kw: Any) -> dict[str, object]:
            return {"status": "COMPLETED"}

    import clinicai.services.reception_service as mod

    setattr(mod, "WorkItemService", _K)
    with pytest.raises(ConflictError):
        asyncio.run(svc.goi_vao_kham(visit_id=_VISIT, identity=_identity()))


def test_luot_khong_thuoc_phong_kham_nay_thi_404() -> None:
    """Chốt đa phòng khám: truy vấn luôn kèm clinic_id, không thấy là không thấy."""
    chu = _chu()

    class _PoolRong(_Pool):
        async def fetchrow(self, sql: str, *args: Any) -> Any:
            return None

    svc = ReceptionService(_PoolRong(chu))
    with pytest.raises(NotFoundError):
        asyncio.run(svc.goi_vao_kham(visit_id=_VISIT, identity=_identity()))


def test_hoan_tac_khi_moc_vua_bi_nguoi_khac_xoa_la_vo_hai() -> None:
    chu = _chu(da_goi=_LUC)

    class _PoolMat(_Pool):
        def acquire(self) -> Any:
            self.chu["da_goi"] = None  # người khác vừa rút trước
            return super().acquire()

    svc = ReceptionService(_PoolMat(chu))
    ket = asyncio.run(svc.hoan_tac_goi_vao_kham(visit_id=_VISIT, identity=_identity()))
    assert ket["chua_tung_goi"] is True, "rút hai lần không phải lỗi"
