"""Phát lại sổ sự kiện để DỰNG LẠI một projection — docs/CHUAN-CAM-LEGO.md mục 3.

Bài kiểm của thesis: *"xoá dashboard, dựng lại từ sổ có ra y như cũ không"*
(`docs/thiet-ke-he-thong/chung-minh-event-driven.md`, bằng chứng #3). Projection
dựng được lại nghĩa là sổ sự kiện chứa ĐỦ sự thật; không dựng lại được là sổ thiếu.

LUẬT:
  * Chỉ bên nhận đã khai là PROJECTION (`dang_ky_projection`) mới được phát lại.
    Bên nhận TÁC VỤ (mở việc, gửi tin) thì không — phát lại chúng là làm lại việc.
  * Phát lại KHÔNG sinh sự kiện mới, KHÔNG sinh dòng giao mới, KHÔNG đụng
    `event_delivery`: nó đọc sổ và gọi thẳng hàm của bên nhận.
  * Mỗi sự kiện được nâng lên version hiện hành trước (`events/nang_cap.py`), và
    mang `replay_id` của lần chạy → `la_phat_lai = True`.
  * Xoá + dựng lại trong MỘT giao dịch: hỏng giữa chừng thì màn cũ còn nguyên.

    PYTHONPATH=src python -m clinicai.events.phat_lai \\
        --projection dong_thoi_gian_luot --clinic <clinic_id> [--luot <visit_id>]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from dataclasses import dataclass

import asyncpg

from clinicai.events.catalogue import DANH_MUC
from clinicai.events.worker import SuKienDaNhan, bo_xu_ly, nang_len_hien_hanh


@dataclass(frozen=True)
class Projection:
    #: Bảng đọc mà bên nhận này ghi (chỉ nó ghi). Có cột `clinic_id`.
    bang: str
    #: Cột khoá theo lượt khám, để dựng lại một lượt thay vì cả phòng khám.
    cot_luot: str = "visit_id"


PROJECTION: dict[str, Projection] = {}


def dang_ky_projection(consumer: str, projection: Projection) -> None:
    """Khai: bên nhận `consumer` là PROJECTION, ghi vào `projection.bang`."""
    PROJECTION[consumer] = projection


async def dung_lai(
    pool: asyncpg.Pool,
    consumer: str,
    *,
    clinic_id: str,
    visit_id: str | None = None,
) -> int:
    """Xoá rồi dựng lại projection từ sổ. Trả số sự kiện đã phát lại."""
    if consumer not in PROJECTION:
        raise ValueError(
            f"'{consumer}' không khai là projection — bên nhận tác vụ không được "
            "phát lại (sẽ làm lại việc)."
        )
    p = PROJECTION[consumer]
    xu_ly = bo_xu_ly(consumer)
    loai = sorted(ten for ten, sk in DANH_MUC.items() if consumer in sk.consumers)
    lan_chay = str(uuid.uuid4())

    async with pool.acquire() as conn, conn.transaction():
        # Tên bảng/cột lấy từ bản khai trong code, không từ người gọi.
        if visit_id is None:
            await conn.execute(
                f"DELETE FROM public.{p.bang} WHERE clinic_id = $1::uuid",  # noqa: S608
                clinic_id,
            )
        else:
            await conn.execute(
                f"DELETE FROM public.{p.bang}"  # noqa: S608
                f" WHERE clinic_id = $1::uuid AND {p.cot_luot} = $2::uuid",
                clinic_id,
                visit_id,
            )
        dong = await conn.fetch(
            """
            SELECT event_id::text, event_type, clinic_id::text, aggregate_id::text,
                   aggregate_version, occurred_at, seq, actor_type,
                   actor_staff_id::text, payload, event_version
              FROM public.domain_event
             WHERE clinic_id = $1::uuid
               AND event_type = ANY($2::text[])
               AND ($3::text IS NULL OR payload ->> 'visit_id' = $3::text)
             ORDER BY seq
            """,
            clinic_id,
            loai,
            visit_id,
        )
        for d in dong:
            su_kien = nang_len_hien_hanh(
                SuKienDaNhan(
                    event_id=d["event_id"],
                    event_type=d["event_type"],
                    clinic_id=d["clinic_id"],
                    aggregate_id=d["aggregate_id"],
                    aggregate_version=d["aggregate_version"],
                    occurred_at=d["occurred_at"],
                    seq=int(d["seq"]),
                    actor_type=d["actor_type"],
                    actor_staff_id=d["actor_staff_id"],
                    payload=json.loads(d["payload"]),
                    replay_id=lan_chay,
                    attempts=0,
                    event_version=int(d["event_version"]),
                )
            )
            await xu_ly(conn, su_kien)
    return len(dong)


async def _main() -> None:
    import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận

    ap = argparse.ArgumentParser(description="Dựng lại một projection từ sổ sự kiện.")
    ap.add_argument("--projection", required=True)
    ap.add_argument("--clinic", required=True)
    ap.add_argument("--luot", default=None)
    a = ap.parse_args()
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
    try:
        n = await dung_lai(pool, a.projection, clinic_id=a.clinic, visit_id=a.luot)
        print(f"Đã dựng lại {a.projection}: {n} sự kiện.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())


__all__ = ["PROJECTION", "Projection", "dang_ky_projection", "dung_lai"]
