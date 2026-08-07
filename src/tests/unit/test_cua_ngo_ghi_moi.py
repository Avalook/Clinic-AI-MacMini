"""Câu TỪ CHỐI của ba đường ghi mới — nhà thuốc, nhắc tái khám, thông báo.

VÌ SAO CHỈ KIỂM PHẦN NÀY.

Ba service này chủ yếu là SQL, và SQL được canh trên Postgres thật ở
`supabase/tests/*.sql` (tồn không xuống âm, sổ chỉ-thêm, sinh việc không đẻ
thêm, bấm mười lần ra một thông báo). Lặp lại chuyện đó bằng stub chỉ kiểm
được cái stub.

Thứ KHÔNG có ở đó là các cửa chặn bằng Python: những câu từ chối phải nói
được bằng tiếng người TRƯỚC khi chạm ràng buộc của database. Một dược sĩ đọc
"violates check constraint drug_batch_qty_non_negative" thì không biết mình
phải làm gì; đọc "lô này chỉ còn 3" thì biết.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.pharmacy_service import PharmacyService, _so
from clinicai.services.recall_job_service import RecallJobService
from clinicai.services.thong_bao_service import ThongBaoService


def _identity(role: ClinicRole = ClinicRole.PHARMACIST) -> StaffIdentity:
    return StaffIdentity(
        staff_id="d0000000-0000-4000-8000-000000000001",
        auth_user_id="u1",
        full_name="Dược sĩ kiểm thử",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _Pool:
    """Pool giả — không service nào dưới đây được đi tới nó.

    Đó chính là điều cần khẳng định: câu từ chối phải bật ra TRƯỚC khi mở kết
    nối. Chạm tới pool nghĩa là một đầu vào rác đã đi được vào tới database.
    """

    def acquire(self) -> Any:  # pragma: no cover - chạm vào là sai
        raise AssertionError(
            "service đã mở kết nối cho một đầu vào lẽ ra phải bị từ chối"
        )


class _Conn:
    """Kết nối giả trả lời theo thứ tự gọi."""

    def __init__(self, *ket_qua: Any) -> None:
        self._kq = list(ket_qua)
        self.da_chay: list[str] = []

    def _lay(self) -> Any:
        return self._kq.pop(0) if self._kq else None

    async def fetch(self, sql: str, *a: Any) -> Any:
        self.da_chay.append(sql)
        return self._lay() or []

    async def fetchrow(self, sql: str, *a: Any) -> Any:
        self.da_chay.append(sql)
        return self._lay()

    async def fetchval(self, sql: str, *a: Any) -> Any:
        self.da_chay.append(sql)
        return self._lay()

    async def execute(self, sql: str, *a: Any) -> None:
        self.da_chay.append(sql)

    def transaction(self) -> Any:
        return _Suot()


class _Suot:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *a: Any) -> bool:
        return False


class _PoolCo:
    """Pool giả CÓ trả lời — cho các đường đi tới được database.

    asyncpg.Pool có cả `fetch`/`fetchrow`/`execute` ở tầng pool (mượn tạm một
    kết nối rồi trả), không chỉ `acquire()`. Service nào gọi thẳng
    `pool.fetch(...)` sẽ vỡ nếu stub chỉ có `acquire`.
    """

    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    async def fetch(self, sql: str, *a: Any) -> Any:
        return await self.conn.fetch(sql, *a)

    async def fetchrow(self, sql: str, *a: Any) -> Any:
        return await self.conn.fetchrow(sql, *a)

    async def fetchval(self, sql: str, *a: Any) -> Any:
        return await self.conn.fetchval(sql, *a)

    async def execute(self, sql: str, *a: Any) -> None:
        await self.conn.execute(sql, *a)

    def acquire(self) -> Any:
        conn = self.conn

        class _Cm:
            async def __aenter__(self) -> _Conn:
                return conn

            async def __aexit__(self, *a: Any) -> bool:
                return False

        return _Cm()


class TestDuongDoc:
    """Đường đọc phải lọc theo phòng khám và trả đúng hình dạng."""

    @pytest.mark.asyncio
    async def test_hang_doi_loc_theo_chua_chot(self) -> None:
        conn = _Conn([{"id": "1", "dispense_status": "CHUA_CAP"}])
        ra = await PharmacyService(_PoolCo(conn)).hang_doi(identity=_identity())
        assert ra and ra[0]["dispense_status"] == "CHUA_CAP"
        # Lọc theo VIỆC CÒN LẠI, không theo ngày: đơn kê hôm qua mà khách hôm
        # nay mới tới lấy vẫn phải nằm trong hàng đợi.
        assert "closed_at IS NULL" in conn.da_chay[0]
        assert "clinic_id" in conn.da_chay[0]

    @pytest.mark.asyncio
    async def test_ton_kho_bao_luon_lo_het_han(self) -> None:
        conn = _Conn([{"id": "b1", "het_han": True}])
        ra = await PharmacyService(_PoolCo(conn)).ton_kho(identity=_identity())
        assert ra[0]["het_han"] is True
        assert "expiry_date" in conn.da_chay[0]

    @pytest.mark.asyncio
    async def test_thong_bao_cua_toi_loc_theo_vai_va_nguoi(self) -> None:
        conn = _Conn([{"id": "t1", "muc_do": "KHAN"}])
        ra = await ThongBaoService(_PoolCo(conn)).cua_toi(
            identity=_identity(ClinicRole.NURSE_ULTRASOUND)
        )
        assert ra[0]["muc_do"] == "KHAN"
        sql = conn.da_chay[0]
        # Chỉ thấy việc CHƯA xử lý, và chỉ của vai mình hoặc đích danh mình.
        assert "da_xu_ly_luc IS NULL" in sql
        assert "vai_nhan" in sql and "nguoi_nhan_staff_id" in sql


class TestChotHaiLanKhongHong:
    """Bấm lại sau khi mạng lag không được báo 'xong' một cách trống rỗng."""

    @pytest.mark.asyncio
    async def test_chot_lai_dong_da_chot_thi_noi_ro(self) -> None:
        # UPDATE không khớp dòng nào (đã chốt trước đó) → nhưng dòng CÓ tồn tại.
        conn = _Conn(None, 1)
        ra = await PharmacyService(_PoolCo(conn)).chot(
            identity=_identity(), prescription_id="p1"
        )
        assert ra["da_chot_tu_truoc"] is True

    @pytest.mark.asyncio
    async def test_ghi_ket_qua_lai_thi_noi_da_ghi_tu_truoc(self) -> None:
        conn = _Conn(None, "DA_GOI")
        ra = await RecallJobService(_PoolCo(conn)).ghi_ket_qua(
            identity=_identity(ClinicRole.CSKH),
            viec_id="v1",
            ket_qua="DA_LIEN_HE",
        )
        assert ra["da_ghi_tu_truoc"] is True


class TestSoLuongThuoc:
    """`_so()` gác mọi con số đi vào kho."""

    @pytest.mark.parametrize("rac", ["", "abc", None, "12 viên"])
    def test_khong_phai_so_thi_noi_ro_o_nao_sai(self, rac: Any) -> None:
        with pytest.raises(ValidationError) as e:
            _so(rac, ten="Số lượng nhập")
        # Câu từ chối phải NHẮC TÊN Ô, không phải "invalid input".
        assert "Số lượng nhập" in str(e.value)

    @pytest.mark.parametrize("so", [0, -1, "-5"])
    def test_khong_duong_thi_tu_choi(self, so: Any) -> None:
        with pytest.raises(ValidationError) as e:
            _so(so, ten="Số lượng cấp")
        assert "lớn hơn 0" in str(e.value)

    def test_so_hop_le_thi_qua(self) -> None:
        assert _so("2.5", ten="x") == pytest.approx(2.5)


class TestNhaThuoc:
    @pytest.mark.asyncio
    async def test_nhap_lo_thieu_so_lo_thi_tu_choi(self) -> None:
        # Số lô là thứ dùng để THU HỒI. Thiếu nó thì lúc có sự cố thuốc không
        # tra ra được đã cấp cho ai.
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_Pool()).nhap_lo(
                identity=_identity(),
                drug_catalog_id="c0000000-0000-4000-8000-000000000001",
                so_luong=10,
                batch_code="   ",
                expiry_date=None,
                unit="viên",
            )
        assert "số lô" in str(e.value).lower()

    @pytest.mark.asyncio
    async def test_nhap_lo_thieu_han_dung_thi_tu_choi(self) -> None:
        # Thuốc không có hạn dùng trong sổ là thuốc không ai biết khi nào bỏ.
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_Pool()).nhap_lo(
                identity=_identity(),
                drug_catalog_id="c0000000-0000-4000-8000-000000000001",
                so_luong=10,
                batch_code="LO-1",
                expiry_date=None,
                unit="viên",
            )
        assert "hạn dùng" in str(e.value).lower()

    @pytest.mark.asyncio
    async def test_tu_choi_lay_thuoc_phai_co_ly_do(self) -> None:
        # CSKH còn gọi lại hỏi; "khách không lấy" mà không nói vì sao thì
        # người gọi không có gì để nói.
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_Pool()).tu_choi(
                identity=_identity(),
                prescription_id="p1",
                ly_do="   ",
            )
        assert "vì sao" in str(e.value).lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ham", ["dieu_chinh", "huy"])
    async def test_dong_kho_phai_co_ly_do(self, ham: str) -> None:
        svc = PharmacyService(_Pool())
        with pytest.raises(ValidationError):
            await getattr(svc, ham)(
                identity=_identity(),
                drug_batch_id="b1",
                so_luong=5,
                ly_do="",
            )

    @pytest.mark.asyncio
    async def test_dieu_chinh_khong_thi_khong_phai_dieu_chinh(self) -> None:
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_Pool()).dieu_chinh(
                identity=_identity(), drug_batch_id="b1", so_luong=0, ly_do="kiểm kê"
            )
        assert "0" in str(e.value)


class TestCapPhatNoiTruocRangBuoc:
    """Ba câu từ chối trong `cap_phat` — mỗi câu phải mang CON SỐ.

    Database đã chặn cả ba (không cấp quá số kê, tồn không xuống âm). Nhưng
    dược sĩ đọc `violates check constraint` thì không biết còn bao nhiêu; đọc
    "chỉ còn 6" thì biết đưa khách mấy viên.
    """

    @staticmethod
    def _conn(don: Any, lo: Any) -> _Conn:
        return _Conn(don, lo)

    @pytest.mark.asyncio
    async def test_cap_qua_so_ke_thi_noi_con_bao_nhieu(self) -> None:
        don = {
            "id": "p1",
            "drug_name_raw": "Androgel",
            "quantity_num": 10,
            "dispensed_qty": 4,
            "closed_at": None,
            "refusal_reason": None,
        }
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_PoolCo(self._conn(don, None))).cap_phat(
                identity=_identity(),
                prescription_id="p1",
                drug_batch_id="b1",
                so_luong=9,
            )
        msg = str(e.value)
        assert "10" in msg and "4" in msg and "6" in msg

    @pytest.mark.asyncio
    async def test_don_da_chot_thi_khong_cap_them(self) -> None:
        from clinicai.api.exceptions import ConflictError

        don = {
            "id": "p1",
            "drug_name_raw": "X",
            "quantity_num": 10,
            "dispensed_qty": 0,
            "closed_at": "2026-08-07",
            "refusal_reason": None,
        }
        with pytest.raises(ConflictError):
            await PharmacyService(_PoolCo(self._conn(don, None))).cap_phat(
                identity=_identity(),
                prescription_id="p1",
                drug_batch_id="b1",
                so_luong=1,
            )

    @pytest.mark.asyncio
    async def test_khong_du_ton_thi_noi_con_bao_nhieu(self) -> None:
        don = {
            "id": "p1",
            "drug_name_raw": "X",
            "quantity_num": None,
            "dispensed_qty": 0,
            "closed_at": None,
            "refusal_reason": None,
        }
        lo = {
            "id": "b1",
            "quantity_on_hand": 3,
            "expiry_date": None,
            "name_base": "Androgel",
        }
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_PoolCo(self._conn(don, lo))).cap_phat(
                identity=_identity(),
                prescription_id="p1",
                drug_batch_id="b1",
                so_luong=5,
            )
        assert "3" in str(e.value) and "5" in str(e.value)

    @pytest.mark.asyncio
    async def test_lo_het_han_thi_tu_choi_va_noi_ngay(self) -> None:
        from datetime import date, timedelta

        hom_qua = date.today() - timedelta(days=1)
        don = {
            "id": "p1",
            "drug_name_raw": "X",
            "quantity_num": None,
            "dispensed_qty": 0,
            "closed_at": None,
            "refusal_reason": None,
        }
        lo = {
            "id": "b1",
            "quantity_on_hand": 100,
            "expiry_date": hom_qua,
            "name_base": "Androgel",
        }
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_PoolCo(self._conn(don, lo))).cap_phat(
                identity=_identity(),
                prescription_id="p1",
                drug_batch_id="b1",
                so_luong=1,
            )
        assert "hết hạn" in str(e.value).lower()
        assert hom_qua.strftime("%d/%m/%Y") in str(e.value)

    @pytest.mark.asyncio
    async def test_khong_tim_thay_don_thi_bao_khong_thay(self) -> None:
        from clinicai.api.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await PharmacyService(_PoolCo(_Conn(None))).cap_phat(
                identity=_identity(),
                prescription_id="p1",
                drug_batch_id="b1",
                so_luong=1,
            )


class TestNhacTaiKham:
    @pytest.mark.asyncio
    async def test_ket_qua_la_thi_tu_choi_va_liet_ke_gia_tri_dung(self) -> None:
        # Một mã lạ lọt vào nghĩa là cột `ket_qua` có giá trị không ai đọc
        # được — đúng thứ mà cả migration 20260807000002 sinh ra để chặn.
        with pytest.raises(ValidationError) as e:
            await RecallJobService(_Pool()).ghi_ket_qua(
                identity=_identity(ClinicRole.CSKH),
                viec_id="v1",
                ket_qua="BUA_RA",
            )
        assert "DA_LIEN_HE" in str(e.value)

    @pytest.mark.asyncio
    async def test_bo_qua_phai_co_ly_do(self) -> None:
        with pytest.raises(ValidationError):
            await RecallJobService(_Pool()).bo_qua(
                identity=_identity(ClinicRole.CSKH), viec_id="v1", ly_do=" "
            )


class TestGoiBoPhan:
    @pytest.mark.asyncio
    async def test_vai_khong_co_that_thi_tu_choi(self) -> None:
        # Gọi một vai không tồn tại = một thông báo không ai nhận được.
        with pytest.raises(ValidationError) as e:
            await ThongBaoService(_Pool()).goi(
                identity=_identity(ClinicRole.TRUONG_CA),
                vai_nhan="BAC_SI_TRUONG",
                tieu_de="SA1 tắc",
                noi_dung="4 người chờ",
            )
        assert "BAC_SI_TRUONG" in str(e.value)

    @pytest.mark.asyncio
    async def test_muc_do_la_thi_tu_choi(self) -> None:
        with pytest.raises(ValidationError):
            await ThongBaoService(_Pool()).goi(
                identity=_identity(ClinicRole.TRUONG_CA),
                vai_nhan="RECEPTION",
                tieu_de="x",
                noi_dung="y",
                muc_do="RAT_KHAN",
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tieu_de", "noi_dung"), [("", "có nội dung"), ("có tiêu đề", "  ")]
    )
    async def test_thong_bao_rong_thi_tu_choi(
        self, tieu_de: str, noi_dung: str
    ) -> None:
        # Một thông báo đỏ không có chữ nào là một lần đánh thức vô nghĩa.
        with pytest.raises(ValidationError):
            await ThongBaoService(_Pool()).goi(
                identity=_identity(ClinicRole.TRUONG_CA),
                vai_nhan="RECEPTION",
                tieu_de=tieu_de,
                noi_dung=noi_dung,
            )


class TestDuongChinhDiTronVen:
    """Đường thành công — để một lần đổi cấu trúc payload không lọt lưới."""

    @pytest.mark.asyncio
    async def test_goi_bo_phan_tra_ve_vai_da_goi(self) -> None:
        conn = _Conn({"id": "t1", "tao_luc": "2026-08-07T09:00:00Z"})
        ra = await ThongBaoService(_PoolCo(conn)).goi(
            identity=_identity(ClinicRole.TRUONG_CA),
            vai_nhan="NURSE_ULTRASOUND",
            tieu_de="SA1 đang tắc",
            noi_dung="4 người chờ, lâu nhất 38 phút",
            nguon_id="SA1",
        )
        assert ra["ok"] and ra["vai_nhan"] == "NURSE_ULTRASOUND"
        # Phải ghi sổ sự kiện, nếu không cuộc gọi không để lại dấu vết nào.
        assert any("event_log" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_goi_lai_khi_chua_ai_xu_ly_thi_khong_nhan_doi(self) -> None:
        # INSERT ... ON CONFLICT DO NOTHING → không trả dòng nào; service phải
        # đi tìm cái cũ và nói rõ, chứ không báo "đã gửi".
        conn = _Conn(None, {"id": "t-cu", "tao_luc": "2026-08-07T08:00:00Z"})
        ra = await ThongBaoService(_PoolCo(conn)).goi(
            identity=_identity(ClinicRole.TRUONG_CA),
            vai_nhan="RECEPTION",
            tieu_de="x",
            noi_dung="y",
            nguon_id="SA1",
        )
        assert ra["da_goi_tu_truoc"] is True and ra["id"] == "t-cu"

    @pytest.mark.asyncio
    async def test_da_xu_ly_tra_ve_thoi_gian_phan_hoi(self) -> None:
        conn = _Conn({"id": "t1", "giay_phan_hoi": 42})
        ra = await ThongBaoService(_PoolCo(conn)).da_xu_ly(
            identity=_identity(ClinicRole.NURSE_ULTRASOUND),
            thong_bao_id="t1",
            ghi_chu="đã điều thêm người",
        )
        # Đo được thời gian phản hồi là lý do bảng này tồn tại.
        assert ra["giay_phan_hoi"] == 42

    @pytest.mark.asyncio
    async def test_da_xu_ly_dong_khong_ton_tai_thi_bao_khong_thay(self) -> None:
        from clinicai.api.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await ThongBaoService(_PoolCo(_Conn(None))).da_xu_ly(
                identity=_identity(), thong_bao_id="t1", ghi_chu=None
            )

    @pytest.mark.asyncio
    async def test_sinh_viec_tra_so_luong_moi(self) -> None:
        conn = _Conn({"luot1_moi": 3, "luot2_moi": 2})
        ra = await RecallJobService(_PoolCo(conn)).sinh(
            identity=_identity(ClinicRole.CSKH)
        )
        assert ra == {"luot1_moi": 3, "luot2_moi": 2}

    @pytest.mark.asyncio
    async def test_danh_sach_tach_dung_hai_luot(self) -> None:
        # `sinh_truoc=False`: bài này kiểm phép TÁCH, không kiểm bộ sinh việc.
        conn = _Conn(
            [
                {"id": "a", "luot_goi": 1},
                {"id": "b", "luot_goi": 2},
                {"id": "c", "luot_goi": 1},
            ]
        )
        ra = await RecallJobService(_PoolCo(conn)).danh_sach(
            identity=_identity(ClinicRole.CSKH), sinh_truoc=False
        )
        assert len(ra["luot1"]) == 2 and len(ra["luot2"]) == 1
        assert ra["cua_so_ngay"] == 7

    @pytest.mark.asyncio
    async def test_bo_qua_dong_khong_ton_tai_thi_bao_khong_thay(self) -> None:
        from clinicai.api.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await RecallJobService(_PoolCo(_Conn(None))).bo_qua(
                identity=_identity(ClinicRole.CSKH),
                viec_id="v1",
                ly_do="khách đã tự đặt lịch",
            )


class TestNhapLoVaoKho:
    """Nhập lô — nơi một số lô gõ nhầm thành hai thứ thuốc chung một dòng tồn."""

    @staticmethod
    def _nhap(pool: Any, **ghi_de: Any) -> Any:
        tham_so: dict[str, Any] = {
            "identity": _identity(),
            "drug_catalog_id": "c1",
            "batch_code": "LO-A1",
            "expiry_date": date(2027, 1, 31),
            "unit": "viên",
            "so_luong": "100",
        }
        tham_so.update(ghi_de)
        return PharmacyService(pool).nhap_lo(**tham_so)

    @pytest.mark.asyncio
    async def test_lo_moi_thi_tao_roi_ghi_so(self) -> None:
        conn = _Conn(
            {"id": "c1", "name_base": "Paracetamol"},  # thuốc có trong danh mục
            None,  # chưa có lô này
            "b-moi",  # INSERT drug_batch RETURNING id
            100,  # tồn sau khi trigger cộng
        )
        ra = await self._nhap(_PoolCo(conn))
        assert ra["ok"] and ra["drug_batch_id"] == "b-moi"
        # Tồn KHÔNG được cộng tay — chỉ có dòng sổ, trigger lo phần còn lại.
        assert any("inventory_txn" in sql for sql in conn.da_chay)
        assert not any("UPDATE public.drug_batch" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_lo_da_co_dung_thuoc_dung_han_thi_nhap_them(self) -> None:
        conn = _Conn(
            {"id": "c1", "name_base": "Paracetamol"},
            {"id": "b-cu", "drug_catalog_id": "c1", "expiry_date": date(2027, 1, 31)},
            150,
        )
        ra = await self._nhap(_PoolCo(conn))
        assert ra["drug_batch_id"] == "b-cu"

    @pytest.mark.asyncio
    async def test_so_lo_da_dung_cho_thuoc_khac_thi_chan(self) -> None:
        conn = _Conn(
            {"id": "c1", "name_base": "Paracetamol"},
            {
                "id": "b-cu",
                "drug_catalog_id": "c-khac",
                "expiry_date": date(2027, 1, 31),
            },
        )
        with pytest.raises(ConflictError) as e:
            await self._nhap(_PoolCo(conn))
        assert "thuốc khác" in str(e.value)

    @pytest.mark.asyncio
    async def test_cung_so_lo_khac_han_dung_thi_chan(self) -> None:
        conn = _Conn(
            {"id": "c1", "name_base": "Paracetamol"},
            {"id": "b-cu", "drug_catalog_id": "c1", "expiry_date": date(2026, 5, 1)},
        )
        with pytest.raises(ConflictError) as e:
            await self._nhap(_PoolCo(conn))
        # Câu lỗi phải nói ra hạn ĐANG CÓ, nếu không dược sĩ không biết sai ở đâu.
        assert "01/05/2026" in str(e.value)

    @pytest.mark.asyncio
    async def test_thuoc_khong_co_trong_danh_muc_thi_bao_khong_thay(self) -> None:
        with pytest.raises(NotFoundError):
            await self._nhap(_PoolCo(_Conn(None)))


class TestDieuChinhVaHuyLo:
    """Sổ kho ghi cả lần bớt đi — bớt quá tồn thì chặn trước khi chạm database."""

    @pytest.mark.asyncio
    async def test_dieu_chinh_am_qua_ton_thi_chan(self) -> None:
        conn = _Conn({"id": "b1", "quantity_on_hand": 3})
        with pytest.raises(ValidationError) as e:
            await PharmacyService(_PoolCo(conn)).dieu_chinh(
                identity=_identity(),
                drug_batch_id="b1",
                so_luong="-10",
                ly_do="kiểm kê lệch",
            )
        assert "chỉ còn 3" in str(e.value)

    @pytest.mark.asyncio
    async def test_dieu_chinh_hop_le_thi_tra_ton_moi(self) -> None:
        conn = _Conn({"id": "b1", "quantity_on_hand": 20}, 18)
        ra = await PharmacyService(_PoolCo(conn)).dieu_chinh(
            identity=_identity(),
            drug_batch_id="b1",
            so_luong="-2",
            ly_do="vỡ 2 ống",
        )
        assert ra["quantity_on_hand"] == 18
        # Bớt kho là việc phải truy được người làm → bắt buộc có sổ sự kiện.
        assert any("event_log" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_huy_lo_khong_ton_tai_thi_bao_khong_thay(self) -> None:
        with pytest.raises(NotFoundError):
            await PharmacyService(_PoolCo(_Conn(None))).huy(
                identity=_identity(),
                drug_batch_id="b1",
                so_luong="5",
                ly_do="hết hạn",
            )


class TestCapPhatDiTronVen:
    """Cấp một phần là chuyện thường ngày — hai sổ phải khớp trong một giao dịch."""

    @pytest.mark.asyncio
    async def test_cap_mot_phan_tra_ve_trang_thai_moi(self) -> None:
        conn = _Conn(
            {  # đơn còn mở, kê 10, đã cấp 0
                "id": "p1",
                "drug_name_raw": "Paracetamol",
                "quantity_num": 10,
                "dispensed_qty": 0,
                "closed_at": None,
                "refusal_reason": None,
            },
            {  # lô còn hàng, còn hạn
                "id": "b1",
                "quantity_on_hand": 50,
                "expiry_date": date(2027, 12, 31),
                "name_base": "Paracetamol",
            },
            {"dispensed_qty": 4, "dispense_status": "CAP_MOT_PHAN"},
        )
        ra = await PharmacyService(_PoolCo(conn)).cap_phat(
            identity=_identity(),
            prescription_id="p1",
            drug_batch_id="b1",
            so_luong="4",
        )
        assert ra["dispense_status"] == "CAP_MOT_PHAN" and ra["dispensed_qty"] == 4
        # Dòng sổ kho phải mang dấu ÂM — `inventory_txn_qty_sign_check`.
        assert any("inventory_txn" in sql for sql in conn.da_chay)
        assert any("dispensed_qty = dispensed_qty" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_tu_choi_tra_ve_dong_da_chot(self) -> None:
        conn = _Conn({"dispensed_qty": 0, "dispense_status": "TU_CHOI"})
        ra = await PharmacyService(_PoolCo(conn)).tu_choi(
            identity=_identity(),
            prescription_id="p1",
            ly_do="khách đã có thuốc ở nhà",
        )
        assert ra["dispense_status"] == "TU_CHOI"
        assert any("event_log" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_chot_lai_dong_da_chot_thi_noi_ro_khong_doi_gi(self) -> None:
        # UPDATE ... AND closed_at IS NULL không khớp dòng nào, nhưng đơn CÓ tồn tại.
        conn = _Conn(None, 1)
        ra = await PharmacyService(_PoolCo(conn)).chot(
            identity=_identity(), prescription_id="p1", ly_do=None
        )
        assert ra == {"ok": True, "da_chot_tu_truoc": True}

    @pytest.mark.asyncio
    async def test_chot_dong_khong_ton_tai_thi_bao_khong_thay(self) -> None:
        with pytest.raises(NotFoundError):
            await PharmacyService(_PoolCo(_Conn(None, None))).chot(
                identity=_identity(), prescription_id="p1", ly_do=None
            )


class TestGhiKetQuaCuocGoi:
    """Gọi xong phải để lại hai dấu vết: việc đóng, và một dòng nhật ký CSKH."""

    @pytest.mark.asyncio
    async def test_ghi_ket_qua_ghi_ca_nhat_ky_cskh(self) -> None:
        conn = _Conn(
            {"id": "v1", "luot_goi": 2, "clinic_patient_id": "cp1"},
        )
        ra = await RecallJobService(_PoolCo(conn)).ghi_ket_qua(
            identity=_identity(ClinicRole.CSKH),
            viec_id="v1",
            ket_qua="DA_LIEN_HE",
            ghi_chu="khách hẹn thứ Năm",
        )
        assert ra["luot_goi"] == 2
        # Màn hồ sơ bệnh nhân đọc từ cskh_log, không đọc bảng nhac_tai_kham.
        assert any("cskh_log" in sql for sql in conn.da_chay)
        assert any("luot_goi" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_ghi_lai_viec_da_ghi_thi_noi_ro_khong_doi_gi(self) -> None:
        conn = _Conn(None, "DA_GOI")
        ra = await RecallJobService(_PoolCo(conn)).ghi_ket_qua(
            identity=_identity(ClinicRole.CSKH),
            viec_id="v1",
            ket_qua="DA_LIEN_HE",
            ghi_chu=None,
        )
        assert ra["da_ghi_tu_truoc"] is True and ra["trang_thai"] == "DA_GOI"

    @pytest.mark.asyncio
    async def test_bo_qua_hop_le_thi_dong_viec(self) -> None:
        ra = await RecallJobService(_PoolCo(_Conn({"id": "v1"}))).bo_qua(
            identity=_identity(ClinicRole.CSKH),
            viec_id="v1",
            ly_do="khách đã tự đặt lịch",
        )
        assert ra == {"ok": True, "id": "v1"}


class TestLuatBacSiBatBuoc:
    """Luật "khách mới của dịch vụ này phải khám bác sĩ kia".

    Thi hành lúc ĐẶT LỊCH. Bốn nhánh dưới đây là bốn cách luật có thể im lặng
    hỏng, và mỗi cái đều đã có tiền lệ trong dự án này.
    """

    @staticmethod
    def _bs(conn: Any) -> Any:
        from clinicai.services.booking_service import BookingService

        return BookingService(_PoolCo(conn))

    @pytest.mark.asyncio
    async def test_chua_chon_bac_si_thi_khong_vuong_luat(self) -> None:
        # Lịch đang chờ xếp người: chưa có gì để đối chiếu. Chặn ở đây là chặn
        # luôn hàng chờ vừa mở ở nhịp trước.
        conn = _Conn()
        ra = await self._bs(conn)._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id="p1",
            service_type_id="sv1",
            doctor_id=None,
            identity=_identity(ClinicRole.RECEPTION),
        )
        assert ra is None
        assert conn.da_chay == [], "không được hỏi database khi chưa có bác sĩ"

    @pytest.mark.asyncio
    async def test_dich_vu_khong_co_luat_thi_qua(self) -> None:
        conn = _Conn(None)
        ra = await self._bs(conn)._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id="p1",
            service_type_id="sv1",
            doctor_id="bs-khac",
            identity=_identity(ClinicRole.RECEPTION),
        )
        assert ra is None

    @pytest.mark.asyncio
    async def test_khach_cu_thi_khong_bi_bat_kham_lai(self) -> None:
        # `khach_moi` do SQL tính từ LỊCH SỬ, không từ ô lễ tân gõ. Khách cũ
        # quay lại mà bị bắt khám lại từ đầu là kiểu sai người dùng chịu trận.
        conn = _Conn(
            {
                "bac_si_id": "bs-thanh",
                "chan_han": True,
                "ten_bac_si": "TS.BS. Phan Chí Thành",
                "ten_dich_vu": "Nội tiết",
                "khach_moi": False,
            }
        )
        ra = await self._bs(conn)._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id="p1",
            service_type_id="sv1",
            doctor_id="bs-khac",
            identity=_identity(ClinicRole.RECEPTION),
        )
        assert ra is None

    @pytest.mark.asyncio
    async def test_dung_bac_si_thi_qua(self) -> None:
        conn = _Conn(
            {
                "bac_si_id": "bs-thanh",
                "chan_han": True,
                "ten_bac_si": "TS.BS. Phan Chí Thành",
                "ten_dich_vu": "Nội tiết",
                "khach_moi": True,
            }
        )
        ra = await self._bs(conn)._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id="p1",
            service_type_id="sv1",
            doctor_id="bs-thanh",
            identity=_identity(ClinicRole.RECEPTION),
        )
        assert ra is None

    @pytest.mark.asyncio
    async def test_sai_bac_si_thi_chan_va_noi_ro_ai(self) -> None:
        conn = _Conn(
            {
                "bac_si_id": "bs-thanh",
                "chan_han": True,
                "ten_bac_si": "TS.BS. Phan Chí Thành",
                "ten_dich_vu": "Nội tiết",
                "khach_moi": True,
            }
        )
        ra = await self._bs(conn)._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id="p1",
            service_type_id="sv1",
            doctor_id="bs-khac",
            identity=_identity(ClinicRole.RECEPTION),
        )
        assert ra is not None
        cau, chan = ra
        # Câu phải nêu ĐÍCH DANH bác sĩ và dịch vụ: "không được phép" thì CSKH
        # không biết phải chuyển sang ai.
        assert "Phan Chí Thành" in cau and "Nội tiết" in cau
        assert chan is True

    @pytest.mark.asyncio
    async def test_chan_han_tat_thi_chi_canh_bao(self) -> None:
        # Phòng khám bật luật lần đầu thường muốn xem nó bắt đúng không trước
        # khi để nó từ chối khách.
        conn = _Conn(
            {
                "bac_si_id": "bs-thanh",
                "chan_han": False,
                "ten_bac_si": "TS.BS. Phan Chí Thành",
                "ten_dich_vu": "Nội tiết",
                "khach_moi": True,
            }
        )
        ra = await self._bs(conn)._luat_bac_si_bat_buoc(
            conn,
            clinic_patient_id="p1",
            service_type_id="sv1",
            doctor_id="bs-khac",
            identity=_identity(ClinicRole.RECEPTION),
        )
        assert ra is not None and ra[1] is False


class TestCauHinhLuatBacSi:
    """Màn cấu hình luật — chỗ quản lý tự khai, thay cho ghi cứng tên trong code."""

    @staticmethod
    def _sv(conn: Any) -> Any:
        from clinicai.services.luat_bac_si_service import LuatBacSiService

        return LuatBacSiService(_PoolCo(conn))

    @pytest.mark.asyncio
    async def test_cach_tinh_la_thu_thi_tu_choi(self) -> None:
        with pytest.raises(ValidationError):
            await self._sv(_Conn()).luu(
                identity=_identity(ClinicRole.MANAGEMENT),
                service_type_id="sv1",
                required_staff_id="bs1",
                cach_tinh="TUY_HUNG",
            )

    @pytest.mark.asyncio
    async def test_qua_n_thang_ma_thieu_so_thang_thi_tu_choi(self) -> None:
        # Thiếu số tháng thì luật không tính được — và nếu để lọt, nó sẽ im lặng
        # thành "không bao giờ khớp" chứ không báo gì.
        with pytest.raises(ValidationError) as e:
            await self._sv(_Conn()).luu(
                identity=_identity(ClinicRole.MANAGEMENT),
                service_type_id="sv1",
                required_staff_id="bs1",
                cach_tinh="QUA_N_THANG",
            )
        assert "số tháng" in str(e.value).lower()

    @pytest.mark.asyncio
    async def test_dich_vu_khong_ton_tai_thi_bao_khong_thay(self) -> None:
        with pytest.raises(NotFoundError):
            await self._sv(_Conn(None)).luu(
                identity=_identity(ClinicRole.MANAGEMENT),
                service_type_id="sv1",
                required_staff_id="bs1",
            )

    @pytest.mark.asyncio
    async def test_nguoi_khong_phai_bac_si_dang_lam_thi_tu_choi(self) -> None:
        # Luật trỏ vào người đã nghỉ sẽ chặn MỌI khách mới của dịch vụ đó mà
        # không ai chuyển sang được ai.
        conn = _Conn({"id": "sv1", "name": "Nội tiết"}, None)
        with pytest.raises(ValidationError) as e:
            await self._sv(conn).luu(
                identity=_identity(ClinicRole.MANAGEMENT),
                service_type_id="sv1",
                required_staff_id="ai-do",
            )
        assert "bác sĩ" in str(e.value).lower()

    @pytest.mark.asyncio
    async def test_xoa_luat_khong_ton_tai_thi_bao_khong_thay(self) -> None:
        with pytest.raises(NotFoundError):
            await self._sv(_Conn(None)).xoa(
                identity=_identity(ClinicRole.MANAGEMENT), luat_id="l1"
            )

    @pytest.mark.asyncio
    async def test_xem_thu_tu_choi_cach_tinh_la(self) -> None:
        with pytest.raises(ValidationError):
            await self._sv(_Conn()).xem_thu(
                identity=_identity(ClinicRole.MANAGEMENT),
                service_type_id="sv1",
                cach_tinh="BUA",
                so_thang=None,
            )

    @pytest.mark.asyncio
    async def test_luu_thanh_cong_ghi_ca_so_su_kien(self) -> None:
        conn = _Conn(
            {"id": "sv1", "name": "Nội tiết"},
            {"id": "bs1", "full_name": "TS.BS. Phan Chí Thành"},
            {"id": "l1"},
        )
        ra = await self._sv(conn).luu(
            identity=_identity(ClinicRole.MANAGEMENT),
            service_type_id="sv1",
            required_staff_id="bs1",
            cach_tinh="DOT_MOI",
        )
        assert ra["ok"] and ra["id"] == "l1"
        # Đổi luật ai-được-khám-ai là quyết định phải truy được người làm.
        assert any("event_log" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_so_thang_bi_bo_khi_cach_tinh_khong_dung_toi(self) -> None:
        # Để lại 12 tháng trên một luật không xét thời gian là dữ liệu gây hiểu
        # nhầm cho người đọc bảng sau này.
        conn = _Conn(
            {"id": "sv1", "name": "Nội tiết"},
            {"id": "bs1", "full_name": "BS X"},
            {"id": "l1"},
        )
        await self._sv(conn).luu(
            identity=_identity(ClinicRole.MANAGEMENT),
            service_type_id="sv1",
            required_staff_id="bs1",
            cach_tinh="CHUA_TUNG",
            so_thang=12,
        )
        assert any("luat_bac_si_bat_buoc" in sql for sql in conn.da_chay)

    @pytest.mark.asyncio
    async def test_danh_sach_tra_ca_luat_dang_tat(self) -> None:
        # Giấu luật đã tắt đi thì người sau sẽ tạo lại nó rồi ngạc nhiên vì trùng.
        conn = _Conn(
            [{"id": "l1", "is_active": False}, {"id": "l2", "is_active": True}]
        )
        ra = await self._sv(conn).danh_sach(identity=_identity(ClinicRole.MANAGEMENT))
        assert len(ra) == 2

    @pytest.mark.asyncio
    async def test_xem_thu_dem_duoc(self) -> None:
        conn = _Conn({"khach_moi": 41, "tong": 54})
        ra = await self._sv(conn).xem_thu(
            identity=_identity(ClinicRole.MANAGEMENT),
            service_type_id="sv1",
            cach_tinh="DOT_MOI",
            so_thang=None,
        )
        assert ra == {"khach_moi": 41, "tong": 54}
