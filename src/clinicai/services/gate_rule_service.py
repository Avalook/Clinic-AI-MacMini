"""Luật thứ tự bắt buộc — "phải qua đây trước khi được đi tiếp".

Yêu cầu của Quang: *"đặt lịch để bác sĩ Thành là người mà khách nào đến cũng gặp
đầu tiên rồi mới được chỉ định gặp bác sĩ khác"* — và quan trọng hơn: đừng viết
cứng cho Dr4Women, để mỗi phòng khám tự khai luật của mình.

MỘT KHUÔN, HAI TÌNH HUỐNG THẬT:

    Dr4Women : xong KHÁM (do BS Thành) trước khi sang bước khám của bác sĩ KHÁC
    Nơi khác : xong SINH HIỆU (ai làm cũng được) trước khi gặp bác sĩ

VÌ SAO PHẦN QUYẾT ĐỊNH LÀ HÀM THUẦN.

Đây là một chốt an toàn: nó nói "không" với một thao tác mà con người đang muốn
làm, giữa ca trực, với bệnh nhân đang đứng đó. Sai theo hướng chặn nhầm thì
phòng khám tắc; sai theo hướng buông lỏng thì luật vô nghĩa. Cả hai đều phải
kiểm được bằng bảng tình huống, không phải bằng cách dựng một lượt khám thật.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()


@dataclass(frozen=True)
class GateRule:
    """Một luật, đúng bốn ô: áp cho ai · bắt buộc qua · chặn gì · ai bỏ qua."""

    id: str
    name: str
    location_id: str | None
    patient_kind: str | None
    service_type_id: str | None
    required_node_codes: tuple[str, ...]
    required_staff_id: str | None
    blocked_node_codes: tuple[str, ...]
    only_when_other_staff: bool
    override_roles: tuple[str, ...]


@dataclass(frozen=True)
class VisitFacts:
    """Những gì đã biết về lượt khám, tại thời điểm định chuyển bước."""

    location_id: str | None
    patient_kind: str | None
    service_type_id: str | None
    #: (node_code, staff_id) của các bước ĐÃ HOÀN TẤT.
    completed: tuple[tuple[str, str | None], ...]
    #: Người sẽ phụ trách bước sắp tới. None = chưa xếp ai.
    target_staff_id: str | None


def applies_to(rule: GateRule, facts: VisitFacts) -> bool:
    """Luật này có áp cho lượt khám này không.

    NULL ở ô nào nghĩa là "mọi giá trị" ở ô đó — không phải "chỉ khớp NULL".
    Hiểu ngược lại thì một luật khai cho mọi bệnh nhân sẽ không áp cho ai cả.
    """
    if rule.location_id and rule.location_id != facts.location_id:
        return False
    if rule.patient_kind and rule.patient_kind != facts.patient_kind:
        return False
    if rule.service_type_id and rule.service_type_id != facts.service_type_id:
        return False
    return True


def satisfied(rule: GateRule, facts: VisitFacts) -> bool:
    """Đã qua cổng chưa: xong BẤT KỲ bước bắt buộc nào, đúng người.

    MỘT TẬP, KHÔNG PHẢI MỘT BƯỚC — và khác biệt ấy chính là luật của Dr4Women.
    BS Thành phụ trách cả năm chuyên khoa, nên "đã gặp BS Thành" có năm hình
    dạng. Đòi đúng MỘT bước thì khám Phụ khoa với Thành xong, chuyển sang Nội
    tiết bác sĩ khác vẫn bị chặn — đúng cái ca mà luật muốn CHO PHÉP.
    """
    for node, staff in facts.completed:
        if node not in rule.required_node_codes:
            continue
        if rule.required_staff_id is None:
            return True
        if staff == rule.required_staff_id:
            return True
    return False


def blocks(rule: GateRule, facts: VisitFacts, to_node: str) -> bool:
    """Luật này có chặn nước đi sang `to_node` không.

    `only_when_other_staff` là ô làm nên tình huống của Dr4Women: bước bị chặn
    (khám) TRÙNG với bước bắt buộc (cũng là khám). Không có ô đó thì luật tự
    chặn chính nó — bệnh nhân không vào được phòng BS Thành để làm cái việc mà
    luật đang đòi.
    """
    if to_node not in rule.blocked_node_codes:
        return False
    if rule.only_when_other_staff:
        # Chưa xếp ai thì chưa biết là "bác sĩ khác" — để đi, chốt sẽ xét lại
        # khi đã có người. Chặn ở đây là chặn cả nước đi hợp lệ vào phòng của
        # chính người gác cổng.
        if facts.target_staff_id is None:
            return False
        if facts.target_staff_id == rule.required_staff_id:
            return False
    return not satisfied(rule, facts)


def first_block(
    rules: list[GateRule], facts: VisitFacts, to_node: str
) -> GateRule | None:
    """Luật ĐẦU TIÊN chặn nước đi này, hoặc None.

    Trả về luật chứ không phải True/False: người dùng cần biết luật NÀO chặn để
    còn ghi lý do đúng chỗ, và để màn hình nói được tên luật thay vì "không được
    phép".
    """
    for rule in rules:
        if applies_to(rule, facts) and blocks(rule, facts, to_node):
            return rule
    return None


def may_override(rule: GateRule, role: str) -> bool:
    return role in rule.override_roles


_RULES_SQL = """
SELECT id, name, location_id, patient_kind, service_type_id,
       required_node_codes, required_staff_id, blocked_node_codes,
       only_when_other_staff, override_roles
  FROM public.visit_gate_rule
 WHERE clinic_id = $1::uuid AND is_active
 ORDER BY created_at
"""

# Người phụ trách một bước = `work_item.assigned_to`. Đọc từ work_item chứ
# không từ visit.attending_doctor_id: một lượt khám có thể qua tay nhiều bác
# sĩ, và câu hỏi ở đây là "AI đã làm bước đó", không phải "ai đứng tên lượt
# khám".
#
# CẢNH BÁO VỀ DỮ LIỆU: hôm nay mới 1/7 work_item có assigned_to. Nên một luật
# đòi ĐÍCH DANH người (required_staff_id) sẽ coi là chưa qua bước — tức là chặn
# nhiều hơn thực tế. Chặn thừa còn hơn buông lỏng ở một chốt an toàn, nhưng
# phải ghi ra đây để không ai đi tìm nguyên nhân ở chỗ khác.
_FACTS_SQL = """
SELECT v.location_id,
       a.patient_kind,
       v.service_type_id,
       coalesce(
         (SELECT array_agg(ARRAY[w.node_code, coalesce(w.assigned_to::text, '')])
            FROM public.work_item w
           WHERE w.visit_id = v.visit_id AND w.status = 'COMPLETED'),
         '{}'
       ) AS completed
  FROM public.visit v
  LEFT JOIN public.appointment a ON a.id = v.appointment_id
 WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
"""


async def load_rules(conn: asyncpg.Connection, clinic_id: str) -> list[GateRule]:
    rows = await conn.fetch(_RULES_SQL, clinic_id)
    return [
        GateRule(
            id=str(r["id"]),
            name=r["name"],
            location_id=str(r["location_id"]) if r["location_id"] else None,
            patient_kind=r["patient_kind"],
            service_type_id=(
                str(r["service_type_id"]) if r["service_type_id"] else None
            ),
            required_node_codes=tuple(r["required_node_codes"] or ()),
            required_staff_id=(
                str(r["required_staff_id"]) if r["required_staff_id"] else None
            ),
            blocked_node_codes=tuple(r["blocked_node_codes"] or ()),
            only_when_other_staff=r["only_when_other_staff"],
            override_roles=tuple(r["override_roles"] or ()),
        )
        for r in rows
    ]


async def load_facts(
    conn: asyncpg.Connection,
    *,
    visit_id: str,
    clinic_id: str,
    target_staff_id: str | None,
) -> VisitFacts:
    row = await conn.fetchrow(_FACTS_SQL, visit_id, clinic_id)
    if row is None:
        raise ValidationError("Không tìm thấy lượt khám.")
    done: list[tuple[str, str | None]] = []
    for pair in row["completed"] or []:
        node, staff = pair[0], pair[1]
        done.append((node, staff or None))
    return VisitFacts(
        location_id=str(row["location_id"]) if row["location_id"] else None,
        patient_kind=row["patient_kind"],
        service_type_id=(
            str(row["service_type_id"]) if row["service_type_id"] else None
        ),
        completed=tuple(done),
        target_staff_id=target_staff_id,
    )


async def enforce(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    visit_id: str,
    to_node: str,
    target_staff_id: str | None,
    override_reason: str | None,
) -> dict[str, Any] | None:
    """Chặn nước đi nếu có luật, hoặc ghi lại một lần bỏ qua.

    Trả về thông tin lần bỏ qua (nếu có) để người gọi ghi vào log; None khi
    không luật nào đụng tới.
    """
    rules = await load_rules(conn, identity.clinic_id)
    if not rules:
        return None

    facts = await load_facts(
        conn,
        visit_id=visit_id,
        clinic_id=identity.clinic_id,
        target_staff_id=target_staff_id,
    )
    rule = first_block(rules, facts, to_node)
    if rule is None:
        return None

    if not override_reason or not override_reason.strip():
        raise ValidationError(
            f"{rule.name}: bệnh nhân chưa qua bước bắt buộc. "
            "Vẫn muốn chuyển thì phải ghi lý do bỏ qua."
        )
    if not may_override(rule, identity.role.value):
        raise ValidationError(
            f"{rule.name}: vai {identity.role.value} không được bỏ qua luật này."
        )

    await conn.execute(
        """
        INSERT INTO public.visit_gate_override
            (clinic_id, rule_id, visit_id, to_node_code, reason, by_staff_id)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6::uuid)
        """,
        identity.clinic_id,
        rule.id,
        visit_id,
        to_node,
        override_reason.strip(),
        identity.staff_id,
    )
    logger.info(
        "gate_overridden",
        rule=rule.name,
        visit_id=visit_id,
        to_node=to_node,
        by_staff_id=identity.staff_id,
    )
    return {"rule_id": rule.id, "rule_name": rule.name}
