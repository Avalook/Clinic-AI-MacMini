from clinicai.services.bao_cao_pham_vi import ca_duoc_xem, cho_phep_ca


def test_staff_only_approved_assigned_shift():
    ca = ca_duoc_xem(
        [
            {"status": "APPROVED", "shift": "SANG"},
            {"status": "PENDING", "shift": "TOI"},
        ],
        truong_ca_ca_ngay=True,
    )
    assert cho_phep_ca("SANG", ca)
    assert not cho_phep_ca("TOI", ca)
    assert not cho_phep_ca(None, ca)
    assert not cho_phep_ca("garbage", ca)


def test_full_and_head_assignment():
    for row in [
        {"status": "APPROVED", "shift": "FULL"},
        {"status": "APPROVED", "shift": "SANG", "la_truong_ca": True},
    ]:
        ca = ca_duoc_xem([row], truong_ca_ca_ngay=True)
        assert cho_phep_ca(None, ca)
        assert cho_phep_ca("TOI", ca)
    assert not ca_duoc_xem([], truong_ca_ca_ngay=True)


def test_pending_head_never_grants_full_day():
    assert not ca_duoc_xem(
        [{"status": "PENDING", "shift": "FULL", "la_truong_ca": True}],
        truong_ca_ca_ngay=True,
    )
