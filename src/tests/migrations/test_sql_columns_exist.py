"""Cột được SELECT phải có thật trong schema.

CHUYỆN ĐÃ XẢY RA. ``/api/v1/catalog/wards`` chạy
``SELECT id, name, parent_id FROM ward`` — bảng ``ward`` chưa bao giờ có cột
``id`` hay ``parent_id`` (nó khoá theo ``code``). ``/api/v1/catalog/service-types``
chọn ``aliases, category, base_price_vnd, sort_order``; không cột nào trong bốn
cột đó tồn tại trong bất kỳ migration nào. Hai endpoint đó trả 500 mỗi lần được
gọi, và không ai thấy vì hiện chưa màn hình nào gọi tới chúng.

VÌ SAO KHÔNG CÓ LỚP NÀO BẮT ĐƯỢC. SQL trong asyncpg là chuỗi ký tự: ruff không
đọc, mypy không đọc, và test đơn vị thì mock ``conn.fetch`` nên câu SQL không bao
giờ chạm Postgres. Lỗi chỉ lộ ra khi có người thật bấm vào — mà ở đây thì chưa
có ai bấm. Cùng loại im lặng với vụ router không được mount
(``test_router_wiring.py``) và vụ đường dẫn lệch giữa hai ngôn ngữ
(``test_dashboard_backend_paths.py``).

PHẠM VI — CỐ Ý HẸP. Chỉ soi những câu ĐƠN GIẢN: danh sách cột thuần (không hàm,
không bí danh, không tiền tố bảng) lấy từ ĐÚNG MỘT bảng, không JOIN. Đó chính là
hình dạng của các câu tra cứu — nơi lỗi này sinh ra. Câu phức tạp bị bỏ qua chứ
không đoán bừa: một bài kiểm báo nhầm sẽ bị người sau nới lỏng cho xanh, và thế
là mất luôn thứ nó canh.

BỘ ĐỌC SCHEMA ĐÃ ĐƯỢC ĐỐI CHIẾU. Bản đồ cột dựng từ migration đã so với
``information_schema`` của Postgres đang chạy: khớp 100% trên 67 bảng. Lần đối
chiếu đó tìm ra một lỗi của chính bộ đọc — dấu ``;`` nằm giữa một câu chú thích
tiếng Việt cắt ngang câu ``ALTER TABLE``, làm mất cột ``form_code_nam``. Vì thế
``_strip_sql_comments`` chạy trước mọi phép đọc.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_MIGRATIONS = _REPO / "supabase/migrations"
_BACKEND = _REPO / "src/clinicai"

# Số câu tối thiểu phải soi được. Không có ngưỡng này, một lần đổi cách viết SQL
# sẽ làm bộ quét trả về rỗng và bài kiểm vẫn XANH — gác rỗng còn tệ hơn không gác.
_MIN_QUERIES_SCANNED = 15

_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?\"?(\w+)\"?\s*\((.*?)\n\);",
    re.IGNORECASE | re.DOTALL,
)
_ALTER = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?:public\.)?\"?(\w+)\"?(.*?);",
    re.IGNORECASE | re.DOTALL,
)
_ADD_COLUMN = re.compile(
    r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?\"?(\w+)\"?", re.IGNORECASE
)
_DROP_COLUMN = re.compile(
    r"DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?\"?(\w+)\"?", re.IGNORECASE
)
# Dạng vòng lặp plpgsql thêm cùng một cột cho nhiều bảng:
#   EXECUTE format('ALTER TABLE public.%I ADD COLUMN clinic_id …', t)
_LOOP_ADD = re.compile(
    r"ALTER\s+TABLE\s+public\.%I\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
    re.IGNORECASE,
)
_ARRAY_LITERAL = re.compile(r"ARRAY\s*\[(.*?)\]", re.DOTALL)
_NOT_A_COLUMN = re.compile(
    r"^\s*(CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|EXCLUDE|LIKE)\b", re.IGNORECASE
)

# Câu SELECT "đơn giản": cột chỉ gồm chữ/số/gạch dưới, dấu phẩy và khoảng trắng.
# Bất cứ dấu ngoặc (hàm), dấu chấm (tiền tố bảng), chữ AS hay `*` nào cũng làm
# câu này KHÔNG khớp — tức là bị bỏ qua, không bị đoán sai.
_SIMPLE_SELECT = re.compile(
    r"SELECT\s+(?P<cols>[A-Za-z_][\w\s,]*?)\s+FROM\s+(?:public\.)?(?P<table>\w+)\b",
    re.IGNORECASE,
)
_SQL_KEYWORDS = frozenset({"distinct", "all", "as", "from", "select"})


def _strip_sql_comments(text: str) -> str:
    """Xem docstring đầu file: dấu ``;`` trong chú thích cắt ngang câu lệnh."""
    return re.sub(r"--[^\n]*", "", text)


def _table_columns() -> dict[str, set[str]]:
    """{tên bảng: {tên cột}} đọc từ toàn bộ migration."""
    columns: dict[str, set[str]] = {}
    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        text = _strip_sql_comments(sql_file.read_text(encoding="utf-8"))

        for table, body in _CREATE.findall(text):
            known = columns.setdefault(table, set())
            depth = 0
            for raw in body.split("\n"):
                line = raw.strip()
                if not line:
                    continue
                if depth == 0 and not _NOT_A_COLUMN.match(line):
                    named = re.match(r"\"?(\w+)\"?\s", line)
                    if named:
                        known.add(named.group(1))
                depth += line.count("(") - line.count(")")

        for table, tail in _ALTER.findall(text):
            known = columns.setdefault(table, set())
            known.update(_ADD_COLUMN.findall(tail))
            for dropped in _DROP_COLUMN.findall(tail):
                known.discard(dropped)

        for added in _LOOP_ADD.findall(text):
            for array in _ARRAY_LITERAL.findall(text):
                for table in re.findall(r"'(\w+)'", array):
                    if table in columns:
                        columns[table].add(added)

    return columns


def _simple_selects() -> list[tuple[str, str, list[str]]]:
    """[(file:line, bảng, [cột])] cho mọi câu SELECT đơn giản trong backend."""
    found: list[tuple[str, str, list[str]]] = []
    for py in sorted(_BACKEND.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        for match in _SIMPLE_SELECT.finditer(text):
            # Có JOIN phía sau thì cột không tiền tố là mơ hồ — bỏ qua.
            tail = text[match.end() : match.end() + 400]
            if re.search(r"\bJOIN\b", tail, re.IGNORECASE):
                continue
            names = [
                c.strip()
                for c in match.group("cols").split(",")
                if c.strip() and c.strip().lower() not in _SQL_KEYWORDS
            ]
            if not names or any(" " in n for n in names):
                continue
            line = text.count("\n", 0, match.start()) + 1
            found.append(
                (f"{py.relative_to(_REPO)}:{line}", match.group("table"), names)
            )
    return found


def test_every_selected_column_exists() -> None:
    schema = _table_columns()
    problems: list[str] = []

    for where, table, names in _simple_selects():
        known = schema.get(table)
        if known is None:
            continue  # view, CTE, bảng tạm — ngoài tầm bộ đọc, bỏ qua
        missing = [n for n in names if n not in known]
        if missing:
            problems.append(
                f"  ✗ {where}\n"
                f"      SELECT {', '.join(missing)} FROM {table}"
                f"  — cột không tồn tại\n"
                f"      {table} có: {', '.join(sorted(known))}"
            )

    assert not problems, "SELECT cột không có trong schema:\n" + "\n".join(problems)


def test_the_scanner_still_reads_the_backend() -> None:
    """Chốt chống-xanh-giả: bộ quét phải thật sự soi được câu SQL."""
    scanned = len(_simple_selects())
    assert scanned >= _MIN_QUERIES_SCANNED, (
        f"chỉ soi được {scanned} câu SELECT đơn giản "
        f"(chờ ít nhất {_MIN_QUERIES_SCANNED}). Có thể cách viết SQL đã đổi và "
        "bài kiểm trên đang gác rỗng — kiểm tra lại _SIMPLE_SELECT."
    )


def test_the_schema_reader_finds_the_core_tables() -> None:
    """Bộ đọc migration phải dựng được bản đồ, không phải trả về rỗng."""
    schema = _table_columns()
    for table in ("appointment", "patient", "service_type", "ward", "slot_hold"):
        assert schema.get(table), f"không đọc được cột nào của bảng {table}"


def test_the_patient_slot_index_exists_in_a_migration() -> None:
    """Chỉ mục chống đặt trùng phải nằm trong migration, không chỉ trong lời kể.

    Đúng chuyện đã xảy ra với ``appointment_no_doctor_overlap``: bốn chỗ trong
    code gọi nó là "the real guard", còn schema thì không có nó — bị DROP ở một
    migration cũ và không ai dựng lại. Một lưới chỉ tồn tại trong chú thích là
    thứ nguy hiểm hơn không có lưới, vì tầng trên cố ý fail-open khi tin rằng
    có nó.
    """
    sql = "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(_MIGRATIONS.glob("*.sql"))
    )
    assert "uq_appointment_patient_slot_live" in sql, (
        "không migration nào tạo uq_appointment_patient_slot_live — "
        "trong khi main.py và booking_service.py đang khai là có"
    )


def test_no_code_claims_the_dropped_overlap_constraint() -> None:
    """``appointment_no_doctor_overlap`` đã bị DROP — đừng khai là nó còn.

    Và đừng dựng lại: EXCLUDE cấm MỌI cặp chồng lấn, tức trần bằng 1, trong khi
    luật phòng khám là 2 chỗ đặt + 1 vãng lai mỗi bác sĩ mỗi khung
    (clinic_policy.py). Trần theo số đếm là việc của trigger, không phải EXCLUDE.
    Nếu ngày nào đó thật sự dựng lại nó bằng migration, bài kiểm này sẽ tự cho
    phép — nó chỉ cấm việc KHAI SUÔNG.
    """
    migrations = "\n".join(
        f.read_text(encoding="utf-8") for f in sorted(_MIGRATIONS.glob("*.sql"))
    )
    really_exists = re.search(
        r"(ADD\s+CONSTRAINT|CREATE\s+.*CONSTRAINT)\s+appointment_no_doctor_overlap",
        migrations,
        re.IGNORECASE,
    )
    if really_exists:
        return

    # KIỂM ĐÚNG THỨ CÓ HẬU QUẢ, KHÔNG ĐOÁN CHỮ TRONG CHÚ THÍCH.
    #
    # Bản đầu của bài kiểm này quét mọi dòng nhắc tên rồi tha cho dòng nào có
    # chữ "không tồn tại" ở gần. Cách đó vừa báo nhầm chính đoạn giải thích, vừa
    # sẽ bỏ lọt một lời khai gian nào tình cờ nằm cạnh một chữ "không". Chú
    # thích sai thì gây hiểu nhầm; ĐOẠN MAP DƯỚI ĐÂY thì gây hành vi sai — nó là
    # thứ quyết định người dùng đọc được câu gì. Nên chỉ kiểm nó.
    handler = (_BACKEND / "main.py").read_text(encoding="utf-8")
    mapping = re.search(
        r"exclusion_violation_handler.*?known\s*=\s*\{(.*?)\}",
        handler,
        re.DOTALL,
    )
    assert mapping, "không tìm thấy bảng ánh xạ trong exclusion_violation_handler"
    assert "appointment_no_doctor_overlap" not in mapping.group(1), (
        "exclusion_violation_handler đang ánh xạ appointment_no_doctor_overlap, "
        "nhưng không migration nào tạo ràng buộc đó — mục này không bao giờ bắn, "
        "và nó làm người đọc tin rằng có một lưới ở đây."
    )
