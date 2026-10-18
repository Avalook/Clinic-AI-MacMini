"""Trang THEO DÕI: agent đang chạy gì, đã tiêu bao nhiêu, bấm dừng ở đâu.

Chỉ ĐỌC các tệp trong `ket-qua/` (sổ chi phí, kết quả các lượt đo/quét) và hiện nút
Dừng/Chạy tiếp (do `may_xem.py` ghi/xoá tệp `DUNG`). Tự làm mới mỗi 5 giây.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from .bao_cao import _CSS

TOI_DA_DONG_GAN_DAY = 15
_JS = """
const CO_MAY = location.protocol.startsWith('http');
document.querySelectorAll('[data-lenh]').forEach(b=>{
  if(!CO_MAY){b.disabled=true;return}
  b.onclick=async()=>{
    const r=await fetch('/'+b.dataset.lenh,{method:'POST',
      headers:{'Content-Type':'application/json'},body:'{}'});
    if(r.ok)location.reload();
  }});
"""


def _doc_so(duong: Path) -> list[dict[str, object]]:
    ra: list[dict[str, object]] = []
    if duong.is_file():
        for d in duong.read_text(encoding="utf8").splitlines():
            try:
                x = json.loads(d)
            except json.JSONDecodeError:
                continue
            if isinstance(x, dict):
                ra.append(x)
    return ra


def _so(x: object) -> float:
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def trang(ket_qua: Path) -> str:
    so = _doc_so(ket_qua / "chi-phi.jsonl")
    tong = sum(_so(d.get("usd")) for d in so)
    theo_mh: dict[str, list[float]] = {}
    for d in so:
        m = str(d.get("mo_hinh", "?"))
        c = theo_mh.setdefault(m, [0, 0.0, 0, 0])
        c[0] += 1
        c[1] += _so(d.get("usd"))
        c[2] += int(_so(d.get("vao")))
        c[3] += int(_so(d.get("ra")))
    dang_dung = (ket_qua / "DUNG").exists()
    bang_mh = "".join(
        f"<tr><td>{escape(m)}</td><td>{int(c[0])}</td><td>{int(c[2]):,}</td>"
        f"<td>{int(c[3]):,}</td><td>${c[1]:.3f}</td></tr>"
        for m, c in sorted(theo_mh.items(), key=lambda x: -x[1][1])
    )
    gan = "".join(
        f"<tr><td>{escape(str(d.get('luc', ''))[11:])}</td>"
        f"<td>{escape(str(d.get('nhan', '')))}</td>"
        f"<td>{escape(str(d.get('mo_hinh', '')).split('/')[-1])}</td>"
        f"<td>${_so(d.get('usd')):.4f}</td><td>{_so(d.get('giay')):.0f}s</td></tr>"
        for d in reversed(so[-TOI_DA_DONG_GAN_DAY:])
    )
    luot = []
    for p in sorted((q for q in ket_qua.iterdir() if q.is_dir()), reverse=True)[:12]:
        mo_ta = ""
        tt = p / "tom-tat.md"
        if tt.is_file():
            mo_ta = f"<pre>{escape(tt.read_text(encoding='utf8')[:1800])}</pre>"
        elif (p / "phat-hien.jsonl").is_file():
            n = len((p / "phat-hien.jsonl").read_text(encoding="utf8").splitlines())
            mo_ta = f"<span class=mo>{n} phát hiện</span>"
        elif (p / "da-doc.jsonl").is_file():
            n = len(_doc_so(p / "da-doc.jsonl"))
            mo_ta = f"<span class=mo>quét model: {n} (tệp×model) đã đọc</span>"
        luot.append(f"<tr><td><b>{escape(p.name)}</b></td><td>{mo_ta}</td></tr>")
    nut = (
        "<button data-lenh=tiep>▶ Cho chạy tiếp</button>"
        if dang_dung
        else "<button data-lenh=dung>■ DỪNG KHẨN CẤP</button>"
    )
    trang_thai = (
        "<b style='color:var(--do)'>ĐANG DỪNG — mọi lần gọi model bị chặn</b>"
        if dang_dung
        else "<b style='color:var(--xanh)'>Cho phép gọi model</b>"
    )
    return (
        "<!doctype html><html lang=vi><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<meta http-equiv=refresh content=5><title>Theo dõi agent</title>"
        f"<style>{_CSS}</style><main>"
        "<h1>Theo dõi agent soát</h1>"
        "<div class=mo><a href='/'>← Phát hiện cần duyệt</a> · tự làm mới 5 giây</div>"
        f"<div class=luoi><div class=o><b>${tong:.2f}</b>đã tiêu (mọi lượt)</div>"
        f"<div class=o><b>{len(so)}</b>lần gọi model</div>"
        f"<div class=o>{trang_thai}<div class=nut>{nut}</div></div></div>"
        "<h2>Chi phí theo model</h2><table><tr><th>Model</th><th>Lần gọi</th>"
        "<th>Token vào</th><th>Token ra</th><th>USD</th></tr>"
        f"{bang_mh or '<tr><td colspan=5>Chưa gọi lần nào.</td></tr>'}</table>"
        "<h2>Các lần gọi gần nhất</h2><table><tr><th>Giờ</th><th>Việc</th>"
        f"<th>Model</th><th>USD</th><th>Mất</th></tr>{gan}</table>"
        "<h2>Các lượt chạy</h2><table>"
        f"{''.join(luot) or '<tr><td>Chưa có.</td></tr>'}</table>"
        f"</main><script>{_JS}</script></html>"
    )
