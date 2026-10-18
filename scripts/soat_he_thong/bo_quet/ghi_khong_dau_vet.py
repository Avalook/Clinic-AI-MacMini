"""Bộ quét: thao tác GHI không để lại dấu vết.

Hiến pháp §3.4: trạng thái quan trọng phải quan sát được; §8: cái đáng lẽ xuất
hiện mà không xuất hiện cũng là tín hiệu. Một lệnh bấm sửa giá, chuyển phòng,
nhập kho mà không có sự kiện / dòng nhật ký / dòng sổ cái nào thì sau này không
ai trả lời được "ai đổi, lúc nào, từ giá trị nào".

CÁCH XÉT. Với mỗi route ghi, theo dõi hàm nó gọi (5 tầng, theo tên) và tìm MỘT
trong: gọi hàm ghi sự kiện/nhật ký (`emit_event`, `_log`, `ghi_nhat_ky`…), hoặc
SQL `INSERT INTO <bảng sự kiện/sổ cái/lịch sử>` (kể cả SQL nằm ở hằng ngoài
hàm). Không gặp gì → ứng viên. KHÔNG xét: trigger trong database (script không
đọc được trigger sẽ ghi gì), nên mức bằng chứng luôn là `suy_ra`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from ..khuon import (
    DoPhu,
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from ..nguon import FuncNode, Nguon, ten_goi

TEN = "ghi_khong_dau_vet"
GHI = {"POST", "PUT", "PATCH", "DELETE"}
HAM_VET = {
    "emit_event",
    "_log",
    "ghi_nhat_ky",
    "_log_payment_event",
    "ghi_su_kien_vat_tu",
    "ghi_su_kien",
    "log_event",
    "audit",
    "ghi_audit",
}
RE_SQL_VET = re.compile(
    r"INSERT\s+INTO\s+(?:public\.)?\w*"
    r"(?:lich_su|_log|revision|txn|history|event|audit|nhat_ky|receipt)\w*",
    re.IGNORECASE,
)
#: POST dùng để ĐỌC / tính thử (thân lớn không đi query string) — không phải lệnh ghi.
DOC_BANG_POST = (
    "xem-truoc",
    "preview",
    "duplicates",
    "get-summary",
    "find-",
    "read-",
    "/query",
    "classify",
    "transcribe",
    "review",
    "triage",
    "auth/login",
    "/quote",
    "/check",
)
#: Đụng tiền / kho / giá: thiếu dấu vết ở đây là việc P1, mức 3 (CLAUDE.md).
TIEN_KHO = (
    "price",
    "pharmacy",
    "vat-tu",
    "hoa-don",
    "payment",
    "cashier",
    "refund",
    "so-no",
    "thu-ngan",
)
#: Thao tác nhẹ (đã đọc, góp ý, bảng điều khiển nội bộ): nêu ra nhưng ưu tiên thấp.
NHE = ("da-doc", "da-xu-ly", "feedback", "/ops/", "display-settings", "traffic")
#: Mọi route ở router này là bề mặt dev/agent-tool (404 ngoài môi trường dev).
BO_QUA_TEP = ("tools.py",)


def _co_vet(nguon: Nguon, tep: Path, fn: FuncNode) -> bool:
    for p, m in [(tep, fn), *nguon.dong_cua_ham(fn, 5)]:
        for x in ast.walk(m):
            if isinstance(x, ast.Call) and ten_goi(x.func) in HAM_VET:
                return True
        if RE_SQL_VET.search(nguon.van_ban_cua_ham(p, m)):
            return True
    return False


def quet(nguon: Nguon) -> tuple[list[PhatHien], DoPhu]:
    do = DoPhu(TEN)
    ra: list[PhatHien] = []
    n_ghi = n_vet = n_doc = 0
    for r in nguon.routes:
        if r.method not in GHI or r.da_nghi or r.tep.name in BO_QUA_TEP:
            continue
        if any(k in r.duong.lower() for k in DOC_BANG_POST):
            n_doc += 1
            continue
        n_ghi += 1
        cay = nguon.cay_py[r.tep]
        fn = next(
            (
                x
                for x in ast.walk(cay)
                if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                and x.name == r.ten
                and x.lineno == r.dong
            ),
            None,
        )
        if fn is None:
            continue
        if _co_vet(nguon, r.tep, fn):
            n_vet += 1
            continue
        rel = nguon.tuong_doi(r.tep)
        duong = r.duong.lower()
        tien_kho = any(k in duong for k in TIEN_KHO)
        nhe = any(k in duong for k in NHE)
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"{r.method} {r.duong}",
                loai=LoaiVanDe.LOGIC_CO_VAN_DE,
                uu_tien=UuTien.P6 if nhe else UuTien.P1,
                muc_bang_chung=MucBangChung.SUY_RA,
                do_chac=0.55,
                tinh_huong=(
                    f"`{r.method} {r.duong}` ({rel}:{r.dong}) ghi dữ liệu nhưng "
                    "theo 5 tầng lời gọi không thấy sự kiện, dòng nhật ký hay dòng "
                    "sổ cái nào được ghi lại."
                ),
                bang_chung=[
                    f"{rel}:{r.dong} — hàm `{r.ten}`",
                    "không gặp emit_event/_log/ghi_nhat_ky, không INSERT vào bảng "
                    "sự kiện/lịch sử/sổ cái trong hàm hay hàm nó gọi",
                ],
                rui_ro=(
                    "Không truy được ai đổi gì, lúc nào, từ giá trị nào. Với giá, "
                    "kho, phân phòng thì sai lệch về sau không dựng lại được."
                ),
                de_xuat=(
                    "Mở service được gọi: (a) có bảng lịch sử/trigger script không "
                    "thấy → ghi chú vào danh sách bỏ qua; (b) thật sự không có → "
                    "thêm một sự kiện đã khai trong events/catalogue.py hoặc dòng "
                    "nhật ký, kèm giá trị cũ → mới."
                ),
                nguoi_chiu_trach_nhiem="Tuyền (dev); Quang chốt thao tác phải có vết",
                thoi_diem="Ưu tiên theo tiền → kho → phân phòng → còn lại",
                ket_qua_mong_doi="Mỗi lệnh ghi quan trọng có một dấu vết truy được",
                cach_xac_nhan="Bài test gọi route rồi đếm dòng event_log/domain_event; "
                "chạy lại bộ quét ghi_khong_dau_vet",
                phuong_an_khac="Một trigger Postgres ghi lịch sử cho cả bảng (bắt cả "
                "đường ghi ngoài API)",
                trich_dan=[TrichDan(rel, r.dong, nguon.dong_thu(r.tep, r.dong))],
                muc_viec=3 if tien_kho else 2,
            )
        )
    do.da_nhin = {
        "route ghi xét": n_ghi,
        "có dấu vết": n_vet,
        "POST thực chất là đọc (bỏ qua)": n_doc,
    }
    do.khong_nhin_duoc = [
        "trigger Postgres tự ghi lịch sử",
        "lệnh ghi đi qua route Next trực tiếp vào database (đã ghi chú: còn 1 chỗ)",
        "ghi bằng SQL ở hằng nằm ngoài tệp của hàm",
    ]
    return ra, do
