"""Đọc code bằng model — cắt khúc, hỏi, đọc câu trả lời, đổi thành ứng viên.

Model chỉ là NGƯỜI ĐỌC ĐẦU TIÊN. Nó không quyết gì: câu trả lời của nó là ứng viên
đi qua đúng cửa trích dẫn như bộ quét tĩnh (`kiem_trich_dan`), rồi tới người duyệt.
Mức bằng chứng của mọi thứ do model nêu ra tối đa là `suy_ra`.

Đề bài KHÔNG gợi ý lỗi nào — chỉ nêu loại lỗi và luật chứng minh (kịch bản cụ thể).
Đó là điều kiện để thước đo recall có nghĩa.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import che_du_lieu
from .chi_phi import SoChiPhi
from .khach import KetQuaGoi, goi

KHUC_DONG = 330
GOI_DONG = 40  # chồng lên nhau để lỗi nằm ở ranh giới không lọt

HE_THONG = """Bạn là kỹ sư soát code kỹ tính cho ClinicAI (quản lý phòng khám: \
FastAPI + Postgres + Next.js/TypeScript). Việc của bạn: tìm LỖI THẬT trong đoạn mã \
người dùng gửi.

Các loại lỗi cần tìm:
- logic_sai: với một đầu vào cụ thể, hàm cho kết quả sai hoặc làm sai việc.
- du_lieu_sai: ghi sai, ghi thiếu, so sánh/cộng lẫn đơn vị hay kiểu, số vượt giới hạn \
cột, ép kiểu hỏng.
- mat_du_lieu: dữ liệu người dùng nhập bị nuốt im lặng, không lưu, hoặc lưu thành giá \
trị mặc định mà không báo.
- lego_thieu_lien_ket: hai thành phần phải nối với nhau nhưng thiếu dây (danh sách \
thiếu một mục, cờ/thuộc tính không bao giờ được dùng, tên lệch nhau).
- hieu_nang: một thao tác gây việc thừa lớn (làm lại cả màn, truy vấn không giới hạn).
- loi_an: lỗi bị che/không hiện đúng nơi người dùng đang nhìn.

LUẬT:
1. Chỉ báo khi viết được KỊCH BẢN cụ thể: đầu vào/trạng thái nào → kết quả sai hoặc \
hậu quả gì. Không báo phong cách, thiếu comment, thiếu test, đặt tên.
2. Dòng trích dẫn phải CÓ THẬT trong đoạn mã (số dòng in ở đầu mỗi dòng). Không bịa.
3. Không chắc thì để do_chac thấp (0.3), đừng bỏ qua cũng đừng khẳng định.
4. Tối đa 5 lỗi, xếp từ nghiêm trọng nhất. Không thấy lỗi thật thì trả [].
5. Không đưa ra quyết định lâm sàng (chẩn đoán, chọn điều trị).

CHỈ trả về MỘT mảng JSON, không chữ nào khác, mỗi phần tử:
{"dong_tu": int, "dong_den": int, "loai": "<một trong các loại trên>", \
"co_che": "<vì sao sai, tối đa 2 câu>", "kich_ban": "<đầu vào → kết quả sai>", \
"trich_dan": "<chép nguyên một dòng mã có thật>", "do_chac": 0.0-1.0}"""


#: Tham số riêng để model "suy nghĩ" không đốt hết ngân sách token trước khi trả lời.
#: Chỉ khai những model ĐÃ thử và thấy có tác dụng (xem thước đo 18/10): MiniMax-M3
#: nhận `thinking.disabled`; DeepSeek-V4*/GLM-5.3-Flash bỏ qua mọi tham số — không
#: dùng được cho việc này ở nhà cung cấp hiện có.
THAM_SO_MODEL: dict[str, dict[str, object]] = {
    "MiniMaxAI/MiniMax-M3": {"thinking": {"type": "disabled"}},
}


def tham_so_cho(mo_hinh: str) -> dict[str, object]:
    return THAM_SO_MODEL.get(mo_hinh.split(":")[0], {})


@dataclass(frozen=True)
class UngVien:
    tep: str
    dong_tu: int
    dong_den: int
    loai: str
    co_che: str
    kich_ban: str
    trich_dan: str
    do_chac: float
    mo_hinh: str


def cat_khuc(noi_dung: str) -> list[tuple[int, str]]:
    """[(dòng bắt đầu 1-based, văn bản đã đánh số dòng)] — mỗi khúc ~330 dòng."""
    ds = noi_dung.splitlines()
    if len(ds) <= KHUC_DONG + GOI_DONG:
        cac = [(0, len(ds))]
    else:
        cac = []
        i = 0
        while i < len(ds):
            cac.append((i, min(len(ds), i + KHUC_DONG)))
            if i + KHUC_DONG >= len(ds):
                break
            i += KHUC_DONG - GOI_DONG
    ra = []
    for a, b in cac:
        dong = (f"{n:>5}| {ds[n - 1]}" for n in range(a + 1, b + 1))
        ra.append((a + 1, "\n".join(dong)))
    return ra


_RAO = re.compile(r"```(?:json)?|```", re.I)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def doc_json(van_ban: str) -> list[dict[str, object]]:
    t = _THINK.sub("", van_ban)
    t = _RAO.sub("", t)
    a, b = t.find("["), t.rfind("]")
    if a < 0 or b <= a:
        return []
    try:
        d = json.loads(t[a : b + 1])
    except json.JSONDecodeError:
        return []
    return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []


def _so(x: object, mac_dinh: float) -> float:
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return mac_dinh


def soat_mot_khuc(
    mo_hinh: str,
    tep: str,
    dong_dau: int,
    van_ban_khuc: str,
    so: SoChiPhi,
    nhan: str,
) -> tuple[list[UngVien], KetQuaGoi]:
    sach, _ = che_du_lieu.sach(van_ban_khuc)
    kq = goi(
        mo_hinh,
        [
            {"role": "system", "content": HE_THONG},
            {"role": "user", "content": f"Tệp: {tep}\n\n{sach}"},
        ],
        so=so,
        nhan=nhan,
        them=tham_so_cho(mo_hinh),
    )
    ra: list[UngVien] = []
    for d in doc_json(kq.van_ban)[:5]:
        tu = int(_so(d.get("dong_tu"), dong_dau))
        den = int(_so(d.get("dong_den"), tu))
        ra.append(
            UngVien(
                tep=tep,
                dong_tu=tu,
                dong_den=max(den, tu),
                loai=str(d.get("loai", ""))[:40],
                co_che=str(d.get("co_che", ""))[:600],
                kich_ban=str(d.get("kich_ban", ""))[:600],
                trich_dan=str(d.get("trich_dan", ""))[:300],
                do_chac=max(0.0, min(1.0, _so(d.get("do_chac"), 0.3))),
                mo_hinh=mo_hinh,
            )
        )
    return ra, kq
