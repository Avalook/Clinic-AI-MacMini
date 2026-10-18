"""Báo cáo HTML cho người duyệt — một tệp, không phụ thuộc mạng.

Người duyệt là Quang/Tuyền, không phải kỹ sư soát code cả ngày: mỗi thẻ mở ra
đủ 10 mục của hiến pháp §13, xếp theo ưu tiên P0 → P6, kèm MỨC BẰNG CHỨNG
(sự thật / suy luận / chưa biết) và nơi script KHÔNG nhìn được. Nút quyết định chỉ
chạy khi mở qua `may_xem.py` (ghi vào so-duyet.jsonl); mở tệp trực tiếp thì chỉ đọc.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from .khuon import DoPhu, PhatHien

_BANG_CHUNG = {
    "quan_sat": ("Sự thật", "script thấy trực tiếp trong code"),
    "suy_ra": ("Suy luận", "phân tích tĩnh — cần người mở ra kiểm"),
    "chua_biet": ("Chưa biết", "nêu ra để người xem, chưa dám kết"),
}
_UU_TIEN = {
    "P0": "P0 · An toàn / toàn vẹn dữ liệu",
    "P1": "P1 · Hệ thống tin khác thực tế",
    "P2": "P2 · Việc/khách có thể rơi",
    "P3": "P3 · Trải nghiệm bệnh nhân",
    "P4": "P4 · Tải nhân viên",
    "P5": "P5 · Điều phối / lego đứt",
    "P6": "P6 · Thừa, rác, hiệu suất",
}
_LOAI = {
    "lego_thieu_lien_ket": "Lego thiếu liên kết",
    "du_lieu_sai": "Dữ liệu sai",
    "mat_du_lieu": "Mất dữ liệu / chưa lưu",
    "logic_co_van_de": "Logic có vấn đề",
    "de_xuat_cai_tien": "Đề xuất cải tiến",
}

_THU_MUC = Path(__file__).resolve().parent
_CSS = (_THU_MUC / "bao_cao.css").read_text(encoding="utf8")
_JS = (_THU_MUC / "bao_cao.js").read_text(encoding="utf8")


def _the(p: PhatHien, quyet: dict[str, str] | None) -> str:
    d = p.dict()
    ten_bc, mo_ta_bc = _BANG_CHUNG[d["muc_bang_chung"]]
    td = "".join(
        f"<li><code>{escape(t.tep)}:{t.dong}</code> — <code>{escape(t.doan[:120])}"
        "</code></li>"
        for t in p.trich_dan
    )
    bc = "".join(f"<li>{escape(x)}</li>" for x in p.bang_chung)
    da = (
        f"<span class=da>Đã quyết: {escape(quyet['quyet_dinh'])} — "
        f"{escape(quyet.get('ly_do', ''))}</span>"
        if quyet
        else ""
    )
    nut = (
        da
        or "<button data-quyet=chap_nhan>Nhận — đưa vào hàng sửa</button>"
        "<button data-quyet=bo_qua>Bỏ qua (có lý do)</button>"
        "<button data-quyet=can_them>Cần thêm thông tin</button>"
    )
    mo_ta = {
        "Tình huống": p.tinh_huong,
        "Rủi ro": p.rui_ro,
        "Đề xuất": p.de_xuat,
        "Ai chịu trách nhiệm": p.nguoi_chiu_trach_nhiem,
        "Khi nào": p.thoi_diem,
        "Kết quả mong đợi": p.ket_qua_mong_doi,
        "Cách xác nhận": p.cach_xac_nhan,
        "Phương án khác": p.phuong_an_khac or "—",
    }
    dl = "".join(f"<dt>{k}</dt><dd>{escape(v)}</dd>" for k, v in mo_ta.items())
    return (
        f'<details class=the data-id="{p.id}"><summary>'
        f'<span class="chip {p.uu_tien.value}">{p.uu_tien.value}</span>'
        f'<span class="chip {d["muc_bang_chung"]}" title="{escape(mo_ta_bc)}">'
        f"{ten_bc} · {int(p.do_chac * 100)}%</span>"
        f"<span class=chip>{_LOAI[d['loai']]}</span>"
        f"<b>{escape(p.khoa)}</b>"
        f"<span class=mo>mức việc {p.muc_viec}</span></summary>"
        f"<div class=than><dl>{dl}</dl><div class=mo>Bằng chứng</div><ul>{bc}</ul>"
        f"<div class=mo>Trích dẫn (script đã mở tệp kiểm)</div><ul>{td}</ul>"
        f"<div class=nut>{nut}</div></div></details>"
    )


def html(
    giu: list[PhatHien],
    do_phu: list[DoPhu],
    loai: list[tuple[PhatHien, str]],
    so_duyet: dict[str, dict[str, str]],
) -> str:
    cho = [p for p in giu if p.id not in so_duyet]
    xong = [p for p in giu if p.id in so_duyet]
    theo_uu: dict[str, list[PhatHien]] = {}
    # Trong cùng mức ưu tiên: việc đụng tiền/kho/quyền (mức 3) lên trước.
    for p in sorted(
        cho, key=lambda x: (x.uu_tien.value, -x.muc_viec, x.bo_quet, x.khoa)
    ):
        theo_uu.setdefault(p.uu_tien.value, []).append(p)
    cac_muc = "".join(
        f"<h2>{_UU_TIEN[u]} <span class=mo>({len(ds)})</span></h2>"
        + "".join(_the(p, None) for p in ds)
        for u, ds in theo_uu.items()
    )
    da_xu = "".join(_the(p, so_duyet[p.id]) for p in xong)
    bang_phu = "".join(
        f"<tr><td><b>{escape(d.bo_quet)}</b></td>"
        f"<td>{escape(', '.join(f'{k}: {v}' for k, v in d.da_nhin.items()))}</td>"
        f"<td>{escape('; '.join(d.khong_nhin_duoc))}</td></tr>"
        for d in do_phu
    )
    bang_loai = "".join(
        f"<tr><td>{escape(p.khoa)}</td><td>{escape(ly)}</td></tr>" for p, ly in loai
    )
    cac_o = "".join(
        f"<div class=o><b>{n}</b>{t}</div>"
        for n, t in (
            (len(cho), "chờ người duyệt"),
            (len(xong), "đã quyết"),
            (len(loai), "bị loại (trích dẫn sai)"),
            (sum(p.uu_tien.value == "P0" for p in cho), "ưu tiên P0 đang chờ"),
        )
    )
    return (
        "<!doctype html><html lang=vi><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<title>Agent soát hệ thống</title>"
        f"<style>{_CSS}</style><main>"
        "<h1>Agent soát hệ thống ClinicAI</h1>"
        "<div class=mo><a href='/tien-do'>Theo dõi tiến độ, chi phí, nút dừng →"
        "</a></div>"
        "<div class=mo>Chỉ đọc · người duyệt · hiến pháp: docs/ai/HIEN-PHAP-AGENT.md. "
        "Phát hiện là <b>ứng viên để người kiểm</b>, không phải kết luận.</div>"
        f"<div class=luoi>{cac_o}</div>"
        f"{cac_muc or '<p>Không có phát hiện nào đang chờ.</p>'}"
        f"{'<h2>Đã quyết</h2>' + da_xu if da_xu else ''}"
        "<h2>Sổ độ phủ — bộ quét nhìn gì, mù ở đâu</h2>"
        "<p class=mo>“0 phát hiện” chỉ có nghĩa là SẠCH ở phần đã nhìn. Cột "
        "cuối là phần agent KHÔNG nhìn được.</p>"
        "<table><tr><th>Bộ quét</th><th>Đã nhìn</th><th>Không nhìn được</th></tr>"
        f"{bang_phu}</table>"
        f"{'<h2>Bị loại</h2><table>' + bang_loai + '</table>' if bang_loai else ''}"
        f"</main><script>{_JS}</script></html>"
    )
