"""Mọi service có healthcheck đều được THEO DÕI ở đủ bốn chỗ (27/09/2026).

Vì sao có: service ``su-kien`` (giao sự kiện — xếp hàng, dòng thời gian) thêm
ngày 23/09 có healthcheck trong compose, nhưng KHÔNG có trong vòng kiểm sức
khoẻ của ``deploy-backend.sh``, không có monitor Kuma, không có trên màn /ops.
Nó chết thì khách check-in xong không vào hàng — mà deploy vẫn báo
``all healthy ✓`` và mọi đèn đều xanh.

Thêm service mới có healthcheck → test này đỏ cho tới khi khai đủ:
  1. ``scripts/deploy-backend.sh``  vòng ``for svc in … ; do`` của health_ok
  2. ``monitoring/monitors.json``   một monitor HTTP (bảng DIEM_DO dưới đây)
  3. ``scripts/collect_ops_status.py`` SERVICE_IDS (+ schema + màn /ops)
"""

from __future__ import annotations

import json
import re
import typing
from pathlib import Path

import yaml  # type: ignore[import-untyped]  # pyyaml đi kèm langchain, không có stub

from clinicai.schemas.ops import HostServiceSnapshot

GOC = Path(__file__).resolve().parents[3]

#: Công cụ theo dõi tự nó — không kiểm chính nó bằng chính nó.
CONG_CU_THEO_DOI = {"uptime-kuma", "dozzle"}

#: Service → điểm đo Kuma gọi (monitors.json).
DIEM_DO = {
    "api": "http://api:8000/health/db",
    "dashboard": "http://dashboard:3000/health",
    "caddy": "http://caddy:80/health",
    "su-kien": "http://api:8000/health/su-kien",
}


def _service_mac_dinh_co_healthcheck() -> set[str]:
    compose = yaml.safe_load((GOC / "docker-compose.yml").read_text())
    return {
        ten
        for ten, sv in compose["services"].items()
        if not sv.get("profiles") and "healthcheck" in sv
    } - CONG_CU_THEO_DOI


def test_bang_diem_do_khop_compose() -> None:
    assert _service_mac_dinh_co_healthcheck() == set(DIEM_DO)


def test_deploy_cho_du_moi_service_xanh() -> None:
    sh = (GOC / "scripts" / "deploy-backend.sh").read_text()
    m = re.search(r"health_ok\(\) \{.*?for svc in ([^;]+); do", sh, re.S)
    assert m, "không tìm thấy vòng health_ok trong deploy-backend.sh"
    assert set(DIEM_DO) <= set(m.group(1).split())


def test_kuma_co_monitor_cho_moi_service() -> None:
    mon = json.loads((GOC / "monitoring" / "monitors.json").read_text())
    urls = {m.get("url") for m in mon["monitors"]}
    thieu = {sv: u for sv, u in DIEM_DO.items() if u not in urls}
    assert not thieu, thieu


def test_bo_thu_thap_schema_va_man_ops_cung_mot_danh_sach() -> None:
    py = (GOC / "scripts" / "collect_ops_status.py").read_text()
    m = re.search(r"SERVICE_IDS = \((.*?)\)", py, re.S)
    assert m
    thu_thap = set(re.findall(r'"([a-z-]+)"', m.group(1)))

    schema = set(typing.get_args(HostServiceSnapshot.model_fields["id"].annotation))

    ts = (GOC / "src" / "dashboard" / "lib" / "ops-summary.ts").read_text()
    m = re.search(r"const SERVICE_IDS = new Set\(\[(.*?)\]\)", ts, re.S)
    assert m
    man_ops = set(re.findall(r'"([a-z-]+)"', m.group(1)))

    assert thu_thap == schema == man_ops
    assert set(DIEM_DO) <= thu_thap


def test_moi_service_deu_log_vao_journald_tren_may_chu() -> None:
    """Sót một service là log của nó lại mất theo mỗi lần deploy."""
    goc = yaml.safe_load((GOC / "docker-compose.yml").read_text())["services"]
    phu = yaml.safe_load((GOC / "docker-compose.journald.yml").read_text())
    assert set(phu["services"]) == set(goc)
    for ten, sv in phu["services"].items():
        assert sv["logging"]["driver"] == "journald", ten
        # journald từ chối tuỳ chọn của json-file — compose chỉ THAY khối khi
        # khác driver, nên ở đây không được có max-size / max-file.
        assert "max-size" not in sv["logging"].get("options", {}), ten
