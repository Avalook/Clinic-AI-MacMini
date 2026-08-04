"""Phần chạm database của ConsentService — thứ tự lệnh và cách dịch lỗi.

Luật ở tầng database (ràng buộc, trigger, chỉ mục duy nhất) đã thử bằng SQL
thật trên prod rồi rollback; xem chú thích trong 20260804000020 và
20260804000021. Ở đây kiểm phần Python: gọi đúng thứ tự, từ chối trước khi ghi,
và biến lỗi database thành câu người vận hành đọc được.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.consent_service import ConsentService
from tests.services.fake_pool import FakePool

CLINIC = "a0000000-0000-4000-8000-000000000001"
CHONG = "11111111-1111-4111-8111-111111111111"
VO = "22222222-2222-4222-8222-222222222222"


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="staff-1",
        auth_user_id="u-1",
        full_name="BS. A",
        role=ClinicRole.DOCTOR,
        department="DOCTOR",
        location_name="Kim Ngưu",
        clinic_id=CLINIC,
        location_id="loc-1",
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class TestLink:
    def test_quan_he_la_khong_hop_le_thi_tu_choi_truoc_khi_cham_db(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="Quan hệ không hợp lệ"):
            _run(
                ConsentService(pool).link(
                    identity=_identity(),
                    patient_a=CHONG,
                    patient_b=VO,
                    relation="BAN_BE",
                )
            )
        assert pool.queries() == []

    def test_tu_lien_ket_voi_chinh_minh_bi_tu_choi(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="chính mình"):
            _run(
                ConsentService(pool).link(
                    identity=_identity(),
                    patient_a=CHONG,
                    patient_b=CHONG,
                    relation="SPOUSE",
                )
            )
        assert pool.queries() == []

    def test_benh_nhan_khong_thuoc_phong_kham_nay(self) -> None:
        """`patient_link` không có khoá ngoại (bệnh nhân định danh bằng
        `clinic_patient_id`), nên id gõ nhầm phải bị bắt ở đây."""
        pool = FakePool(None)  # _must_exist(patient_a) → không thấy
        with pytest.raises(NotFoundError, match="Không tìm thấy bệnh nhân"):
            _run(
                ConsentService(pool).link(
                    identity=_identity(),
                    patient_a=CHONG,
                    patient_b=VO,
                    relation="SPOUSE",
                )
            )

    def test_lien_ket_thanh_cong_co_ghi_event(self) -> None:
        pool = FakePool(1, 1, {"id": "link-1"})
        out = _run(
            ConsentService(pool).link(
                identity=_identity(),
                patient_a=CHONG,
                patient_b=VO,
                relation="spouse",  # chữ thường vẫn nhận
                note="theo lời khai lễ tân",
            )
        )
        assert out == {"link_id": "link-1", "relation": "SPOUSE"}
        assert pool.wrote("INSERT INTO event_log")

    def test_lien_ket_trung_noi_bang_tieng_viet(self) -> None:
        """Chỉ mục `least/greatest` bắt cả chiều ngược. Người dùng thấy câu
        giải thích, không thấy tên ràng buộc."""
        pool = FakePool(1, 1, asyncpg.UniqueViolationError("dup"))
        with pytest.raises(ConflictError, match="đã được liên kết"):
            _run(
                ConsentService(pool).link(
                    identity=_identity(),
                    patient_a=VO,
                    patient_b=CHONG,
                    relation="SPOUSE",
                )
            )


class TestGrant:
    def test_khong_neu_form_nao(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="form nào"):
            _run(
                ConsentService(pool).grant(
                    identity=_identity(),
                    subject_patient_id=CHONG,
                    grantee_patient_id=VO,
                    form_codes=["", "   "],
                    source_document="a.pdf",
                )
            )
        assert pool.queries() == []

    def test_khong_co_ban_dong_y_co_chu_ky(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="chữ ký"):
            _run(
                ConsentService(pool).grant(
                    identity=_identity(),
                    subject_patient_id=CHONG,
                    grantee_patient_id=VO,
                    form_codes=["HMVS"],
                    source_document="   ",
                )
            )

    def test_dong_y_cho_chinh_minh_la_vo_nghia(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="chính mình"):
            _run(
                ConsentService(pool).grant(
                    identity=_identity(),
                    subject_patient_id=CHONG,
                    grantee_patient_id=CHONG,
                    form_codes=["HMVS"],
                    source_document="a.pdf",
                )
            )

    def test_ma_form_duoc_chuan_hoa_hoa(self) -> None:
        pool = FakePool({"id": "c-1"})
        out = _run(
            ConsentService(pool).grant(
                identity=_identity(),
                subject_patient_id=CHONG,
                grantee_patient_id=VO,
                form_codes=[" hmvs ", "nk"],
                source_document=" ho-so/2026/DY-01.pdf ",
            )
        )
        assert out["form_codes"] == ["HMVS", "NK"]
        assert pool.wrote("INSERT INTO event_log")

    def test_da_co_ban_dang_hieu_luc(self) -> None:
        pool = FakePool(asyncpg.UniqueViolationError("dup"))
        with pytest.raises(ConflictError, match="Thu hồi bản cũ"):
            _run(
                ConsentService(pool).grant(
                    identity=_identity(),
                    subject_patient_id=CHONG,
                    grantee_patient_id=VO,
                    form_codes=["HMVS"],
                    source_document="a.pdf",
                )
            )

    def test_chua_lien_ket_thi_trigger_chan(self) -> None:
        """Trigger `clinical_data_consent_needs_link` ném mã
        `foreign_key_violation`; câu của nó đã là tiếng Việt nên giữ nguyên."""
        pool = FakePool(
            asyncpg.ForeignKeyViolationError(
                "Hai bệnh nhân này chưa được liên kết\nCONTEXT: ..."
            )
        )
        with pytest.raises(ValidationError, match="chưa được liên kết"):
            _run(
                ConsentService(pool).grant(
                    identity=_identity(),
                    subject_patient_id=CHONG,
                    grantee_patient_id=VO,
                    form_codes=["HMVS"],
                    source_document="a.pdf",
                )
            )


class TestRevoke:
    def test_khong_ghi_ly_do(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="lý do"):
            _run(
                ConsentService(pool).revoke(
                    identity=_identity(), consent_id="c-1", reason="  "
                )
            )
        assert pool.queries() == []

    def test_khong_con_ban_dang_hieu_luc(self) -> None:
        pool = FakePool(None)
        with pytest.raises(NotFoundError, match="đang hiệu lực"):
            _run(
                ConsentService(pool).revoke(
                    identity=_identity(), consent_id="c-1", reason="BN rút"
                )
            )

    def test_thu_hoi_ghi_them_chu_khong_xoa(self) -> None:
        pool = FakePool({"id": "c-1"})
        out = _run(
            ConsentService(pool).revoke(
                identity=_identity(), consent_id="c-1", reason="BN rút đồng ý"
            )
        )
        assert out == {"consent_id": "c-1", "revoked": True}
        assert pool.wrote("UPDATE public.clinical_data_consent")
        assert not any("DELETE" in q for q in pool.queries())


class TestSharedForm:
    def test_thieu_ma_form(self) -> None:
        pool = FakePool()
        with pytest.raises(ValidationError, match="Thiếu mã form"):
            _run(
                ConsentService(pool).shared_form(
                    identity=_identity(),
                    subject_patient_id=CHONG,
                    viewing_patient_id=VO,
                    form_code="",
                )
            )

    def test_chua_dong_y_thi_khong_doc_bang_ho_so(self) -> None:
        """Quan trọng: khi bị từ chối, câu SELECT hồ sơ KHÔNG được chạy. Lọc
        sau khi đọc là đã đọc rồi — và dữ liệu đã nằm trong bộ nhớ tiến trình."""
        pool = FakePool([])  # load() → không có bản đồng ý nào
        out = _run(
            ConsentService(pool).shared_form(
                identity=_identity(),
                subject_patient_id=CHONG,
                viewing_patient_id=VO,
                form_code="nk",
            )
        )
        assert out == {"allowed": False, "form_code": "NK", "responses": []}
        assert not pool.wrote("clinical_form_response")

    def test_co_dong_y_thi_tra_ho_so(self) -> None:
        pool = FakePool(
            [
                {
                    "subject_patient_id": CHONG,
                    "grantee_patient_id": VO,
                    "form_codes": ["ALL"],
                    "revoked_at": None,
                }
            ],
            [
                {
                    "id": "r-1",
                    "visit_id": "v-1",
                    "form_data": {"x": 1},
                    "updated_at": None,
                }
            ],
        )
        out = _run(
            ConsentService(pool).shared_form(
                identity=_identity(),
                subject_patient_id=CHONG,
                viewing_patient_id=VO,
                form_code="NK",
            )
        )
        assert out["allowed"] is True
        assert out["responses"][0]["visit_id"] == "v-1"
        assert pool.wrote("clinical_form_response")


class TestLinkedPartners:
    def test_noi_ro_tung_chieu_chia_se_form_nao(self) -> None:
        """Một danh sách chỉ nói "đã liên kết" sẽ được đọc thành "xem được
        hết". Màn hình phải nói được cả hai chiều."""
        pool = FakePool(
            [
                {
                    "id": "l-1",
                    "relation": "SPOUSE",
                    "patient_a": CHONG,
                    "patient_b": VO,
                    "other_patient_id": CHONG,
                    "other_name": "Anh B",
                    "other_code": "BN-2",
                }
            ],
            [
                {
                    "subject_patient_id": CHONG,
                    "grantee_patient_id": VO,
                    "form_codes": ["HMVS"],
                    "revoked_at": None,
                }
            ],
        )
        out = _run(
            ConsentService(pool).linked_partners(identity=_identity(), patient_id=VO)
        )
        assert out[0]["they_shared_with_this_patient"] == ["HMVS"]
        assert out[0]["this_patient_shared_with_them"] == []
