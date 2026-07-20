"""Lab triage rules — clinical classification GROUP_A/B/C.

═══════════════════════════════════════════════════════════════
MIGRATION CONTRACT (đọc kỹ trước khi sửa)
═══════════════════════════════════════════════════════════════

File này là HARDCODED placeholder cho P9.2. Sẽ migrate sang
bảng kb_policy_rule ở Phase 10 bằng 1 script SQL seed.

ĐỂ MIGRATION DỄ DÀNG, MỌI RULE PHẢI:
1. JSON-serializable hoàn toàn (không có lambda, không có class instance)
2. Có key 'policy_key' format 'lab.triage.<rule_name>'
   (sẽ thành kb_policy_rule.policy_key)
3. Có key 'version' integer (sẽ thành kb_policy_rule.version)
4. Có key 'owner_role' = 'MEDICAL_DIRECTOR'
   (sẽ thành kb_policy_rule.owner_role)
5. Toàn bộ logic match nằm trong key 'rule_data'
   (sẽ thành kb_policy_rule.rule_data JSONB)

KHÔNG THÊM Python logic phức tạp vào file này. Logic match nằm
ở classify.py — đọc rule_data dict và evaluate.

P10 migration script sẽ chỉ cần:

    for rule in LAB_TRIAGE_RULES.values():
        await conn.execute(
            "INSERT INTO kb_policy_rule "
            "(policy_key, version, owner_role, rule_data) "
            "VALUES ($1, $2, $3, $4)",
            rule['policy_key'],
            rule['version'],
            rule['owner_role'],
            json.dumps(rule['rule_data']),
        )

═══════════════════════════════════════════════════════════════
"""

from typing import Any

LAB_TRIAGE_RULES: dict[str, dict[str, Any]] = {
    # ─────────── GROUP_C: NGUY HIỂM, BẮT BUỘC BS REVIEW ───────────
    "HIV_REACTIVE": {
        "policy_key": "lab.triage.hiv_reactive",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_C",
            "requires_doctor_review": True,
            "match": {
                "panel_code_in": ["HIV", "HIV_AB", "HIV_COMBO", "HIV_AG_AB"],
                "flag_in": ["POSITIVE", "REACTIVE", "POS"],
            },
            "reason_template": (
                "HIV reactive/positive — BẮT BUỘC BS review trước khi notify BN"
            ),
            "priority": 100,
        },
    },
    "HBV_HIGH_VIRAL_LOAD": {
        "policy_key": "lab.triage.hbv_high_viral_load",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_C",
            "requires_doctor_review": True,
            "match": {
                "panel_code_in": ["HBV_DNA", "HBV_VIRAL_LOAD"],
                "numeric_gt": 100000,
            },
            "reason_template": "HBV viral load cao bất thường — BS review",
            "priority": 90,
        },
    },
    "NIPT_HIGH_RISK": {
        "policy_key": "lab.triage.nipt_high_risk",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_C",
            "requires_doctor_review": True,
            "match": {
                "panel_code_in": ["NIPT", "NIPT_T21", "NIPT_T18", "NIPT_T13"],
                "flag_in": ["HIGH_RISK", "POSITIVE"],
            },
            "reason_template": (
                "NIPT high risk — BẮT BUỘC tư vấn BS, không notify BN trực tiếp"
            ),
            "priority": 100,
        },
    },
    "HCG_PREGNANCY_DECLINING": {
        "policy_key": "lab.triage.hcg_pregnancy_declining",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_C",
            "requires_doctor_review": True,
            "match": {
                "panel_code_in": ["BETA_HCG", "HCG"],
                "flag_in": ["DECLINING", "ABNORMAL_DROP"],
            },
            "reason_template": ("βHCG giảm bất thường — nghi sảy/dọa sảy, BS review"),
            "priority": 95,
        },
    },
    # ─────────── GROUP_B: CẦN THEO DÕI ───────────
    "GLUCOSE_GESTATIONAL_HIGH": {
        "policy_key": "lab.triage.glucose_gestational_high",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_B",
            "requires_doctor_review": False,
            "match": {
                "panel_code_in": ["GLU", "GLUCOSE", "OGTT"],
                "numeric_gt": 7.0,
                "numeric_lte": 11.0,
            },
            "reason_template": ("Đường huyết cao nghi tiểu đường thai kỳ — theo dõi"),
            "priority": 50,
        },
    },
    "HEMOGLOBIN_LOW_PREGNANCY": {
        "policy_key": "lab.triage.hemoglobin_low_pregnancy",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_B",
            "requires_doctor_review": False,
            "match": {
                "panel_code_in": ["HGB", "HEMOGLOBIN", "CBC_HGB"],
                "numeric_lt": 11.0,
                "numeric_gte": 9.0,
            },
            "reason_template": ("Hemoglobin thấp — thiếu máu nhẹ-trung bình, theo dõi"),
            "priority": 40,
        },
    },
    "FLAG_HIGH_GENERIC": {
        "policy_key": "lab.triage.flag_high_generic",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_B",
            "requires_doctor_review": False,
            "match": {
                "flag_in": ["H", "HIGH", "L", "LOW"],
            },
            "reason_template": "Kết quả ngoài reference range — cần theo dõi",
            "priority": 10,
        },
    },
    # ─────────── GROUP_A: BÌNH THƯỜNG ───────────
    "FLAG_NORMAL": {
        "policy_key": "lab.triage.flag_normal",
        "version": 1,
        "owner_role": "MEDICAL_DIRECTOR",
        "rule_data": {
            "triage_group": "GROUP_A",
            "requires_doctor_review": False,
            "match": {
                "flag_in": ["N", "NORMAL", None],
                "numeric_within_range": True,
            },
            "reason_template": "Kết quả bình thường",
            "priority": 5,
        },
    },
}
