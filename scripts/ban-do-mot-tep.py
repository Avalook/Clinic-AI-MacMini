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
html{font-size:16px;--reader-font:16px}body{min-width:0!important;font-size:var(--reader-font)!important;line-height:1.75!important}
body *{min-width:0}p,li,td,code,a{overflow-wrap:anywhere}
button,input,select,textarea{font-size:var(--reader-font)!important}
pre{max-width:100%;overflow:auto}table{font-size:14px!important}
.embedded-intro{margin:12px 16px;border-bottom:1px solid var(--line,#ddd)}
.embedded-intro>summary{padding:10px 0;min-height:44px;cursor:pointer}
.embedded-intro .dau{position:static}
.nguon,.phu,.mo,small,.nhan,.the-tt{font-size:var(--reader-font)!important}
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
  document.documentElement.style.setProperty('--reader-font',(event.data.font||16)+'px');
  readableText();
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
   const minimum=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--reader-font'))||16;
   if([...element.childNodes].some(node=>node.nodeType===3&&node.textContent.trim())&&(element.dataset.readerFont||parseFloat(getComputedStyle(element).fontSize)<minimum)){
    element.style.fontSize=minimum+'px';element.dataset.readerFont='true';
   }
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
    if section in ("he-thong", "so-hoc"):
        source = re.sub(
            r"(<header\b[^>]*>.*?</header>)",
            '<details class="embedded-intro"><summary>Chú thích, nguồn & tuỳ chọn bản gốc</summary>'
            r"\1</details>",
            source,
            count=1,
            flags=re.DOTALL,
        )
    # Cầu nối chạy sau mã gốc để màu của shell thắng thiết lập đã lưu ở trang con.
    return source.replace("</body>", bridge + "</body>")


SHELL = read("scripts/ban-do-assets/shell.html")
OVERVIEW = read("scripts/ban-do-assets/overview.html")


def build() -> str:
    """Dựng một tệp, thêm cách đọc có dẫn dắt và giữ cả bản đồ gốc."""
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short=8", "HEAD"], cwd=ROOT, text=True
    ).strip()
    frames = {name: frame_source(name) for name in ("lego", "he-thong", "so-hoc")}
    match = re.search(r"window.LEGO=(.*?);/\*<</DU-LIEU", frames["lego"], re.DOTALL)
    if match is None:
        raise ValueError("Thiếu dữ liệu Lego đã ghép")
    lego = json.loads(match[1])
    blocks = [
        "su-kien",
        "next",
        "thu-ngan",
        "thu-ngan",
        "thuoc",
        "dat-lich",
        "gotrue",
        "postgres",
        "sse",
        "gotrue",
    ]
    tasks = []
    for match in re.finditer(
        r"^### (\d+)\. (.+)\n([\s\S]*?)(?=^### |^## |\Z)",
        read("docs/VIEC-CAN-LAM.md"),
        re.MULTILINE,
    ):
        number = int(match[1])
        if number > 10:
            continue
        tasks.append(
            {
                "number": number,
                "title": match[2],
                "html": markdown(match[3]),
                "high": bool(re.search(r"mức 3", match[3], re.IGNORECASE)),
                "block": blocks[number - 1],
                "anchor": slug(f"{number}. {match[2]}"),
            }
        )
    sections = [f'<section id="tong-quan">{OVERVIEW}</section>']
    for name, file in (
        ("viec-can-lam", "VIEC-CAN-LAM.md"),
        ("toc-do", "RA-SOAT-TOC-DO.md"),
        ("muc-luc", "BAN-DO-HE-THONG.md"),
    ):
        content = markdown(read("docs/" + file))
        toc = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h[23]>', content)
        links = "".join(
            f'<a href="#{name}/{anchor}">{re.sub("<[^>]+>", "", title)}</a>'
            for _, anchor, title in toc
        )
        content = re.sub(r' id="([^"]+)"', lambda m: f' id="{name}-{m[1]}"', content)
        if name == "muc-luc":
            content = (
                "<h1>Mục lục & cách cập nhật</h1><h2>Nên đọc theo đường nào?</h2>"
                "<ol><li>Tổng quan: đọc 6 câu hỏi từ chuyện bệnh nhân tới việc cần sửa.</li>"
                "<li>Lego: chọn một nút, đi từng bước, mở tên code sau.</li>"
                "<li>Hệ thống và Sổ học: đối chiếu số đo, hạ tầng, quy tắc.</li>"
                "<li>Việc cần làm và Tốc độ: đọc nguyên báo cáo khi cần chốt kế hoạch.</li></ol>"
                "<h2>Sinh lại bản HTML</h2>"
                "<pre><code>python3 scripts/ban-do-mot-tep.py</code></pre>"
                "<p>Giao diện cách đọc nằm ở scripts/ban-do-assets/. "
                "Nội dung nằm ở các nguồn bên dưới. Không sửa tay tệp HTML sinh ra.</p>"
                + content
            )
        sections.append(
            f'<section id="{name}" hidden><div class="doc-layout">'
            f'<article class="paper">{content}</article><aside class="doc-toc">'
            f'<details open><summary>Trong mục này</summary><div class="toc-links">{links}'
            "</div></details></aside></div></section>"
        )
    sections.append(
        '<section id="lego" hidden><div class="page-intro">'
        '<span class="eyebrow">TRA MỘT THAO TÁC</span>'
        "<h1>Bấm một nút, đi qua đâu?</h1>"
        "<p>Chọn việc ở danh sách, đọc từng bước. Tên dễ hiểu ở trước; "
        "bảng dữ liệu, sự kiện và mã nguồn nằm trong phần mở rộng.</p></div>"
        '<div id="lego-guide"></div><details class="original">'
        "<summary>Mở bản Lego gốc đầy đủ · khối, dây & chế độ 1.000 người</summary>"
        '<p class="muted">Dùng khi muốn nhìn toàn mạng và các nhánh liên quan.</p>'
        '<div class="frame-wrap"></div></details></section>'
    )
    for name, title, description, choices in (
        (
            "he-thong",
            "Hệ thống chạy như thế nào?",
            "Bắt đầu ở Môi trường, sau đó đọc số đo thật. Bảo mật và bảng điều khiển là các phần tra cứu sâu.",
            [
                ("moi-truong", "1. Môi trường & đường đi"),
                ("luong", "2. Số đo thật"),
                ("bao-mat", "3. Bảo mật"),
                ("bang", "4. Bảng điều khiển"),
                ("hang-cho", "5. Có cần thêm hạ tầng?"),
            ],
        ),
        (
            "so-hoc",
            "Học hệ thống theo từng khối",
            "Mở một khối để học các màn của nó. Gặp tên code chưa nhớ thì dùng Từ điển; học xong thử một Thẻ tự kiểm.",
            [
                ("/", "1. Chọn khối nghiệp vụ"),
                ("/tu-dien", "2. Tra tên code"),
                ("/the", "3. Thẻ tự kiểm"),
                ("/toc-do", "4. Tốc độ theo code"),
                ("/cach-doc", "5. Cách đọc chi tiết"),
            ],
        ),
    ):
        buttons = "".join(
            f'<button type="button" data-frame-target="{target}">{label}</button>'
            for target, label in choices
        )
        sections.append(
            f'<section id="{name}" hidden><div class="frame-intro"><h1>{title}</h1>'
            f'<p>{description}</p></div><div class="frame-choices">{buttons}</div>'
            '<div class="frame-wrap"></div></section>'
        )
    descriptions = [
        "Bắt đầu · 6 câu hỏi",
        "10 việc & kế hoạch",
        "Đọc từng thao tác",
        "Môi trường & số đo",
        "Vì sao chậm, sửa gì",
        "Từ điển & thẻ học",
        "Nguồn & hướng dẫn",
    ]
    values = {
        "__DATE__": dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
        .date()
        .isoformat(),
        "__SHA__": sha,
        "__NAV__": "".join(
            f'<a href="#{key}"><span>{i + 1:02d}</span><div><strong>{value}</strong>'
            f"<small>{descriptions[i]}</small></div></a>"
            for i, (key, value) in enumerate(SECTIONS.items())
        ),
        "__CONTENT__": "\n".join(sections),
        "__FRAMES__": json_script(frames),
        "__SECTIONS__": json_script(SECTIONS),
        "__DATA__": json_script(
            {
                "lego": lego,
                "system": json.loads(read("docs/he-thong/so-do.json")),
                "dictionary": json.loads(read("docs/so-hoc/viet-tay.json"))["tu_dien"],
                "tasks": tasks,
            }
        ),
        "__CSS__": "\n".join(
            read("scripts/ban-do-assets/" + name)
            for name in ("shell.css", "overview.css", "lego-reader.css")
        ),
        "__SHELL_JS__": read("scripts/ban-do-assets/shell.js"),
        "__OVERVIEW_JS__": read("scripts/ban-do-assets/overview.js"),
        "__LEGO_JS__": read("scripts/ban-do-assets/lego-reader.js"),
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
