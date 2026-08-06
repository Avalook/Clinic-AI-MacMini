"""Unit tests for the authoritative queue call-order (Phase 4, cluster #5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from clinicai.services.queue_order import (
    REASON_CHO_DOC_KQ,
    REASON_DAT_TRUOC_DUNG_GIO,
    REASON_DEN_TRE,
    REASON_DEN_TRUC_TIEP,
    REASON_UU_TIEN,
    QueueEntry,
    b3_ready_appt_ids,
    call_rank,
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
    )


# --------------------------- queue_rank --------------------------- #
def test_queue_rank_ut_numeric_other() -> None:
    assert queue_rank("ƯT1", "s")[:2] == (0, 1)
    assert queue_rank("ƯT", "s")[:2] == (0, 0)
    assert queue_rank("12", "s")[:2] == (1, 12)
    assert queue_rank("abc", "s")[:2] == (2, 0)
    assert queue_rank(None, "s")[:2] == (2, 0)


# --------------------------- call_rank tiers --------------------------- #
def test_ut_is_top_priority_tier_minus2() -> None:
    e = _e("a", qn="ƯT2", channel="HOTLINE", checked_in=SLOT)
    assert call_rank(e)[0] == -2
    assert call_rank(e)[1] == 2


def test_b3_ready_tier_minus1() -> None:
    e = _e("a", channel="HOTLINE", checked_in=SLOT, b3=True)
    assert call_rank(e)[0] == -1


def test_booked_on_time_tier0_by_appt() -> None:
    e = _e("a", channel="ZALO", checked_in=SLOT + timedelta(minutes=8))
    r = call_rank(e)
    assert r[0] == 0
    assert r[1] == SLOT.timestamp() * 1000  # ordered by APPOINTMENT time


def test_booked_late_falls_to_tier1_by_arrival() -> None:
    arrive = SLOT + timedelta(minutes=20)  # đã ra ngoài khung 15'
    e = _e("a", channel="ZALO", checked_in=arrive)
    r = call_rank(e)
    assert r[0] == 1
    assert r[1] == arrive.timestamp() * 1000


def test_cua_so_dung_gio_dai_bang_khung_khong_phai_hang_so() -> None:
    """Cùng một người đến muộn 12 phút — khung dài bao nhiêu quyết định làn.

    Đây là lỗi đã sửa: cửa sổ từng là hằng số 10 phút, nên người check-in ở phút
    thứ 12 — VẪN ĐANG TRONG KHUNG 18:00–18:15 CỦA MÌNH — bị đẩy xuống làn vãng
    lai. Bài này khẳng định cửa sổ đi theo khung, không khẳng định con số nào.
    """
    den_muon_12 = SLOT + timedelta(minutes=12)

    trong_khung_15 = _e("a", channel="ZALO", checked_in=den_muon_12, grace_ms=KHUNG_15)
    assert call_rank(trong_khung_15)[0] == 0, "trong khung của mình thì vẫn đúng hẹn"

    ngoai_khung_10 = _e(
        "a", channel="ZALO", checked_in=den_muon_12, grace_ms=10 * 60_000
    )
    assert call_rank(ngoai_khung_10)[0] == 1, "khung ngắn hơn thì cùng người đó là muộn"


def test_hai_bac_si_hai_do_dai_khung_xep_doc_lap() -> None:
    """`doctor_booking_override` cho phép hai bác sĩ có khung dài khác nhau
    trong cùng một buổi — nên cửa sổ phải nằm trên TỪNG DÒNG, không phải một
    tham số chung cho cả bảng."""
    den_muon_20 = SLOT + timedelta(minutes=20)
    bs_khung_15 = _e("a", channel="ZALO", checked_in=den_muon_20, grace_ms=KHUNG_15)
    bs_khung_30 = _e("b", channel="ZALO", checked_in=den_muon_20, grace_ms=30 * 60_000)
    assert call_rank(bs_khung_15)[0] == 1
    assert call_rank(bs_khung_30)[0] == 0


def test_walkin_tier1_by_arrival() -> None:
    arrive = SLOT + timedelta(minutes=5)
    e = _e("a", channel="WALK_IN", checked_in=arrive)
    r = call_rank(e)
    assert r[0] == 1
    assert r[1] == arrive.timestamp() * 1000


def test_pre_checkin_falls_back_to_ticket_order() -> None:
    e = _e("a", qn="7", channel=None, checked_in=None)
    assert call_rank(e)[:2] == (1, 7)


# --------------------------- full ordering --------------------------- #
def test_order_queue_priority_sequence() -> None:
    ut = _e("ut", qn="ƯT1", channel="HOTLINE", checked_in=SLOT)
    b3 = _e("b3", channel="ZALO", checked_in=SLOT, b3=True)
    booked = _e("bk", channel="ZALO", checked_in=SLOT + timedelta(minutes=5))
    walkin = _e("wk", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=2))
    late = _e("lt", channel="ZALO", checked_in=SLOT + timedelta(minutes=30))
    order = [e.appointment_id for e in order_queue([late, walkin, booked, b3, ut])]
    # ƯT(-2) < b3(-1) < booked(0) < walk-in/late(1, by arrival: walkin 9:02 < late 9:30)
    assert order == ["ut", "b3", "bk", "wk", "lt"]


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
def test_duoc_day_len_nghia_la_co_nguoi_den_truoc_bi_xep_sau() -> None:
    """Đây là câu mà màn tivi phải giải thích được.

    Khách vãng lai đến 9:00, người có hẹn 9:05 đến đúng 9:05. Người có hẹn được
    gọi trước dù đến sau — và đó chính là lúc người vãng lai thấy khó hiểu, nên
    phải có chú thích.
    """
    vang_lai = _e("wk", channel="WALK_IN", checked_in=SLOT)
    co_hen = _e(
        "bk",
        channel="ZALO",
        slot=SLOT + timedelta(minutes=5),
        checked_in=SLOT + timedelta(minutes=5),
    )

    theo_id = {d.entry.appointment_id: d for d in explain_queue([vang_lai, co_hen])}

    assert theo_id["bk"].call_order < theo_id["wk"].call_order
    assert theo_id["bk"].promoted is True
    assert theo_id["bk"].promoted_over == 1
    assert theo_id["bk"].call_reason == REASON_DAT_TRUOC_DUNG_GIO
    assert theo_id["wk"].promoted is False


def test_dung_thu_tu_den_thi_khong_ai_duoc_day_len() -> None:
    ds = [
        _e("a", channel="WALK_IN", checked_in=SLOT),
        _e("b", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=3)),
        _e("c", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=7)),
    ]
    assert [d.entry.appointment_id for d in explain_queue(ds)] == ["a", "b", "c"]
    assert all(d.promoted is False for d in explain_queue(ds))


def test_uu_tien_va_cho_doc_kq_khong_bao_gio_mang_ly_do_dat_truoc() -> None:
    """Người quen của bác sĩ cũng vượt lên, nhưng KHÔNG phải vì đã đặt lịch.

    Dán nhầm câu "được đẩy lên vì đã đặt lịch trước" lên một vé ƯT là nói dối
    với cả phòng chờ.
    """
    ut = _e("ut", qn="ƯT1", channel="HOTLINE", checked_in=SLOT + timedelta(minutes=40))
    b3 = _e("b3", channel="ZALO", checked_in=SLOT + timedelta(minutes=40), b3=True)
    som = _e("s", channel="WALK_IN", checked_in=SLOT)

    theo_id = {d.entry.appointment_id: d for d in explain_queue([ut, b3, som])}
    assert theo_id["ut"].call_reason == REASON_UU_TIEN
    assert theo_id["b3"].call_reason == REASON_CHO_DOC_KQ
    assert theo_id["ut"].promoted is True  # vẫn vượt lên…
    assert theo_id["ut"].call_reason != REASON_DAT_TRUOC_DUNG_GIO  # …vì lý do khác


def test_den_tre_va_den_truc_tiep_la_hai_ly_do_khac_nhau() -> None:
    """Cùng làn 1, nhưng một người lỡ hẹn còn một người không có hẹn. Gộp lại
    thành một câu là làm mất thông tin mà Lễ tân cần khi giải thích."""
    tre = _e("t", channel="ZALO", checked_in=SLOT + timedelta(minutes=40))
    vang_lai = _e("v", channel="WALK_IN", checked_in=SLOT + timedelta(minutes=41))
    theo_id = {d.entry.appointment_id: d for d in explain_queue([tre, vang_lai])}
    assert theo_id["t"].call_tier == theo_id["v"].call_tier == 1
    assert theo_id["t"].call_reason == REASON_DEN_TRE
    assert theo_id["v"].call_reason == REASON_DEN_TRUC_TIEP


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
