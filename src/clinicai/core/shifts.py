"""Ca trực đổi thành KHOẢNG PHÚT trong ngày.

``work_roster.shift`` là một trong bốn nhãn: ``FULL``, ``SANG``, ``CHIEU``,
``TOI``. Các nhãn ấy nói về thời gian, nhưng bản thân chúng không mang giờ —
nên module này là chỗ duy nhất biết "sáng" nghĩa là mấy giờ tới mấy giờ.

── VÌ SAO ĐỔI MÔ HÌNH (Tuyền, 21/08/2026) ────────────────────────────────────

Bản cũ suy ca từ MỘT mốc chia viết cứng (12:00): sáng = mở cửa → 12:00, chiều =
12:00 → đóng cửa. Chú thích của chính bản ấy đã tiên đoán *"nó sẽ là thứ đầu
tiên phòng khám thứ hai muốn đổi"*, và hôm nay đúng vậy — nhưng theo một cách
mà một mốc chia KHÔNG diễn tả nổi:

    sáng  08:00 ─ 13:00
                  ╳  nghỉ trưa 13:00–14:00
    chiều 14:00 ─ 17:30
    tối   17:30 ─ 21:30

Giữa sáng và chiều có một khoảng TRỐNG. Một mốc chia không tạo ra được khoảng
trống, nên ca phải được KHAI TƯỜNG MINH chứ không suy ra.

Hệ quả kéo theo, và là lý do chữ ký hàm đổi: ca ``FULL`` giờ là HAI khoảng rời
nhau (08:00–13:00 và 14:00–21:30), không còn là một. Vì thế ``shift_windows``
trả về một DANH SÁCH. Đây là thay đổi phá vỡ tương thích có chủ ý — sáu nơi gọi
phải sửa, và thà chúng lỗi biên dịch còn hơn lặng lẽ nhận khoảng đầu tiên rồi
để bác sĩ trực cả ngày biến mất khỏi buổi chiều.

── GIỜ CA SỐNG Ở ĐÂU ─────────────────────────────────────────────────────────

Trong ``clinic.settings->'ca_lam_viec'``, để mỗi phòng khám tự khai (phòng mở
8h, phòng mở 9h). Module này THUẦN: cấu hình đi vào bằng tham số, không đọc
database. Thiếu cấu hình thì lùi về ``CA_MAC_DINH`` dưới đây — một phòng khám
mới dựng vẫn chạy được ngay, và con số mặc định là con số Dr4Women đang dùng
chứ không phải một con số bịa.

Mọi khoảng đều NỬA MỞ ``[lo, hi)``, cùng quy ước với mọi khoảng phút khác trong
hệ thống: một khung bắt đầu đúng 17:30 thuộc ca TỐI, không thuộc ca chiều.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

Window = tuple[int, int]

#: Thứ tự CÓ Ý NGHĨA: sớm trước, muộn sau. Giao diện in theo thứ tự này.
CAC_CA: tuple[str, ...] = ("SANG", "CHIEU", "TOI")

#: Nhãn tiếng Việt — một chỗ duy nhất, để backend và tin nhắn nói giống màn hình.
NHAN_CA: dict[str, str] = {
    "SANG": "Sáng",
    "CHIEU": "Chiều",
    "TOI": "Tối",
    "FULL": "Cả ngày",
}

#: Giờ ca mặc định khi phòng khám chưa khai. Đây là giờ Dr4Women chốt 21/08/2026.
CA_MAC_DINH: dict[str, Window] = {
    "SANG": (8 * 60, 13 * 60),
    "CHIEU": (14 * 60, 17 * 60 + 30),
    "TOI": (17 * 60 + 30, 21 * 60 + 30),
}


def phut_tu_gio(hhmm: str) -> int | None:
    """``"08:30"`` → 510. Chuỗi hỏng trả ``None`` thay vì ném lỗi.

    Cấu hình do người gõ vào; một ô đánh máy sai không được phép làm sập màn
    đặt lịch của cả phòng khám. Ca hỏng bị bỏ qua và các ca còn lại vẫn chạy.
    """
    try:
        gio, phut = str(hhmm).strip().split(":")
        g, p = int(gio), int(phut)
    except (ValueError, AttributeError):
        return None
    if not (0 <= g <= 24 and 0 <= p < 60):
        return None
    return g * 60 + p


def doc_cau_hinh_ca(settings: Mapping[str, Any] | None) -> dict[str, Window]:
    """``clinic.settings`` → giờ của từng ca.

    Chỉ nhận những ca khai ĐỦ và HỢP LỆ; ca nào thiếu thì lấy mặc định. Trộn
    được như vậy vì mỗi ca độc lập — phòng khám đổi giờ ca tối không có lý do
    gì làm hỏng ca sáng.
    """
    ket: dict[str, Window] = dict(CA_MAC_DINH)
    raw = (settings or {}).get("ca_lam_viec")
    if not isinstance(raw, Mapping):
        return ket
    for ma in CAC_CA:
        muc = raw.get(ma)
        if not isinstance(muc, Mapping):
            continue
        lo = phut_tu_gio(str(muc.get("bat_dau", "")))
        hi = phut_tu_gio(str(muc.get("ket_thuc", "")))
        if lo is None or hi is None or hi <= lo:
            continue
        ket[ma] = (lo, hi)
    return ket


def ca_tu_settings(raw: object) -> dict[str, Window]:
    """``clinic.settings`` (thô, từ asyncpg) → giờ của từng ca.

    Cột JSONB về tay Python có thể là dict (khi có codec) HOẶC chuỗi JSON (khi
    không) — nên chỗ nào cũng phải chịu được cả hai. Bản đầu của đợt này viết
    hàm gỡ băng ấy BA LẦN ở ba service; một sự thật ba bản là ba cơ hội để
    chúng lệch nhau, đúng thứ mà chính module này đã dọn một lần với bản
    TypeScript của luật xếp hàng.

    Hỏng hay thiếu thì trả giờ ca MẶC ĐỊNH — phòng khám mới dựng vẫn chạy ngay.
    """
    doc: Any = raw
    if isinstance(doc, (str, bytes)):
        try:
            doc = json.loads(doc)
        except (ValueError, TypeError):
            return dict(CA_MAC_DINH)
    if not isinstance(doc, Mapping):
        return dict(CA_MAC_DINH)
    return doc_cau_hinh_ca(doc)


def shift_windows(
    shift: str,
    open_min: int,
    close_min: int,
    ca: Mapping[str, Window] | None = None,
) -> list[Window]:
    """Các khoảng phút mà một ca trực phủ, đã kẹp vào giờ mở cửa hôm đó.

    Trả danh sách RỖNG khi ca ấy không còn phút nào — ví dụ ca SÁNG của một ngày
    chỉ mở cửa từ 17:00. Không phải lỗi, chỉ là một ca không có giờ nào.

    ``FULL`` = HỢP của cả ba ca (Tuyền chốt 21/08/2026), nên nó có thể là hai
    khoảng rời nhau khi phòng khám nghỉ trưa.
    """
    bang = dict(ca) if ca else dict(CA_MAC_DINH)

    if shift == "FULL":
        tho = [bang[m] for m in CAC_CA if m in bang]
    elif shift in bang:
        tho = [bang[shift]]
    else:
        # Nhãn lạ: coi như cả ngày thay vì lặng lẽ bỏ qua. Một ca không đọc được
        # mà biến mất sẽ khoá lịch của một bác sĩ đang thật sự đi làm — sai theo
        # hướng đó tệ hơn hẳn.
        tho = [(open_min, close_min)]

    ket: list[Window] = []
    for lo, hi in tho:
        lo2, hi2 = max(lo, open_min), min(hi, close_min)
        if hi2 > lo2:
            ket.append((lo2, hi2))
    return merge_windows(ket)


def gio_lam_viec(
    open_min: int, close_min: int, ca: Mapping[str, Window] | None = None
) -> list[Window]:
    """GIỜ LÀM VIỆC THẬT của phòng khám hôm đó = hợp của các ca.

    Tuyền chốt 21/08/2026: ngoài ba ca thì không đặt lịch được. Giờ mở cửa
    (``clinic.settings->hours``) nói cửa mở lúc nào; hàm này nói lúc nào CÓ
    NGƯỜI KHÁM. Hai chuyện khác nhau, và trước đây hệ chỉ biết chuyện thứ nhất
    nên vẫn mời đặt lịch vào giờ nghỉ trưa.
    """
    return shift_windows("FULL", open_min, close_min, ca)


NHAN_THU = {
    "0": "Chủ nhật",
    "1": "Thứ Hai",
    "2": "Thứ Ba",
    "3": "Thứ Tư",
    "4": "Thứ Năm",
    "5": "Thứ Sáu",
    "6": "Thứ Bảy",
}


def _gio(phut: int) -> str:
    return f"{phut // 60:02d}:{phut % 60:02d}"


def kiem_cau_hinh_ca(
    ca: Mapping[str, Window],
    gio_mo_dong: Mapping[str, tuple[str, str]] | None = None,
) -> list[str]:
    """Cấu hình ca quản lý vừa nhập có dùng được không — danh sách lỗi, rỗng là ổn.

    Trả DANH SÁCH chứ không ném ở lỗi đầu tiên: người nhập sai hai ô thì nên
    thấy cả hai, chứ không phải sửa một ô rồi bấm lưu để biết ô thứ hai.

    Bốn điều được kiểm, và điều cuối là điều dễ quên nhất:

    1. Đủ ba ca. Thiếu một ca thì bản đọc lặng lẽ lấy giờ MẶC ĐỊNH cho ca ấy —
       người nhập tưởng mình đã bỏ ca tối, hệ vẫn chạy ca tối 17:30–21:30.
    2. Giờ kết thúc sau giờ bắt đầu.
    3. Các ca không chồng lên nhau, và theo đúng thứ tự sáng → chiều → tối. Hai
       ca chồng nhau thì một mốc giờ thuộc hai ca, và KPI theo ca — thứ cả việc
       này sinh ra để phục vụ — đếm đôi.
    4. Ca phải NẰM TRONG giờ mở cửa của mọi ngày đã khai. Không kiểm thì ca vẫn
       lưu được nhưng bị CẮT lúc đọc: khai ca tối tới 22:00 trong khi cửa đóng
       21:00, hệ nhận lịch tới 21:00 và không báo gì. Im lặng cắt bớt là kiểu
       sai khó lần nhất, vì màn cấu hình vẫn hiện đúng con số đã nhập.
    """
    loi: list[str] = []

    thieu = [m for m in CAC_CA if m not in ca]
    if thieu:
        loi.append(
            "Thiếu ca: "
            + ", ".join(NHAN_CA.get(m, m) for m in thieu)
            + ". Phải khai đủ ba ca, vì ca thiếu sẽ lặng lẽ dùng giờ mặc định."
        )

    for ma in CAC_CA:
        if ma not in ca:
            continue
        lo, hi = ca[ma]
        ten = NHAN_CA.get(ma, ma)
        if not (0 <= lo < 24 * 60) or not (0 < hi <= 24 * 60):
            loi.append(f"Ca {ten}: giờ phải nằm trong một ngày.")
        elif hi <= lo:
            loi.append(
                f"Ca {ten}: giờ kết thúc ({_gio(hi)}) phải sau giờ bắt đầu "
                f"({_gio(lo)})."
            )

    co = [(ma, ca[ma]) for ma in CAC_CA if ma in ca and ca[ma][1] > ca[ma][0]]
    for (ma_a, (lo_a, hi_a)), (ma_b, (lo_b, _hi_b)) in zip(co, co[1:], strict=False):
        if lo_b < hi_a:
            loi.append(
                f"Ca {NHAN_CA.get(ma_b, ma_b)} bắt đầu lúc {_gio(lo_b)}, "
                f"trước khi ca {NHAN_CA.get(ma_a, ma_a)} kết thúc ({_gio(hi_a)}). "
                "Hai ca chồng nhau thì một giờ thuộc hai ca và KPI đếm đôi."
            )

    for thu, (mo_s, dong_s) in (gio_mo_dong or {}).items():
        mo, dong = phut_tu_gio(mo_s or ""), phut_tu_gio(dong_s or "")
        if mo is None or dong is None:
            continue
        ten_thu = NHAN_THU.get(str(thu), f"thứ {thu}")
        for ma in CAC_CA:
            if ma not in ca:
                continue
            lo, hi = ca[ma]
            if hi <= lo:
                continue
            if lo < mo or hi > dong:
                loi.append(
                    f"{ten_thu} mở cửa {_gio(mo)}–{_gio(dong)}, không chứa hết ca "
                    f"{NHAN_CA.get(ma, ma)} ({_gio(lo)}–{_gio(hi)}). "
                    "Nới giờ mở cửa hoặc thu ca lại — để nguyên thì ca bị cắt "
                    "mà không báo gì."
                )
    return loi


def khung_theo_thu(
    gio_mo_dong: Mapping[str, tuple[str, str]],
    ca: Mapping[str, Window] | None = None,
) -> dict[str, list[list[int]]]:
    """Giờ mở cửa từng thứ → KHUNG NHẬN LỊCH từng thứ, tính bằng phút.

    ``{"1": ("07:00", "22:00")}`` → ``{"1": [[480, 780], [840, 1290]]}``.

    Giờ mở cửa nói cửa mở lúc nào; khung này nói lúc nào NHẬN ĐƯỢC LỊCH — hai
    chuyện khác nhau, vì ba ca không phủ kín giờ mở cửa (nghỉ trưa, và hai đầu
    ngày). Trình duyệt lọc ô giờ theo đây để không mời rồi mới mắng.

    Ở đây chứ không ở router: quy đổi "17:30" ra phút rồi cắt theo giờ mở cửa là
    LUẬT, và luật nằm trong router thì không ai kiểm được nó mà không dựng cả
    một request. Thứ nào khai giờ hỏng thì BỎ QUA thứ đó — trình duyệt hiểu
    "vắng mặt" là "chưa biết" và không lọc, còn máy chủ vẫn chặn.
    """
    ket: dict[str, list[list[int]]] = {}
    for thu, (mo_s, dong_s) in gio_mo_dong.items():
        mo, dong = phut_tu_gio(mo_s or ""), phut_tu_gio(dong_s or "")
        if mo is None or dong is None:
            continue
        ket[str(thu)] = [[lo, hi] for lo, hi in gio_lam_viec(mo, dong, ca)]
    return ket


def ca_cua_phut(minute: int, ca: Mapping[str, Window] | None = None) -> str:
    """Mốc phút này thuộc ca nào — dùng khi phải SUY ca từ giờ một lịch hẹn.

    Trả ca sớm nhất mà mốc ấy rơi vào. Rơi vào khoảng trống (nghỉ trưa) hoặc
    ngoài mọi ca thì trả về ca GẦN NHẤT phía trước, và nếu sớm hơn cả ca đầu
    thì trả ca đầu.

    Vì sao không trả ``None``: nơi gọi duy nhất là lúc tự xếp một dòng lịch trực
    cho bác sĩ vừa được gán vào một lịch hẹn. Không có ca nghĩa là không xếp
    được dòng nào, và bác sĩ có tên trong lịch hẹn mà vắng trong lịch trực —
    đúng cái lệch mà việc tự xếp này sinh ra để chữa.
    """
    bang = dict(ca) if ca else dict(CA_MAC_DINH)
    co_mat = [(bang[m][0], bang[m][1], m) for m in CAC_CA if m in bang]
    if not co_mat:
        return "SANG"
    co_mat.sort()
    for lo, hi, ma in co_mat:
        if lo <= minute < hi:
            return ma
    truoc = [ma for lo, _hi, ma in co_mat if lo <= minute]
    return truoc[-1] if truoc else co_mat[0][2]


def merge_windows(windows: list[Window]) -> list[Window]:
    """Gộp các khoảng chồng/kề nhau thành danh sách rời nhau, đã sắp xếp.

    Một bác sĩ có thể có nhiều dòng trong lịch trực cùng một ngày — ở nhiều trạm
    khác nhau, và ca có thể khác nhau (SÁNG ở trạm này, CHIỀU ở trạm kia). Bác
    sĩ đó có mặt trong HỢP của các ca, nên phải gộp trước khi hỏi.
    """
    if not windows:
        return []
    out: list[Window] = []
    for lo, hi in sorted(windows):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def covers(windows: list[Window], minute: int) -> bool:
    """Mốc phút này có nằm trong ca trực nào không (nửa mở ``[lo, hi)``)."""
    return any(lo <= minute < hi for lo, hi in windows)


def describe(windows: list[Window]) -> str:
    """Các ca thành câu đọc được, để đưa thẳng vào thông báo cho người dùng."""

    def hhmm(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    return ", ".join(f"{hhmm(lo)}–{hhmm(hi)}" for lo, hi in windows)
