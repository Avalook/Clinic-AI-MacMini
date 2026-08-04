"""Không route nào được nuốt route anh em của nó.

CHUYỆN ĐÃ XẢY RA. `GET /api/v1/appointments/{id}` (scheduling_router) đăng ký
trước `booking_router`, và `{id}` trần khớp MỌI chuỗi. Nên hai endpoint này:

    GET /api/v1/appointments/policy    luật đặt lịch — độ dài khung, số chỗ
    GET /api/v1/appointments/quote     sức chứa từng khung để tô màu ô lịch

chưa bao giờ chạy. Mọi lần gọi trả 422 vì "policy" không phải UUID. Starlette so
khớp theo MẪU đường dẫn chứ không theo kiểu, và một request đã khớp mẫu thì
KHÔNG rơi xuống route kế tiếp khi validate hỏng.

Nó im lặng suốt vì phía trình duyệt có `?? 15` / `?? 3`: getBookingPolicy() trả
null, màn hình lặng lẽ dùng con số viết cứng, lưới vẫn vẽ ra một thứ trông hợp
lý. Hai lớp che nhau — một lỗi 422 không ai đọc, và một giá trị mặc định làm nó
trông như đang chạy.

Test này không kiểm hành vi của endpoint (đã có test khác). Nó kiểm điều mà
không test hành vi nào bắt được: đường dẫn có tới ĐÚNG hàm không.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def app_routes() -> list[tuple[frozenset[str], str, str]]:
    os.environ.setdefault("APP_ENV", "test")
    from clinicai.main import app

    out = []
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        endpoint = getattr(r, "endpoint", None)
        if path and methods and endpoint:
            out.append((frozenset(methods), path, endpoint.__name__))
    return out


def _resolve(
    app_routes: list[tuple[frozenset[str], str, str]], method: str, url: str
) -> str:
    """Hàm nào thật sự nhận request này, theo đúng luật khớp của Starlette."""
    from starlette.routing import compile_path

    for methods, path, name in app_routes:
        if method not in methods:
            continue
        regex, _, _ = compile_path(path)
        if regex.match(url):
            return name
    return "<không route nào khớp>"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/api/v1/appointments/policy", "booking_policy"),
        ("/api/v1/appointments/quote", "capacity_quote"),
        # Và route tham số vẫn phải nhận UUID thật.
        (
            "/api/v1/appointments/3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "get_appointment_by_id",
        ),
    ],
)
def test_literal_paths_are_not_swallowed(
    app_routes: list[tuple[frozenset[str], str, str]], url: str, expected: str
) -> None:
    assert _resolve(app_routes, "GET", url) == expected


def test_no_bare_path_param_shadows_a_literal_sibling(
    app_routes: list[tuple[frozenset[str], str, str]],
) -> None:
    """Luật chung, để lỗi này không tái diễn ở một cặp route khác.

    Một route có đoạn `{tham_so}` KHÔNG kiểu, đứng trước một route anh em có
    đoạn cố định ở cùng vị trí, sẽ nuốt route kia. Cách sửa là thêm bộ chuyển
    đổi (`{id:uuid}`, `{n:int}`) chứ không phải đổi thứ tự đăng ký — thứ tự là
    một ràng buộc vô hình nằm ở file khác.
    """
    import re

    bare = re.compile(r"\{[^:}]+\}")
    problems: list[str] = []

    for i, (methods_a, path_a, name_a) in enumerate(app_routes):
        if not bare.search(path_a):
            continue
        prefix_a = path_a.split("{", 1)[0]
        depth_a = path_a.count("/")
        for methods_b, path_b, name_b in app_routes[i + 1 :]:
            if not (methods_a & methods_b):
                continue
            if "{" in path_b.replace(prefix_a, "", 1):
                continue  # đoạn tương ứng cũng là tham số — không phải xung đột
            if path_b.startswith(prefix_a) and path_b.count("/") == depth_a:
                problems.append(f"{path_a} ({name_a}) nuốt {path_b} ({name_b})")

    assert not problems, "Route bị che:\n  " + "\n  ".join(problems)
