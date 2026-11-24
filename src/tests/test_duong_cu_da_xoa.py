"""Đường cũ đã gỡ 24/11/2026 không được mọc lại (luật thiết kế 2).

Đã gỡ, kèm bằng chứng không ai dùng (log Caddy + API prod 22–24/11, grep, bảng):
- `POST /api/v1/auth/login` + `AuthService` — cửa đăng nhập thứ hai bên cạnh
  GoTrue. Dashboard chỉ gọi GoTrue; bảng `app_credential` trên prod 0 dòng.
- `/api/v1/tools/*` (vốn tự trả 404 ở production), `/api/v1/orchestrator/chat`,
  `POST /api/v1/lab/triage/{id}` + gói `tools/`, `graphs/`, `orchestrator/`
  (LangGraph) — không màn nào gọi.
- Sentry (`core/sentry.py`, `sentry-sdk`) — chết từ 27/09, lỗi đi kho `loi_nhom`.
- RabbitMQ (`event_bus/consumer.py`, chế độ worker mặc định, `aio-pika`, service
  `rabbitmq`/`worker` trong compose) — prod chưa từng bật profile `workers`.

Muốn đưa lại một thứ ở đây thì sửa bài này trong cùng PR và nói lý do.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from clinicai.main import app

GOC = Path(__file__).resolve().parents[2]

DUONG_DA_GO = (
    "/api/v1/auth/login",
    "/api/v1/tools/",
    "/api/v1/orchestrator/",
    "/api/v1/lab/triage/",
)

MODULE_DA_GO = (
    "clinicai.tools",
    "clinicai.graphs",
    "clinicai.orchestrator",
    "clinicai.core.sentry",
    "clinicai.services.auth_service",
    "clinicai.api.v1.routers.auth",
    "clinicai.api.v1.routers.tools",
    "clinicai.api.v1.routers.orchestrator",
    "clinicai.event_bus.consumer",
)

GOI_DA_GO = ("sentry-sdk", "aio-pika", "langgraph", "langchain", "psycopg")


def test_khong_route_nao_cua_duong_cu() -> None:
    con = sorted(
        r.path
        for r in app.routes
        if isinstance(r, APIRoute)
        and any(r.path == d or r.path.startswith(d) for d in DUONG_DA_GO)
    )
    assert con == [], f"đường đã gỡ mọc lại: {con}"


def test_khong_module_nao_cua_duong_cu() -> None:
    con = [m for m in MODULE_DA_GO if importlib.util.find_spec(m) is not None]
    assert con == [], f"module đã gỡ mọc lại: {con}"


def test_khong_phu_thuoc_chet_trong_pyproject() -> None:
    # Chỉ đọc khối dependencies thật, bỏ dòng chú thích (chú thích có nhắc tên gói).
    dong = [
        d.strip().lower()
        for d in (GOC / "pyproject.toml").read_text(encoding="utf-8").splitlines()
        if d.strip().startswith('"')
    ]
    con = sorted({g for g in GOI_DA_GO for d in dong if d.startswith(f'"{g}')})
    assert con == [], f"phụ thuộc đã gỡ quay lại pyproject.toml: {con}"


def test_worker_khong_co_che_do_thi_thoat_ma_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chế độ mặc định cũ (RabbitMQ) đã gỡ: thiếu cờ là cấu hình sai, không chạy bừa."""
    from clinicai import worker

    monkeypatch.setattr(sys, "argv", ["clinicai.worker"])
    with pytest.raises(SystemExit) as loi:
        worker.main()
    assert loi.value.code == 2


def test_compose_khong_con_rabbitmq_va_worker_mac_dinh() -> None:
    compose = (GOC / "docker-compose.yml").read_text(encoding="utf-8")
    # Đo khai báo service / biến, không đo chú thích (chú thích được kể lịch sử).
    assert not re.search(r"^  rabbitmq:|^  worker:|RABBITMQ_", compose, re.MULTILINE)
    # Mọi lệnh chạy worker phải nói rõ chế độ; không cờ = thoát mã 2.
    assert '"python", "-m", "clinicai.worker"]' not in compose
