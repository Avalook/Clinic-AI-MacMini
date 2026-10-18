"""Sổ chi phí + trần chi tiêu + công tắc dừng của tầng model.

Trần là của RIÊNG agent (không dựa vào trần phía nhà cung cấp): chi phí tính từ
`usage` mỗi lần trả về, cộng dồn, và `truoc_khi_goi` từ chối khi (đã tiêu + ước
tính lần gọi kế) vượt trần. Công tắc dừng: tạo tệp `ket-qua/DUNG` là mọi lần gọi
kế tiếp bị chặn, kể cả ở tiến trình đang chạy.

Mỗi dòng sổ chỉ có: giờ, mô hình, nhãn việc, token vào/ra, USD — không có nội dung.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

#: USD / 1 triệu token (vào, ra). Lấy từ danh sách HF router 18/10/2026 (nhà cung
#: cấp rẻ nhất đang `live`); AVIS lấy từ bảng giá Quang đưa (đổi VND→USD ≈ 26.500).
BANG_GIA: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.05, 0.25),
    "openai/gpt-oss-20b": (0.05, 0.20),
    "zai-org/GLM-5.3-Flash": (0.15, 0.50),
    "zai-org/GLM-5.3": (1.40, 4.40),
    "deepseek-ai/DeepSeek-V4.1-Flash": (0.30, 1.20),
    "deepseek-ai/DeepSeek-V4-Pro-0813": (1.32, 3.96),
    "MiniMaxAI/MiniMax-M3": (0.30, 1.20),
    "Qwen/Qwen3.8-27B": (0.42, 3.00),
    "Qwen/Qwen3.8-2.4T-A95B": (2.00, 6.00),
    "moonshotai/Kimi-K3": (3.00, 15.00),
    "moonshotai/Kimi-K2.7-Code": (0.95, 4.00),
    "moonshotai/Kimi-K2.6": (0.80, 3.40),
    "moonshotai/Kimi-K2-Instruct-0905": (0.60, 2.50),
    "deepseek-ai/DeepSeek-V3-0324": (0.24, 0.90),
    "deepseek-ai/DeepSeek-V3.1": (0.25, 0.95),
    "Qwen/Qwen3-235B-A22B-Instruct-2507": (0.20, 0.60),
    "Qwen/Qwen3-Next-80B-A3B-Instruct": (0.09, 1.10),
    "Qwen/Qwen3-Coder-30B-A3B-Instruct": (0.228, 0.912),
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8": (0.27, 0.85),
    "avis:claude-opus-5": (5.0, 25.0),
    "avis:claude-sonnet-5": (2.0, 10.0),
    "avis:claude-haiku-4.5": (1.0, 5.0),
}
#: Mô hình lạ → giá cao, để trần vẫn bảo vệ khi quên khai giá.
GIA_MAC_DINH = (3.0, 15.0)
#: Ước lượng thận trọng cho lần gọi kế tiếp khi chưa biết output (token).
UOC_TOKEN_RA = 3000


class TuChoiError(RuntimeError):
    """Không gọi vì một hàng rào (trần, công tắc dừng, host lạ, thiếu khoá)."""


class LoiGoiError(RuntimeError):
    """Một lần gọi hỏng (hết giờ, 5xx, 4xx) — bỏ khúc này, KHÔNG dừng cả lượt."""


def gia(mo_hinh: str) -> tuple[float, float]:
    goc = mo_hinh.split(":")[0] if not mo_hinh.startswith("avis:") else mo_hinh
    return BANG_GIA.get(goc, GIA_MAC_DINH)


class SoChiPhi:
    def __init__(self, duong: Path, tran_usd: float, thu_muc_dung: Path) -> None:
        self.duong = duong
        self.tran_usd = tran_usd
        self.tep_dung = thu_muc_dung / "DUNG"
        self._khoa = threading.Lock()
        self.da_tieu = 0.0
        self.so_lan = 0
        self.theo_mo_hinh: dict[str, float] = {}

    def truoc_khi_goi(self) -> None:
        if self.tep_dung.exists():
            raise TuChoiError("Có tệp DUNG — người đã bấm dừng.")
        with self._khoa:
            if self.da_tieu + 0.01 > self.tran_usd:
                raise TuChoiError(
                    f"Chạm trần chi tiêu ${self.tran_usd:.2f} (đã tiêu "
                    f"${self.da_tieu:.2f})."
                )

    def ghi(self, mo_hinh: str, vao: int, ra: int, nhan: str, giay: float) -> float:
        g_vao, g_ra = gia(mo_hinh)
        usd = (vao * g_vao + ra * g_ra) / 1e6
        with self._khoa:
            self.da_tieu += usd
            self.so_lan += 1
            self.theo_mo_hinh[mo_hinh] = self.theo_mo_hinh.get(mo_hinh, 0.0) + usd
            self.duong.parent.mkdir(parents=True, exist_ok=True)
            with self.duong.open("a", encoding="utf8") as f:
                f.write(
                    json.dumps(
                        {
                            "luc": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "mo_hinh": mo_hinh,
                            "nhan": nhan,
                            "vao": vao,
                            "ra": ra,
                            "usd": round(usd, 6),
                            "giay": round(giay, 1),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        return usd
