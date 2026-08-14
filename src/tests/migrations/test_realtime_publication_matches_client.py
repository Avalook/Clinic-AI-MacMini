"""The realtime table list exists twice. This makes the two agree.

WHAT WENT WRONG WITHOUT IT. ``RealtimeRefresher.tsx`` subscribed to twenty
tables. The ``supabase_realtime`` publication contained two. Subscribing to a
table that is not published raises no error, logs nothing, and returns a
perfectly healthy channel — it simply never delivers an event. So for months the
app showed a pulsing green "Realtime" pill, counted "+N cập nhật" that was always
zero, and actually synchronised through a 25-second ``setInterval``. Nobody could
see it because *nothing was broken*: data did arrive, just late, and the only
symptom was a clinic that felt slow.

Two lists in two languages that must match, with silence as the failure mode, is
exactly what a test is for.

DIRECTION OF THE CHECK. Subscribing to an unpublished table is the dangerous
half — it fakes liveness. Publishing a table nobody subscribes to only wastes
WAL and RLS evaluation, so it is a warning-shaped problem, not a lie; the test
reports it but the hard assertion is on the first.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_CLIENT = _REPO / "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx"
_MIGRATIONS = _REPO / "supabase/migrations"


def _published_tables() -> set[str]:
    """Every table any migration adds to ``supabase_realtime``.

    Covers both spellings used in this repo: the direct
    ``ALTER PUBLICATION … ADD TABLE public.x`` and the guarded loop in
    20260803000004 that lists tables in a plpgsql array.
    """
    published: set[str] = set()
    # The trailing `;` matters: 20260803000004 also contains the statement as a
    # plpgsql *format string* (`... ADD TABLE public.%I`), and without anchoring
    # on the semicolon the optional `public\.` group backtracks and captures the
    # literal word "public" as a table name.
    direct = re.compile(
        r"ALTER\s+PUBLICATION\s+supabase_realtime\s+ADD\s+TABLE\s+"
        r"(?:ONLY\s+)?(?:public\.)?\"?(\w+)\"?\s*;",
        re.IGNORECASE,
    )
    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8")
        published.update(m.group(1) for m in direct.finditer(text))

        # The loop form: live_tables text[] := ARRAY[ 'a', 'b', … ];
        for block in re.finditer(
            r"live_tables\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]", text, re.DOTALL
        ):
            published.update(re.findall(r"'(\w+)'", block.group(1)))

        # …and the removals. 20260803000008 unpublishes nine tables that reached
        # the publication by hand (dashboard clicks, or a maintenance script that
        # lives outside supabase/migrations/ so nobody can tell whether it ran).
        # Without reading the DROPs, this file would keep asserting against a
        # picture of the publication that migrations alone never described.
        for block in re.finditer(
            r"unwatched\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]", text, re.DOTALL
        ):
            published.difference_update(re.findall(r"'(\w+)'", block.group(1)))
    return published


def _subscribed_tables() -> set[str]:
    """The LIVE_TABLES array the browser actually subscribes to."""
    text = _CLIENT.read_text(encoding="utf-8")
    match = re.search(r"const LIVE_TABLES = \[(.*?)\] as const;", text, re.DOTALL)
    assert match, "LIVE_TABLES not found in RealtimeRefresher.tsx"
    # Drop // comments before pulling the quoted names out.
    body = re.sub(r"//[^\n]*", "", match.group(1))
    return set(re.findall(r'"(\w+)"', body))


@pytest.mark.skipif(not _CLIENT.exists(), reason="dashboard sources not present")
def test_every_subscribed_table_is_published() -> None:
    """A subscription to an unpublished table is silent, permanent nothing."""
    missing = _subscribed_tables() - _published_tables()
    assert not missing, (
        "RealtimeRefresher subscribes to tables that no migration publishes: "
        f"{sorted(missing)}. Those subscriptions will never fire and the UI "
        "will fall back to polling while still showing a live indicator. Add "
        "them to the publication, or remove them from LIVE_TABLES."
    )


@pytest.mark.skipif(not _CLIENT.exists(), reason="dashboard sources not present")
def test_publication_has_no_unwatched_tables() -> None:
    """Publishing what nobody watches costs WAL and an RLS check per subscriber."""
    unwatched = _published_tables() - _subscribed_tables()
    assert not unwatched, (
        f"Published but not subscribed: {sorted(unwatched)}. Every published "
        "table makes Realtime re-run RLS for each subscriber on each change. "
        "Either subscribe to it or drop it from the publication."
    )


def _tables_with_notify_trigger() -> set[str]:
    """Bảng có trigger `trg_notify_*` do một migration nào đó tạo ra.

    Đọc mọi mảng `bang text[] := ARRAY[…]` trong các migration có gọi
    `notify_row_change` — đúng khuôn mà 20260806000001 và 20260814000001 dùng.
    """
    ra: set[str] = set()
    for path in sorted(_MIGRATIONS.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        if "notify_row_change" not in text:
            continue
        for block in re.finditer(
            r"bang\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]", text, re.DOTALL
        ):
            ra.update(re.findall(r"'(\w+)'", block.group(1)))
    return ra


@pytest.mark.skipif(not _CLIENT.exists(), reason="dashboard sources not present")
def test_moi_bang_duoc_nghe_deu_co_trigger_bao_tin() -> None:
    """Nghe một bảng KHÔNG phát tin là im lặng vĩnh viễn.

    BÀI KIỂM NÀY RA ĐỜI VÌ BÀI KIỂM NGAY TRÊN CANH NHẦM CƠ CHẾ.

    `test_every_subscribed_table_is_published` đối chiếu LIVE_TABLES với
    PUBLICATION — cơ chế của Supabase Realtime. Nhưng 06/08/2026 hệ thống đã bỏ
    Realtime, chuyển sang LISTEN/NOTIFY (quyền REPLICATION không xin được ở
    database cho thuê). Từ hôm ấy, thứ quyết định một bảng có phát tin hay không
    là TRIGGER `trg_notify_*`, không phải publication.

    Ba ngày sau, 20260809000009 thêm bốn bảng của màn chăm sóc vào publication —
    đúng khuôn cũ, và bài kiểm trên xanh. Nhưng không bảng nào được gắn trigger,
    nên chúng chưa từng phát một tin nào. Đo trên prod 14/08: 11 bảng có
    trigger, bốn bảng ấy không có bảng nào — trong khi RealtimeRefresher vẫn
    nghe đủ cả bốn suốt năm ngày.

    Hệ quả đúng bằng câu mà chính migration ấy viết ra để cảnh báo: hai CSKH
    ngồi cạnh nhau không thấy việc của nhau, và khách nghe máy hai lần.

    Bài kiểm cũ được GIỮ LẠI, không xoá: publication vẫn phải khớp, phòng khi
    ai đó quay lại Realtime. Nhưng từ nay bài kiểm này mới là bài canh thứ đang
    thật sự chạy.
    """
    missing = _subscribed_tables() - _tables_with_notify_trigger()
    assert not missing, (
        f"RealtimeRefresher nghe {sorted(missing)} nhưng không migration nào gắn "
        "trigger `trg_notify_*` cho chúng. Đăng ký nghe một bảng không phát tin "
        "thì im lặng — không lỗi, không cảnh báo, chỉ là màn hình chỉ tự mới sau "
        "nhịp dự phòng 60 giây."
    )
