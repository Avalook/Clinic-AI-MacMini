"""Unit tests for the authoritative queue call-order (Phase 4, cluster #5).

ĐỔI 15/09/2026 (Luật 12.5 — quyết định đảo thì viết lại bài kiểm kèm lý do):
CONTEXT v1.0 bỏ hai làn tự vượt của Model ②. Vé ƯT chỉ còn là nhãn; người quay
lại đọc kết quả chèn SAU mọi người đã chờ lúc kết quả về, TRƯỚC người vào hàng
sau. Có hẹn hay đến thẳng không còn phân biệt (Tuyền chốt 15/09): mọi người đã
check-in xếp theo giờ check-in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from clinicai.services.queue_order import (
    REASON_CHO_DOC_KQ,
    REASON_DAT_TRUOC_DUNG_GIO,
    REASON_DEN_TRE,
    REASON_DEN_TRUC_TIEP,
    QueueEntry,
    b3_ready_appt_ids,
    b3_ready_times,
    call_rank,
    call_reason,
    explain_queue,
    order_queue,
    queue_rank,
)

UTC = timezone.utc
SLOT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


KHUNG_15 = 15 * 60_000  # khung 15 phút — cấu hình thật của Dr4Women hôm nay


def _e(
    appt: str,
    *,
    qn: str | None = None,
    checked_in: datetime | None = None,
    channel: str | None = None,
    b3: bool = False,
    b3_at: datetime | None = None,
    slot: datetime = SLOT,
    grace_ms: int = KHUNG_15,
) -> QueueEntry:
    return QueueEntry(
        appointment_id=appt,
        doctor_id="d1",
        queue_number=qn,
        slot_start=slot,
        checked_in_at=checked_in,
        booking_channel=channel,
        grace_ms=grace_ms,
        b3_ready=b3,
        b3_ready_at=b3_at,
    )


# --------------------------- queue_rank --------------------------- #
def test_queue_rank_ut_numeric_other() -> None:
    # Vé "ƯT" không còn hạng riêng (Tuyền chốt 15/09/2026: bỏ vé ưu tiên).
    assert queue_rank("ƯT1", "s")[:2] == (2, 0)
    assert queue_rank("12", "s")[:2] == (1, 12)
    assert queue_rank("abc", "s")[:2] == (2, 0)
    assert queue_rank(None, "s")[:2] == (2, 0)


# --------------------------- call_rank tiers --------------------------- #
def test_khach_uu_tien_chi_la_nhan_khong_tu_vuot() -> None:
    """Tuyền chốt 15/09/2026: ưu tiên/VIP là cờ trên HỒ SƠ khách để lễ tân biết,
    không tự vượt hàng. Thay vé "ƯT…" (nhãn suy từ số vé)."""
    from dataclasses import replace

    vip = replace(
        _e("vip", qn="ƯT2", channel="HOTLINE", checked_in=SLOT + timedelta(minutes=30)),
        khach_uu_tien=True,
    )
    som = _e("s", channel="WALK_IN", checked_in=SLOT)
    theo_id = {d.entry.appointment_id: d for d in explain_queue([vip, som])}
    assert theo_id["s"].call_order < theo_id["vip"].call_order
    assert theo_id["vip"].uu_tien is True and theo_id["s"].uu_tien is False


def test_le_tan_keo_tay_len_truoc_nguoi_den_truoc() -> None:
    """Lễ tân kéo khách lên trước (theo chỉ đạo trưởng ca): mốc kéo tay thay giờ
    check-in khi xếp (20260915000016). Người check-in sau vẫn đứng cuối."""
    from dataclasses import replace

    a = _e("a", channel="WALK_IN", checked_in=SLOT)
    b = _e("b", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=10))
    c = _e("c", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=20))
    moc_truoc_a = SLOT.timestamp() * 1000 - 1
    c_keo = replace(c, thu_tu_tay_ms=moc_truoc_a)
    thu_tu = [d.entry.appointment_id for d in explain_queue([a, b, c_keo])]
    assert thu_tu == ["c", "a", "b"]
    moi = _e("d", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=30))
    assert [d.entry.appointment_id for d in explain_queue([a, b, c_keo, moi])][
        -1
    ] == "d"


def test_b3_ready_la_nhom_quay_lai() -> None:
    e = _e("a", channel="HOTLINE", checked_in=SLOT, b3=True)
    assert call_rank(e)[0] == -1
    assert call_reason(e) == REASON_CHO_DOC_KQ


def test_pre_checkin_falls_back_to_ticket_order() -> None:
    e = _e("a", qn="7", channel=None, checked_in=None)
    assert call_rank(e)[:2] == (1, 7)


def test_unchecked_legacy_priority_ticket_is_only_a_label() -> None:
    """Missing booking channels must not put unchecked priority tickets first."""
    priority = _e("priority", qn="ƯT9")
    numeric = _e("numeric", qn="2")
    unknown = _e("unknown", qn="abc")
    arrived = _e("arrived", channel="WALK_IN", checked_in=SLOT)
    decisions = explain_queue([priority, unknown, numeric, arrived])

    assert [d.entry.appointment_id for d in decisions] == [
        "arrived",
        "numeric",
        "priority",
        "unknown",
    ]
    assert all(d.call_tier == 1 for d in decisions[1:])
    assert decisions[2].uu_tien is False  # nhãn chỉ từ cờ hồ sơ, không từ số vé
    assert all(d.promoted is False for d in decisions)


def test_da_check_in_xep_theo_gio_check_in_khong_theo_gio_hen() -> None:
    """Tuyền chốt 15/09/2026: không phân biệt có hẹn hay đến thẳng — ai
    check-in trước khám trước. Thay các bài cũ khẳng định "có hẹn đúng giờ xếp
    theo giờ hẹn, đứng trước vãng lai" (Model ②, Luật 12.5)."""
    vang_lai = _e("wk", channel="WALK_IN", checked_in=SLOT)
    co_hen = _e(
        "bk",
        channel="ZALO",
        slot=SLOT - timedelta(minutes=30),
        checked_in=SLOT + timedelta(minutes=1),
    )
    assert call_rank(co_hen)[0] == call_rank(vang_lai)[0] == 0
    assert call_rank(co_hen)[1] == (SLOT + timedelta(minutes=1)).timestamp() * 1000
    theo_id = {d.entry.appointment_id: d for d in explain_queue([co_hen, vang_lai])}
    assert theo_id["wk"].call_order < theo_id["bk"].call_order
    assert theo_id["bk"].promoted is False and theo_id["wk"].promoted is False


def test_chua_check_in_dung_sau_nguoi_da_co_mat() -> None:
    chua_den = _e("x", channel="ZALO", slot=SLOT - timedelta(hours=1))
    da_den = _e("y", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=50))
    assert [e.appointment_id for e in order_queue([chua_den, da_den])] == ["y", "x"]


def test_gio_hen_va_do_dai_khung_chi_con_quyet_ly_do_hien_thi() -> None:
    """Cửa sổ "đúng giờ" vẫn đi theo độ dài khung của từng dòng — nhưng chỉ để
    gọi đúng tên lý do (đúng giờ / đến trễ / vãng lai), không đổi chỗ đứng."""
    den_muon_12 = SLOT + timedelta(minutes=12)
    khung_15 = _e("a", channel="ZALO", checked_in=den_muon_12, grace_ms=KHUNG_15)
    khung_10 = _e("b", channel="ZALO", checked_in=den_muon_12, grace_ms=10 * 60_000)
    vang_lai = _e("c", channel="WALK_IN", checked_in=den_muon_12)
    assert call_reason(khung_15) == REASON_DAT_TRUOC_DUNG_GIO
    assert call_reason(khung_10) == REASON_DEN_TRE
    assert call_reason(vang_lai) == REASON_DEN_TRUC_TIEP
    assert call_rank(khung_15)[:2] == call_rank(khung_10)[:2] == call_rank(vang_lai)[:2]


# --------------------------- full ordering --------------------------- #
def test_order_queue_priority_sequence() -> None:
    # ƯT đến 9:40 → theo giờ check-in, không lên đầu.
    ut = _e("ut", qn="ƯT1", channel="HOTLINE", checked_in=SLOT + timedelta(minutes=40))
    # Kết quả về 9:10 → chèn sau những ai đã chờ trước 9:10 (bk 9:05, wk 9:02).
    b3 = _e(
        "b3",
        channel="ZALO",
        checked_in=SLOT,
        b3=True,
        b3_at=SLOT + timedelta(minutes=10),
    )
    booked = _e("bk", channel="ZALO", checked_in=SLOT + timedelta(minutes=5))
    walkin = _e("wk", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=2))
    late = _e("lt", channel="ZALO", checked_in=SLOT + timedelta(minutes=30))
    order = [e.appointment_id for e in order_queue([late, walkin, booked, b3, ut])]
    # Ai check-in trước khám trước: wk 9:02 < bk 9:05 < (b3 về 9:10) < lt < ut.
    assert order == ["wk", "bk", "b3", "lt", "ut"]


# --------------------------- b3_ready_appt_ids --------------------------- #
def test_b3_ready_requires_all_resulted() -> None:
    labs: list[dict[str, object]] = [
        {"appointment_id": "a", "result_value": "5.2", "external_ref": None},
        {"appointment_id": "a", "result_value": None, "external_ref": "LIS-9"},
        {"appointment_id": "b", "result_value": "1", "external_ref": None},
        {"appointment_id": "b", "result_value": "  ", "external_ref": None},  # pending
        {"appointment_id": "c", "result_value": None, "external_ref": None},  # pending
    ]
    ready = b3_ready_appt_ids(labs)
    assert ready == {"a"}  # a: all resulted; b: 1 pending; c: none resulted


# --------------------------- explain_queue --------------------------- #
def test_dung_thu_tu_den_thi_khong_ai_duoc_day_len() -> None:
    ds = [
        _e("a", channel="WALK_IN", checked_in=SLOT),
        _e("b", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=3)),
        _e("c", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=7)),
    ]
    assert [d.entry.appointment_id for d in explain_queue(ds)] == ["a", "b", "c"]
    assert all(d.promoted is False for d in explain_queue(ds))


def test_ut_va_quay_lai_khong_con_vuot_nguoi_den_truoc() -> None:
    """Bản cũ khẳng định vé ƯT "vẫn vượt lên". CONTEXT v1.0 đảo điều đó: cả vé
    ƯT lẫn người quay lại đọc kết quả đều KHÔNG vượt người đã chờ trước họ."""
    ut = _e("ut", qn="ƯT1", channel="HOTLINE", checked_in=SLOT + timedelta(minutes=40))
    b3 = _e("b3", channel="ZALO", checked_in=SLOT + timedelta(minutes=40), b3=True)
    som = _e("s", channel="WALK_IN", checked_in=SLOT)

    theo_id = {d.entry.appointment_id: d for d in explain_queue([ut, b3, som])}
    assert theo_id["s"].call_order == 0
    assert theo_id["b3"].call_reason == REASON_CHO_DOC_KQ
    assert theo_id["ut"].promoted is False and theo_id["b3"].promoted is False
    assert theo_id["ut"].call_reason != REASON_DAT_TRUOC_DUNG_GIO


def test_quay_lai_dung_sau_nguoi_da_cho_truoc_nguoi_vao_sau() -> None:
    """[CHỐT-TUYỀN] ví dụ ba người: A khám lần đầu lúc 9:00 rồi đi xét nghiệm;
    B đến 9:20, kết quả của A về 9:30, C đến 9:40. Hàng: B → A → C."""
    a = _e(
        "A",
        channel="WALK_IN",
        checked_in=SLOT,
        b3=True,
        b3_at=SLOT + timedelta(minutes=30),
    )
    b = _e("B", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=20))
    c = _e("C", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=40))
    assert [e.appointment_id for e in order_queue([c, a, b])] == ["B", "A", "C"]


def test_hai_nguoi_quay_lai_ai_du_dieu_kien_truoc_thi_truoc() -> None:
    a = _e(
        "A",
        channel="WALK_IN",
        checked_in=SLOT,
        b3=True,
        b3_at=SLOT + timedelta(minutes=50),
    )
    b = _e(
        "B",
        channel="WALK_IN",
        checked_in=SLOT + timedelta(minutes=5),
        b3=True,
        b3_at=SLOT + timedelta(minutes=20),
    )
    c = _e("C", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=30))
    assert [e.appointment_id for e in order_queue([a, b, c])] == ["B", "C", "A"]


def test_thieu_moc_ket_qua_thi_coi_nhu_cho_tu_luc_den() -> None:
    """Không có mốc thì không đoán — giữ chỗ theo giờ check-in, không đẩy ai
    lên trước người đến trước."""
    a = _e("A", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=10), b3=True)
    b = _e("B", channel="WALK_IN", checked_in=SLOT)
    c = _e("C", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=20))
    assert [e.appointment_id for e in order_queue([a, b, c])] == ["B", "A", "C"]


def test_moc_ket_qua_som_hon_gio_den_khong_day_len() -> None:
    a = _e(
        "A",
        channel="WALK_IN",
        checked_in=SLOT + timedelta(minutes=10),
        b3=True,
        b3_at=SLOT,
    )
    b = _e("B", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=5))
    assert [e.appointment_id for e in order_queue([a, b])] == ["B", "A"]


def test_b3_ready_times_lay_moc_ket_qua_cuoi_cung() -> None:
    t1 = SLOT + timedelta(minutes=10)
    t2 = SLOT + timedelta(minutes=25)
    labs: list[dict[str, object]] = [
        {"appointment_id": "a", "result_value": "1", "result_received_at": t2},
        {"appointment_id": "a", "result_value": "2", "result_received_at": t1},
        {"appointment_id": "b", "result_value": None, "result_received_at": t1},
    ]
    assert b3_ready_times(labs) == {"a": t2}


def test_thu_tu_lien_tuc_khong_trung_khong_hong() -> None:
    ds = [
        _e(str(i), channel="WALK_IN", checked_in=SLOT + timedelta(minutes=i))
        for i in range(6)
    ]
    assert [d.call_order for d in explain_queue(ds)] == list(range(6))


def test_module_van_thuan_khong_cham_database() -> None:
    """Cách hỏng dễ nhất là ai đó thêm một lượt tra chính sách vào call_rank cho
    tiện. Bài canh này chặn đúng việc đó."""
    import inspect

    from clinicai.services import queue_order

    ma_nguon = inspect.getsource(queue_order)
    assert "asyncpg" not in ma_nguon
    assert "async def" not in ma_nguon
    assert "await " not in ma_nguon


def test_lich_khong_ghi_kenh_van_la_khach_da_dat_lich() -> None:
    """Trống ≠ vãng lai.

    Máy chủ thật có 16 lịch hẹn không ghi kênh đặt (ONLINE 21 · TRỐNG 16 ·
    WALK_IN 7 · HOTLINE 4). Luật cũ coi trống là vãng lai, nên gần một phần ba
    số lịch bị tước mất quyền ưu tiên mà người bệnh đã có bằng cách đặt trước —
    im lặng, không dấu hiệu nào trên màn hình.
    """
    den_trong_khung = SLOT + timedelta(minutes=5)
    khong_ghi_kenh = _e("a", channel=None, checked_in=den_trong_khung)
    assert call_rank(khong_ghi_kenh)[0] == 0
    assert call_reason(khong_ghi_kenh) == REASON_DAT_TRUOC_DUNG_GIO


def test_chi_walk_in_moi_la_vang_lai() -> None:
    """Kênh chỉ còn quyết LÝ DO hiển thị; chỗ đứng như nhau (Tuyền 15/09)."""
    den_trong_khung = SLOT + timedelta(minutes=5)
    for kenh in ("ZALO_PK", "HOTLINE", "ONLINE", "FB_DR4WOMEN", "", "  "):
        e = _e("a", channel=kenh, checked_in=den_trong_khung)
        assert call_reason(e) == REASON_DAT_TRUOC_DUNG_GIO, f"kênh {kenh!r}"
        assert call_rank(e)[0] == 0

    for kenh in ("WALK_IN", "walk_in", " Walk_In "):
        e = _e("a", channel=kenh, checked_in=den_trong_khung)
        assert call_reason(e) == REASON_DEN_TRUC_TIEP, f"kênh {kenh!r}"
        assert call_rank(e)[0] == 0
