"""QUAN SÁT API (14/10/2026): request nào chậm, và bể kết nối có đầy không.

Vì sao có file này. Tối 12/10 (18–22h) ~4.500 request chạm DB chậm >3s, số
request chờ cùng lúc vọt 1→270, trong khi trang không chạm DB vẫn nhanh — nghi
CẠN BỂ KẾT NỐI của API (một tiến trình uvicorn, `POOL_MAX_SIZE` kết nối). Không
chứng minh được vì log API không ghi thời gian xử lý và Postgres không ghi câu
chậm. File này là phần ĐO; phần CẢNH BÁO nằm ở `services/canh_gac_pool.py`.

Ba thứ, mỗi thứ một chỗ, đều trong bộ nhớ của tiến trình API:
  · `request_xong` — mỗi request: có đáng ghi một dòng log riêng không
    (>= `NGUONG_CHAM_MS`), và gom vào cửa sổ một phút.
  · `gan_do_pool` — bọc `Pool._acquire` để đo THỜI GIAN CHỜ mượn kết nối và số
    người đang chờ. Đây là con số trả lời "pool có cạn không": request chậm vì
    SQL chậm thì chờ-mượn ≈ 0; chậm vì cạn pool thì chờ-mượn ≈ toàn bộ độ chậm.
  · `lay_mau_pool` — mỗi giây đọc số kết nối bận (`size - idle`).

KHÔNG GHI NỘI DUNG (Luật 8.2). Chỉ mẫu đường dẫn đã chuẩn hoá (`/patients/{id}`,
không bao giờ đường dẫn thật), phương thức, mã trạng thái, số mili-giây, mã
request. Không query string, không thân, không header, không tên người.

Chạy một vòng sự kiện, không khoá: mọi hàm ở đây được gọi từ vòng sự kiện của
API (middleware, `_acquire`, vòng nền). Handler `def` thường chạy ở luồng phụ
nhưng không gọi vào đây.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import asyncpg
import structlog

from clinicai.core.telemetry import percentile

logger = structlog.get_logger()

#: Request chậm hơn mức này (tính tới lúc có header phản hồi) thì ghi MỘT dòng log.
NGUONG_CHAM_MS = 500.0
#: Trần số dòng log riêng mỗi phút. Sự cố như 12/10 có ~4.500 request chậm trong
#: bốn giờ ≈ 19/phút — trần để một cơn bão không đẩy log 10MB×5 của container
#: đi mất lịch sử. Phần vượt trần vẫn được ĐẾM trong dòng tổng hợp.
TRAN_DONG_CHAM_MOI_PHUT = 30
#: Một lần mượn kết nối chờ quá mức này = pool đầy (ghi log + tính vào cảnh báo).
NGUONG_CHO_POOL_MS = 2000.0
#: Chờ quá mức này thì đếm là "có chờ" (phân biệt với mượn tức thì ~0ms).
NGUONG_CO_CHO_MS = 100.0
TRAN_DONG_POOL_MOI_PHUT = 10
#: Bận từ chừng này phần kết nối tối đa trở lên = "bận cao" (8/10 ở bể cũ).
TY_LE_BAN_CAO = 0.8
#: Bận cao liên tiếp chừng này giây thì ghi log + tính vào cảnh báo.
NGUONG_BAN_LIEN_TIEP_GIAY = 10
#: Trần số mẫu giữ để tính phân vị trong một phút (14 req/s × 60 ≈ 840).
TRAN_MAU_PHUT = 20000
SO_ROUTE_CHAM_TOP = 5


@dataclass
class CuaSoPhut:
    """Số liệu gom của MỘT phút (rồi `chot_phut` trả ra và làm mới)."""

    bat_dau: float = field(default_factory=time.time)
    so_request: int = 0
    so_cham: int = 0
    so_5xx: int = 0
    mau_ms: list[float] = field(default_factory=list)
    #: (phương thức, mẫu đường dẫn) → [số lần chậm, ms lớn nhất]
    cham_theo_route: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    dong_cung_luc_max: int = 0
    dong_log_cham: int = 0
    dong_log_pool: int = 0
    # --- pool ---
    so_muon: int = 0
    so_cho: int = 0  # mượn phải chờ >= NGUONG_CO_CHO_MS
    so_cho_qua_2s: int = 0
    cho_max_ms: float = 0.0
    cho_tong_ms: float = 0.0
    dang_cho_max: int = 0
    ban_max: int = 0
    so_mau_pool: int = 0
    so_mau_ban_cao: int = 0
    ban_cao_lien_max: int = 0
    so_mau_day: int = 0


class QuanSat:
    """Bộ gom số liệu. Một bản dùng chung cho tiến trình (`quan_sat` ở cuối)."""

    def __init__(self) -> None:
        self._cua_so = CuaSoPhut()
        self._dong_cung_luc = 0
        self._dang_cho = 0
        self._ban_cao_lien = 0
        self._day_lien = 0
        #: Bể kết nối đang đo (để `/ops/pool` đọc số tức thời).
        self.pool: Any = None
        self.pool_max = 0
        #: Tổng hợp phút vừa chốt gần nhất (vòng nền đặt) — cho `/ops/pool`.
        self.phut_gan_nhat: dict[str, Any] | None = None

    # ------------------------------------------------------------------ request
    def request_bat_dau(self) -> None:
        self._dong_cung_luc += 1
        if self._dong_cung_luc > self._cua_so.dong_cung_luc_max:
            self._cua_so.dong_cung_luc_max = self._dong_cung_luc

    def request_xong(self, *, route: str, method: str, status: int, ms: float) -> bool:
        """Ghi một request đã xong. Trả True = ĐÁNG ghi một dòng log riêng."""
        self._dong_cung_luc = max(0, self._dong_cung_luc - 1)
        w = self._cua_so
        w.so_request += 1
        if status >= 500:
            w.so_5xx += 1
        if len(w.mau_ms) < TRAN_MAU_PHUT:
            w.mau_ms.append(ms)
        if ms < NGUONG_CHAM_MS:
            return False
        w.so_cham += 1
        muc = w.cham_theo_route.setdefault((method, route), [0.0, 0.0])
        muc[0] += 1
        muc[1] = max(muc[1], ms)
        if w.dong_log_cham >= TRAN_DONG_CHAM_MOI_PHUT:
            return False
        w.dong_log_cham += 1
        return True

    # --------------------------------------------------------------------- pool
    def muon_bat_dau(self) -> None:
        self._dang_cho += 1
        if self._dang_cho > self._cua_so.dang_cho_max:
            self._cua_so.dang_cho_max = self._dang_cho

    def muon_xong(self, cho_ms: float) -> bool:
        """Một lần mượn kết nối kết thúc (có được hay không). Trả True = chờ
        quá `NGUONG_CHO_POOL_MS` và còn quota ghi log."""
        self._dang_cho = max(0, self._dang_cho - 1)
        w = self._cua_so
        w.so_muon += 1
        w.cho_tong_ms += cho_ms
        w.cho_max_ms = max(w.cho_max_ms, cho_ms)
        if cho_ms >= NGUONG_CO_CHO_MS:
            w.so_cho += 1
        if cho_ms < NGUONG_CHO_POOL_MS:
            return False
        w.so_cho_qua_2s += 1
        if w.dong_log_pool >= TRAN_DONG_POOL_MOI_PHUT:
            return False
        w.dong_log_pool += 1
        return True

    def dang_cho(self) -> int:
        return self._dang_cho

    def lay_mau_pool(self, ban: int, toi_da: int) -> str | None:
        """Mỗi giây một lần. Trả "day" / "ban_keo_dai" khi VỪA chạm ngưỡng cần
        ghi log (đúng một lần cho mỗi đợt), còn lại None."""
        w = self._cua_so
        w.so_mau_pool += 1
        w.ban_max = max(w.ban_max, ban)
        su_kien: str | None = None

        if toi_da > 0 and ban >= toi_da:
            w.so_mau_day += 1
            self._day_lien += 1
            # "Đầy hơn 2 giây" = hai mẫu 1 giây liên tiếp đều kín.
            if self._day_lien == 2:
                su_kien = "day"
        else:
            self._day_lien = 0

        if toi_da > 0 and ban >= toi_da * TY_LE_BAN_CAO:
            w.so_mau_ban_cao += 1
            self._ban_cao_lien += 1
            w.ban_cao_lien_max = max(w.ban_cao_lien_max, self._ban_cao_lien)
            if self._ban_cao_lien == NGUONG_BAN_LIEN_TIEP_GIAY and su_kien is None:
                su_kien = "ban_keo_dai"
        else:
            self._ban_cao_lien = 0
        return su_kien

    # ------------------------------------------------------------------- chốt
    def chot_phut(self) -> dict[str, Any]:
        """Trả tổng hợp phút vừa rồi (chỉ số + số liệu thô) và mở cửa sổ mới.

        Cửa sổ mới KẾ THỪA các đợt đang diễn ra (số giây bận liên tiếp, số
        request đang bay) — chỉ số liệu cộng dồn trong phút là được làm mới."""
        w = self._cua_so
        moi = CuaSoPhut()
        moi.dong_cung_luc_max = self._dong_cung_luc
        moi.dang_cho_max = self._dang_cho
        moi.ban_cao_lien_max = self._ban_cao_lien
        self._cua_so = moi

        mau = w.mau_ms
        top = sorted(w.cham_theo_route.items(), key=lambda kv: kv[1][0], reverse=True)[
            :SO_ROUTE_CHAM_TOP
        ]
        return {
            "giay": round(time.time() - w.bat_dau, 1),
            "so_request": w.so_request,
            "so_cham_500ms": w.so_cham,
            "so_5xx": w.so_5xx,
            "p50_ms": round(percentile(mau, 50), 1),
            "p95_ms": round(percentile(mau, 95), 1),
            "max_ms": round(max(mau), 1) if mau else 0.0,
            "dong_cung_luc_max": w.dong_cung_luc_max,
            "dong_log_cham_bi_nen": max(0, w.so_cham - w.dong_log_cham),
            "top_route_cham": [
                {
                    "route": f"{m} {r}",
                    "so_lan": int(v[0]),
                    "max_ms": round(v[1], 1),
                }
                for (m, r), v in top
            ],
            "pool": {
                "toi_da": self.pool_max,
                "ban_max": w.ban_max,
                "dang_cho_max": w.dang_cho_max,
                "so_muon": w.so_muon,
                "so_muon_phai_cho": w.so_cho,
                "so_cho_qua_2s": w.so_cho_qua_2s,
                "cho_max_ms": round(w.cho_max_ms, 1),
                "cho_tb_ms": round(w.cho_tong_ms / w.so_muon, 2) if w.so_muon else 0.0,
                "giay_ban_cao": w.so_mau_ban_cao,
                "giay_ban_cao_lien_max": w.ban_cao_lien_max,
                "giay_day": w.so_mau_day,
                "so_mau": w.so_mau_pool,
            },
        }

    def tuc_thoi(self) -> dict[str, Any]:
        """Số tức thời cho `/ops/pool` (không đụng DB)."""
        p = self.pool
        if p is None:
            return {"co_pool": False}
        size = int(p.get_size())
        idle = int(p.get_idle_size())
        return {
            "co_pool": True,
            "toi_da": int(p.get_max_size()),
            "toi_thieu": int(p.get_min_size()),
            "dang_mo": size,
            "ranh": idle,
            "ban": size - idle,
            "dang_cho": self._dang_cho,
            "request_dang_xu_ly": self._dong_cung_luc,
        }


quan_sat = QuanSat()


async def do_acquire(
    goc: Callable[[Any], Awaitable[Any]], timeout: Any, pool: Any
) -> Any:
    """Mượn kết nối qua `goc` và ghi thời gian chờ. Đo cả khi mượn lỗi/bị huỷ
    (`finally`): request bị bỏ chờ chính là trường hợp cạn bể cần thấy nhất."""
    quan_sat.muon_bat_dau()
    t0 = time.perf_counter()
    try:
        return await goc(timeout)
    finally:
        cho_ms = (time.perf_counter() - t0) * 1000.0
        if quan_sat.muon_xong(cho_ms):
            logger.warning(
                "pool_cho_lau",
                cho_ms=round(cho_ms, 1),
                dang_cho=quan_sat.dang_cho(),
                ban=int(pool.get_size()) - int(pool.get_idle_size()),
                toi_da=int(pool.get_max_size()),
            )


class _PoolCoDo(asyncpg.Pool):  # type: ignore[misc]
    """`asyncpg.Pool` có đo chờ mượn. KHÔNG thêm trạng thái (`__slots__ = ()`):
    chỉ đổi lớp của bể đã dựng nên `create_pool` giữ nguyên mọi tham số."""

    __slots__ = ()

    async def _acquire(self, timeout: Any) -> Any:
        return await do_acquire(super()._acquire, timeout, self)


def gan_do_pool(pool: Any) -> bool:
    """Đổi lớp của `pool` sang `_PoolCoDo` để đo thời gian chờ mượn kết nối.

    Mọi đường mượn (`async with pool.acquire()`, `pool.fetch(...)`, `await
    pool.acquire()`) đi qua `Pool._acquire` ở asyncpg 0.30 nên chặn đúng một chỗ
    là đủ. (Gán đè `pool._acquire = …` không được: `Pool` dùng `__slots__`.)
    `_acquire` là hàm riêng tư của asyncpg: nếu bản mới đổi tên/lớp thì ở đây
    KHÔNG làm app hỏng — chỉ mất số đo (trả False, log cảnh báo), và test
    `test_quan_sat` đỏ để người nâng bản biết.
    """
    if not isinstance(pool, asyncpg.Pool) or not callable(
        getattr(asyncpg.Pool, "_acquire", None)
    ):
        logger.warning("quan_sat_khong_bo_duoc_pool", ly_do="Pool._acquire biến mất")
        return False
    try:
        pool.__class__ = _PoolCoDo
    except TypeError:
        logger.warning("quan_sat_khong_bo_duoc_pool", ly_do="không đổi được lớp bể")
        return False
    quan_sat.pool = pool
    quan_sat.pool_max = int(pool.get_max_size())
    return True
