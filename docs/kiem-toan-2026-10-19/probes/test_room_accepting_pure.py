"""Pure-helper probe for the accepting=false room worklist mismatch.

Run with PYTHONPATH pointing at the pinned-main snapshot's src directory.
This probe does not open a database or use patient data.
"""

from clinicai.services.nhan_tai_phong import dem_sap_den, trang_thai_chi_dinh


def test_non_accepting_room_still_marks_pending_order_receivable() -> None:
    room_row = {
        "id": "synthetic-order",
        "visit_id": "synthetic-visit",
        "service_name": "Synthetic service",
        "room_id": "synthetic-room",
        "accepting": False,
        "execution_status": "PENDING",
        "chua_vao": True,
        "q_id": None,
        "q_status": None,
        "q_room_id": None,
        "o_room_id": None,
        "o_phong": None,
        "huong_dan_id": None,
        "huong_dan": None,
        "chuyen": False,
        "selection_status": "SELECTED",
    }

    card = trang_thai_chi_dinh(
        room_row,
        "synthetic-room",
        tien_chan=False,
    )

    assert card is not None
    assert card["nhan_duoc"] is True
    assert dem_sap_den([(room_row, card)], "synthetic-room") == 0
