"""Bộ quét: route GHI mà không thấy cửa quyền nào chặn.

Lego quyền chỉ có nghĩa khi MỌI đường ghi đi qua một cửa hỏi `can(...)`. Một route
ghi quên cửa là chỗ ai đăng nhập cũng bấm được (P0). Bộ quét không chứng minh
route thiếu cửa — nó báo "tôi đã theo dõi 4 tầng lời gọi mà không thấy câu hỏi
quyền nào"; người xem mở hàm ra kiểm. Vì vậy mức bằng chứng luôn là `suy_ra`.

Nhận ra cửa: `cua_quyen(...)` / `require_role*(...)` ở tham số hoặc trong biến cấp
module (vd `_GHI = cua_quyen(...)`), `can(...)` trong thân hàm hoặc hàm nó gọi, và
mọi `Depends(...)` trỏ tới hàm có một trong các thứ trên.
"""

from __future__ import annotations

import ast

from ..khuon import (
    DoPhu,
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from ..nguon import FuncNode, Nguon, ten_goi

TEN = "cua_route"
GHI = {"POST", "PUT", "PATCH", "DELETE"}
NHA_MAY_CUA = {"cua_quyen", "require_role", "require_role_co_the_mo"}
HAM_KIEM = {
    "can",
    "can_o_phong_nao_do",
    "co_quyen",
    "quyen_hieu_luc",
    "kiem_quyen",
    "yeu_cau_quyen",
    "assert_role",
}
#: Công khai CÓ CHỦ Ý — nơi cấp token không thể đòi token.
CONG_KHAI = {"/api/v1/auth/login"}


def _thuoc_tinh_vai(n: ast.AST) -> bool:
    return isinstance(n, ast.Attribute) and n.attr in ("role", "vai_tro", "roles")


def _co_cau_hoi_quyen(fn: FuncNode) -> bool:
    for x in ast.walk(fn):
        if isinstance(x, ast.Call):
            t = ten_goi(x.func)
            if t in HAM_KIEM or t in NHA_MAY_CUA:
                return True
            if t and t.startswith(("can_", "kiem_quyen", "require_")):
                return True
        if _thuoc_tinh_vai(x):
            return True
    return False


def _ten_cua(nguon: Nguon) -> set[str]:
    """Tên (trần, toàn repo) là cửa: `X = cua_quyen(...)`, rồi mọi bí danh
    `Y = X` hoặc `Z = Depends(X)`, lặp tới khi không thêm được nữa — vì cửa
    thường định nghĩa một nơi (`cua_ghi_y_khoa`) và router khác import lại."""
    ra: set[str] = set()
    cac_gan = [
        (n.value, [t.id for t in n.targets if isinstance(t, ast.Name)])
        for cay in nguon.cay_py.values()
        for n in cay.body
        if isinstance(n, ast.Assign)
    ]
    for _ in range(5):
        them = False
        for v, dich in cac_gan:
            la_cua = False
            if isinstance(v, ast.Call):
                f = ten_goi(v.func)
                if f in NHA_MAY_CUA:
                    la_cua = True
                elif f == "Depends" and v.args:
                    a0 = v.args[0]
                    la_cua = ten_goi(a0) in ra or (
                        isinstance(a0, ast.Call) and ten_goi(a0.func) in NHA_MAY_CUA
                    )
            elif isinstance(v, ast.Name):
                la_cua = v.id in ra
            if la_cua and not set(dich) <= ra:
                ra.update(dich)
                them = True
        if not them:
            break
    return ra


def _tim_ham(cay: ast.Module, ten: str, dong: int) -> FuncNode | None:
    for n in ast.walk(cay):
        if (
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == ten
            and n.lineno == dong
        ):
            return n
    return None


def _co_cua(nguon: Nguon, fn: FuncNode, cua: set[str]) -> bool:
    for m in [fn, *(m for _, m in nguon.dong_cua_ham(fn))]:
        for x in ast.walk(m):
            if not isinstance(x, ast.Call):
                continue
            f = ten_goi(x.func)
            if f in NHA_MAY_CUA:
                return True
            if f == "Depends" and x.args and ten_goi(x.args[0]) in cua:
                return True
        if _co_cau_hoi_quyen(m):
            return True
    return False


def quet(nguon: Nguon) -> tuple[list[PhatHien], DoPhu]:
    ham = nguon.routes
    do = DoPhu(TEN)
    ra: list[PhatHien] = []
    n_ghi = n_cua = 0
    cua = _ten_cua(nguon)
    for h in ham:
        if h.method not in GHI:
            continue
        n_ghi += 1
        cay = nguon.cay_py.get(h.tep)
        if cay is None:
            continue
        if h.duong in CONG_KHAI or h.da_nghi:
            n_cua += 1
            continue
        fn = _tim_ham(cay, h.ten, h.dong)
        if fn is None:
            continue
        if _co_cua(nguon, fn, cua):
            n_cua += 1
            continue
        rel = nguon.tuong_doi(h.tep)
        ra.append(
            PhatHien(
                bo_quet=TEN,
                khoa=f"{h.method} {h.duong}",
                loai=LoaiVanDe.LOGIC_CO_VAN_DE,
                uu_tien=UuTien.P0,
                muc_bang_chung=MucBangChung.SUY_RA,
                do_chac=0.5,
                tinh_huong=(
                    f"Route ghi `{h.method} {h.duong}` ({rel}:{h.dong}, hàm "
                    f"`{h.ten}`) không thấy cửa quyền nào: không `cua_quyen`, "
                    "không `can(...)` trong hàm hay 4 tầng hàm nó gọi."
                ),
                bang_chung=[
                    f"{rel}:{h.dong} — không tham số Depends(cua_quyen/require_role)",
                    "theo dõi 4 tầng lời gọi theo tên hàm: không gặp can/co_quyen/"
                    "require_*/.role",
                ],
                rui_ro=(
                    "Nếu đúng là không có cửa: mọi tài khoản đã đăng nhập (kể cả vai "
                    "không được cấp lego tương ứng) gọi được lệnh ghi này."
                ),
                de_xuat=(
                    "Mở hàm kiểm: (a) có cửa đi qua đường script không theo được "
                    "(middleware, SQL) → thêm vào CONG_KHAI/ghi chú; (b) thật sự "
                    "thiếu → thêm `cua_quyen(<mã quyền>)` đúng khối công việc."
                ),
                nguoi_chiu_trach_nhiem="Tuyền (dev) soát; Quang chốt vai nào được ghi",
                thoi_diem="Trước đợt lên prod kế tiếp",
                ket_qua_mong_doi="Route có cửa, hoặc được ghi là công khai có chủ ý",
                cach_xac_nhan="Chạy lại bộ quét cua_route: phát hiện biến mất; "
                "thêm bài HTTP 403 cho vai không có quyền",
                phuong_an_khac="Gắn cửa ở cấp router (`dependencies=`) cho cả nhóm",
                trich_dan=[TrichDan(rel, h.dong, nguon.dong_thu(h.tep, h.dong))],
                muc_viec=3,
            )
        )
    do.da_nhin = {"route ghi": n_ghi, "route ghi có cửa/công khai chủ ý": n_cua}
    do.khong_nhin_duoc = [
        "cửa đặt ở proxy Next (src/dashboard/proxy.ts) hoặc middleware FastAPI",
        "kiểm quyền bằng RLS/SQL thuần không qua Python",
        "route GET (chỉ xét lệnh ghi)",
        "lời gọi hàm qua biến/hàm bậc cao (chỉ theo tên trực tiếp, 4 tầng)",
    ]
    return ra, do
