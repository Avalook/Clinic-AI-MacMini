"""Khách gọi model ngoài — CỔNG DUY NHẤT từ máy này ra Internet.

Mọi byte rời máy đi qua `goi()`. Vì vậy hàng rào nằm ở đây, không rải rác:

* Chỉ HTTPS, chỉ tới tên miền trong danh sách cho phép (HF router; AVIS khi người
  dùng cấp `AVIS_BASE_URL`). Không theo chuyển hướng — chuyển hướng sang chỗ khác
  sẽ mang theo header Authorization.
* Khoá đọc từ `~/.config/clinicai-ai/.env.ai` (ngoài repo). KHÔNG BAO GIỜ in, ghi
  log, hay đưa vào thông báo lỗi.
* Nội dung gửi đi phải qua `che_du_lieu.sach()` — đường dẫn cấm bị từ chối, mẫu
  giống khoá/token bị che. Người gọi không có đường nào gửi chuỗi chưa lọc.
* Trần chi tiêu + công tắc dừng (`ket-qua/DUNG`) kiểm TRƯỚC mỗi lần gọi; chi phí
  tính từ `usage` mà nhà cung cấp trả về, ghi sổ sau mỗi lần.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from . import chi_phi
from .chi_phi import LoiGoiError, TuChoiError

DUONG_KHOA = Path.home() / ".config" / "clinicai-ai" / ".env.ai"
#: Nhiều cổng chặn User-Agent mặc định của Python (Cloudflare 403) — tự khai tên.
UA = "clinicai-soat-he-thong/1.0"
HF_URL = "https://router.huggingface.co/v1/chat/completions"
HOST_CHO_PHEP_MAC_DINH = {"router.huggingface.co"}


@dataclass(frozen=True)
class KetQuaGoi:
    van_ban: str
    token_vao: int
    token_ra: int
    usd: float
    giay: float


class _KhongTheoChuyenHuong(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a: object, **_k: object) -> None:
        return None


def _doc_khoa() -> dict[str, str]:
    ra: dict[str, str] = {}
    if not DUONG_KHOA.is_file():
        return ra
    for dong in DUONG_KHOA.read_text(encoding="utf8").splitlines():
        if "=" in dong and not dong.lstrip().startswith("#"):
            k, _, v = dong.partition("=")
            ra[k.strip()] = v.strip().strip("\"'")
    return ra


def _dich(mo_hinh: str) -> tuple[str, str]:
    """(url, tên khoá) cho một mô hình. `avis:<tên>` đi AVIS, còn lại đi HF."""
    if mo_hinh.startswith("avis:"):
        base = _doc_khoa().get("AVIS_BASE_URL", "").rstrip("/")
        if not base:
            raise TuChoiError(
                "Chưa có AVIS_BASE_URL trong .env.ai — chưa gọi AVIS được."
            )
        return base + "/chat/completions", "AVIS_API_KEY"
    return HF_URL, "HF_TOKEN"


def _kiem_url(url: str) -> None:
    p = urlparse(url)
    cho_phep = set(HOST_CHO_PHEP_MAC_DINH)
    base = _doc_khoa().get("AVIS_BASE_URL", "")
    if base:
        cho_phep.add(urlparse(base).hostname or "")
    if p.scheme != "https" or (p.hostname or "") not in cho_phep:
        raise TuChoiError(f"Host không được phép: {p.hostname}")


def goi(
    mo_hinh: str,
    tin_nhan: list[dict[str, str]],
    *,
    so: chi_phi.SoChiPhi,
    max_tokens: int = 4500,
    nhiet_do: float = 0.1,
    nhan: str = "",
    cho_toi_da: int = 240,
    them: dict[str, object] | None = None,
) -> KetQuaGoi:
    so.truoc_khi_goi()  # ném TuChoiError nếu vượt trần hoặc có tệp DUNG
    url, ten_khoa = _dich(mo_hinh)
    _kiem_url(url)
    khoa = _doc_khoa().get(ten_khoa) or os.environ.get(ten_khoa, "")
    if not khoa:
        raise TuChoiError(f"Thiếu {ten_khoa} (đặt trong {DUONG_KHOA}).")
    ten_gui = mo_hinh[5:] if mo_hinh.startswith("avis:") else mo_hinh
    body: dict[str, object] = {
        "model": ten_gui,
        "messages": tin_nhan,
        "max_tokens": max_tokens,
        "temperature": nhiet_do,
    }
    body.update(them or {})  # vd {"reasoning_effort": "low"} cho model suy nghĩ
    than = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        than,
        {
            "Authorization": f"Bearer {khoa}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    tls = urllib.request.HTTPSHandler(context=ssl.create_default_context())
    opener = urllib.request.build_opener(_KhongTheoChuyenHuong, tls)
    t0 = time.time()
    loi_cuoi = ""
    for lan in range(3):
        try:
            with opener.open(req, timeout=cho_toi_da) as r:
                d = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            # KHÔNG đưa nội dung request (có thể chứa mã nguồn) hay header vào lỗi.
            loi_cuoi = f"HTTP {e.code}"
            if e.code in (401, 403):
                raise TuChoiError(f"{ten_khoa} bị từ chối ({e.code}).") from None
            if e.code not in (408, 429, 500, 502, 503, 504):
                raise LoiGoiError(f"{mo_hinh}: {loi_cuoi}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            loi_cuoi = type(e).__name__
        time.sleep(2 * (lan + 1))
    else:
        raise LoiGoiError(f"{mo_hinh}: hết lượt thử ({loi_cuoi})")
    giay = time.time() - t0
    u = d.get("usage") or {}
    vao, ra = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
    usd = so.ghi(mo_hinh, vao, ra, nhan, giay)
    ch = (d.get("choices") or [{}])[0].get("message") or {}
    van_ban = ch.get("content") or ""
    return KetQuaGoi(van_ban, vao, ra, usd, giay)


def liet_ke_mo_hinh_avis() -> list[str]:
    """Danh sách mã model AVIS cho khoá này (GET /models, không tốn token)."""
    base = _doc_khoa().get("AVIS_BASE_URL", "").rstrip("/")
    if not base:
        raise TuChoiError("Chưa có AVIS_BASE_URL trong .env.ai.")
    url = base + "/models"
    _kiem_url(url)
    khoa = _doc_khoa().get("AVIS_API_KEY", "")
    if not khoa:
        raise TuChoiError("Thiếu AVIS_API_KEY.")
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {khoa}", "User-Agent": UA}
    )
    tls = urllib.request.HTTPSHandler(context=ssl.create_default_context())
    opener = urllib.request.build_opener(_KhongTheoChuyenHuong, tls)
    try:
        with opener.open(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LoiGoiError(f"AVIS /models: HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise LoiGoiError(f"AVIS /models: {type(e).__name__}") from None
    ds = d.get("data", d) if isinstance(d, dict) else d
    return sorted(str(m.get("id", m)) if isinstance(m, dict) else str(m) for m in ds)
