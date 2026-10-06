"""Bảng màn hình nghe phải là bảng database thật sự phát tin.

DANH SÁCH BẢNG "LIVE" NẰM Ở HAI NƠI, HAI NGÔN NGỮ. Phía trình duyệt:
``LIVE_TABLES`` trong ``RealtimeRefresher.tsx`` (và trong ``truong-ca/shared.tsx``),
cùng mọi lời gọi ``useNgheBang([...])``. Phía Postgres: những bảng có trigger
gọi ``notify_row_change`` → ``pg_notify('clinicai_changes')`` → FastAPI SSE
(``clinicai/core/change_broker.py``) → ``RealtimeRefresher`` phát lại thành
``SU_KIEN_BANG`` trên window.

HAI NƠI LỆCH NHAU THÌ REALTIME CHẾT IM LẶNG. Nghe một bảng không có trigger
không ném lỗi, không ghi log, dòng SSE vẫn khoẻ, chấm xanh "Realtime" vẫn sáng —
chỉ là tin của bảng ấy không bao giờ tới, và màn hình sống bằng nhịp dự phòng
60 giây. Không có gì *hỏng* để ai nhìn thấy: dữ liệu vẫn về, chỉ là về muộn, và
triệu chứng duy nhất là một phòng khám "thấy chậm". Đã cắn thật hai lần:

* Thời Supabase Realtime: ``RealtimeRefresher`` nghe hai mươi bảng, publication
  ``supabase_realtime`` có hai — nhiều tháng đồng bộ bằng ``setInterval`` 25 giây
  dưới một chấm xanh nhấp nháy.
* 09/08/2026: bốn bảng màn chăm sóc được thêm vào publication — đúng khuôn cũ,
  bài kiểm publication xanh — nhưng từ 06/08 hệ thống đã chuyển sang
  LISTEN/NOTIFY, và không bảng nào được gắn trigger. Đo trên prod 14/08: bốn
  bảng ấy chưa phát một tin nào suốt năm ngày; hai CSKH ngồi cạnh nhau không
  thấy việc của nhau, khách nghe máy hai lần.

VÌ SAO TỆP NÀY THAY ``test_realtime_publication_matches_client.py``. Bài cũ so
``LIVE_TABLES`` với publication ``supabase_realtime`` — cơ chế đã BỎ hẳn từ
27/09/2026 (``20260927000002_notify_realtime_con_lai.sql``). Canh một cơ chế
chết thì xanh hay đỏ đều không nói gì về màn hình. Bài này chỉ canh điều kiện
đang thật sự quyết định một bảng có phát tin hay không: trigger.

HAI LỚP KIỂM.

1. Tĩnh (luôn chạy): dựng tập "bảng có trigger notify" bằng cách đọc
   ``supabase/migrations`` THEO THỨ TỰ ÁP, kể cả ``DROP TRIGGER`` / ``DROP
   TABLE`` / ``DROP FUNCTION`` ở migration sau. Bộ đọc hiểu đúng hai khuôn có
   trong repo: ``CREATE TRIGGER`` viết thẳng (tên trigger tuỳ ý — vd
   ``trg_tep_ket_qua_bao_tin_khi_sua``; bảng lấy từ mệnh đề ``ON``), và vòng
   ``DO $$ … FOREACH t IN ARRAY … EXECUTE format('CREATE TRIGGER %I …')``. Gặp
   một khối ``DO`` gắn trigger notify mà không đọc ra được mảng tên bảng thì
   bài ĐỎ — bộ đọc lệch khuôn phải lộ ra, không được trả về tập rỗng rồi xanh.
2. Trên DB (``pytest.mark.db``, cần ``DATABASE_URL_TEST`` đã áp migration): hỏi
   ``pg_trigger`` xem mỗi bảng màn hình nghe có trigger ĐANG BẬT gọi
   ``notify_row_change`` không. Lớp này bắt thứ đọc tĩnh không thấy được: vòng
   20260806000001 tự BỎ QUA bảng chưa tồn tại hoặc thiếu cột ``clinic_id``
   (``RAISE NOTICE … CONTINUE``), nên migration "có viết" chưa chắc database
   "có trigger". Nó cũng đối chiếu ngược bộ đọc tĩnh: mọi trigger bộ đọc tin là
   có phải có thật — bộ đọc nói dối thì bài tĩnh xanh oan.

``useNgheBang`` ĐƯỢC KIỂM TĨNH. Mọi lời gọi trong ``src/dashboard`` hiện có
một trong hai dạng: mảng chữ tại chỗ ``useNgheBang(["a", "b"], …)``, hoặc tên
một hằng khai trong CÙNG tệp ``const TEN = [ … ] as const;``. Bộ đọc đếm số lời
gọi và đòi đọc được TẤT CẢ: một dạng mới (mảng ghép, hằng import từ tệp khác…)
làm bài đỏ với lời nhắn rõ, thay vì bỏ qua lặng lẽ. Ngoài phạm vi: màn tự nghe
``SU_KIEN_BANG`` rồi so tên bảng bằng tay (``ClinicalRecordForm``,
``dung-giu-cho``…) — tên bảng nằm trong biểu thức tuỳ ý, không đọc tĩnh chắc
chắn được.

CHIỀU KIỂM. Nghe bảng không phát tin là nửa nguy hiểm — nó giả vờ sống. Bảng
phát tin mà không màn nào nghe (vd ``event_log`` cho bộ relay, ``slot_hold``
cho ``dung-giu-cho``) chỉ tốn một lần đánh thức, không phải lời nói dối — không
kiểm.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import asyncpg
import pytest

from clinicai.core.change_broker import CHANNEL

_REPO = Path(__file__).resolve().parents[3]
_MIGRATIONS = _REPO / "supabase/migrations"
_DASHBOARD = _REPO / "src/dashboard"
_APP = _DASHBOARD / "app/(dashboard)"
_CLIENT = _APP / "RealtimeRefresher.tsx"
_TRUONG_CA = _APP / "truong-ca/shared.tsx"
_DINH_NGHIA_HOOK = _APP / "dung-nghe-bang.ts"

_CO_GIAO_DIEN = pytest.mark.skipif(
    not _CLIENT.exists(), reason="dashboard sources not present"
)

# Dùng chung cho mọi khuôn: tên bảng có thể kèm `public.` và/hoặc ngoặc kép.
_TEN_BANG = r"(?:public\.)?\"?(\w+)\"?"

# ── Phía database: đọc migration ────────────────────────────────────────────

_CREATE_TRIGGER = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+\"?(\w+)\"?\b(.*?)\bON\s+"
    + _TEN_BANG
    + r"(.*?);",
    re.IGNORECASE | re.DOTALL,
)
_DROP_TRIGGER = re.compile(
    r"DROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?\"?(\w+)\"?\s+ON\s+" + _TEN_BANG,
    re.IGNORECASE,
)
_DROP_TABLE = re.compile(
    r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([\w\s,.\"]+?)\s*(?:CASCADE|RESTRICT)?\s*;",
    re.IGNORECASE,
)
_DROP_FUNCTION = re.compile(
    r"DROP\s+FUNCTION\s+(?:IF\s+EXISTS\s+)?(?:public\.)?notify_row_change\b",
    re.IGNORECASE,
)
_KHOI_DO = re.compile(r"\bDO\s+(\$\w*\$)(.*?)\1", re.IGNORECASE | re.DOTALL)
# Trong khối DO: `format('CREATE TRIGGER %I … ON public.%I …', 'trg_notify_' || t, t)`
_TAO_DONG = re.compile(r"'CREATE\s+TRIGGER\s+%I", re.IGNORECASE)
_XOA_DONG = re.compile(r"'DROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?%I", re.IGNORECASE)
_TEN_TRIGGER_DONG = re.compile(r"'trg_notify_'\s*\|\|\s*(\w+)")
_FOREACH = re.compile(
    r"FOREACH\s+(\w+)\s+IN\s+ARRAY\s+(?:ARRAY\s*\[(.*?)\]|(\w+))",
    re.IGNORECASE | re.DOTALL,
)


def _bo_chu_thich_sql(text: str) -> str:
    """Dấu ``;`` trong chú thích tiếng Việt cắt ngang câu lệnh — bỏ trước khi đọc."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", text)


def _mang_ten(than: str) -> list[str]:
    return re.findall(r"'(\w+)'", than)


def _su_kien_khoi_do(
    ten_file: str, vi_tri: int, than: str
) -> list[tuple[int, str, str, str]]:
    """Gắn/gỡ trigger notify do một vòng ``DO $$ … FOREACH … $$`` làm.

    Trả về ``(vị trí, "them"|"bo", bảng, tên trigger)``. Khối DO không đụng
    trigger notify → rỗng. Đụng mà không đọc ra được mảng → ném AssertionError.
    """
    tao = bool(_TAO_DONG.search(than)) and "notify_row_change" in than
    xoa = bool(_XOA_DONG.search(than)) and bool(_TEN_TRIGGER_DONG.search(than))
    if not tao and not xoa:
        return []
    m_ten = _TEN_TRIGGER_DONG.search(than)
    m_lap = _FOREACH.search(than)
    assert m_ten and m_lap, (
        f"{ten_file}: khối DO gắn trigger notify theo khuôn lạ (không thấy "
        "`'trg_notify_' || biến` hoặc `FOREACH … IN ARRAY …`). Dạy bộ đọc khuôn "
        "mới thay vì để nó bỏ qua."
    )
    bien, mang_tai_cho, ten_mang = m_lap.groups()
    assert m_ten.group(1) == bien, (
        f"{ten_file}: tên trigger ghép từ `{m_ten.group(1)}` nhưng vòng lặp chạy "
        f"trên `{bien}` — bộ đọc không chắc bảng nào được gắn."
    )
    if mang_tai_cho is not None:
        bang = _mang_ten(mang_tai_cho)
    else:
        m_mang = re.search(
            rf"\b{ten_mang}\s+text\[\]\s*:=\s*ARRAY\s*\[(.*?)\]", than, re.DOTALL
        )
        assert m_mang, (
            f"{ten_file}: vòng lặp chạy trên `{ten_mang}` nhưng không thấy "
            f"`{ten_mang} text[] := ARRAY[…]` trong cùng khối DO."
        )
        bang = _mang_ten(m_mang.group(1))
    assert bang, f"{ten_file}: mảng bảng của khối DO gắn trigger notify rỗng?"
    # Trong cùng một vòng: DROP rồi CREATE → còn trigger. Chỉ DROP → mất.
    hanh_dong = "them" if tao else "bo"
    return [(vi_tri, hanh_dong, b, f"trg_notify_{b}") for b in bang]


def _su_kien_migration(ten_file: str, text: str) -> list[tuple[int, str, str, str]]:
    """Mọi lần gắn/gỡ trigger notify trong một migration, theo thứ tự xuất hiện."""
    su_kien: list[tuple[int, str, str, str]] = []
    for m in _KHOI_DO.finditer(text):
        su_kien.extend(_su_kien_khoi_do(ten_file, m.start(), m.group(2)))
    # Câu viết thẳng. Trong khối DO, câu động dùng `%I` nên không khớp các mẫu
    # này; câu viết thẳng tên thật (nếu có) thì vẫn đúng là một lần gắn/gỡ.
    for m in _CREATE_TRIGGER.finditer(text):
        ten, bang = m.group(1), m.group(3)
        if "notify_row_change" in m.group(0):
            su_kien.append((m.start(), "them", bang, ten))
        else:
            # Cùng tên nhưng nay trỏ hàm khác (CREATE OR REPLACE) → hết báo tin.
            su_kien.append((m.start(), "bo", bang, ten))
    for m in _DROP_TRIGGER.finditer(text):
        su_kien.append((m.start(), "bo", m.group(2), m.group(1)))
    for m in _DROP_TABLE.finditer(text):
        for ten in m.group(1).split(","):
            ten = ten.strip().strip('"')
            if ten.startswith("pg_temp."):
                continue
            ten = ten.removeprefix("public.").strip('"')
            if re.fullmatch(r"\w+", ten):
                su_kien.append((m.start(), "bo_bang", ten, ""))
    for m in _DROP_FUNCTION.finditer(text):
        su_kien.append((m.start(), "bo_het", "", ""))
    su_kien.sort(key=lambda s: s[0])
    return su_kien


def _trigger_notify_theo_migration() -> dict[str, set[str]]:
    """``{bảng: {tên trigger}}`` — trigger gọi ``notify_row_change`` còn lại sau
    khi áp mọi migration theo thứ tự tên tệp (đúng thứ tự
    ``apply-pending-migrations.sh`` áp)."""
    con: dict[str, set[str]] = {}
    for path in sorted(_MIGRATIONS.glob("*.sql")):
        text = _bo_chu_thich_sql(path.read_text(encoding="utf-8"))
        for _, hanh_dong, bang, ten in _su_kien_migration(path.name, text):
            if hanh_dong == "them":
                con.setdefault(bang, set()).add(ten)
            elif hanh_dong == "bo":
                con.get(bang, set()).discard(ten)
            elif hanh_dong == "bo_bang":
                con.pop(bang, None)
            elif hanh_dong == "bo_het":
                con.clear()
    return {bang: ten for bang, ten in con.items() if ten}


# ── Phía giao diện: bảng màn hình nghe ──────────────────────────────────────


def _bo_chu_thich_ts(text: str) -> str:
    """Bỏ chú thích đứng đầu dòng — lời giải thích lịch sử được phép nhắc tên cũ.

    Chỉ bỏ chú thích bắt đầu ở đầu dòng: `//` giữa dòng có thể nằm trong chuỗi
    (``"https://…"``) và cắt nhầm mã thật.
    """
    text = re.sub(r"^\s*/\*.*?\*/", "", text, flags=re.DOTALL | re.MULTILINE)
    return re.sub(r"^\s*//[^\n]*", "", text, flags=re.MULTILINE)


def _ten_trong_mang(ten_file: str, than: str) -> set[str]:
    """Tên bảng trong một mảng chữ TS. Có gì khác chuỗi chữ → bộ đọc từ chối."""
    than = re.sub(r"//[^\n]*", "", than)
    con_lai = re.sub(r'"\w+"|\s|,', "", than)
    assert not con_lai, (
        f"{ten_file}: mảng bảng có phần không phải chuỗi chữ ({con_lai!r}) — "
        "bộ đọc tĩnh không chắc màn nghe bảng nào."
    )
    return set(re.findall(r'"(\w+)"', than))


def _hang_live_tables(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"const LIVE_TABLES = \[(.*?)\] as const;", text, re.DOTALL)
    assert m, f"Không thấy `const LIVE_TABLES = [ … ] as const;` trong {path.name}"
    bang = _ten_trong_mang(path.name, m.group(1))
    assert bang, f"LIVE_TABLES trong {path.name} rỗng — bộ đọc lệch khuôn?"
    return bang


def _moi_file_giao_dien() -> list[Path]:
    """Mọi file .ts/.tsx của dashboard — tỉa node_modules/.next ngay khi duyệt."""
    ra: list[Path] = []
    for goc, thu_muc, ten_file in os.walk(_DASHBOARD):
        thu_muc[:] = [
            d for d in thu_muc if d != "node_modules" and not d.startswith(".")
        ]
        ra.extend(Path(goc) / f for f in ten_file if f.endswith((".ts", ".tsx")))
    return ra


_GOI_HOOK = re.compile(r"(?<![\w.])useNgheBang\(")
_GOI_HOOK_DOC_DUOC = re.compile(
    r"(?<![\w.])useNgheBang\(\s*(?:\[(?P<mang>.*?)\]|(?P<hang>\w+))\s*,",
    re.DOTALL,
)


def _bang_nghe_qua_hook() -> dict[str, set[str]]:
    """``{tệp: {bảng}}`` cho mọi lời gọi ``useNgheBang`` trong dashboard."""
    ra: dict[str, set[str]] = {}
    for path in _moi_file_giao_dien():
        if path == _DINH_NGHIA_HOOK:
            continue
        text = _bo_chu_thich_ts(path.read_text(encoding="utf-8"))
        so_goi = len(_GOI_HOOK.findall(text))
        if not so_goi:
            continue
        ten = str(path.relative_to(_DASHBOARD))
        doc_duoc = list(_GOI_HOOK_DOC_DUOC.finditer(text))
        assert len(doc_duoc) == so_goi, (
            f"{ten}: {so_goi} lời gọi useNgheBang nhưng chỉ đọc được "
            f"{len(doc_duoc)}. Dạng mới (mảng ghép, hằng import…) → khai mảng "
            "chữ tại chỗ hoặc `const TEN = [ … ] as const;` trong cùng tệp."
        )
        for m in doc_duoc:
            if m.group("mang") is not None:
                bang = _ten_trong_mang(ten, m.group("mang"))
            else:
                hang = m.group("hang")
                m_hang = re.search(
                    rf"const {hang} = \[(.*?)\] as const;", text, re.DOTALL
                )
                assert m_hang, (
                    f"{ten}: useNgheBang({hang}) nhưng không thấy "
                    f"`const {hang} = [ … ] as const;` trong cùng tệp."
                )
                bang = _ten_trong_mang(ten, m_hang.group(1))
            assert bang, f"{ten}: useNgheBang với mảng rỗng?"
            ra.setdefault(ten, set()).update(bang)
    return ra


def _moi_bang_man_nghe() -> dict[str, set[str]]:
    """``{nơi nghe: {bảng}}`` — LIVE_TABLES hai tệp + mọi lời gọi useNgheBang."""
    nghe = {
        "RealtimeRefresher.tsx LIVE_TABLES": _hang_live_tables(_CLIENT),
        "truong-ca/shared.tsx LIVE_TABLES": _hang_live_tables(_TRUONG_CA),
    }
    nghe.update(_bang_nghe_qua_hook())
    return nghe


def _thieu(nghe: dict[str, set[str]], co_trigger: set[str]) -> dict[str, list[str]]:
    return {
        noi: sorted(bang - co_trigger)
        for noi, bang in nghe.items()
        if bang - co_trigger
    }


# ── Bài kiểm tĩnh ───────────────────────────────────────────────────────────


@_CO_GIAO_DIEN
def test_live_tables_deu_co_trigger_bao_tin() -> None:
    """Mỗi bảng trong LIVE_TABLES (RealtimeRefresher, trưởng ca) có trigger notify."""
    co_trigger = set(_trigger_notify_theo_migration())
    nghe = {
        "RealtimeRefresher.tsx": _hang_live_tables(_CLIENT),
        "truong-ca/shared.tsx": _hang_live_tables(_TRUONG_CA),
    }
    thieu = _thieu(nghe, co_trigger)
    assert not thieu, (
        f"LIVE_TABLES nghe bảng không có trigger notify trong migration: {thieu}. "
        "Nghe một bảng không phát tin thì im lặng — không lỗi, không cảnh báo, "
        "màn chỉ tự mới sau nhịp dự phòng 60 giây. Thêm migration gắn trigger "
        "gọi `notify_row_change` (khuôn 20260927000002), hoặc bỏ bảng khỏi "
        "LIVE_TABLES."
    )


@_CO_GIAO_DIEN
def test_bang_cac_man_nghe_qua_hook_deu_co_trigger_bao_tin() -> None:
    """Màn tự fetch nghe ké dòng SSE qua ``useNgheBang`` — cùng bẫy với LIVE_TABLES."""
    nghe = _bang_nghe_qua_hook()
    assert nghe, "Không tìm thấy màn nào dùng useNgheBang — bộ đọc đã lệch khuôn?"
    thieu = _thieu(nghe, set(_trigger_notify_theo_migration()))
    assert not thieu, (
        f"Màn nghe bảng không có trigger notify trong migration: {thieu}. Thêm "
        "migration gắn trigger gọi `notify_row_change` (khuôn 20260927000002)."
    )


def test_bo_doc_migration_bat_du_cac_khuon_da_biet() -> None:
    """Gác bộ đọc: mỗi khuôn trigger trong repo phải được hiểu đúng.

    Không có bài này, một lần bộ đọc hỏng (regex lệch) trả về tập nhỏ hơn — bài
    trên đỏ, người sửa "cho xanh" bằng cách nới bộ đọc… hoặc tệ hơn, trả về tập
    TO hơn và mọi thứ xanh oan. Mỗi dòng dưới là một khuôn có thật.
    """
    co = _trigger_notify_theo_migration()
    # Vòng `bang text[] := ARRAY[…]` (20260806000001, 20260814000001…).
    assert "trg_notify_appointment" in co.get("appointment", set())
    assert "trg_notify_payment_cycle" in co.get("payment_cycle", set())
    # Vòng `FOREACH x IN ARRAY ARRAY[…]` (20260915000006).
    assert "trg_notify_queue_entry" in co.get("queue_entry", set())
    # CREATE TRIGGER viết thẳng (20260926000007).
    assert "trg_notify_form_instance" in co.get("form_instance", set())
    # Tên trigger không theo `trg_notify_*` — bảng lấy từ mệnh đề ON (20261001000000).
    assert "trg_tep_ket_qua_bao_tin_khi_sua" in co.get("tep_ket_qua", set())
    # Trigger không gọi notify_row_change thì không được tính.
    assert "trg_payment_cycle_guard" not in co.get("payment_cycle", set())
    # Câu chuỗi format trong khối DO không bị đọc thành bảng tên "public"/"I".
    assert not {"public", "I"} & set(co)


def test_bo_doc_migration_tinh_ca_drop_o_migration_sau() -> None:
    """DROP TRIGGER / DROP TABLE ở migration sau phải gỡ trigger đã gắn trước."""
    truoc = _su_kien_migration(
        "a.sql",
        "CREATE TRIGGER trg_notify_x AFTER INSERT ON public.x "
        "FOR EACH ROW EXECUTE FUNCTION public.notify_row_change();",
    )
    assert [(h, b, t) for _, h, b, t in truoc] == [("them", "x", "trg_notify_x")]
    sau = _su_kien_migration("b.sql", "DROP TRIGGER IF EXISTS trg_notify_x ON x;")
    assert [(h, b, t) for _, h, b, t in sau] == [("bo", "x", "trg_notify_x")]
    bang = _su_kien_migration("c.sql", "DROP TABLE IF EXISTS public.x CASCADE;")
    assert [(h, b) for _, h, b, _ in bang] == [("bo_bang", "x")]
    vong = _su_kien_migration(
        "d.sql",
        _bo_chu_thich_sql(
            "DO $$\nDECLARE t text; bang text[] := ARRAY['y'];\nBEGIN\n"
            "FOREACH t IN ARRAY bang LOOP\n"
            "EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I',"
            " 'trg_notify_' || t, t);\nEND LOOP;\nEND $$;"
        ),
    )
    assert [(h, b, t) for _, h, b, t in vong] == [("bo", "y", "trg_notify_y")]


@_CO_GIAO_DIEN
def test_giao_dien_khong_con_dang_ky_supabase_realtime() -> None:
    """Không màn nào được mở kênh Supabase Realtime nữa.

    `postgres_changes` bắt Realtime mở replication slot với plugin wal2json, và
    Postgres của mình từ chối — mỗi lần thử là một dòng ERROR (~8.600/ngày đo
    trên prod 27/09) mà màn vẫn không nhận được gì. Tin đi LISTEN/NOTIFY → SSE;
    nghe bảng thì dùng `useNgheBang`, xem trạng thái kết nối thì dùng
    `useTrangThaiDong`.
    """
    vi_pham = []
    for path in _moi_file_giao_dien():
        ma = path.read_text(encoding="utf-8")
        # Bỏ chú thích: lời giải thích lịch sử được phép nhắc tên cũ.
        ma = re.sub(r"/\*.*?\*/", "", ma, flags=re.DOTALL)
        ma = re.sub(r"//[^\n]*", "", ma)
        if re.search(r"postgres_changes|\.channel\(|removeChannel\(", ma):
            vi_pham.append(str(path.relative_to(_DASHBOARD)))
    assert not vi_pham, f"Còn đăng ký Supabase Realtime ở: {sorted(vi_pham)}"


# ── Bài kiểm trên DB đã áp migration ────────────────────────────────────────

_SQL_TRIGGER_NOTIFY = """
SELECT c.relname AS bang, t.tgname AS ten
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_proc p ON p.oid = t.tgfoid
 WHERE NOT t.tgisinternal
   AND n.nspname = 'public'
   AND p.proname = 'notify_row_change'
   AND t.tgenabled <> 'D'
"""


async def _trigger_notify_tren_db(url: str) -> tuple[dict[str, set[str]], str | None]:
    """``({bảng: {trigger đang bật}}, thân hàm notify_row_change | None)``."""
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch(_SQL_TRIGGER_NOTIFY)
        than_ham = await conn.fetchval(
            "SELECT pg_get_functiondef(p.oid) FROM pg_proc p"
            " JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public' AND p.proname = 'notify_row_change'"
        )
    finally:
        await conn.close()
    co: dict[str, set[str]] = {}
    for r in rows:
        co.setdefault(r["bang"], set()).add(r["ten"])
    return co, than_ham


@pytest.mark.db
@pytest.mark.asyncio
@_CO_GIAO_DIEN
async def test_tren_db_moi_bang_man_nghe_co_trigger_dang_bat(test_db_url: str) -> None:
    """Trên database thật: mỗi bảng màn hình nghe có trigger notify ĐANG BẬT.

    Bắt thứ đọc migration không thấy: vòng gắn trigger tự bỏ qua bảng thiếu
    ``clinic_id``; trigger bị ``DISABLE``; hàm ``notify_row_change`` phát sai
    kênh so với ``change_broker.CHANNEL`` (trigger vẫn chạy, không ai nghe).
    """
    co, than_ham = await _trigger_notify_tren_db(test_db_url)
    assert than_ham, (
        "DB thử không có hàm public.notify_row_change — chưa áp migration? "
        "(scripts/apply-pending-migrations.sh --apply)"
    )
    assert f"'{CHANNEL}'" in than_ham, (
        f"notify_row_change không pg_notify vào kênh '{CHANNEL}' mà change_broker "
        "LISTEN — mọi trigger vẫn chạy nhưng không màn nào nhận được tin."
    )
    thieu = _thieu(_moi_bang_man_nghe(), set(co))
    assert not thieu, (
        f"Trên DB, màn nghe bảng không có trigger notify đang bật: {thieu}."
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_tren_db_bo_doc_migration_khong_bia_trigger(test_db_url: str) -> None:
    """Mọi trigger notify bộ đọc tĩnh tin là có — phải có thật trên DB.

    Chiều ngược (DB có mà migration không có) KHÔNG kiểm: DB thử dùng chung có
    thể đã áp migration của nhánh khác.
    """
    co, _ = await _trigger_notify_tren_db(test_db_url)
    bia = {
        bang: sorted(ten - co.get(bang, set()))
        for bang, ten in _trigger_notify_theo_migration().items()
        if ten - co.get(bang, set())
    }
    assert not bia, (
        f"Bộ đọc migration nói có trigger notify nhưng DB không có: {bia}. Hoặc "
        "migration tự bỏ qua bảng (thiếu bảng / thiếu clinic_id), hoặc bộ đọc "
        "đọc sai khuôn — bài kiểm tĩnh đang xanh oan."
    )
