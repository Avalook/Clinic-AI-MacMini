# -*- coding: utf-8 -*-
"""Markdown → HTML, dựng sẵn ở Python (không phụ thuộc thư viện chạy trên trình duyệt).

Đủ cho những gì các nút dùng: h3 · đoạn · danh sách - và 1. · bảng | · trích dẫn > ·
khối ``` · `code` · **đậm** · *nghiêng* · [[wikilink]] · [nhãn](url) · «trích».
Tên file trong backtick thành chip bằng chứng bấm được.
"""
from __future__ import annotations

import html
import re

WIKI = re.compile(r"\[\[([a-z0-9\-]+)\]\]")
LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
CODE = re.compile(r"`([^`\n]+)`")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
ITAL = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")
FILE = re.compile(r"^([\w/\-.()]+\.(?:py|sql|ts|tsx|mts|yml|yaml|md|sh))(?::(\d+(?:-\d+)?))?$")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(text: str, titles: dict[str, str], ev: dict[str, dict]) -> str:
    """Xử lý inline. Bảo vệ code/link bằng token để bold/ital không phá chúng."""
    slots: list[str] = []

    def keep(h: str) -> str:
        slots.append(h)
        return f"\x00{len(slots)-1}\x00"

    def code_sub(m: re.Match) -> str:
        raw = m.group(1)
        fm = FILE.match(raw)
        if fm and (raw in ev or fm.group(1) in ev):
            key = raw if raw in ev else fm.group(1)
            line = fm.group(2) or ""
            label = esc(raw)
            return keep(f'<button class="ev" data-ev="{esc(key)}" data-line="{line}" '
                        f'title="Mở bằng chứng: {esc(ev[key]["path"])}">{label}</button>')
        return keep(f"<code>{esc(raw)}</code>")

    def wiki_sub(m: re.Match) -> str:
        nid = m.group(1)
        t = titles.get(nid, nid).split(" — ")[0]
        return keep(f'<a class="wl" href="#{nid}" data-jump="{nid}">{esc(t)}</a>')

    def link_sub(m: re.Match) -> str:
        return keep(f'<a href="{esc(m.group(2))}" target="_blank" rel="noopener noreferrer">'
                    f"{esc(m.group(1))}</a>")

    out = CODE.sub(code_sub, text)
    out = WIKI.sub(wiki_sub, out)
    out = LINK.sub(link_sub, out)
    out = esc(out)
    out = BOLD.sub(lambda m: f"<b>{m.group(1)}</b>", out)
    out = ITAL.sub(lambda m: f"<i>{m.group(1)}</i>", out)
    out = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], out)
    return out


def render(md: str, titles: dict[str, str], ev: dict[str, dict]) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)

    def inl(t: str) -> str:
        return inline(t, titles, ev)

    while i < n:
        ln = lines[i]

        if not ln.strip():
            i += 1
            continue

        if ln.startswith("```"):
            lang = ln[3:].strip()
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(f'<pre class="code" data-lang="{esc(lang)}"><code>'
                       + esc("\n".join(buf)) + "</code></pre>")
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1)) + 1  # ## → h3 (h2 dành cho tiêu đề nút)
            out.append(f"<h{lvl}>{inl(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if ln.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip())
                i += 1
            body = " ".join(x for x in buf if x)
            cite = ""
            cm = re.search(r"—\s*\*([^*]+)\*\s*$", body)
            if cm:
                cite = cm.group(1)
                body = body[: cm.start()].rstrip()
            out.append('<blockquote><p>' + inl(body) + "</p>"
                       + (f"<cite>{inl(cite)}</cite>" if cite else "") + "</blockquote>")
            continue

        if ln.lstrip().startswith("|"):
            buf = []
            while i < n and lines[i].lstrip().startswith("|"):
                buf.append(lines[i].strip())
                i += 1
            rows = [[c.strip() for c in r.strip("|").split("|")] for r in buf]
            align: list[str] = []
            if len(rows) > 1 and all(re.fullmatch(r":?-{2,}:?", c) for c in rows[1]):
                for c in rows[1]:
                    align.append("right" if c.endswith(":") and not c.startswith(":")
                                 else "center" if c.startswith(":") and c.endswith(":") else "left")
                head, body_rows = rows[0], rows[2:]
            else:
                head, body_rows = rows[0], rows[1:]
                align = ["left"] * len(head)

            def cell(tag: str, cells: list[str]) -> str:
                o = []
                for k, c in enumerate(cells):
                    a = align[k] if k < len(align) else "left"
                    st = f' style="text-align:{a}"' if a != "left" else ""
                    o.append(f"<{tag}{st}>{inl(c)}</{tag}>")
                return "<tr>" + "".join(o) + "</tr>"

            out.append('<div class="tw"><table><thead>' + cell("th", head) + "</thead><tbody>"
                       + "".join(cell("td", r) for r in body_rows) + "</tbody></table></div>")
            continue

        if re.match(r"^\d+\.\s", ln):
            buf = []
            while i < n and re.match(r"^\d+\.\s", lines[i]):
                buf.append(re.sub(r"^\d+\.\s", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inl(x)}</li>" for x in buf) + "</ol>")
            continue

        if re.match(r"^[-*]\s", ln):
            buf = []
            while i < n and re.match(r"^[-*]\s", lines[i]):
                buf.append(re.sub(r"^[-*]\s", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inl(x)}</li>" for x in buf) + "</ul>")
            continue

        buf = []
        while i < n and lines[i].strip() and not re.match(
            r"^(#{2,4}\s|>|\||```|\d+\.\s|[-*]\s)", lines[i]
        ):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + inl(" ".join(buf)) + "</p>")

    return "".join(out)


def cited_files(md: str) -> set[str]:
    found = set()
    for m in CODE.finditer(md):
        fm = FILE.match(m.group(1))
        if fm:
            found.add(fm.group(1))      # tên trần: để kiểm thiếu map
            found.add(m.group(1))       # kèm dòng: để neo đúng chỗ
    return found
