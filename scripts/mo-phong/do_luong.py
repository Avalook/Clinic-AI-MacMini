"""Đo lường cho buổi khám giả lập: lời gọi API, sự kiện, độ trễ giao tin.

  * `SoGoi` nghe MỌI lời gọi API (qua `ket_noi.NGHE_LOI_GOI`): endpoint (mã
    thay bằng {id}), vai, mã HTTP, thời gian → p50/p95/max, lỗi 5xx.
  * `ThuSuKien` đọc sổ sự kiện (`domain_event` + `event_delivery`) và nhật ký
    (`event_log`) từ một mốc: gắn mỗi THAO TÁC với các sự kiện nó sinh ra (theo
    khoảng seq, lọc theo người làm), đo độ trễ từ lúc ghi tới lúc bên nhận xử
    lý xong, tìm tin chết / còn treo.
  * `thao_tac(...)`: bọc một thao tác nghiệp vụ, ghi (thời điểm, người, tên,
    kết quả, ms, sự kiện phát ra). Thao tác THÀNH CÔNG mà không phát sự kiện
    nghiệp vụ nào = ứng viên "dây nối thiếu" (báo cáo xét tiếp).
"""

from __future__ import annotations

import re
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ket_noi import NGHE_LOI_GOI, LoiApi, sql

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def mau_duong(duong: str) -> str:
    return _UUID.sub("{id}", duong.split("?")[0])


class SoGoi:
    def __init__(self) -> None:
        self._khoa = threading.Lock()
        self.goi: list[tuple[float, str, str, str, int, float]] = []
        NGHE_LOI_GOI.append(self._ghi)

    def _ghi(self, email: str, cach: str, duong: str, ma: int, ms: float) -> None:
        with self._khoa:
            self.goi.append((time.time(), email.split("@")[0], cach, mau_duong(duong), ma, ms))

    def tong_hop(self) -> list[dict[str, Any]]:
        nhom: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
        for _, _ai, cach, duong, ma, ms in self.goi:
            nhom[(cach, duong)].append((ma, ms))
        ra = []
        for (cach, duong), ds in sorted(nhom.items()):
            ms = sorted(m for _, m in ds)
            ra.append({
                "endpoint": f"{cach} {duong}",
                "so_lan": len(ds),
                "p50_ms": round(statistics.median(ms), 1),
                "p95_ms": round(ms[max(0, int(len(ms) * 0.95) - 1)], 1),
                "max_ms": round(ms[-1], 1),
                "ma": dict(sorted(_dem(m for m, _ in ds).items())),
            })
        return ra

    def loi_5xx(self) -> list[tuple[Any, ...]]:
        return [g for g in self.goi if g[4] >= 500]


def _dem(xs: Any) -> dict[Any, int]:
    d: dict[Any, int] = defaultdict(int)
    for x in xs:
        d[x] += 1
    return d


def moc_seq() -> int:
    return int(sql("select coalesce(max(seq),0) from domain_event")[0][0])


def su_kien_sau(seq: int) -> list[dict[str, Any]]:
    cot = ["seq", "event_type", "source_module", "actor_staff_id", "aggregate_type",
           "aggregate_id", "recorded_at", "correlation_id", "causation_id"]
    rows = sql(
        "select seq, event_type, source_module, coalesce(actor_staff_id::text,''),"
        " aggregate_type, aggregate_id, recorded_at, coalesce(correlation_id::text,''),"
        f" coalesce(causation_id::text,'') from domain_event where seq > {seq} order by seq"
    )
    return [dict(zip(cot, r, strict=False)) for r in rows]


def giao_tin_sau(seq: int) -> list[dict[str, Any]]:
    cot = ["seq", "event_type", "consumer", "status", "attempts", "tre_ms", "loi"]
    rows = sql(
        "select e.seq, e.event_type, d.consumer, d.status, d.attempts,"
        " coalesce(round(extract(epoch from (d.processed_at - e.recorded_at))*1000)::text,''),"
        " left(coalesce(d.last_error,''),200)"
        " from event_delivery d join domain_event e on e.event_id=d.event_id"
        f" where e.seq > {seq} order by e.seq, d.consumer"
    )
    return [dict(zip(cot, r, strict=False)) for r in rows]


def nhat_ky_sau(moc_iso: str) -> list[dict[str, Any]]:
    cot = ["event_type", "aggregate_type", "source", "recorded_at"]
    rows = sql(
        "select event_type, aggregate_type, source, recorded_at from event_log"
        f" where recorded_at >= '{moc_iso}' order by recorded_at"
    )
    return [dict(zip(cot, r, strict=False)) for r in rows]


@dataclass
class ThaoTac:
    luc: float
    ai: str
    ten: str
    loai: str  # nhóm thao tác (vd "check-in", "thu tiền dịch vụ")
    kq: str  # OK | CHẶN ĐÚNG | HỎNG | LẼ RA PHẢI CHẶN
    ms: float
    ma: int | None = None
    loi: str | None = None
    su_kien: list[str] = field(default_factory=list)
    khach: str | None = None


class NhatKyThaoTac:
    """Sổ thao tác của cả buổi (nhiều luồng ghi cùng lúc)."""

    def __init__(self) -> None:
        self._khoa = threading.Lock()
        self._seq_khoa = threading.Lock()
        self.ds: list[ThaoTac] = []
        #: Bật khi chỉ MỘT luồng chạy: gắn chính xác sự kiện cho từng thao tác.
        self.tuan_tu = False

    def lam(self, ai: str, loai: str, ten: str, fn: Any, *, khach: str | None = None,
            mong_loi: int | tuple[int, ...] | None = None, doi_su_kien: bool = False) -> Any:
        """Chạy MỘT thao tác. `mong_loi`: hệ thống PHẢI từ chối (mã HTTP).
        `doi_su_kien`: chạy tuần tự để gắn chính xác sự kiện của thao tác."""
        truoc = moc_seq() if (doi_su_kien or self.tuan_tu) else None
        t0 = time.monotonic()
        kq, ma, loi, tra = "OK", None, None, None
        try:
            tra = fn()
        except LoiApi as e:
            ma = e.ma
            mong = (mong_loi,) if isinstance(mong_loi, int) else (mong_loi or ())
            kq = "CHẶN ĐÚNG" if ma in mong else "HỎNG"
            loi = str(e.noi_dung)[:400]
        except Exception as e:  # noqa: BLE001
            kq, loi = "HỎNG", f"{type(e).__name__}: {e}"[:400]
        else:
            if mong_loi:
                kq = "LẼ RA PHẢI CHẶN"
        ms = (time.monotonic() - t0) * 1000
        sk: list[str] = []
        if truoc is not None and kq == "OK":
            time.sleep(1.5)  # đợi worker giao tin → bắt cả sự kiện do bên nhận phát tiếp
            sk = [f"{r['event_type']}" for r in su_kien_sau(truoc)]
        with self._khoa:
            self.ds.append(ThaoTac(time.time(), ai, ten, loai, kq, ms, ma, loi, sk, khach))
        dau = {"OK": "✓", "CHẶN ĐÚNG": "✓"}.get(kq, "✗")
        print(f"  {dau} [{ai}] {ten}" + (f" → {kq} {ma or ''} {loi or ''}"[:220] if dau == "✗" else ""), flush=True)
        if kq in ("HỎNG", "LẼ RA PHẢI CHẶN"):
            return None
        return tra
