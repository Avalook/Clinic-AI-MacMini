"""Ghép hồ sơ người này vào màn hình người kia — luật §6.5, cho mọi dịch vụ.

Tình huống thật đứng sau file test này: hai vợ chồng đi khám hiếm muộn. Bác sĩ
mở buổi khám của người vợ. Câu hỏi mà `may_surface` trả lời là "có được kéo kết
quả tinh dịch đồ của chồng vào màn hình này không" — và câu trả lời mặc định
phải là KHÔNG, kể cả khi hai người đã được liên kết trong hệ thống.

Bốn chốt ở tầng database đã được thử trên prod (rollback) và đều chặn: đồng ý
mà chưa liên kết, liên kết ngược chiều thành dòng thứ hai, hai bản đồng ý cùng
hiệu lực, thu hồi mà không ghi lý do. Ở đây là phần logic thuần.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clinicai.services.consent_service import ALL_FORMS, Consent, may_surface

CHONG = "chong-uuid"
VO = "vo-uuid"
NGUOI_LA = "nguoi-la-uuid"

DA_THU_HOI = datetime(2026, 8, 4, tzinfo=UTC)


def _dong_y(
    *,
    subject: str = CHONG,
    grantee: str = VO,
    forms: tuple[str, ...] = ("HMVS",),
    revoked: datetime | None = None,
) -> Consent:
    return Consent(
        subject_patient_id=subject,
        grantee_patient_id=grantee,
        form_codes=forms,
        revoked_at=revoked,
    )


class TestHoSoCuaChinhMinh:
    def test_khong_can_ai_dong_y(self) -> None:
        assert may_surface(
            subject_patient_id=VO,
            viewing_patient_id=VO,
            form_code="NK",
            consents=[],
        )

    def test_ke_ca_khi_ban_dong_y_cua_chinh_ho_da_bi_thu_hoi(self) -> None:
        """Thu hồi quyền chia sẻ CHO NGƯỜI KHÁC không đụng tới quyền của chính
        chủ với hồ sơ của mình."""
        assert may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=CHONG,
            form_code="NK",
            consents=[_dong_y(revoked=DA_THU_HOI)],
        )


class TestMacDinhLaKhong:
    def test_khong_co_ban_dong_y_nao(self) -> None:
        assert not may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="NK",
            consents=[],
        )

    def test_da_lien_ket_nhung_chua_dong_y_van_la_khong(self) -> None:
        """Liên kết vợ chồng nằm ở bảng khác và KHÔNG vào đây. Hàm này chỉ nhìn
        bản đồng ý — nên "đã là vợ chồng" tự nó không mở được hồ sơ nào."""
        assert not may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="NK",
            consents=[],
        )


class TestPhamVi:
    def test_dung_form_thi_duoc(self) -> None:
        assert may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="HMVS",
            consents=[_dong_y(forms=("HMVS",))],
        )

    def test_form_khac_thi_khong(self) -> None:
        """Đây là cả lý do `form_codes` là DANH SÁCH chứ không phải một cờ:
        chồng cho vợ xem hồ sơ hiếm muộn chung, không cho xem hồ sơ nam khoa."""
        assert not may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="NK",
            consents=[_dong_y(forms=("HMVS",))],
        )

    def test_pham_vi_all_mo_moi_form(self) -> None:
        assert may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="NK",
            consents=[_dong_y(forms=(ALL_FORMS,))],
        )

    @pytest.mark.parametrize("form", ["NK", "HMVS", "SK", "PK", "NT"])
    def test_pham_vi_all_mo_ca_nhung_form_chua_ton_tai(self, form: str) -> None:
        """Danh mục form còn dài ra. `ALL` phải giữ nghĩa "mọi form", kể cả form
        thêm sau ngày ký bản đồng ý — đó chính là điều người ký đã đồng ý."""
        assert may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code=form,
            consents=[_dong_y(forms=(ALL_FORMS,))],
        )

    def test_pham_vi_rong_khong_mo_gi(self) -> None:
        """Database đã chặn phạm vi rỗng (`clinical_data_consent_has_scope`),
        nhưng hàm này cũng không được coi rỗng là "cho hết" — dữ liệu cũ, dữ
        liệu nhập tay, hay một đợt migrate hỏng đều có thể sinh ra dòng rỗng."""
        assert not may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="NK",
            consents=[_dong_y(forms=())],
        )


class TestThuHoi:
    def test_ban_da_thu_hoi_khong_con_hieu_luc(self) -> None:
        assert not may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="HMVS",
            consents=[_dong_y(forms=(ALL_FORMS,), revoked=DA_THU_HOI)],
        )

    def test_ban_moi_khong_bi_ban_cu_da_thu_hoi_lam_hong(self) -> None:
        """Thu hồi là GHI THÊM chứ không xoá, nên hai dòng cùng một cặp là bình
        thường: một đã thu hồi, một đang hiệu lực."""
        assert may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="HMVS",
            consents=[
                _dong_y(forms=("HMVS",), revoked=DA_THU_HOI),
                _dong_y(forms=("HMVS",)),
            ],
        )


class TestDungNguoi:
    def test_dong_y_cho_nguoi_khac_khong_dung_cho_nguoi_nay(self) -> None:
        assert not may_surface(
            subject_patient_id=CHONG,
            viewing_patient_id=VO,
            form_code="HMVS",
            consents=[_dong_y(grantee=NGUOI_LA, forms=(ALL_FORMS,))],
        )

    def test_dong_y_khong_chay_nguoc_chieu(self) -> None:
        """Chồng cho vợ xem hồ sơ của chồng KHÔNG có nghĩa vợ cho chồng xem hồ
        sơ của vợ. Hai chiều là hai bản đồng ý."""
        assert not may_surface(
            subject_patient_id=VO,
            viewing_patient_id=CHONG,
            form_code="HMVS",
            consents=[_dong_y(subject=CHONG, grantee=VO, forms=(ALL_FORMS,))],
        )

    def test_ho_so_cua_nguoi_thu_ba_khong_lot_qua(self) -> None:
        assert not may_surface(
            subject_patient_id=NGUOI_LA,
            viewing_patient_id=VO,
            form_code="HMVS",
            consents=[_dong_y(subject=CHONG, grantee=VO, forms=(ALL_FORMS,))],
        )
