#!/usr/bin/env python3
"""Gom bản đồ ClinicAI thành HTML ngoại tuyến, chỉ dùng thư viện chuẩn.

Chạy từ bất kỳ thư mục nào: python3 scripts/ban-do-mot-tep.py.
Nguồn gốc được giữ nguyên; chỉ bản nhúng nhận cầu nối điều hướng và CSS đọc.
"""

from __future__ import annotations

# ruff: noqa: E501
# HTML/CSS/JS tự chứa giữ dòng nguyên vẹn để đối chiếu với bản hiển thị.
import datetime as dt
import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SECTIONS = {
    "tong-quan": "Tổng quan",
    "viec-can-lam": "Việc cần làm",
    "lego": "Lego",
    "he-thong": "Hệ thống",
    "toc-do": "Tốc độ",
    "so-hoc": "Sổ học",
    "muc-luc": "Mục lục / cách cập nhật",
}


def read(relative: str) -> str:
    """Đọc nguồn UTF-8 trong repo; lỗi thiếu nguồn được báo ngay."""
    return (ROOT / relative).read_text(encoding="utf-8")


def json_script(value: object) -> str:
    """Mã hoá JSON an toàn bên trong thẻ script HTML."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c"
    )


def destination(url: str) -> str | None:
    """Đổi đường dẫn tài liệu đã gộp thành mục và neo nội bộ."""
    path, _, anchor = url.partition("#")
    for suffix, section in (
        ("lego/index.html", "lego"),
        ("he-thong/index.html", "he-thong"),
        ("so-hoc/index.html", "so-hoc"),
        ("VIEC-CAN-LAM.md", "viec-can-lam"),
        ("RA-SOAT-TOC-DO.md", "toc-do"),
        ("BAN-DO-HE-THONG.md", "muc-luc"),
        ("ban-do-clinicai.html", "tong-quan"),
    ):
        if path.endswith(suffix):
            return section + ("/" + anchor if anchor else "")
    return None


def inline(text: str) -> str:
    """Đổi code, liên kết, nhấn mạnh; luôn escape HTML nguồn."""
    tokens: list[str] = []

    def keep(value: str) -> str:
        tokens.append(value)
        return f"\x00{len(tokens) - 1}\x00"

    text = re.sub(
        r"`([^`]+)`", lambda m: keep("<code>" + html.escape(m[1]) + "</code>"), text
    )

    def link(match: re.Match[str]) -> str:
        label, url = match.groups()
        label_html = html.escape(label)
        label_html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", label_html)
        label_html = re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m[1])], label_html)
        target = destination(url)
        escaped = html.escape(url, quote=True)
        if target:
            return keep(f'<a href="#{html.escape(target)}">{label_html}</a>')
        if url.startswith(("https://", "http://", "#")):
            return keep(f'<a href="{escaped}">{label_html}</a>')
        # Tệp ngoài phạm vi vẫn đọc được tên, không mở nhầm trang trắng offline.
        return keep(f'<span title="Nguồn ngoài tệp gộp: {escaped}">{label_html}</span>')

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m[1])], text)


def slug(text: str) -> str:
    """Giữ dấu tiếng Việt như neo tiêu đề của GitHub."""
    return re.sub(r"[^\w\s-]", "", text.lower()).replace(" ", "-")


def markdown(source: str) -> str:
    """Chuyển tập Markdown nguồn: tiêu đề, bảng, list, quote và fenced code."""
    lines = source.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    index = 0
    list_tag = ""

    def flush() -> None:
        if paragraph:
            output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"</{list_tag}>")
            list_tag = ""

    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("```"):
            flush()
            close_list()
            code = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            output.append(
                "<pre><code>" + html.escape("\n".join(code)) + "</code></pre>"
            )
        elif (
            "|" in line
            and index + 1 < len(lines)
            and re.fullmatch(r"[\s|:-]+", lines[index + 1])
            and "-" in lines[index + 1]
        ):
            flush()
            close_list()

            def cells(row: str, tag: str) -> str:
                row = re.sub(r"`[^`]*`", lambda m: m[0].replace("|", "\x01"), row)
                return (
                    "<tr>"
                    + "".join(
                        f"<{tag}>{inline(cell.strip().replace(chr(1), '|').replace(chr(92) + '|', '|'))}</{tag}>"
                        for cell in re.split(r"(?<!\\)\|", row.strip().strip("|"))
                    )
                    + "</tr>"
                )

            output.append(
                '<div class="table-scroll"><table><thead>'
                + cells(line, "th")
                + "</thead><tbody>"
            )
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                output.append(cells(lines[index], "td"))
                index += 1
            output.append("</tbody></table></div>")
            continue
        elif match := re.match(r"^(#{1,6})\s+(.+)$", line):
            flush()
            close_list()
            level, title = len(match[1]), match[2]
            output.append(
                f'<h{level} id="{html.escape(slug(title))}">{inline(title)}</h{level}>'
            )
        elif match := re.match(r"^(?:([-*+])|\d+\.)\s+(.+)$", line):
            flush()
            item = match[2]
            while index + 1 < len(lines):
                following = lines[index + 1]
                if not following.startswith("  ") or not following.strip():
                    break
                if re.match(r"^(?:[-*+]|\d+\.)\s", following.strip()):
                    break
                item += " " + following.strip()
                index += 1
            tag = "ul" if match[1] else "ol"
            if list_tag != tag:
                close_list()
                output.append(f"<{tag}>")
                list_tag = tag
            output.append("<li>" + inline(item) + "</li>")
        elif line.startswith(">"):
            flush()
            close_list()
            output.append("<blockquote>" + inline(line.lstrip("> ")) + "</blockquote>")
        elif re.fullmatch(r"[-*_]{3,}", line):
            flush()
            close_list()
            output.append("<hr>")
        elif not line:
            flush()
            close_list()
        else:
            paragraph.append(line)
        index += 1
    flush()
    close_list()
    return "\n".join(output)


FRAME_BRIDGE = r"""
<style>
html{font-size:14px}body{min-width:0!important;font-size:14px!important}
body *{min-width:0}p,li,td,code,a{overflow-wrap:anywhere}
button,input,select,textarea{font-size:14px!important}
pre{max-width:100%;overflow:auto}table{font-size:14px!important}
.nguon,.phu,.mo,small,.nhan,.the-tt{font-size:14px!important}
@media(max-width:600px){button{min-height:40px}header{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style><script>
(function(){
 const sections=__DESTINATIONS__;
 // about:srcdoc không cho replaceState với URL của trang mẹ. Hash vẫn dùng được.
 history.replaceState=function(state,title,url){
  if(typeof url==='string'&&url.startsWith('#')){
   if(location.hash!==url)location.hash=url;
  }
 };
 function send(){parent.postMessage({clinicai:'hash',section:__SECTION__,hash:location.hash.slice(1)},'*')}
 window.addEventListener('hashchange',send);
 window.addEventListener('message',function(event){
  if(event.source!==parent||!event.data||event.data.clinicai!=='state')return;
  document.documentElement.dataset.theme=event.data.theme;
  if(event.data.target && location.hash.slice(1)!==event.data.target){
   if(window.LEGO&&/^(nv|ht|tai)(\/|$)/.test(event.data.target)){
    const [mode,operation]=event.data.target.split('/');
    document.querySelector('[data-che-do="'+mode+'"]')?.click();
    const op=operation&&document.querySelector('[data-op="'+CSS.escape(operation)+'"]');
    if(op&&op.getAttribute('aria-pressed')!=='true')op.click();
    return;
   }
   const infrastructure=(window.LEGO?.khoi_ha_tang||[]).some(x=>x.id===event.data.target);
   if(infrastructure)document.querySelector('[data-che-do="ht"]')?.click();
   else if(window.LEGO&&(window.LEGO.khoi_nghiep_vu||[]).some(x=>x.id===event.data.target))document.querySelector('[data-che-do="nv"]')?.click();
   const block=document.querySelector('[data-khoi="'+CSS.escape(event.data.target)+'"]');
   if(block){block.click();block.scrollIntoView({block:'center'});}
   else location.hash=event.data.target;
  }
 });
 document.addEventListener('click',function(event){
  const a=event.target.closest('a[href]');if(!a)return;
  const href=a.getAttribute('href');
  // Link tương đối trong srcdoc mặc định lấy URL mẹ, sẽ tải lại cả tệp trong khung.
  if(href.startsWith('#')){event.preventDefault();location.hash=href;return;}
  const path=href.split('#')[0];
  const item=Object.entries(sections).find(([suffix])=>path.endsWith(suffix));
  if(item||href.endsWith('/pull/530')){event.preventDefault();parent.postMessage({clinicai:'navigate',section:item?item[1]:'toc-do',target:href.split('#').slice(1).join('#')},'*');}
  else if(!/^https?:/.test(href)){event.preventDefault();}
 },true);
 function readableText(){
  document.body.querySelectorAll('*').forEach(element=>{
   if(['SCRIPT','STYLE'].includes(element.tagName))return;
   if([...element.childNodes].some(node=>node.nodeType===3&&node.textContent.trim())&&parseFloat(getComputedStyle(element).fontSize)<14)element.style.fontSize='14px';
  });
 }
 readableText();
 new MutationObserver(readableText).observe(document.body,{childList:true,subtree:true});
 parent.postMessage({clinicai:'ready',section:__SECTION__},'*');
})();
</script>
"""


def frame_source(section: str) -> str:
    """Nhúng tài nguyên trang và cầu nối; không sửa tệp nguồn."""
    source = read(f"docs/{section}/index.html")
    handwritten = json.loads(read(f"docs/{section}/viet-tay.json"))
    if section == "lego":
        pattern = r"/\*<<DU-LIEU>>\*/window.LEGO=(.*?);/\*<</DU-LIEU>>\*/"
        match = re.search(pattern, source, re.DOTALL)
        if match is None:
            raise ValueError("Không tìm thấy dữ liệu Lego trong nguồn")
        generated = json.loads(match[1])
        data = {**generated, **handwritten}
        data["consumer"] = {
            key: {**generated["consumer"].get(key, {}), **value}
            for key, value in handwritten["consumer"].items()
        }
        # Mảng thao tác của HTML có đường đi suy từ code, không có trong bản viết tay.
        for key in ("thao_tac", "de_xuat"):
            originals = {item["id"]: item for item in generated[key]}
            data[key] = [
                {**originals.get(item["id"], {}), **item} for item in handwritten[key]
            ]
        replacement = (
            "/*<<DU-LIEU>>*/window.LEGO=" + json_script(data) + ";/*<</DU-LIEU>>*/"
        )
        source = source[: match.start()] + replacement + source[match.end() :]
    elif section == "he-thong":
        pattern = r'(<script id="du-lieu" type="application/json">)(.*?)(</script>)'
        match = re.search(pattern, source, re.DOTALL)
        if match is None:
            raise ValueError("Không tìm thấy dữ liệu Hệ thống trong nguồn")
        data = {
            **json.loads(match[2]),
            "viet_tay": handwritten,
            "so_do": json.loads(read("docs/he-thong/so-do.json")),
        }
        replacement = match[1] + json_script(data) + match[3]
        source = source[: match.start()] + replacement + source[match.end() :]
    else:
        data_js = read("docs/so-hoc/data.js")
        data = json.loads(
            data_js.split("window.SO_HOC =", 1)[1].strip().removesuffix(";")
        )
        data = {**data, "viet_tay": handwritten}
        source = source.replace(
            '<script src="data.js"></script>',
            "<script>window.SO_HOC=" + json_script(data) + ";</script>",
        )
    mapping = {
        "lego/index.html": "lego",
        "he-thong/index.html": "he-thong",
        "so-hoc/index.html": "so-hoc",
        "VIEC-CAN-LAM.md": "viec-can-lam",
        "RA-SOAT-TOC-DO.md": "toc-do",
        "BAN-DO-HE-THONG.md": "muc-luc",
    }
    bridge = FRAME_BRIDGE.replace("__DESTINATIONS__", json_script(mapping)).replace(
        "__SECTION__", json_script(section)
    )
    # Cầu nối chạy sau mã gốc để màu của shell thắng thiết lập đã lưu ở trang con.
    return source.replace("</body>", bridge + "</body>")


SHELL = r"""<!doctype html>
<html lang="vi" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; frame-src about:; connect-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'">
<title>Bản đồ ClinicAI · một tệp</title><style>
:root{color-scheme:light;--bg:#f5f3ee;--card:#fffefa;--ink:#292820;--muted:#68665d;--line:#d8d3c7;--accent:#b95016;--wash:#fff0df}
:root[data-theme=dark]{color-scheme:dark;--bg:#181b20;--card:#232830;--ink:#eee9df;--muted:#bcb7ae;--line:#454951;--accent:#ffac62;--wash:#3e2d20}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif}
button,input,select{font:inherit}button,a{touch-action:manipulation}a{color:var(--accent)}button{cursor:pointer;border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--card);color:var(--ink);min-height:40px}
button:focus-visible,a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.top{position:sticky;top:0;z-index:20;background:var(--card);border-bottom:1px solid var(--line);padding:12px 24px}
.brand{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.brand strong{font-size:22px}.stamp{font-size:14px;color:var(--muted)}
nav{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}nav a{padding:6px 10px;text-decoration:none;border:1px solid transparent;border-radius:8px;font-size:14px;font-weight:600}nav a[aria-current=page]{background:var(--wash);border-color:var(--accent)}
main{max-width:1440px;margin:auto}section[hidden]{display:none!important}.paper{max-width:1100px;margin:auto;padding:24px}h1{font-size:28px}h2{font-size:22px}h3{font-size:18px}p,li,td{overflow-wrap:anywhere}code{font-size:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--card);border:1px solid var(--line);padding:16px;border-radius:12px}
.table-scroll{max-width:100%;overflow:auto}table{border-collapse:collapse;min-width:560px;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:12px;text-align:left;vertical-align:top}blockquote{border-left:3px solid var(--accent);margin-left:0;padding-left:16px}
iframe{display:block;border:0;width:100%;height:calc(100dvh - 164px);min-height:500px;background:var(--bg)}.notice{padding:12px 24px;background:var(--wash);font-size:14px}
@media(max-width:600px){.top{padding:8px 12px}.brand strong{font-size:18px}.stamp{width:100%}nav{gap:0}nav a{padding:6px;font-size:14px}.paper{padding:16px}h1{font-size:24px}iframe{height:calc(100dvh - 230px)}.notice{padding:8px 12px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style></head><body>
<header class="top"><div class="brand"><strong>ClinicAI / Bản đồ một tệp</strong><button type="button" id="theme">Đổi sáng / tối</button><span class="stamp">Sinh __DATE__ · commit __SHA__ · nguồn đo 23/10/2026</span></div><nav aria-label="Các mục bản đồ">__NAV__</nav></header>
<main>__CONTENT__</main>
<script>
const frames=__FRAMES__;
const sectionNames=__SECTIONS__;
let theme=matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light';
try{theme=localStorage.getItem('ban-do-theme')||theme}catch(e){}
function applyTheme(){document.documentElement.dataset.theme=theme;document.body.dataset.theme=theme;document.querySelectorAll('iframe').forEach(frame=>frame.contentWindow.postMessage({clinicai:'state',theme},'*'));}
document.getElementById('theme').onclick=()=>{theme=theme==='dark'?'light':'dark';try{localStorage.setItem('ban-do-theme',theme)}catch(e){}applyTheme()};
function route(){
 const hash=location.hash.slice(1)||'tong-quan';const [id,...rest]=hash.split('/');
 const section=sectionNames[id]?id:'tong-quan';const target=rest.join('/');
 document.querySelectorAll('main>section').forEach(el=>el.hidden=el.id!==section);
 document.querySelectorAll('nav a').forEach(el=>{if(el.hash==='#'+section)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')});
 if(frames[section]){
  let frame=document.querySelector('#'+section+' iframe');
  if(!frame){frame=document.createElement('iframe');frame.title=sectionNames[section];frame.setAttribute('sandbox','allow-scripts allow-same-origin');frame.srcdoc=frames[section];document.getElementById(section).append(frame);}
  frame.contentWindow.postMessage({clinicai:'state',theme,target},'*');
 }else if(target){document.getElementById(decodeURIComponent(target))?.scrollIntoView({block:'start'});}
 document.dispatchEvent(new CustomEvent('clinicai-section',{detail:section}));
}
window.navigate=function(section,target=''){location.hash=section+(target?'/'+target:'');route()};
window.addEventListener('hashchange',route);
window.addEventListener('message',event=>{
 const data=event.data;if(!data||!data.clinicai)return;
 const frame=[...document.querySelectorAll('iframe')].find(f=>f.contentWindow===event.source);if(!frame)return;
 if(data.clinicai==='navigate'){window.navigate(data.section,data.target||'');return;}
 if(data.clinicai==='ready'){const target=location.hash.slice(1).split('/').slice(1).join('/');frame.contentWindow.postMessage({clinicai:'state',theme,target},'*');return;}
 if(data.clinicai==='hash'&&frame.parentElement.id===location.hash.slice(1).split('/')[0]){history.replaceState(null,'','#'+data.section+(data.hash?'/'+data.hash:''));}
});
applyTheme();route();
</script></body></html>
"""

# Tổng quan dùng chung nguồn JSON với bản đồ chi tiết, không gọi mạng lúc xem.
OVERVIEW = r"""<style>
#ov-root{--ov-bg:#fff;--ov-soft:#eef1f5;--ov-ink:#1c2430;--ov-muted:#556070;--ov-line:#d5dbe3;--ov-blue:#2f5fd0;--ov-blue-soft:#e3ebfb;--ov-orange:#e8730c;--ov-orange-soft:#fff0e2;--ov-red:#d33a2c;--ov-yellow:#a46d00;--ov-green:#187d44;color:var(--ov-ink);font:15px/1.5 system-ui,sans-serif;max-width:1248px;margin:auto;overflow-wrap:anywhere}
body[data-theme=dark] #ov-root,:root[data-theme=dark] #ov-root{--ov-bg:#1b2129;--ov-soft:#232b35;--ov-ink:#e6ebf2;--ov-muted:#a3aebd;--ov-line:#46515f;--ov-blue:#7aa2ff;--ov-blue-soft:#1f2c47;--ov-orange:#ff9a3d;--ov-orange-soft:#3a2814;--ov-red:#ff6b5e;--ov-yellow:#f0b429;--ov-green:#45c27f}
#ov-root *{box-sizing:border-box}#ov-root h2{font-size:22px;line-height:1.3;margin:0 0 8px}#ov-root h3{font-size:18px;margin:0}#ov-root p{margin:8px 0}#ov-root button,#ov-root input{font:inherit}#ov-root button{cursor:pointer;color:var(--ov-ink);background:var(--ov-bg);border:1px solid var(--ov-line);border-radius:8px;padding:8px 12px;min-height:40px}#ov-root button:hover,#ov-root button:focus-visible{outline:2px solid var(--ov-orange);outline-offset:2px}#ov-root button:disabled{opacity:.5;cursor:default}#ov-root code{font-size:14px;overflow-wrap:anywhere}#ov-root .ov-muted{color:var(--ov-muted);font-size:14px}#ov-root .ov-panel{background:var(--ov-bg);border:1px solid var(--ov-line);border-radius:12px;padding:20px;margin:20px 0;min-width:0}#ov-root .ov-head,#ov-root .ov-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap}#ov-root .ov-head{justify-content:space-between;margin-bottom:12px}#ov-root .ov-legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--ov-muted);font-size:14px}.ov-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;background:var(--ov-green)}.ov-dot.ov-red{background:var(--ov-red)}.ov-dot.ov-yellow{background:var(--ov-yellow)}#ov-root .ov-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:28px 24px;margin:24px 0 16px}#ov-root .ov-block{position:relative;min-height:100px;background:var(--ov-blue-soft);border:2px solid transparent;border-radius:10px;padding:16px 12px 12px;opacity:.45;transition:opacity .2s,border-color .2s,background .2s;min-width:0}#ov-root .ov-block::before{content:"";position:absolute;top:-10px;left:14px;width:56px;height:10px;background:radial-gradient(circle at 9px 5px,var(--ov-blue) 6px,transparent 6.5px) 0 0/22px 10px repeat-x}#ov-root .ov-block::after{content:"→";position:absolute;right:-23px;top:32px;color:var(--ov-line);font-size:22px}#ov-root .ov-block:nth-child(4n)::after{content:"↓";right:10px;top:auto;bottom:-29px}#ov-root .ov-block:last-child::after{display:none}#ov-root .ov-block strong{display:block}#ov-root .ov-active{opacity:1;background:var(--ov-orange-soft);border-color:var(--ov-orange)}#ov-root .ov-active::after{color:var(--ov-orange)}#ov-root .ov-active::before{background-image:radial-gradient(circle at 9px 5px,var(--ov-orange) 6px,transparent 6.5px)}#ov-root .ov-person{display:inline-block;color:var(--ov-orange);margin-right:6px}#ov-root .ov-caption{padding:12px;background:var(--ov-soft);border-radius:8px;min-height:70px}#ov-root .ov-track{height:12px;border-radius:6px;background:var(--ov-soft);overflow:hidden;margin:12px 0}#ov-root .ov-fill{height:100%;width:0;background:var(--ov-orange);transform-origin:left}#ov-root .ov-steps{padding-left:24px}#ov-root .ov-steps li{padding:8px;border-left:2px solid var(--ov-line);opacity:.6}#ov-root .ov-steps li.ov-current{opacity:1;border-color:var(--ov-orange);background:var(--ov-orange-soft)}#ov-root .ov-time{display:inline-block;font-size:14px;border:1px solid var(--ov-line);border-radius:6px;padding:0 6px;margin:4px}#ov-root .ov-async{border:2px dashed var(--ov-line);border-radius:12px;padding:16px;margin:16px 0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}#ov-root .ov-async .ov-block::after{content:"⇢";color:var(--ov-orange)}#ov-root .ov-async .ov-block:last-child::after{display:none}#ov-root .ov-pulse{display:flex;align-items:center;gap:12px;flex-wrap:wrap}#ov-root .ov-pulse span:first-child{font-size:32px;color:var(--ov-orange);font-variant-numeric:tabular-nums}#ov-root .ov-load{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}#ov-root .ov-capacity{padding:14px;border:1px solid var(--ov-line);border-radius:10px;min-width:0}#ov-root .ov-capacity strong{display:block}#ov-root .ov-load .ov-track{height:18px}#ov-root .ov-range{display:flex;align-items:center;gap:16px;flex-wrap:wrap}#ov-root .ov-range input{width:min(100%,360px);accent-color:var(--ov-orange)}#ov-root .ov-load-notes p{padding:8px 0;border-bottom:1px solid var(--ov-line)}#ov-root .ov-chart{display:flex;gap:3px;align-items:stretch;height:230px;margin:20px 0 8px;border-bottom:1px solid var(--ov-line)}#ov-root .ov-bar-wrap{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:flex-end;position:relative}#ov-root .ov-bar{background:var(--ov-blue);height:var(--ov-height);min-height:1px;transform:scaleY(0);transform-origin:bottom}#ov-root .ov-bar.ov-peak{background:var(--ov-orange)}#ov-root .ov-hour{font-size:14px;color:var(--ov-muted);height:24px;text-align:center}#ov-root .ov-chart-key{display:flex;justify-content:space-between;font-size:14px;color:var(--ov-muted)}#ov-root .ov-tasks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}#ov-root details{border:1px solid var(--ov-line);border-radius:10px;padding:12px;min-width:0}#ov-root summary{cursor:pointer;font-weight:600;min-height:40px}#ov-root details p{font-size:14px}#ov-root .ov-source{font-size:14px;color:var(--ov-muted);margin-top:12px}#ov-root .ov-static .ov-block{opacity:1}#ov-root .ov-static *{transition:none!important}
@media(max-width:650px){#ov-root .ov-panel{padding:14px;margin:14px 0}#ov-root .ov-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:28px 20px}#ov-root .ov-block::after{right:-21px}#ov-root .ov-block:nth-child(2n)::after{content:"↓";right:8px;top:auto;bottom:-29px}#ov-root .ov-block:last-child::after{display:none}#ov-root .ov-load,#ov-root .ov-tasks{grid-template-columns:1fr}#ov-root .ov-async{grid-template-columns:1fr;gap:24px}#ov-root .ov-async .ov-block::after{content:"⇣";right:12px;top:auto;bottom:-29px}#ov-root .ov-head{align-items:flex-start}#ov-root .ov-hour{font-size:14px}#ov-root .ov-chart{gap:2px;height:180px}}
/* Dây đi zích-zắc qua đúng thứ tự DOM, không nối tắt từ khối 4 sang khối 8. */
@media(min-width:651px){
 #ov-root .ov-grid .ov-block:nth-child(5){grid-area:2/4}
 #ov-root .ov-grid .ov-block:nth-child(6){grid-area:2/3}
 #ov-root .ov-grid .ov-block:nth-child(7){grid-area:2/2}
 #ov-root .ov-grid .ov-block:nth-child(8){grid-area:2/1}
 #ov-root .ov-grid .ov-block:nth-child(n+5)::after{content:"←";left:-25px;right:auto;top:32px;bottom:auto}
}
@media(max-width:650px){
 #ov-root .ov-grid .ov-block:nth-child(3){grid-area:2/2}
 #ov-root .ov-grid .ov-block:nth-child(4){grid-area:2/1}
 #ov-root .ov-grid .ov-block:nth-child(5){grid-area:3/1}
 #ov-root .ov-grid .ov-block:nth-child(6){grid-area:3/2}
 #ov-root .ov-grid .ov-block:nth-child(7){grid-area:4/2}
 #ov-root .ov-grid .ov-block:nth-child(8){grid-area:4/1}
 #ov-root .ov-grid .ov-block:nth-child(3)::after,#ov-root .ov-grid .ov-block:nth-child(7)::after{content:"←";left:-23px;right:auto;top:32px;bottom:auto}
 #ov-root .ov-grid .ov-block:nth-child(4)::after{left:8px;right:auto}
}
@media(prefers-reduced-motion:reduce){#ov-root *{transition:none!important;animation:none!important}}
</style>
<div id="ov-root">
 <h2>ClinicAI — nhìn một lượt, hiểu đường đi</h2>
 <p class="ov-muted">Chọn một minh hoạ rồi nhìn khối sáng cam. Đây là bản đồ từ mã nguồn và số đo đã lưu; các tình huống đông người là ước theo cấu hình, chưa thử tải.</p>
 <div class="ov-legend"><span><i class="ov-dot"></i>Đường ghi bình thường</span><span><i class="ov-dot ov-yellow"></i>Chờ / cần chú ý</span><span><i class="ov-dot ov-red"></i>Nút nghẽn / rủi ro</span><span>Cam: khối và dây đang đi qua · nét đứt: bất đồng bộ</span></div>
 <p id="ov-motion-note" class="ov-muted"></p>
 <section class="ov-panel" id="ov-journey"><div class="ov-head"><h3>01 · Hành trình một bệnh nhân</h3><div class="ov-controls"></div></div><p class="ov-muted">Chấm cam là khách. Nhịp chạy chỉ để kể chuyện, không phải thời gian chờ khám đã đo.</p><div class="ov-grid" id="ov-journey-blocks"></div><div class="ov-caption" id="ov-journey-caption"></div></section>
 <section class="ov-panel" id="ov-payment"><div class="ov-head"><h3>02 · Một lần bấm “Thu”</h3><div class="ov-controls"></div></div><p id="ov-payment-summary"></p><div class="ov-grid" id="ov-payment-blocks"></div><div class="ov-track" aria-hidden="true"><div class="ov-fill" id="ov-payment-progress"></div></div><p id="ov-payment-clock" class="ov-muted"></p><div class="ov-caption" id="ov-payment-caption"></div><details><summary>Mở từng bước, thời gian và nguồn</summary><ol class="ov-steps" id="ov-payment-steps"></ol></details><p class="ov-source" id="ov-payment-source"></p></section>
 <section class="ov-panel" id="ov-events"><div class="ov-head"><h3>03 · Ghi xong rồi, sự kiện còn đang đi</h3><div class="ov-controls"></div></div><p>Ghi dữ liệu xong mới báo màn qua <code>pg_notify → SSE</code>. Một đường khác ghi việc vào sổ <code>domain_event → event_delivery</code>; worker <code>su-kien</code> giao lần lượt cho bên nhận. Đây là hai đường có liên quan, không phải một hàng duy nhất.</p><div class="ov-async"><div class="ov-block" id="ov-event-book"><strong>Sổ sự kiện</strong><span class="ov-muted">domain_event · event_delivery</span></div><div class="ov-block" id="ov-event-worker"><strong>Worker su-kien</strong><span class="ov-muted">Một tiến trình · tuần tự</span></div><div class="ov-block" id="ov-event-receiver"><strong>Bên nhận → ghi → SSE</strong><span class="ov-muted">Công nợ · hành trình · sổ nợ…</span></div></div><div class="ov-pulse"><span id="ov-event-clock">1,0 s</span><p id="ov-event-caption"></p></div><div class="ov-track" aria-hidden="true"><div class="ov-fill" id="ov-event-progress"></div></div><p class="ov-source">Nhịp nghỉ 1 giây: nguồn bước Thu tiền dịch vụ, worker.py:332. Thời gian giao trong hình chỉ là nhịp minh hoạ; không phải số đo. Không dùng RabbitMQ / Redis trên đường này.</p></section>
 <section class="ov-panel" id="ov-load"><div class="ov-head"><h3>04 · Nếu mọi người cùng bấm?</h3><div class="ov-controls"></div></div><p class="ov-muted" id="ov-load-disclaimer"></p><div class="ov-range"><label for="ov-people">Người cùng bấm: <strong id="ov-people-count">1</strong></label><input id="ov-people" type="range" min="0" max="3" step="1" value="0" aria-valuetext="1 người"><span class="ov-muted">1 · 11 · 101 · 1.000</span></div><div class="ov-load" id="ov-capacities"></div><div class="ov-load-notes" id="ov-load-notes"></div><p class="ov-source">Thanh đầy = tỉ lệ nhu cầu minh hoạ trên năng lực cấu hình, không phải đo sử dụng CPU. Next 4 tiến trình không có nghĩa chỉ nhận được 4 request; Postgres được bể API chặn trước. Một người bấm cũng chưa có kết quả thử tải riêng.</p></section>
 <section class="ov-panel" id="ov-prod"><div class="ov-head"><h3>05 · 24 giờ của prod</h3><div class="ov-controls"></div></div><p id="ov-prod-summary"></p><div class="ov-chart" id="ov-chart" role="img"></div><div class="ov-chart-key"><span>00h</span><span>06h</span><span>12h</span><span>18h</span><span>23h</span></div><p class="ov-muted" id="ov-prod-source"></p><details><summary>Đọc số request từng giờ</summary><div id="ov-prod-values"></div></details></section>
 <section class="ov-panel" id="ov-work"><div class="ov-head"><h3>06 · 10 việc cần làm</h3></div><p class="ov-muted">Mở thẻ để đọc gốc và hướng sửa; nút trong thẻ đưa tới khối Lego liên quan. Đỏ = có mức 3; vàng = mức 2. Thứ tự theo VIEC-CAN-LAM.md, không phải trạng thái đã sửa.</p><div class="ov-tasks" id="ov-tasks"></div></section>
</div>
<script>
(() => {
 'use strict';
 const OVERVIEW_DATA = __OVERVIEW_DATA__;
 const {lego,system,tasks} = OVERVIEW_DATA;
 const root=document.getElementById('ov-root'), get=id=>document.getElementById(id);
 const number=n=>Number(n).toLocaleString('vi-VN');
 const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const plain=s=>String(s).replace(/\[([^\]]+)\]\([^)]*\)/g,'$1').replace(/[*`]/g,'');
 const reduce=matchMedia('(prefers-reduced-motion: reduce)');
 const payments=lego.thao_tac.find(x=>x.id==='thu-ngan-01');
 const controllers=[];
 function controller(id,duration,draw,auto=false){
   const section=get(id),controls=section.querySelector('.ov-controls');
   let elapsed=0,playing=false,last=0,frame=0;
   const play=document.createElement('button'),restart=document.createElement('button');
   play.type=restart.type='button';play.textContent='Chạy';restart.textContent='Chạy lại';controls.append(play,restart);
   function paint(){draw(reduce.matches?1:Math.min(elapsed/duration,1));}
   function stop(){playing=false;cancelAnimationFrame(frame);play.textContent='Chạy tiếp';play.setAttribute('aria-pressed','false');}
   function tick(now){if(!playing)return;if(last)elapsed+=now-last;last=now;paint();if(elapsed>=duration){stop();play.textContent='Đã xong · chạy lại';return;}frame=requestAnimationFrame(tick);}
   function start(reset=false){if(reduce.matches)return;if(reset||elapsed>=duration)elapsed=0;last=0;playing=true;play.textContent='Tạm dừng';play.setAttribute('aria-pressed','true');frame=requestAnimationFrame(tick);}
   play.addEventListener('click',()=>playing?stop():start());restart.addEventListener('click',()=>{stop();elapsed=0;paint();start(true);});
   function motion(){stop();play.disabled=restart.disabled=reduce.matches;root.classList.toggle('ov-static',reduce.matches);paint();}
   reduce.addEventListener('change',motion);motion();
   const c={stop,start,paint};controllers.push(c);
   if(auto){const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){start(true);observer.disconnect();}},{threshold:.25});observer.observe(section);}
   return c;
 }
 function block(title,description=''){return `<div class="ov-block"><strong>${escape(title)}</strong><span class="ov-muted">${escape(description)}</span></div>`;}
 const route=['dat-lich','tiep-don','kham','phong-dv','thu-ngan','thuoc','check-out','ket-qua-cskh'].map(id=>lego.khoi_nghiep_vu.find(x=>x.id===id));
 get('ov-journey-blocks').innerHTML=route.map(x=>block(x.ten,x.mo_ta)).join('');
 controller('ov-journey',16000,p=>{const index=Math.min(7,Math.floor(p*8));[...get('ov-journey-blocks').children].forEach((el,i)=>{el.classList.toggle('ov-active',i===index);el.querySelector('strong').textContent=(i===index?'● ':'')+route[i].ten;});get('ov-journey-caption').textContent=`${index+1}/${route.length} · ${route[index].ten}: ${route[index].mo_ta}`;});
 const infra=[['trinh-duyet','Trình duyệt'],['caddy','Caddy'],['next','Next.js'],['api','FastAPI'],['postgres','Postgres'],['notify','Trigger pg_notify'],['sse','SSE'],['tabs','Các tab tải lại']];
 get('ov-payment-blocks').innerHTML=infra.map(x=>block(x[1])).join('');
 get('ov-payment-summary').textContent=payments.tong_thoi_gian.y;
 get('ov-payment-steps').innerHTML=payments.buoc.map((s,i)=>`<li data-ov-step="${i}"><i class="ov-dot ${s.den==='do'?'ov-red':s.den==='vang'?'ov-yellow':''}"></i>${escape(s.y)} <span class="ov-time">${escape(s.thoi_gian)} · ${s.nhan_tg==='do'?'đã đo':'ước'}</span><div class="ov-source">${escape(s.nguon)}</div></li>`).join('');
 const measuredWrite=lego.do_that.find(x=>x.ma==='ghi-tien');
 const measuredLoad=lego.do_that.find(x=>x.ma==='tai-quay');
 get('ov-payment-source').textContent=`${measuredWrite.y}: ${measuredWrite.so}, đã đo (${measuredWrite.nguon}). ${measuredLoad.y}: ${measuredLoad.so}, đã đo (${measuredLoad.nguon}). Khoảng 7 giây là ước từ 2 lượt tải × 3,4 giây; phần phân bổ chuyển động Caddy/Next/API chỉ để minh hoạ, không phải đo từng tầng. Số đo prod mới hơn nằm ở biểu đồ bên dưới (${system.do_luc}).`;
 const writeSeconds=parseFloat(measuredWrite.so.match(/\d+,\d+/)[0].replace(',','.'));
 const boardSeconds=parseFloat(measuredLoad.so.match(/\d+,\d+/)[0].replace(',','.'));
 const total=boardSeconds*2;
 const storyDuration=4200+(total-1)*1000;
 controller('ov-payment',storyDuration,p=>{
   const storyMs=p*storyDuration;
   // Phát chậm phần ghi để thấy từng tầng; đồng hồ vẫn giữ số nguồn.
   const seconds=storyMs<3000?storyMs/3000*writeSeconds:storyMs<3600?writeSeconds+(storyMs-3000)/600*.03:storyMs<4200?writeSeconds+.03+(storyMs-3600)/600*(1-writeSeconds-.03):1+(storyMs-4200)/1000;
   const index=seconds<writeSeconds?Math.min(4,Math.floor(seconds/writeSeconds*5)):seconds<writeSeconds+.03?5:seconds<1?6:7;
   [...get('ov-payment-blocks').children].forEach((el,i)=>el.classList.toggle('ov-active',i===index));
   get('ov-payment-progress').style.width=`${p*100}%`;
   const step=seconds<writeSeconds?Math.min(3,Math.floor(seconds/writeSeconds*4)):seconds<writeSeconds+.03?4:seconds<2?5:seconds<total?6:7;
   [...get('ov-payment-steps').children].forEach((el,i)=>el.classList.toggle('ov-current',i===step));
   get('ov-payment-clock').textContent=`${seconds.toLocaleString('vi-VN',{maximumFractionDigits:2})} / ~${total.toLocaleString('vi-VN')} giây · phần ghi phát chậm để thấy từng khối; đồng hồ không tuyến tính · tổng ước từ 2 lượt tải bảng đã đo`;
   get('ov-payment-caption').textContent=payments.buoc[step].y;
 });
 controller('ov-events',6000,p=>{const ms=p*6000,phase=ms%2000,rest=phase<1000;get('ov-event-clock').textContent=rest?`${((1000-phase)/1000).toFixed(1).replace('.',',')} s`:'⇢';get('ov-event-caption').textContent=rest?'Worker đang nghỉ giữa hai vòng — sự kiện mới phải chờ tới lần thức tiếp theo.':'Worker thức, đọc event_delivery rồi giao từng bên nhận; bên nhận ghi lại dữ liệu và có thể bắn tin mới.';['ov-event-book','ov-event-worker','ov-event-receiver'].forEach((id,i)=>get(id).classList.toggle('ov-active',rest?i===0:i===Math.min(2,1+Math.floor((phase-1000)/500))));get('ov-event-progress').style.width=`${rest?phase/10:(phase-1000)/10}%`;});
 const layers=lego.tai.tang,people=[1,11,101,1000];
 const poolCapacity=Number(layers.find(x=>x.id==='pool').ten.match(/(\d+) kết nối/)[1]);
 const nextCapacity=Number(layers.find(x=>x.id==='next').ten.match(/(\d+) tiến trình/)[1]);
 const workerCapacity=Number(layers.find(x=>x.id==='su-kien').ten.match(/(\d+) tiến trình/)[1]);
 const loadRows=[['next','Next.js',nextCapacity],['pool','Bể kết nối API',poolCapacity],['postgres','Postgres',system.db.max_ket_noi],['su-kien','Worker su-kien',workerCapacity]];
 get('ov-load-disclaimer').textContent=lego.tai.nhan;
 get('ov-capacities').innerHTML=loadRows.map(([id,title,capacity])=>`<div class="ov-capacity" data-ov-layer="${id}"><strong>${escape(title)}</strong><span class="ov-muted">${capacity} ${id==='postgres'||id==='pool'?'kết nối':'tiến trình'}</span><div class="ov-track"><div class="ov-fill"></div></div><span class="ov-capacity-text"></span></div>`).join('');
 function loadDraw(p){const n=people[Number(get('ov-people').value)];get('ov-people-count').textContent=number(n);get('ov-people').setAttribute('aria-valuetext',`${number(n)} người`);loadRows.forEach(([id,title,cap])=>{const el=root.querySelector(`[data-ov-layer="${id}"]`),demand=id==='postgres'?Math.min(n,poolCapacity):n;el.querySelector('.ov-fill').style.width=`${Math.min(demand/cap,1)*p*100}%`;el.querySelector('.ov-capacity-text').textContent=id==='pool'?`${Math.min(n,cap)} đang mượn · ${Math.max(0,n-cap)} chờ (ước)`:id==='postgres'?`API đưa tối đa ${Math.min(n,poolCapacity)} kết nối vào; còn GoTrue, worker…`:id==='next'?`${number(n)} tab; dựng trang chia trên ${cap} tiến trình`:`${number(n)} lệnh sinh sự kiện; giao lần lượt`;});get('ov-load-notes').innerHTML=loadRows.map(([id,title])=>{const layer=layers.find(x=>x.id===id);return `<p><strong>${escape(title)}:</strong> ${escape(n===1?'Một người: minh hoạ cấu hình, chưa có số thử tải riêng.':layer['n'+n])}</p>`;}).join('');}
 const loadControl=controller('ov-load',1500,loadDraw);
 get('ov-people').addEventListener('input',()=>{loadControl.stop();loadDraw(1);});loadDraw(1);
 const hourly=system.prod.req_moi_gio,peak=Math.max(...hourly);
 get('ov-prod-summary').textContent=`${number(system.prod.tong_req_24h)} request trong cửa sổ 24 giờ đã lưu. Đỉnh ${system.prod.gio_dinh.gio}h: ${number(system.prod.gio_dinh.so_req)} request — đã đo.`;
 get('ov-chart').setAttribute('aria-label',`Request theo 24 giờ, đỉnh ${system.prod.gio_dinh.gio} giờ ${number(peak)} request`);
 get('ov-chart').innerHTML=hourly.map((n,h)=>`<div class="ov-bar-wrap" title="${h}h: ${number(n)} request"><div class="ov-bar${n===peak?' ov-peak':''}" style="--ov-height:${n/peak*100}%"></div></div>`).join('');
 get('ov-prod-source').textContent=`Đã đo · ${system.do_luc}. Nguồn: docs/he-thong/so-do.json → prod.req_moi_gio. Đây là ảnh chụp số đo, không phải bảng theo dõi trực tiếp.`;
 get('ov-prod-values').innerHTML=hourly.map((n,h)=>`<p>${String(h).padStart(2,'0')}h: <strong>${number(n)}</strong> request</p>`).join('');
 controller('ov-prod',2000,p=>{root.querySelectorAll('.ov-bar').forEach((el,i)=>el.style.transform=`scaleY(${Math.max(0,Math.min(1,p*2-i/24))})`);},true);
 const taskMap=['su-kien','next','thu-ngan','thu-ngan','thuoc','dat-lich','gotrue','postgres','sse','gotrue'];
 const taskText=typeof tasks==='string'?tasks:(tasks.markdown||'');
 const taskSections=[...taskText.matchAll(/^### (\d+)\. (.+)\n([\s\S]*?)(?=^### |^## |$(?![\s\S]))/gm)].filter(x=>+x[1]<=10);
 get('ov-tasks').innerHTML=taskSections.map(([all,n,title,body],i)=>{const red=/Mức 3|\*\*3\*\*|\+ \*\*3/i.test(body);return `<details><summary><i class="ov-dot ${red?'ov-red':'ov-yellow'}"></i>${n}. ${escape(title)}</summary>${body.trim().split('\n').filter(x=>x.startsWith('- ')).map(x=>`<p>${escape(plain(x.slice(2)))}</p>`).join('')}<button type="button" data-ov-target="${taskMap[i]}">Xem khối Lego liên quan →</button></details>`;}).join('');
 root.querySelectorAll('[data-ov-target]').forEach(button=>button.addEventListener('click',()=>{if(typeof window.navigate==='function')window.navigate('lego',button.dataset.ovTarget);else window.dispatchEvent(new CustomEvent('clinicai:navigate',{detail:{section:'lego',target:button.dataset.ovTarget}}));}));
 function motionNote(){get('ov-motion-note').textContent=reduce.matches?'Máy đang bật giảm chuyển động: hiển thị bản tĩnh, mọi animation đã dừng.':'Mỗi minh hoạ có nút Chạy / Tạm dừng và Chạy lại. Biểu đồ 24 giờ vẽ khi bạn cuộn tới.';}
 reduce.addEventListener('change',motionNote);motionNote();
 document.addEventListener('visibilitychange',()=>{if(document.hidden)controllers.forEach(c=>c.stop());});
})();
</script>
"""


def build() -> str:
    """Dựng HTML xác định theo nguồn, ngày và commit hiện tại."""
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short=8", "HEAD"], cwd=ROOT, text=True
    ).strip()
    overview_data = {
        "system": json.loads(read("docs/he-thong/so-do.json")),
        "lego": json.loads(read("docs/lego/viet-tay.json")),
        "tasks": read("docs/VIEC-CAN-LAM.md"),
    }
    overview = OVERVIEW.replace("__OVERVIEW_DATA__", json_script(overview_data))
    sections = [f'<section id="tong-quan">{overview}</section>']
    for name, file in (
        ("viec-can-lam", "VIEC-CAN-LAM.md"),
        ("toc-do", "RA-SOAT-TOC-DO.md"),
        ("muc-luc", "BAN-DO-HE-THONG.md"),
    ):
        content = markdown(read("docs/" + file))
        if name == "muc-luc":
            content = (
                "<h1>Mục lục / cách cập nhật</h1><p>Đây là bản ngoại tuyến. "
                "Nguồn ngoài phạm vi gộp được ghi tên để tra trong repo. "
                "Liên kết HTTPS chỉ mở khi bạn chủ động bấm.</p>"
                "<h2>Sinh lại tệp gộp</h2><pre><code>python3 scripts/ban-do-mot-tep.py</code></pre>"
                "<p>Sửa nguồn, chạy các script sinh từng bản đồ bên dưới nếu code đổi, "
                "rồi chạy lệnh gộp. Không sửa tay tệp HTML kết quả. "
                "Giữ tệp ở máy cá nhân; có nội dung bảo mật nội bộ.</p>" + content
            )
        sections.append(
            f'<section id="{name}" hidden><article class="paper">{content}</article></section>'
        )
    sections.extend(
        f'<section id="{name}" hidden></section>'
        for name in ("lego", "he-thong", "so-hoc")
    )
    values = {
        "__DATE__": dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
        .date()
        .isoformat(),
        "__SHA__": sha,
        "__NAV__": "".join(f'<a href="#{k}">{v}</a>' for k, v in SECTIONS.items()),
        "__CONTENT__": "\n".join(sections),
        "__FRAMES__": json_script(
            {name: frame_source(name) for name in ("lego", "he-thong", "so-hoc")}
        ),
        "__SECTIONS__": json_script(SECTIONS),
    }
    result = SHELL
    for key, value in values.items():
        result = result.replace(key, value)
    return result


def main() -> None:
    """Ghi tệp đầu ra với trần dung lượng được giao."""
    output = build()
    size = len(output.encode("utf-8"))
    if size > 15 * 1024 * 1024:
        raise ValueError(f"Tệp gộp vượt 15 MB: {size} byte")
    target = DOCS / "ban-do-clinicai.html"
    target.write_text(output, encoding="utf-8")
    print(f"{target.relative_to(ROOT)}: {size:,} byte")


if __name__ == "__main__":
    main()
