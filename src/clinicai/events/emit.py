"""Một đường duy nhất để phát sự kiện nghiệp vụ.

VÌ SAO CHỈ MỘT ĐƯỜNG. Repo hiện có 15 chỗ `INSERT INTO event_log` thô nằm ngoài
`audit.py`, mỗi chỗ một dạng metadata. Hệ quả là không câu truy vấn nào đọc được
cả sổ, và mỗi lần thêm một trường lại phải đi sửa 15 chỗ. `emit_event` là cửa duy
nhất vào `domain_event`, nên trường mới thêm một lần là xong.

CÙNG GIAO DỊCH, LUÔN LUÔN. `conn` là connection của người gọi. Sự kiện và thay
đổi hiện trạng commit cùng nhau hoặc cùng không — không có "commit xong rồi
phát", vì tiến trình chết đúng khoảng giữa là mất sự kiện mà không ai biết
(mẫu transactional outbox, microservices.io).

DÒNG GIAO TẠO NGAY TẠI ĐÂY. Mỗi bên nhận khai trong danh mục được một dòng
`event_delivery`, viết trong chính giao dịch này. Không dùng con trỏ chạy theo
`seq`: số thứ tự được cấp TRƯỚC khi commit, hai giao dịch song song commit lệch
thứ tự, và bên nhận đã đọc qua số lớn sẽ bỏ sót số nhỏ vĩnh viễn — im lặng.
Cái giá của cách này: thêm một bên nhận mới thì nó chỉ thấy sự kiện từ lúc thêm
trở đi; muốn xử lý lịch sử thì chạy script bù, và script đó phải đóng dấu
`replay_id`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import PayloadSuKien, tra


@dataclass(frozen=True)
class NguoiGayRa:
    """Ai làm ra chuyện này.

    `actor_staff_id IS NULL` = "hệ thống" là không đủ: cron, bot Zalo và AI điều
    phối phải phân biệt được, và khi AI làm thay người thì phải ghi được cả hai.
    Mô hình lấy theo FHIR Provenance/AuditEvent (who / onBehalfOf / software).
    """

    actor_type: str
    staff_id: str | None = None
    role: str | None = None
    on_behalf_of: str | None = None
    agent_version: str | None = None


def nguoi(identity: StaffIdentity) -> NguoiGayRa:
    """Người thật đang bấm."""
    return NguoiGayRa(
        actor_type="HUMAN",
        staff_id=identity.staff_id,
        role=identity.role.value,
    )


HE_THONG = NguoiGayRa(actor_type="SYSTEM")


def ai_agent(
    *, ten_agent: str, phien_ban: str, thay_cho: str | None = None
) -> NguoiGayRa:
    """AI tự hành động. Bắt buộc khai phiên bản để sau còn truy được."""
    return NguoiGayRa(
        actor_type="AGENT",
        role=ten_agent,
        agent_version=phien_ban,
        on_behalf_of=thay_cho,
    )


async def emit_event(
    conn: asyncpg.Connection,
    *,
    ten: str,
    clinic_id: str,
    aggregate_id: str,
    payload: PayloadSuKien,
    boi: NguoiGayRa,
    aggregate_version: int | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    replay_id: str | None = None,
    so_ke_tiep: bool = False,
) -> str:
    """Ghi một sự kiện + dòng giao cho từng bên nhận. Trả về `event_id`.

    `ten`                tên sự kiện, phải có trong danh mục
    `aggregate_id`       đối tượng mà chuyện này xảy ra với
    `aggregate_version`  số thứ tự trong cùng đối tượng, cho bên nhận cần đúng
                         thứ tự; sự kiện khai `theo_thu_tu=True` thì bắt buộc
    `correlation_id`     cả chuỗi việc, thường là id lượt khám
    `causation_id`       lệnh/sự kiện nào gây ra chuyện này
    `replay_id`          có giá trị = phát lại/nhập lịch sử, bên nhận không được
                         gửi thông báo ra ngoài
    `so_ke_tiep`         True = sổ tự lấy số kế tiếp của đối tượng (lớn nhất + 1)
                         thay cho `aggregate_version`

    VÌ SAO CÓ `so_ke_tiep` (24/09/2026). Một chỉ định có BA bộ đếm nghiệp vụ:
    đặt (1), thực hiện (`execution_revision`), điều phối (`routing_revision`).
    Dùng thẳng một bộ đếm làm số thứ tự trong sổ thì hai bộ đụng nhau — "đã chỉ
    định" mang số 1 và lần "bắt đầu làm" đầu tiên cũng mang số 1, Postgres chặn
    (`uq_domain_event_aggregate_version`) và phòng không bấm Bắt đầu được. Số
    thứ tự trong sổ là MỘT dãy của đối tượng; bộ đếm nghiệp vụ nằm trong payload.
    An toàn khi người gọi đã khoá đối tượng (mọi lệnh của chỉ định khoá LƯỢT
    trước); chỉ mục duy nhất vẫn là lưới cuối nếu có ai quên khoá.
    """
    su_kien = tra(ten)
    if so_ke_tiep:
        aggregate_version = int(
            await conn.fetchval(
                "SELECT coalesce(max(aggregate_version), 0) + 1 FROM domain_event"
                " WHERE clinic_id = $1::uuid AND aggregate_type = $2"
                "   AND aggregate_id = $3::uuid",
                clinic_id,
                su_kien.aggregate_type,
                aggregate_id,
            )
        )

    if not isinstance(payload, su_kien.payload):
        raise TypeError(
            f"Sự kiện '{ten}' cần payload {su_kien.payload.__name__}, "
            f"nhận được {type(payload).__name__}."
        )
    if su_kien.theo_thu_tu and aggregate_version is None:
        raise ValueError(
            f"Sự kiện '{ten}' khai theo_thu_tu=True nên phải có aggregate_version: "
            "thiếu nó là bên nhận xử lý đảo thứ tự mà không ai biết."
        )

    event_id = str(uuid.uuid4())
    noi_dung: dict[str, Any] = payload.model_dump(mode="json")

    await conn.execute(
        """
        INSERT INTO domain_event
            (event_id, event_type, event_version, clinic_id,
             aggregate_type, aggregate_id, aggregate_version,
             correlation_id, causation_id,
             actor_type, actor_staff_id, actor_role, on_behalf_of, agent_version,
             source_module, is_public, payload, replay_id)
        VALUES ($1::uuid, $2, $3, $4::uuid,
                $5, $6::uuid, $7,
                $8::uuid, $9::uuid,
                $10, $11::uuid, $12, $13::uuid, $14,
                $15, $16, $17::jsonb, $18::uuid)
        """,
        event_id,
        su_kien.ten,
        su_kien.version,
        clinic_id,
        su_kien.aggregate_type,
        aggregate_id,
        aggregate_version,
        correlation_id,
        causation_id,
        boi.actor_type,
        boi.staff_id,
        boi.role,
        boi.on_behalf_of,
        boi.agent_version,
        su_kien.source_module,
        su_kien.is_public,
        json.dumps(noi_dung, ensure_ascii=False),
        replay_id,
    )

    if su_kien.consumers:
        await conn.executemany(
            """
            INSERT INTO event_delivery
                (event_id, consumer, clinic_id, aggregate_id, aggregate_version)
            VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5)
            """,
            [
                (event_id, consumer, clinic_id, aggregate_id, aggregate_version)
                for consumer in su_kien.consumers
            ],
        )

    return event_id


__all__ = ["HE_THONG", "NguoiGayRa", "ai_agent", "emit_event", "nguoi"]
