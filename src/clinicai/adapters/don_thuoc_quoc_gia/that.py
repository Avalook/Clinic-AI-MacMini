"""Hệ thống đơn thuốc quốc gia THẬT — theo QĐ 808/QĐ-BYT (01/04/2022), bản PDF ở
https://donthuocquocgia.vn/quyet-dinh-808.pdf (mục VI đăng nhập bác sĩ, VII gửi đơn).
CHƯA từng chạy với hệ thống thật (chưa có tài khoản liên thông, không có sandbox
công khai) — lần đầu bật phải theo docs/LIEN-THONG-DON-THUOC.md mục "Thử lần đầu".

Nhãn: [808] = theo văn bản; [ĐOÁN] = tài liệu không nói, chọn theo các phần mềm
đang chạy (mã nguồn công khai trên GitHub) — kiểm lại với bộ phận hỗ trợ kỹ thuật
hotrokythuat@donthuocquocgia.vn.

  · Gửi đơn cần token CỦA BÁC SĨ đứng tên [808 VII] — hệ thống lấy tên, CCHN, cơ
    sở từ token; gói không chứa thông tin bác sĩ. Token sống 7 ngày, không có
    refresh [808 VI] → nhớ theo bác sĩ, hết hạn / 401 thì đăng nhập lại.
  · 200 = thành công; 422 = `danh_sach_cac_loi` (hình dạng không mô tả) [808].
  · 422 nói mã đơn đã tồn tại → coi là đã gửi (lần trước hết giờ chờ mà thật ra
    thành công; mã đơn duy nhất trong phòng khám nên không thể là đơn khác) [ĐOÁN].
  · `signature` rỗng khi chưa có bộ ký số: Bộ Y tế chưa hướng dẫn định dạng (HDSD
    FAQ 1.6, 1.22); các phần mềm đang chạy gửi rỗng [ĐOÁN].
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import httpx

from clinicai.ports.don_thuoc_quoc_gia import ChuKy, GoiDon, GuiDonError, KetQuaGui

DANG_NHAP_CO_SO = "/api/auth/dang-nhap-co-so-kham-chua-benh"
THEM_BAC_SI = "/api/v1/them-bac-si"
DANG_NHAP_BAC_SI = "/api/auth/dang-nhap-bac-si"
GUI_DON = "/api/v1/gui-don-thuoc"
#: Token sống 7 ngày [808]; dùng 6 ngày cho chắc.
TOKEN_SONG_GIAY = 6 * 24 * 3600
#: 1 chưa có thông tin, 2 nam, 3 nữ [808 VII.3 mục 8].
_GIOI_TINH = {"NAM": 2, "NU": 3}
#: 422 chỉ được coi là "đơn này đã lên rồi" khi câu lỗi nói về MÃ ĐƠN và sự trùng
#: — "bác sĩ đã tồn tại", "trùng mã thuốc" thì KHÔNG (ghi DA_GUI nhầm = mất đơn
#: mà không ai biết). Mẫu câu thật chưa có (câu hỏi 5 trong docs) [ĐOÁN].
_MA_DON = re.compile(r"m[ãa] đ[ơo]n|ma_don_thuoc")
_TRUNG = re.compile(r"(đ[ãa] t[ồo]n t[ạa]i|tr[ùu]ng|already exist)")


def da_ton_tai(loi: str) -> bool:
    """HÀM THUẦN: câu 422 có phải "mã đơn này đã có trên hệ thống" không."""
    s = loi.lower()
    return bool(_MA_DON.search(s) and _TRUNG.search(s))


def _ngay_dmy(iso: str | None) -> str:
    """yyyy-mm-dd → d/m/Y (dd/mm/yyyy) như [808]."""
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


def goi_api(goi: GoiDon, chu_ky: ChuKy | None) -> dict[str, Any]:
    """HÀM THUẦN: gói chuẩn ClinicAI → JSON `/api/v1/gui-don-thuoc` [808 VII.3].
    Tên trường theo JSON mẫu của văn bản (bảng trong văn bản ghi khác ở mã BHYT và
    chẩn đoán — các phần mềm đang chạy dùng tên của JSON mẫu)."""
    nb = goi.nguoi_benh
    return {
        "loai_don_thuoc": goi.ma_don[-1],
        "ma_don_thuoc": goi.ma_don,
        "ho_ten_benh_nhan": nb.ho_ten,
        "ma_dinh_danh_y_te": "",
        "ma_dinh_danh_cong_dan": nb.so_dinh_danh or "",
        "ngay_sinh_benh_nhan": _ngay_dmy(nb.ngay_sinh),
        # Không bắt buộc (chỉ bắt buộc với trẻ < 72 tháng) — ClinicAI không lưu
        # cân nặng theo lượt; gửi null thay vì bịa số 0 [ĐOÁN].
        "can_nang": None,
        "gioi_tinh": _GIOI_TINH.get(nb.gioi_tinh or "", 1),
        "ma_so_the_bao_hiem_y_te": "",
        "thong_tin_nguoi_giam_ho": nb.nguoi_giam_ho or "",
        "dia_chi": nb.dia_chi or "",
        "chan_doan": [
            {
                "ma_chan_doan": ";".join(goi.ma_icd),
                "ten_chan_doan": goi.chan_doan or "",
                "ket_luan": goi.chan_doan or "",
            }
        ],
        "luu_y": "",
        # 2 = ngoại trú — phòng khám không có nội trú [808; HDSD FAQ 1.30].
        "hinh_thuc_dieu_tri": 2,
        "dot_dung_thuoc": [],
        "thong_tin_don_thuoc": [
            {
                "ma_thuoc": t.ma_thuoc or "",
                "biet_duoc": t.hoat_chat or t.ten_thuoc,
                "ten_thuoc": t.ten_thuoc,
                "don_vi_tinh": t.don_vi or "",
                "so_luong": t.so_luong_so,
                "cach_dung": "; ".join(x for x in (t.cach_dung, t.luu_y) if x),
            }
            for t in goi.thuoc
        ],
        "loi_dan": goi.loi_dan or "",
        "so_dien_thoai_nguoi_kham_benh": nb.dien_thoai or "",
        # Số NGÀY tới lần tái khám [808] — chưa nối lịch hẹn tái khám.
        "ngay_tai_kham": None,
        "ngay_gio_ke_don": datetime.fromisoformat(goi.ngay_ke).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "signature": chu_ky.gia_tri if chu_ky else "",
    }


def _loi_422(r: httpx.Response) -> str:
    try:
        d = r.json()
    except ValueError:
        return r.text[:300]
    return str(d.get("danh_sach_cac_loi", d) if isinstance(d, dict) else d)[:300]


@dataclass
class ProviderThat:
    url: str
    ma_lien_thong_co_so: str
    #: mã liên thông bác sĩ → mật khẩu.
    #: repr=False: một dòng log `%r` không được in mật khẩu / token.
    mat_khau_bac_si: dict[str, str] = field(repr=False)
    ten: str = "THAT"
    client: httpx.AsyncClient | None = None
    _token: dict[str, tuple[str, float]] = field(default_factory=dict, repr=False)

    def thieu(self, goi: GoiDon) -> list[str]:
        """Trường QĐ 808 bắt buộc ngoài mức tối thiểu TT 26."""
        ra: list[str] = []
        bs = goi.bac_si
        if bs is not None and not (
            bs.ma_lien_thong and bs.ma_lien_thong in self.mat_khau_bac_si
        ):
            ra.append("mã liên thông + mật khẩu của bác sĩ (DTQG_BAC_SI)")
        if not goi.nguoi_benh.ngay_sinh:
            ra.append("ngày sinh đầy đủ của người bệnh (API đòi ngày/tháng/năm)")
        if not (goi.nguoi_benh.dia_chi or "").strip():
            ra.append("địa chỉ người bệnh")
        for i, t in enumerate(goi.thuoc, start=1):
            if not t.ma_thuoc:
                ra.append(f"mã thuốc dòng {i}")
            if t.so_luong_so is None:
                ra.append(f"số lượng dạng số dòng {i}")
            if not t.don_vi:
                ra.append(f"đơn vị tính dòng {i}")
        return ra

    def _http(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(base_url=self.url, timeout=20.0)
        return self.client

    async def _dang_nhap(self, ma_bs: str) -> str:
        con = self._token.get(ma_bs)
        if con and con[1] > time.monotonic():
            return con[0]
        r = await self._http().post(
            DANG_NHAP_BAC_SI,
            json={
                "ma_lien_thong_bac_si": ma_bs,
                "ma_lien_thong_co_so_kham_chua_benh": self.ma_lien_thong_co_so,
                "password": self.mat_khau_bac_si[ma_bs],
            },
        )
        if r.status_code == 422:
            raise GuiDonError(f"DANG_NHAP_BS_BI_TU_CHOI: {_loi_422(r)}", thu_lai=False)
        if r.status_code != 200:
            raise GuiDonError(f"DANG_NHAP_BS_HTTP_{r.status_code}")
        tok = str(r.json().get("token") or "")
        if not tok:
            raise GuiDonError("DANG_NHAP_BS: không có token trong trả lời")
        self._token[ma_bs] = (tok, time.monotonic() + TOKEN_SONG_GIAY)
        return tok

    async def gui(self, goi: GoiDon, chu_ky: ChuKy | None) -> KetQuaGui:
        if goi.bac_si is None or not goi.bac_si.ma_lien_thong:
            raise GuiDonError("THIEU_DU_LIEU: bác sĩ / mã liên thông", thu_lai=False)
        ma_bs = goi.bac_si.ma_lien_thong
        than = goi_api(goi, chu_ky)
        for lan in (1, 2):
            tok = await self._dang_nhap(ma_bs)
            r = await self._http().post(
                GUI_DON, json=than, headers={"Authorization": f"bearer {tok}"}
            )
            if r.status_code == 401 and lan == 1:
                self._token.pop(ma_bs, None)  # token hết hạn sớm: đăng nhập lại
                continue
            break
        if r.status_code == 200:
            return KetQuaGui(ma_tra_ve=str(r.json().get("success", "OK"))[:200])
        if r.status_code == 422:
            loi = _loi_422(r)
            if da_ton_tai(loi):
                # Không chép câu 422 (có thể lặp dữ liệu khách; cột không che).
                return KetQuaGui(ma_tra_ve="DA_CO_TREN_HE_THONG")
            raise GuiDonError(f"BI_TU_CHOI_422: {loi}", thu_lai=False)
        raise GuiDonError(f"GUI_DON_HTTP_{r.status_code}")

    async def them_bac_si(self, ma_bs: str, mat_khau_co_so: str) -> str:
        """Thêm bác sĩ (đã được Sở duyệt mã liên thông) vào cơ sở — làm MỘT lần
        cho mỗi bác sĩ, trước khi bác sĩ đăng nhập gửi đơn được [808 III, IV]."""
        r = await self._http().post(
            DANG_NHAP_CO_SO,
            json={
                "ma_lien_thong_co_so_kham_chua_benh": self.ma_lien_thong_co_so,
                "password": mat_khau_co_so,
            },
        )
        if r.status_code != 200:
            raise GuiDonError(f"DANG_NHAP_CO_SO_HTTP_{r.status_code}: {_loi_422(r)}")
        tok = str(r.json().get("token") or "")
        r = await self._http().post(
            THEM_BAC_SI,
            json={"ma_lien_thong_bac_si": ma_bs},
            headers={"Authorization": f"bearer {tok}"},
        )
        if r.status_code != 200:
            raise GuiDonError(f"THEM_BAC_SI_HTTP_{r.status_code}: {_loi_422(r)}")
        return str(r.json().get("success", "OK"))


__all__ = ["ProviderThat", "da_ton_tai", "goi_api"]
