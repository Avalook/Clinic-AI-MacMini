"""Từ Internet chỉ `/auth/v1` tới được Supabase tự dựng (23/11/2026, bảo mật).

Khoá anon nằm trong JS gửi xuống trình duyệt, RLS lọc theo phòng khám chứ không
theo vai → để `/rest/v1` mở là AI ĐĂNG NHẬP ĐƯỢC (kể cả Đối tác, TV phòng chờ)
đọc thẳng ~110 bảng. Thử thật trên stack local: token lễ tân đọc 63 hồ sơ
`patient` qua Caddyfile cũ. Lý do + số đo đầy đủ ở comment `caddy/Caddyfile`.

Test này canh cả hai Caddyfile (prod + staging):
  1. khối chuyển tiếp sang gateway Supabase chỉ khớp `/auth/v1/*`;
  2. có khối trả 403 cho `/rest/v1` và `/realtime/v1` (cả dạng không gạch chéo);
  3. ngoài hai khối Supabase/đăng nhập, không chỗ nào khác proxy sang gateway
     hay bộ chặn dò mật khẩu (site giám sát, site phụ).
Đọc chữ của Caddyfile, không chạy Caddy — lượt chạy thật nằm trong kịch bản PR.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CADDYFILES = [REPO / "caddy" / "Caddyfile", REPO / "caddy" / "Caddyfile.staging"]

DUONG_DONG = {"/rest/v1", "/rest/v1/*", "/realtime/v1", "/realtime/v1/*"}


def _khong_comment(tep: Path) -> str:
    return "\n".join(
        dong
        for dong in tep.read_text(encoding="utf-8").splitlines()
        if not dong.lstrip().startswith("#")
    )


def _matcher(noi_dung: str, ten: str) -> set[str]:
    m = re.findall(rf"^\t@{ten} path (.+)$", noi_dung, flags=re.M)
    assert len(m) == 1, f"@{ten}: cần đúng một khai báo, thấy {len(m)}"
    return set(m[0].split())


def _than_handle(noi_dung: str, ten: str) -> str:
    m = re.search(rf"^\thandle @{ten} \{{\n(.*?)^\t\}}$", noi_dung, flags=re.M | re.S)
    assert m, f"thiếu `handle @{ten}`"
    return m.group(1)


@pytest.mark.parametrize("tep", CADDYFILES, ids=lambda p: p.name)
def test_chi_auth_v1_chuyen_sang_gateway(tep: Path) -> None:
    s = _khong_comment(tep)
    assert _matcher(s, "supabase") == {"/auth/v1/*"}
    assert "SUPABASE_GATEWAY_HOST" in _than_handle(s, "supabase")


@pytest.mark.parametrize("tep", CADDYFILES, ids=lambda p: p.name)
def test_rest_va_realtime_tra_403(tep: Path) -> None:
    s = _khong_comment(tep)
    assert _matcher(s, "dong_supabase") == DUONG_DONG
    than = _than_handle(s, "dong_supabase").strip()
    # Đúng một câu trả lời 403 — không proxy đi đâu cả.
    assert than == "respond 403"


@pytest.mark.parametrize("tep", CADDYFILES, ids=lambda p: p.name)
def test_khong_cho_nao_khac_toi_gateway(tep: Path) -> None:
    s = _khong_comment(tep)
    # Mọi dòng proxy sang gateway / bộ chặn đăng nhập phải nằm trong đúng hai
    # khối đã canh. Thêm site mới (giám sát, site phụ) mà chép nhầm khối cũ là đỏ.
    proxy_gateway = re.findall(r"reverse_proxy \{\$SUPABASE_GATEWAY_HOST", s)
    proxy_guard = re.findall(r"reverse_proxy \{\$AUTH_GUARD_HOST", s)
    assert len(proxy_gateway) == 1
    assert len(proxy_guard) == 1
    assert _matcher(s, "dangnhap") == {"/auth/v1/token*"}
    # Không còn khai báo đường cũ ở bất kỳ matcher nào khác.
    for dong in re.findall(r"^\t@\w+ path .+$", s, flags=re.M):
        if dong.startswith("\t@dong_supabase "):
            continue
        assert "/rest/v1" not in dong and "/realtime/v1" not in dong, dong
    # Không lối tắt nào khác tới PostgREST / Realtime: `handle_path`, `route`,
    # hay proxy thẳng tên dịch vụ trong stack Supabase.
    assert "handle_path" not in s
    assert not re.search(r"^\s*route\b", s, flags=re.M)
    assert not re.search(r"reverse_proxy\s+\S*(rest|realtime)\S*:", s)


@pytest.mark.parametrize("tep", CADDYFILES, ids=lambda p: p.name)
def test_chi_co_cac_matcher_da_biet(tep: Path) -> None:
    # Matcher mới kiểu `/rest/*` hay `/*` đi tới đâu cũng phải qua mắt người
    # soát: thêm matcher là sửa danh sách này có chủ ý.
    s = _khong_comment(tep)
    ten = set(re.findall(r"^\s*@(\w+) ", s, flags=re.M))
    assert ten == {"tinh", "dong_supabase", "dangnhap", "supabase", "ok"}


@pytest.mark.parametrize("tep", CADDYFILES, ids=lambda p: p.name)
def test_khoi_chan_dung_truoc_khoi_bat_het(tep: Path) -> None:
    s = _khong_comment(tep)
    chan = s.index("\thandle @dong_supabase {")
    bat_het = s.index("\thandle {\n\t\treverse_proxy dashboard:3000")
    assert chan < bat_het
