"""THEO DÕI MÀN HÌNH trong lúc buổi khám chạy — như có người ngồi nhìn mọi màn.

Một luồng nền đọc định kỳ các màn vận hành (lễ tân, bàn khám, phòng, TV, thu
ngân, nhà thuốc, đối tác, trưởng ca, chuông) bằng đúng tài khoản của vai xem màn
ấy. Mỗi lần đọc, rút ra "khách nào đang có mặt trên màn" (theo mã lượt / mã
khách) và ghi lại MỐC XUẤT HIỆN / BIẾN MẤT. Từ đó báo cáo:

  * độ trễ: thao tác X lúc t0 → khách hiện ở màn Y lúc t1;
  * treo: khách đã về / đã xong mà vẫn còn trên màn Y sau N giây;
  * lệch: hai màn nói hai điều khác nhau về cùng một khách;
  * lỗi đọc: màn trả 4xx/5xx hoặc chậm.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ket_noi import LoiApi, NguoiDung

#: Hàm rút tập "khoá khách" (mã lượt / mã khách / tên) từ phản hồi của màn.
RutKhach = Callable[[Any], dict[str, str]]


@dataclass
class Man:
    ten: str
    nguoi: NguoiDung
    duong: str
    rut: RutKhach
    #: khoá → mô tả trạng thái trên màn lúc đọc lần cuối
    hien_tai: dict[str, str] = field(default_factory=dict)
    lan_doc: int = 0
    loi: list[str] = field(default_factory=list)
    ms: list[float] = field(default_factory=list)


@dataclass
class Moc:
    luc: float
    man: str
    khoa: str
    loai: str  # HIỆN | ĐỔI | MẤT
    mo_ta: str


class TheoDoi:
    def __init__(self, chu_ky: float = 1.0) -> None:
        self.man: list[Man] = []
        self.moc: list[Moc] = []
        self._chu_ky = chu_ky
        self._dung = threading.Event()
        self._luong: threading.Thread | None = None
        self._khoa = threading.Lock()

    def them(self, ten: str, nguoi: NguoiDung, duong: str, rut: RutKhach) -> None:
        self.man.append(Man(ten, nguoi, duong, rut))

    def _doc_mot(self, m: Man) -> None:
        t0 = time.monotonic()
        try:
            data = m.nguoi.get(m.duong)
        except LoiApi as e:
            m.loi.append(f"{e.ma}: {str(e.noi_dung)[:160]}")
            return
        except Exception as e:  # noqa: BLE001
            m.loi.append(f"{type(e).__name__}: {e}"[:200])
            return
        m.ms.append((time.monotonic() - t0) * 1000)
        m.lan_doc += 1
        try:
            moi = m.rut(data)
        except Exception as e:  # noqa: BLE001 — màn đổi hình dạng
            m.loi.append(f"rút khách hỏng: {type(e).__name__}: {e}"[:200])
            return
        bay_gio = time.time()
        with self._khoa:
            for k, v in moi.items():
                if k not in m.hien_tai:
                    self.moc.append(Moc(bay_gio, m.ten, k, "HIỆN", v))
                elif m.hien_tai[k] != v:
                    self.moc.append(Moc(bay_gio, m.ten, k, "ĐỔI", v))
            for k in set(m.hien_tai) - set(moi):
                self.moc.append(Moc(bay_gio, m.ten, k, "MẤT", m.hien_tai[k]))
            m.hien_tai = moi

    def _chay(self) -> None:
        while not self._dung.is_set():
            for m in self.man:
                self._doc_mot(m)
            self._dung.wait(self._chu_ky)

    def bat_dau(self) -> None:
        self._luong = threading.Thread(target=self._chay, daemon=True)
        self._luong.start()

    def dung(self) -> None:
        self._dung.set()
        if self._luong:
            self._luong.join(timeout=10)
        for m in self.man:  # lần đọc cuối, trạng thái cuối cùng của mọi màn
            self._doc_mot(m)

    # ── truy vấn cho báo cáo ──────────────────────────────────────────────

    def lan_hien_dau(self, man: str, khoa: str, sau: float = 0) -> float | None:
        for m in self.moc:
            if m.man == man and m.khoa == khoa and m.loai in ("HIỆN", "ĐỔI") and m.luc >= sau:
                return m.luc
        return None

    def con_tren_man(self, khoa: str) -> list[str]:
        return [m.ten for m in self.man if khoa in m.hien_tai]

    def tong_hop(self) -> list[dict[str, Any]]:
        ra = []
        for m in self.man:
            ms = sorted(m.ms)
            ra.append({
                "man": m.ten,
                "duong": m.duong,
                "lan_doc": m.lan_doc,
                "p50_ms": round(ms[len(ms) // 2], 1) if ms else None,
                "max_ms": round(ms[-1], 1) if ms else None,
                "so_loi": len(m.loi),
                "loi_mau": m.loi[:3],
                "con_lai_cuoi_buoi": sorted(m.hien_tai)[:40],
            })
        return ra
