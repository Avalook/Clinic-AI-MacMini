"""Quét TOÀN BỘ mã bằng model: đọc → gom → bác bỏ → phát hiện cho người duyệt.

Bốn bước, mỗi bước loại bớt ồn:

1. ĐỌC   mỗi tệp (đã lọc, đã che) cắt khúc, 1–2 model rẻ khác họ đọc độc lập.
2. GOM   ứng viên cùng chỗ (≤ 15 dòng) gộp thành một nhóm; nhiều model cùng chỉ ra
         một chỗ → độ chắc tăng (đồng thuận chéo họ model).
3. TRÍCH DẪN  dòng model trích phải CÓ THẬT trong tệp. Số dòng lệch thì script tìm
         lại theo nội dung; không tìm thấy = bịa → loại, không đến người.
4. BÁC BỎ   một model mạnh hơn được yêu cầu CỐ BÁC BỎ từng nhóm (đọc rộng ±60 dòng,
         tìm chỗ đã xử lý trường hợp đó). Kết luận "sai" → loại kèm lý do.

Sổ `da-doc.jsonl` ghi tệp+băm nội dung+model đã đọc: chạy lại không đọc lại tệp
chưa đổi (tiết kiệm tiền, và để agent chạy từng đợt có điểm dừng).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..khuon import (
    LoaiVanDe,
    MucBangChung,
    PhatHien,
    TrichDan,
    UuTien,
)
from ..nguon import Nguon
from . import che_du_lieu, soat_model
from .chi_phi import SoChiPhi, TuChoiError
from .khach import goi

#: Đường dẫn rủi ro cao (tiền, kho, lịch, quyền, đăng nhập) — đọc trước, mức việc 3.
TU_KHOA_RUI_RO = (
    "pharmacy",
    "kho_",
    "vat_tu",
    "inventory",
    "payment",
    "cashier",
    "thu_ngan",
    "thu-ngan",
    "hoa_don",
    "hoa-don",
    "refund",
    "hoan_",
    "so_no",
    "cong_no",
    "permission",
    "phan_quyen",
    "auth",
    "identity",
    "booking",
    "migrations",
)
GOP_DONG = 15
DUOI_NGUON = (".py", ".ts", ".tsx", ".sql")
LOAI_UU_TIEN = {
    "mat_du_lieu": UuTien.P0,
    "du_lieu_sai": UuTien.P1,
    "logic_sai": UuTien.P1,
    "loi_an": UuTien.P4,
    "lego_thieu_lien_ket": UuTien.P5,
    "hieu_nang": UuTien.P6,
}
LOAI_KHUON = {
    "mat_du_lieu": LoaiVanDe.MAT_DU_LIEU,
    "du_lieu_sai": LoaiVanDe.DU_LIEU_SAI,
    "logic_sai": LoaiVanDe.LOGIC_CO_VAN_DE,
    "loi_an": LoaiVanDe.LOGIC_CO_VAN_DE,
    "lego_thieu_lien_ket": LoaiVanDe.LEGO_THIEU_LIEN_KET,
    "hieu_nang": LoaiVanDe.DE_XUAT_CAI_TIEN,
}


def la_rui_ro(duong: str) -> bool:
    d = duong.lower()
    return any(k in d for k in TU_KHOA_RUI_RO)


def chon_tep(
    nguon: Nguon,
    tien_to: tuple[str, ...] | None = None,
    chi_rui_ro: bool = False,
    bo_migration: bool = False,
) -> list[Path]:
    """Mã nguồn cần đọc, rủi ro cao trước, tệp lớn sau; bỏ test, sinh tự động."""
    cac: list[Path] = []
    for goc in (nguon.py, nguon.dash / "app", nguon.dash / "lib", nguon.migrations_dir):
        if not goc.is_dir():
            continue
        for p in goc.rglob("*"):
            if p.suffix not in DUOI_NGUON or not p.is_file():
                continue
            rel = nguon.tuong_doi(p)
            if any(x in p.parts for x in ("node_modules", ".next", "__pycache__")):
                continue
            if "/tests/" in rel or rel.endswith((".test.mts", ".test.ts", ".d.ts")):
                continue
            if not che_du_lieu.duoc_gui(rel):
                continue
            if tien_to and not rel.startswith(tien_to):
                continue
            if chi_rui_ro and not la_rui_ro(rel):
                continue
            if bo_migration and rel.endswith(".sql"):
                continue
            cac.append(p)
    return sorted(cac, key=lambda p: (not la_rui_ro(str(p)), -p.stat().st_size))


def _bam(nd: str) -> str:
    return hashlib.sha1(nd.encode()).hexdigest()[:12]


def doc_da_lam(duong: Path) -> set[tuple[str, str, str]]:
    ra: set[tuple[str, str, str]] = set()
    if duong.is_file():
        for d in duong.read_text(encoding="utf8").splitlines():
            try:
                x = json.loads(d)
                ra.add((x["tep"], x["bam"], x["mo_hinh"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return ra


def doc_tat_ca(
    nguon: Nguon,
    cac_tep: list[Path],
    mo_hinh: list[str],
    so: SoChiPhi,
    thu_muc: Path,
    song_song: int = 4,
) -> tuple[list[soat_model.UngVien], str]:
    """Đọc từng tệp bằng từng model. Trả (ứng viên mới, lý do dừng nếu có)."""
    tho = thu_muc / "ung-vien-tho.jsonl"
    da = thu_muc / "da-doc.jsonl"
    xong = doc_da_lam(da)
    viec: list[tuple[str, str, str, int, str]] = []
    for p in cac_tep:
        rel = nguon.tuong_doi(p)
        nd = nguon.doc(p)
        b = _bam(nd)
        for m in mo_hinh:
            if (rel, b, m) in xong:
                continue
            for dong_dau, khuc in soat_model.cat_khuc(nd):
                viec.append((rel, b, m, dong_dau, khuc))
    ra: list[soat_model.UngVien] = []
    dung = ""

    def lam(v: tuple[str, str, str, int, str]) -> list[soat_model.UngVien] | None:
        nonlocal dung
        rel, _b, m, dong_dau, khuc = v
        try:
            ds, _ = soat_model.soat_mot_khuc(m, rel, dong_dau, khuc, so, "soat:doc")
            return ds
        except TuChoiError as e:
            dung = str(e)
            return None
        except Exception:  # noqa: BLE001 — một khúc lỗi không giết cả đợt
            return None

    hoan_tat: dict[tuple[str, str, str], int] = defaultdict(int)
    tong_khuc: dict[tuple[str, str, str], int] = defaultdict(int)
    for rel, b, m, _d, _k in viec:
        tong_khuc[(rel, b, m)] += 1
    with ThreadPoolExecutor(max_workers=song_song) as ex:
        for v, kq in zip(viec, ex.map(lam, viec), strict=True):
            khoa = (v[0], v[1], v[2])
            if kq is None:
                continue
            hoan_tat[khoa] += 1
            ra += kq
            with tho.open("a", encoding="utf8") as f:
                for u in kq:
                    f.write(json.dumps(u.__dict__, ensure_ascii=False) + "\n")
            # Chỉ ghi 'đã đọc' khi đủ MỌI khúc của tệp (không đọc dở rồi coi là xong).
            if hoan_tat[khoa] == tong_khuc[khoa]:
                with da.open("a", encoding="utf8") as f:
                    f.write(
                        json.dumps(
                            {"tep": v[0], "bam": v[1], "mo_hinh": v[2]},
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
    return ra, dung


def doc_lai_tho(duong: Path) -> list[soat_model.UngVien]:
    if not duong.is_file():
        return []
    ra = []
    for d in duong.read_text(encoding="utf8").splitlines():
        try:
            ra.append(soat_model.UngVien(**json.loads(d)))
        except (json.JSONDecodeError, TypeError):
            continue
    return ra


_KHOANG = re.compile(r"\s+")


def dinh_vi_lai(nguon: Nguon, rel: str, u: soat_model.UngVien) -> int | None:
    """Dòng thật của trích dẫn. Gần `dong_tu` thì giữ; lệch thì tìm theo nội dung;
    không có trong tệp thì None (model bịa)."""
    quote = _KHOANG.sub(" ", u.trich_dan).strip()
    if len(quote) < 6:
        return None
    ds = nguon.doc(nguon.goc / rel).splitlines()
    gan = [
        i
        for i, d in enumerate(ds, 1)
        if quote in _KHOANG.sub(" ", d) or _KHOANG.sub(" ", d).strip() in quote
        if len(_KHOANG.sub(" ", d).strip()) >= 6
    ]
    if not gan:
        return None
    return min(gan, key=lambda i: abs(i - u.dong_tu))


def gom(
    nguon: Nguon, ung: list[soat_model.UngVien]
) -> tuple[list[list[tuple[soat_model.UngVien, int]]], int]:
    """Nhóm ứng viên cùng chỗ. Trả (nhóm, số ứng viên bị loại vì trích dẫn bịa)."""
    theo_tep: dict[str, list[tuple[soat_model.UngVien, int]]] = defaultdict(list)
    bia = 0
    for u in ung:
        dong = dinh_vi_lai(nguon, u.tep, u)
        if dong is None:
            bia += 1
            continue
        theo_tep[u.tep].append((u, dong))
    nhom: list[list[tuple[soat_model.UngVien, int]]] = []
    for ds in theo_tep.values():
        ds.sort(key=lambda x: x[1])
        cur: list[tuple[soat_model.UngVien, int]] = []
        for u, d in ds:
            if cur and d > max(x[1] for x in cur) + GOP_DONG:
                nhom.append(cur)
                cur = []
            cur.append((u, d))
        if cur:
            nhom.append(cur)
    return nhom, bia


def _ngu_canh(nguon: Nguon, rel: str, dong: int, rong: int = 60) -> str:
    ds = nguon.doc(nguon.goc / rel).splitlines()
    a, b = max(1, dong - rong), min(len(ds), dong + rong)
    return "\n".join(f"{n:>5}| {ds[n - 1]}" for n in range(a, b + 1))


DE_BAC_BO = """Bạn là kiểm toán viên NGHI NGỜ. Người soát khác nêu một lỗi trong mã \
dưới đây. Việc của bạn là CỐ BÁC BỎ nó: tìm trong đoạn mã (và trong chính dòng được \
nêu) chỗ đã xử lý trường hợp đó, giả định sai của người soát, hoặc lý do kịch bản \
không thể xảy ra. Chỉ khi không bác bỏ được và kịch bản thật sự dẫn tới hậu quả mới \
kết luận đúng.

Trả về MỘT đối tượng JSON, không chữ nào khác:
{"ket_luan": "dung" | "sai" | "khong_chac", "ly_do": "<1-2 câu, chỉ rõ dòng>", \
"do_chac": 0.0-1.0}"""


def bac_bo(
    nguon: Nguon,
    nhom: list[tuple[soat_model.UngVien, int]],
    mo_hinh: str,
    so: SoChiPhi,
) -> dict[str, object]:
    u, dong = max(nhom, key=lambda x: x[0].do_chac)
    msg = (
        f"Tệp: {u.tep}\n\n{che_du_lieu.sach(_ngu_canh(nguon, u.tep, dong))[0]}\n\n"
        f"LỖI ĐƯỢC NÊU (quanh dòng {dong}):\nLoại: {u.loai}\nCơ chế: {u.co_che}\n"
        f"Kịch bản: {u.kich_ban}"
    )
    kq = goi(
        mo_hinh,
        [{"role": "system", "content": DE_BAC_BO}, {"role": "user", "content": msg}],
        so=so,
        max_tokens=2500,
        nhan="soat:bac-bo",
    )
    t = soat_model._THINK.sub("", kq.van_ban)
    a, b = t.find("{"), t.rfind("}")
    try:
        d = json.loads(t[a : b + 1]) if 0 <= a < b else {}
    except json.JSONDecodeError:
        d = {}
    return d if isinstance(d, dict) else {}


def bac_bo_tat_ca(
    nguon: Nguon,
    nhoms: list[list[tuple[soat_model.UngVien, int]]],
    mo_hinh: str,
    so: SoChiPhi,
    song_song: int = 4,
) -> list[dict[str, object]]:
    def lam(n: list[tuple[soat_model.UngVien, int]]) -> dict[str, object]:
        try:
            return bac_bo(nguon, n, mo_hinh, so)
        except TuChoiError as e:
            return {"ket_luan": "chua_kiem", "ly_do": str(e)}
        except Exception:  # noqa: BLE001
            return {"ket_luan": "chua_kiem", "ly_do": "lỗi khi gọi model"}

    with ThreadPoolExecutor(max_workers=song_song) as ex:
        return list(ex.map(lam, nhoms))


def thanh_phat_hien(
    nhom: list[tuple[soat_model.UngVien, int]],
    ket_luan: dict[str, object],
) -> PhatHien:
    u, dong = max(nhom, key=lambda x: x[0].do_chac)
    models = sorted({x[0].mo_hinh.split("/")[-1].split(":")[0] for x in nhom})
    rui_ro_tien_kho = la_rui_ro(u.tep)
    uu_tien = LOAI_UU_TIEN.get(u.loai, UuTien.P1)
    if rui_ro_tien_kho and uu_tien is UuTien.P1 and u.loai == "du_lieu_sai":
        uu_tien = UuTien.P0
    kl = str(ket_luan.get("ket_luan", ""))
    try:
        dc = float(ket_luan.get("do_chac", u.do_chac))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        dc = u.do_chac
    dong_y = min(0.15, 0.07 * (len(models) - 1))  # nhiều họ model cùng chỉ → nhích lên
    do_chac = round(min(0.9, max(0.1, 0.5 * dc + 0.5 * u.do_chac + dong_y)), 2)
    if kl == "khong_chac":
        do_chac = min(do_chac, 0.4)
    muc = (
        MucBangChung.CHUA_BIET
        if kl in ("khong_chac", "chua_kiem")
        else (MucBangChung.SUY_RA)
    )
    return PhatHien(
        bo_quet="model",
        khoa=f"{u.tep}:{dong // 25 * 25}:{u.loai}",
        loai=LOAI_KHUON.get(u.loai, LoaiVanDe.LOGIC_CO_VAN_DE),
        uu_tien=uu_tien,
        muc_bang_chung=muc,
        do_chac=do_chac,
        tinh_huong=f"{u.co_che} (quanh {u.tep}:{dong})",
        bang_chung=[
            f"Kịch bản do model nêu: {u.kich_ban}",
            f"{len(models)} model đọc độc lập chỉ ra chỗ này: {', '.join(models)}",
            "Bước bác bỏ: "
            + (
                f"{kl} — {ket_luan.get('ly_do', '')}"
                if kl
                else "chưa kiểm (hết trần hoặc lỗi)"
            ),
        ],
        rui_ro="Nếu kịch bản đúng: " + u.kich_ban[:300],
        de_xuat=(
            "Người kiểm mở đúng dòng, tự chạy kịch bản trên. Nếu đúng: sửa tối "
            "thiểu + thêm một bài test tái hiện (đột biến phải đỏ trước khi sửa). "
            "Nếu sai: bấm Bỏ qua kèm lý do để lần quét sau không hỏi lại."
        ),
        nguoi_chiu_trach_nhiem="Tuyền (dev) kiểm; Quang chốt nếu đụng luật nghiệp vụ",
        thoi_diem="Theo mức ưu tiên; mức việc 3 cần kế hoạch duyệt trước",
        ket_qua_mong_doi="Kịch bản không còn tái hiện được",
        cach_xac_nhan="Bài test tái hiện kịch bản xanh sau khi sửa; chạy lại bộ quét",
        trich_dan=[TrichDan(u.tep, dong, u.trich_dan[:200])],
        muc_viec=3 if rui_ro_tien_kho else 2,
    )


def doc_xuyen_tep(
    nguon: Nguon,
    paths: list[Path],
    models: list[str],
    so: SoChiPhi,
    folder: Path,
    offline: bool = False,
) -> tuple[list[soat_model.UngVien], str, int]:
    """One bounded bundle per root; failures never become completed reads."""
    from .doc_xuyen_tep import _read
    from .xuyen_tep import BanDo

    graph = BanDo(nguon)
    ledger = folder / "da-doc-xuyen-tep.jsonl"
    raw = folder / "ung-vien-xuyen-tep.jsonl"
    done = doc_da_lam(ledger)
    result: list[soat_model.UngVien] = []
    completed = 0
    stop = ""
    refused = False
    manifests = []
    for path in paths:
        rel = nguon.tuong_doi(path)
        bundle = graph.goi(rel)
        manifests.append(
            {
                "goc": rel,
                "bam": bundle.bam,
                "tep": bundle.tep,
                "bo_qua": bundle.bo_qua,
                "chua_biet": bundle.chua_biet,
                "ky_tu": len(bundle.van_ban),
            }
        )
        for model in models:
            key = (rel, bundle.bam, model)
            model_hash = hashlib.sha256(model.encode()).hexdigest()[:12]
            cache = folder / f"xuyen-{bundle.bam}-{model_hash}.json"
            if not offline and key in done and cache.is_file():
                result.extend(
                    soat_model.UngVien(**d) for d in json.loads(cache.read_text())
                )
                completed += 1
                continue
            if offline:
                continue
            try:
                candidates = _read(model, rel, bundle, so)
            except TuChoiError as exc:
                stop = str(exc)
                refused = True
                break
            except Exception as exc:  # noqa: BLE001 — report failure, never mark complete
                stop = f"{rel}: lỗi đọc {type(exc).__name__}"
                continue
            result.extend(candidates)
            cache.write_text(
                json.dumps([u.__dict__ for u in candidates], ensure_ascii=False),
                encoding="utf8",
            )
            with ledger.open("a", encoding="utf8") as stream:
                stream.write(
                    json.dumps({"tep": rel, "bam": bundle.bam, "mo_hinh": model}) + "\n"
                )
            completed += 1
        if refused:
            break
    (folder / "pham-vi-xuyen-tep.json").write_text(
        json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf8"
    )
    raw.write_text(
        "".join(json.dumps(u.__dict__, ensure_ascii=False) + "\n" for u in result),
        encoding="utf8",
    )
    return result, stop, completed
