"""THƯỚC ĐO — model có tìm lại được các lỗi đã biết không (recall)?

Nguồn: `ban-giao-1710/THUOC-DO-QUET-AI-KHO-LOI-DA-BIET.md` (20 lỗi, mỗi lỗi có commit
sửa). Với mỗi lỗi ta đưa cho model **tệp ở NGAY TRƯỚC commit sửa** (`sha^:tệp`) —
model không thấy bản sửa, không thấy lịch sử, không thấy tài liệu kể lỗi — và đề bài
không gợi ý lỗi nào. Model bắt được khi:

  1. phát hiện nằm trong ±40 dòng quanh chỗ commit sửa đã đổi (vị trí), VÀ
  2. một model THẨM PHÁN khác (rẻ) xác nhận mô tả đúng cơ chế lỗi (cơ chế).

Thẩm phán tự động có thể sai — lấy mẫu duyệt tay (file `tom-tat.md` liệt kê từng
phát hiện trúng để người đối chiếu). Cỡ mẫu 20 nên mọi tỉ lệ phải đọc kèm khoảng tin
cậy; con số không phải để khoe mà để CHỌN model và biết tin tầng model tới đâu.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import chi_phi, soat_model
from .che_du_lieu import duoc_gui
from .chi_phi import LoiGoiError, SoChiPhi, TuChoiError
from .khach import goi

DUNG_SAI_DONG = 40
#: Thẩm phán phải là model KHÔNG suy nghĩ ẩn (V4.1-Flash trả rỗng → thẩm phán luôn "0",
#: làm sai cả thước đo; đã mắc ở lượt đo đầu 18/10).
THAM_PHAN = "MiniMaxAI/MiniMax-M3:novita"

#: Cơ chế đáp án — viết lại từ bảng của kho lỗi, KHÔNG đưa cho model soát.
CO_CHE: dict[str, tuple[str, str]] = {
    "P1": (
        "P",
        "Đơn vị lô (hộp) khác đơn vị bán (gói/viên): giao thuốc lọc lô theo đơn vị "
        "bán nên không lô nào khớp, thuốc đã giao và tính tiền mà không trừ kho.",
    ),
    "P2": (
        "P",
        "Ghép số lượng với đơn vị mà không kiểm chữ gõ đã kết thúc bằng đơn vị: "
        "gõ '2 gói' + đơn vị 'gói' thành 'gói gói'.",
    ),
    "P3": (
        "P",
        "signOut() không tham số mặc định phạm vi global: một người đăng xuất thì "
        "mọi thiết bị dùng chung tài khoản đều bị đá ra.",
    ),
    "P4": (
        "P",
        "Trigger notify_row_change bắn ở MỌI UPDATE của phiếu khám (kể cả tự lưu), "
        "làm mọi màn của mọi người dựng lại; chỉ nên báo khi đổi trường quan trọng.",
    ),
    "P5": (
        "P",
        "Trang /patients/new là màn tự tải nhưng không có trong danh sách "
        "MAN_TU_TAI nên bị router.refresh() dựng lại liên tục.",
    ),
    "P6": (
        "P",
        "Thiếu trần giá trị cho số lượng/giá nhập: số cực lớn vượt cột numeric của "
        "Postgres gây HTTP 500 thay vì lỗi 422 báo người dùng.",
    ),
    "P7": (
        "P",
        "Hạn dùng gõ sai bị nuốt im lặng thành 'chưa có hạn' (hoặc dd/mm/yyyy đọc "
        "sai) thay vì báo lỗi.",
    ),
    "P8": ("P", "Kiểm kê ca nhận một đơn vị chưa từng có lô nào — thiếu kiểm đơn vị."),
    "P9": (
        "P",
        "Điều chỉnh kiểm kê không áp được dòng nào nhưng vẫn đánh dấu phiếu đã "
        "điều chỉnh (không điều kiện) nên phiếu kẹt, không hoàn tác được.",
    ),
    "P10": (
        "P",
        "Lỗi 422 của pydantic chỉ có `detail`, không có `message` tiếng Việt nên "
        "giao diện chỉ hiện 'Máy chủ từ chối'.",
    ),
    "P11": ("P", "Ô 'Tổng tồn' cộng lẫn các đơn vị khác nhau (hộp cộng với viên)."),
    "P12": (
        "P",
        "Lỗi khi thêm mặt hàng ở quầy bán hiện ở chỗ người dùng không nhìn/không "
        "cuộn tới nên họ không biết thao tác thất bại.",
    ),
    "H1": (
        "H",
        "Nhánh lượt cũ ('old') của bảng quầy thu không còn LIMIT: kéo hàng nghìn "
        "lượt cũ có đơn thuốc chưa thu, truy vấn mất ~40 giây.",
    ),
    "H2": (
        "H",
        "Quét tem báo sai lý do khi lô không dùng được vì lệch đơn vị hộp/gói "
        "(thông báo không nêu đúng nguyên nhân).",
    ),
    "N1": (
        "N",
        "Gõ 'Viên' cho thuốc bán theo 'viên' thì lô lưu đúng chữ người gõ ('Viên') "
        "thay vì chữ chuẩn của danh mục, màn hiện hai cách viết.",
    ),
    "N2": (
        "N",
        "Hệ số quy đổi rác ('abc', '-5'): máy chủ báo lỗi nhưng giao diện vẫn hiện "
        "kết quả '= 10 gói' của lần xem trước (nói dối người nhập).",
    ),
    "T1": (
        "T",
        "Bộ phát hiện chỉ lấy 200 dòng đầu (LIMIT) nên bài test đỏ chập chờn tuỳ "
        "thứ tự chạy khi DB có dữ liệu dư.",
    ),
    "T2": (
        "T",
        "Test hàng loạt dùng tiền tố tên trùng với bài đếm 84 dòng vật tư nên hai "
        "file test chung DB làm lệch số đếm.",
    ),
    "T3": (
        "T",
        "Bài DB giả định phòng khám sạch nhưng chạy song song chung DB: dữ liệu dư "
        "từ bài khác làm kết quả chập chờn.",
    ),
    "T4": (
        "T",
        "Bảng tạm drug_batch trong bài test thiếu cột noi_chua nên bài lỗi trên "
        "môi trường CI khác.",
    ),
}


@dataclass(frozen=True)
class Ca:
    sha_sua: str
    tep: str  # tệp tại sha^ (None nếu tìm theo tiền tố tên)
    loi: tuple[str, ...]
    #: tìm tệp theo tiền tố tên trong thư mục (dùng cho migration cũ)
    tien_to: str | None = None


PH = "src/clinicai/services/pharmacy_service.py"
KHO = "src/clinicai/services/kho_thuoc_service.py"
INV = "src/dashboard/app/(dashboard)/pharmacy/inventory"
CAC_CA: tuple[Ca, ...] = (
    Ca("4f26d64a", PH, ("P1",)),
    Ca("4f26d64a", KHO, ("P1",)),
    Ca("6d382ca4", "src/dashboard/lib/phieu-kham.ts", ("P2",)),
    Ca("8b55a345", "src/dashboard/app/(auth)/login/actions.ts", ("P3",)),
    Ca("3a2ae530", "supabase/migrations/", ("P4",), "20261010100001"),
    Ca("79f179e8", "src/dashboard/lib/man-tu-tai.ts", ("P5",)),
    Ca("0a85404c", KHO, ("P6", "P7")),
    Ca("0a85404c", "src/clinicai/services/vat_tu_kho_service.py", ("P6",)),
    Ca("0a85404c", PH, ("P6", "P7")),
    Ca("0a85404c", "src/clinicai/services/kiem_ke_ca_service.py", ("P8", "P9")),
    Ca("0a85404c", "src/clinicai/main.py", ("P10",)),
    Ca("0a85404c", f"{INV}/InventoryBoard.tsx", ("P11",)),
    Ca("0a85404c", "src/dashboard/app/(dashboard)/thu-ngan/ChinhDonQuay.tsx", ("P12",)),
    Ca("413ee011", "src/clinicai/services/cashier_board_service.py", ("H1",)),
    Ca("a1f7684b", "src/clinicai/services/ban_thuoc_service.py", ("H2",)),
    Ca("3306dc94", PH, ("N1",)),
    Ca("ba542139", f"{INV}/QuyDoiNhap.tsx", ("N2",)),
    Ca("3a04cda7", "src/tests/services/test_agent_giam_sat_db.py", ("T1",)),
    Ca("4a63a3a3", "src/tests/services/test_vat_tu_hang_loat_db.py", ("T2",)),
    Ca("03e60baa", "src/tests/services/test_canh_bao_han_lo_db.py", ("T3",)),
    Ca("03e60baa", "src/tests/services/test_tiep_don_gio_thuc_db.py", ("T3",)),
    Ca("03e60baa", "src/tests/services/test_vat_tu_ban_them_db.py", ("T3",)),
    Ca("dfa0d21e", "src/tests/services/test_pharmacy_dispense_units_db.py", ("T4",)),
)

GIT = "/usr/bin/git"
LENH_GIT_DOC = {"show", "diff", "ls-tree"}  # chỉ đọc


def _git(goc: Path, *args: str) -> str:
    if args[0] not in LENH_GIT_DOC:
        raise ValueError(f"lệnh git không phải chỉ-đọc: {args[0]}")
    r = subprocess.run(  # noqa: S603 — danh sách đối số cố định, không shell
        [GIT, *args], cwd=goc, capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        raise FileNotFoundError(r.stderr.strip()[:200])
    return r.stdout


def lay_tep(goc: Path, ca: Ca) -> tuple[str, str]:
    """(đường dẫn thật, nội dung) của tệp tại NGAY TRƯỚC commit sửa."""
    duong = ca.tep
    if ca.tien_to:
        ds = _git(goc, "ls-tree", "--name-only", f"{ca.sha_sua}^", ca.tep).split()
        duong = next(d for d in ds if Path(d).name.startswith(ca.tien_to))
    return duong, _git(goc, "show", f"{ca.sha_sua}^:{duong}")


RE_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+")


def vung_sua(goc: Path, ca: Ca, duong: str) -> list[tuple[int, int]] | None:
    """Các khoảng dòng (phiên bản CŨ) mà commit sửa đã đổi; None = cả tệp."""
    if ca.tien_to:
        return None
    out = _git(goc, "diff", "-U0", f"{ca.sha_sua}^", ca.sha_sua, "--", duong)
    ra = []
    for d in out.splitlines():
        m = RE_HUNK.match(d)
        if m:
            a = int(m.group(1))
            n = int(m.group(2)) if m.group(2) is not None else 1
            ra.append((a, a + max(n, 1) - 1))
    return ra


def trung_vi_tri(u: soat_model.UngVien, vung: list[tuple[int, int]] | None) -> bool:
    if vung is None:
        return True
    return any(
        u.dong_tu <= hi + DUNG_SAI_DONG and u.dong_den >= lo - DUNG_SAI_DONG
        for lo, hi in vung
    )


def tham_phan(so: SoChiPhi, ung: soat_model.UngVien, ds_loi: tuple[str, ...]) -> str:
    """Trả mã lỗi đã biết mà phát hiện mô tả, hoặc '' nếu không khớp lỗi nào."""
    muc = "\n".join(f"{i + 1}. [{m}] {CO_CHE[m][1]}" for i, m in enumerate(ds_loi))
    msg = (
        "Dưới đây là các lỗi ĐÃ BIẾT trong một đoạn mã và MỘT phát hiện của "
        "người soát.\n"
        f"LỖI ĐÃ BIẾT:\n{muc}\n\nPHÁT HIỆN:\nCơ chế: {ung.co_che}\n"
        f"Kịch bản: {ung.kich_ban}\n\nPhát hiện có mô tả ĐÚNG CƠ CHẾ của một lỗi "
        "đã biết không (cùng nguyên nhân gốc, không chỉ cùng khu vực)? Trả đúng một "
        f"con số: số thứ tự lỗi (1-{len(ds_loi)}) nếu khớp, hoặc 0 nếu không."
    )
    kq = goi(
        THAM_PHAN,
        [{"role": "user", "content": msg}],
        so=so,
        max_tokens=1500,
        nhan="tham-phan",
        them=soat_model.tham_so_cho(THAM_PHAN),
    )
    if not (kq.van_ban or "").strip():
        raise LoiGoiError("thẩm phán trả rỗng")  # KHÔNG coi là "không khớp"
    m = re.search(r"\d+", kq.van_ban or "")
    k = int(m.group()) if m else 0
    return ds_loi[k - 1] if 1 <= k <= len(ds_loi) else ""


def chay_mot_mo_hinh(
    goc: Path,
    mo_hinh: str,
    so: SoChiPhi,
    thu_muc: Path,
    cac_ca: tuple[Ca, ...] = CAC_CA,
    song_song: int = 4,
) -> dict[str, object]:
    ten_an = re.sub(r"[^A-Za-z0-9.]+", "_", mo_hinh)
    t0 = time.time()
    da_tieu_dau = so.theo_mo_hinh.get(mo_hinh, 0.0)
    viec: list[tuple[int, str, int, str]] = []
    tep_ca: dict[int, tuple[str, list[tuple[int, int]] | None]] = {}
    bo_qua: list[str] = []
    for i, ca in enumerate(cac_ca):
        try:
            duong, nd = lay_tep(goc, ca)
        except (FileNotFoundError, StopIteration):
            bo_qua.append(f"{ca.sha_sua}:{ca.tep}")
            continue
        if not duoc_gui(duong):
            bo_qua.append(f"{duong} (bị bộ lọc cấm)")
            continue
        tep_ca[i] = (duong, vung_sua(goc, ca, duong))
        for dong_dau, khuc in soat_model.cat_khuc(nd):
            viec.append((i, duong, dong_dau, khuc))

    ung_theo_ca: dict[int, list[soat_model.UngVien]] = {i: [] for i in tep_ca}
    rong = loi = 0
    dung_vi = ""
    dem = {"khuc_loi_goi": 0, "khuc_tra_rong": 0}

    def lam(
        v: tuple[int, str, int, str],
    ) -> tuple[int, list[soat_model.UngVien] | None]:
        i, duong, dong_dau, khuc = v
        try:
            ds, kq = soat_model.soat_mot_khuc(
                mo_hinh, duong, dong_dau, khuc, so, f"thuoc-do:{cac_ca[i].loi[0]}"
            )
        except TuChoiError as e:
            nonlocal dung_vi
            dung_vi = str(e)
            return i, None
        except Exception:  # noqa: BLE001 — một khúc lỗi không giết cả lượt đo
            dem["khuc_loi_goi"] += 1
            return i, []
        if not kq.van_ban.strip():
            dem["khuc_tra_rong"] += 1  # thường: model suy nghĩ hết ngân sách token
            return i, []
        return i, ds

    with ThreadPoolExecutor(max_workers=song_song) as ex:
        for i, ds in ex.map(lam, viec):
            if ds is None:
                loi += 1
            else:
                ung_theo_ca[i] += ds
    rong = sum(1 for ds in ung_theo_ca.values() if not ds)

    trung: dict[str, dict[str, object]] = {}
    tong_ung = 0
    for i, ds in ung_theo_ca.items():
        ca = cac_ca[i]
        duong, vung = tep_ca[i]
        tong_ung += len(ds)
        for u in ds:
            if not trung_vi_tri(u, vung):
                continue
            try:
                ma = tham_phan(so, u, ca.loi)
            except TuChoiError as e:
                dung_vi = str(e)
                break
            except LoiGoiError:
                dem["tham_phan_loi"] = dem.get("tham_phan_loi", 0) + 1
                continue
            if ma and ma not in trung:
                trung[ma] = {
                    "tep": duong,
                    "dong": [u.dong_tu, u.dong_den],
                    "co_che_model": u.co_che,
                    "kich_ban": u.kich_ban,
                    "do_chac": u.do_chac,
                }
    (thu_muc / f"ung-vien-{ten_an}.json").write_text(
        json.dumps(
            {str(i): [u.__dict__ for u in ds] for i, ds in ung_theo_ca.items()},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf8",
    )
    return {
        "mo_hinh": mo_hinh,
        "trung": trung,
        "tong_loi": len(CO_CHE),
        "so_trung": len(trung),
        "tong_ung_vien": tong_ung,
        "khuc_loi_do_tran_hoac_dung": loi,
        "tep_khong_ung_vien": rong,
        "so_khuc": len(viec),
        **dem,
        "bo_qua": bo_qua,
        "dung_vi": dung_vi,
        "usd": round(so.theo_mo_hinh.get(mo_hinh, 0.0) - da_tieu_dau, 4),
        "giay": round(time.time() - t0),
    }


def tom_tat(ket_qua: list[dict[str, object]]) -> str:
    nhom = {n: [m for m, (g, _) in CO_CHE.items() if g == n] for n in "PHNT"}
    dong = [
        "| Model | Trúng | P (12) | H (2) | N (2) | T (4) | Ứng viên | USD | Giây |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for k in ket_qua:
        t = set(k["trung"])  # type: ignore[call-overload]
        cot = [f"{len(t & set(v))}/{len(v)}" for v in nhom.values()]
        ghi = " ⚠ dừng sớm" if k["dung_vi"] else ""
        dong.append(
            f"| `{k['mo_hinh']}`{ghi} | **{k['so_trung']}/{k['tong_loi']}** | "
            + " | ".join(cot)
            + f" | {k['tong_ung_vien']} | {k['usd']} | {k['giay']} |"
        )
    dong.append("\n### Chi tiết lỗi bắt được (để người đối chiếu cơ chế)\n")
    for k in ket_qua:
        dong.append(f"**{k['mo_hinh']}**")
        for ma, d in sorted(k["trung"].items()):  # type: ignore[attr-defined]
            dong.append(f"- {ma} @ {d['tep']}:{d['dong'][0]} — {d['co_che_model']}")
        thieu = sorted(set(CO_CHE) - set(k["trung"]))  # type: ignore[call-overload]
        dong.append(f"- *trượt:* {', '.join(thieu) or '(không)'}\n")
    return "\n".join(dong)


__all__ = ["CO_CHE", "CAC_CA", "chay_mot_mo_hinh", "tom_tat", "chi_phi"]
