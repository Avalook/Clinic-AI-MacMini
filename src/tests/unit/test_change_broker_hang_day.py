"""Hàng đợi một màn hình đầy → thay bằng MỘT tin "không rõ", không bỏ im (16/11/2026).

Trước đây đầy thì bỏ tin mới — vô hại vì tin nào cũng chỉ nói "bảng X đổi". Từ khi
tin mang id lượt (`v`), bỏ một tin = phiếu của đúng lượt đó lỡ cập nhật và người
dùng nhìn số cũ. Tin `t: null` bảo màn hỏi lại tất cả — đúng hành vi an toàn của
tin cũ — và che luôn ca UPDATE hàng loạt (300 lượt → 300 tin trong một giao dịch).
"""

import json

from clinicai.core.change_broker import QUEUE_SIZE, ChangeBroker

C = "a0000000-0000-4000-8000-000000000001"


def _tin(i: int, c: str = C) -> str:
    return json.dumps({"t": "service_order", "c": c, "v": f"luot-{i}"})


def test_hang_day_thi_con_dung_mot_tin_khong_ro() -> None:
    broker = ChangeBroker("postgresql://unused")
    q = broker.subscribe(C)
    for i in range(QUEUE_SIZE + 1):
        broker._on_notify(None, 0, "", _tin(i))
    assert q.qsize() == 1
    assert json.loads(q.get_nowait()) == {"t": None, "c": C}


def test_sau_tin_khong_ro_hang_nhan_tiep_binh_thuong() -> None:
    broker = ChangeBroker("postgresql://unused")
    q = broker.subscribe(C)
    for i in range(QUEUE_SIZE + 2):
        broker._on_notify(None, 0, "", _tin(i))
    assert q.qsize() == 2
    assert json.loads(q.get_nowait())["t"] is None
    assert json.loads(q.get_nowait()) == json.loads(_tin(QUEUE_SIZE + 1))


def test_chua_day_thi_giu_nguyen_tung_tin() -> None:
    broker = ChangeBroker("postgresql://unused")
    q = broker.subscribe(C)
    for i in range(QUEUE_SIZE):
        broker._on_notify(None, 0, "", _tin(i))
    assert [json.loads(q.get_nowait())["v"] for _ in range(QUEUE_SIZE)] == [
        f"luot-{i}" for i in range(QUEUE_SIZE)
    ]


def test_mot_man_day_khong_lam_hong_man_khac() -> None:
    broker = ChangeBroker("postgresql://unused")
    cham = broker.subscribe(C)
    nhanh = broker.subscribe(C)
    for i in range(QUEUE_SIZE + 1):
        broker._on_notify(None, 0, "", _tin(i))
        if not nhanh.empty():
            nhanh.get_nowait()
    assert cham.qsize() == 1
    assert nhanh.empty()
