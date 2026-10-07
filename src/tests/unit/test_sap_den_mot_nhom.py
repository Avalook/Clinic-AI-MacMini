"""Sắp đến: mỗi khách đúng một nhóm + nhãn lượt Điều trị chờ thanh toán.

Staging 07/10 (Khách 0116, lượt đặt Laser): Laser đã xong ở Phòng thủ thuật,
hàng bác sĩ (tuỳ chọn) còn "waiting", chưa check-out → khách hiện CẢ ở "Đã xong"
LẪN ở "Sắp đến · +1 khách khác" với nhãn "đang chờ khám" — trông như hai người.
"""

from typing import Any

from clinicai.services import nhan_tai_phong as ntp

PHONG = "phong-thu-thuat"
KHAC = "phong-sieu-am"


def _khach(vid: str, **them: Any) -> dict[str, Any]:
    k: dict[str, Any] = {
        "visit_id": vid,
        "full_name": f"Khách {vid}",
        "patient_code": vid,
        "so_tiep_don": None,
        "so_booking": None,
        "q_lane": None,
        "q_status": None,
        "q_room_id": None,
        "q_phong": None,
        "nhom_kham": "KHAM",
        "da_qua_ban_kham": False,
        "con_viec": 0,
    }
    k.update(them)
    return k


def _dong(vid: str, trang_thai: str, *, o_room_id: str | None, nhan: bool = False):
    r = {"visit_id": vid, "room_id": PHONG, "o_room_id": o_room_id, "accepting": True}
    c = {
        "trang_thai": trang_thai,
        "nhan_duoc": nhan,
        "chuyen": False,
        "huong_dan_day": False,
    }
    return r, c


def test_khach_da_xong_o_phong_khong_con_o_sap_den() -> None:
    k = _khach(
        "v1", q_lane="DOCTOR", q_status="waiting", nhom_kham="DIEU_TRI", con_viec=0
    )
    dong = [_dong("v1", ntp.XONG, o_room_id=PHONG)]
    assert ntp.gom_sap_den([k], dong, PHONG) == []


def test_xong_mot_con_mot_nhan_duoc_thi_van_o_sap_den() -> None:
    k = _khach("v1", con_viec=1)
    dong = [
        _dong("v1", ntp.XONG, o_room_id=PHONG),
        _dong("v1", ntp.SAP_DEN, o_room_id=None, nhan=True),
    ]
    out = ntp.gom_sap_den([k], dong, PHONG)
    assert [o["visit_id"] for o in out] == ["v1"]
    assert out[0]["so_nhan_duoc"] == 1


def test_xong_o_phong_khac_thi_van_hien_o_day() -> None:
    """Khách xong ở phòng khác, chưa có gì ở đây → vẫn là "khách khác hôm nay"."""
    k = _khach("v1", q_lane="ROOM", q_status="waiting", q_room_id=KHAC, q_phong="SA")
    dong = [_dong("v1", ntp.XONG, o_room_id=KHAC)]
    out = ntp.gom_sap_den([k], dong, PHONG)
    assert [o["visit_id"] for o in out] == ["v1"]


def test_luot_dieu_tri_xong_het_ghi_cho_thanh_toan() -> None:
    k = _khach(
        "v1", q_lane="DOCTOR", q_status="waiting", nhom_kham="DIEU_TRI", con_viec=0
    )
    out = ntp.gom_sap_den([k], [], KHAC)
    assert out[0]["dang_o"] == ntp.CAU_CHO_THANH_TOAN


def test_luot_dieu_tri_da_qua_ban_kham_giu_nhan_cu() -> None:
    k = _khach(
        "v1",
        q_lane="DOCTOR",
        q_status="waiting",
        nhom_kham="DIEU_TRI",
        da_qua_ban_kham=True,
        con_viec=0,
    )
    out = ntp.gom_sap_den([k], [], KHAC)
    assert out[0]["dang_o"] == "đang chờ khám"


def test_luot_dieu_tri_con_viec_giu_nhan_cu() -> None:
    k = _khach(
        "v1", q_lane="DOCTOR", q_status="waiting", nhom_kham="DIEU_TRI", con_viec=1
    )
    assert ntp.gom_sap_den([k], [], KHAC)[0]["dang_o"] == "đang chờ khám"


def test_luot_kham_thuong_giu_nhan_cu() -> None:
    k = _khach("v1", q_lane="DOCTOR", q_status="waiting", con_viec=0)
    assert ntp.gom_sap_den([k], [], KHAC)[0]["dang_o"] == "đang chờ khám"


def test_cau_dang_o_cho_thanh_toan_khong_de_khi_dang_kham() -> None:
    assert ntp.cau_dang_o("DOCTOR", "serving", None, cho_tt=True) == (
        "đang khám ở bàn khám"
    )
    assert ntp.cau_dang_o(None, None, None, cho_tt=True) == ntp.CAU_CHO_THANH_TOAN
    assert ntp.cau_dang_o("ROOM", "waiting", "SA", cho_tt=True) == "đang chờ ở SA"
