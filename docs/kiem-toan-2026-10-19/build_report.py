"""Build an offline audit page from durable, versioned audit records.

Run with the workspace Python that has markdown_it installed. This generator
does not read application secrets, contact the network, or mutate source code.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent
MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")
CODE_SUFFIXES = {'.py', '.pyi', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.sql', '.sh', '.bash', '.go', '.rs', '.java', '.kt', '.css', '.html'}
MAIN_LABELS = {
    "still_present_on_main": "Còn trên main trong phạm vi đã kiểm",
    "partially_addressed_on_main": "Main đã xử lý một phần",
    "addressed_on_main": "Main đã có bản sửa",
}
LEVEL_LABELS = {
    "confirmed_static": "Chứng cứ code / chưa tái hiện đầy đủ",
    "reproduced_local": "Đã tái hiện local ở bản nêu trong hồ sơ",
    "hypothesis": "Giả thuyết cần thử",
    "design_gap": "Khoảng trống sản phẩm / kiểm chứng",
}


def esc(value: object) -> str:
    """Escape every data value before inserting it into HTML."""
    return html.escape(str(value), quote=True)


def load(name: str) -> object:
    """Load an audit JSON artifact from the same directory."""
    return json.loads((ROOT / name).read_text())


def markdown_section(name: str) -> str:
    """Render controlled Markdown; raw HTML is disabled."""
    return '<div class="prose">' + MARKDOWN.render((ROOT / name).read_text()) + "</div>"


def tags(finding: dict) -> str:
    """Show severity, evidence and main disposition independently."""
    state = finding["main_validation"]["status"]
    color = "patched" if state == "addressed_on_main" else finding["severity"].lower()
    return (
        f'<span class="tag {color}">{esc(finding["severity"])}</span>'
        '<span class="tag neutral">'
        f'{esc(LEVEL_LABELS[finding["evidence_level"]])}</span>'
        f'<span class="tag {"patched" if state == "addressed_on_main" else "neutral"}">'
        f"{esc(MAIN_LABELS[state])}</span>"
    )


def evidence_html(finding: dict) -> str:
    """Embed source proof so the page remains useful away from the repo."""
    parts = ["<details><summary>Bằng chứng, test và giới hạn kiểm chứng</summary>"]
    label = (
        "Vị trí phát hiện trên main ghim"
        if finding.get("reference_version") == "pinned_main"
        else "Vị trí ở working tree ban đầu"
    )
    parts.append(f"<h4>{label}</h4><ul>")
    for item in finding["evidence"]:
        parts.append(
            f'<li><span class="path">{esc(item["path"])}:{item["line"]}'
            f"–{item['end_line']}</span><br>{esc(item['detail'])}</li>"
        )
    parts.append("</ul><h4>Đối chiếu nguồn main ghim 956ba4f2</h4>")
    for item in finding["main_validation"]["evidence"]:
        parts.append(
            '<div class="evidence">'
            f'<div class="path">{esc(item["path"])}:{item["line"]}–{item["end_line"]}'
            f"<br><small>SHA-256: {esc(item['sha256'])}</small></div>"
            f"<pre>{esc(item['excerpt'])}</pre></div>"
        )
    validation = finding["validation"]
    parts.append(f"<p><strong>Phương pháp:</strong> {esc(validation['method'])}</p>")
    if validation.get("command"):
        parts.append(f"<pre>{esc(validation['command'])}</pre>")
    parts.append(
        f"<p><strong>Kết quả:</strong> {esc(validation['result'])}</p>"
        f"<p><strong>Giới hạn:</strong> {esc(validation['limitations'])}</p></details>"
    )
    reference = finding.get("external_reference")
    parsed_reference = urlparse(str(reference)) if reference else None
    if (
        parsed_reference
        and parsed_reference.scheme == "https"
        and parsed_reference.netloc == "www.postgresql.org"
    ):
        # Source links are references for human review, not page resources.
        parts = [
            *parts[:-1],
            parts[-1].replace(
                "</details>",
                '<p><strong>Nguồn kỹ thuật:</strong> '
                f'<a href="{esc(reference)}" rel="noopener">PostgreSQL 17 — Transactions and Identifiers</a></p>'
                "</details>",
            ),
        ]
    return "".join(parts)


def finding_html(finding: dict) -> str:
    """Render one complete risk record, including resolved-on-main records."""
    main = finding["main_validation"]
    fields = [
        ("Quan sát ban đầu", finding["summary"]),
        ("Khi nào xảy ra", finding["trigger"]),
        ("Tác động và phạm vi", finding["impact"]),
        ("Cách cải tiến đề xuất", finding["recommendation"]),
        ("Nghiệm thu sau sửa", finding["acceptance"]),
    ]
    description = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in fields)
    return (
        f'<article class="finding" id="{esc(finding["id"])}" '
        f'data-main-status="{esc(main["status"])}" '
        f'data-level="{esc(finding["evidence_level"])}">'
        f'<span class="eyebrow">{esc(finding["id"])} · '
        f'{esc(finding["category"])}</span>'
        f"<h3>{esc(finding['title'])}</h3>{tags(finding)}"
        '<p class="decision"><strong>Kết luận trên main:</strong> '
        f'{esc(main["note"])}</p>'
        f"<dl>{description}</dl>{evidence_html(finding)}</article>"
    )


def ledger_html(files: list[dict]) -> str:
    """Render the entire pinned-tree ledger, with honest inspection stages."""
    rows = []
    for item in files:
        fingerprint = item.get("sha256") or item.get("git_blob_sha1")
        rows.append(
            f"<tr><td><code>{esc(item['path'])}</code><br>"
            f'<span class="path">{esc(fingerprint)}</span></td>'
            f"<td>{esc(item['status'])}</td><td>{esc(item['method'])}</td></tr>"
        )
    return (
        "<details><summary>Mở ledger đầy đủ của 2.890 file trên main ghim</summary>"
        '<p class="meta">SHA-256 khi có snapshot; còn lại là Git blob SHA-1. '
        "Hash nhận diện nội dung, không phải dấu chứng nhận đã hiểu code.</p>"
        '<div class="table-wrap ledger"><table><thead><tr><th>File / fingerprint</th>'
        "<th>Mức đã kiểm</th><th>Phương pháp và giới hạn</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div></details>"
    )


def test_runs_html(runs: list[dict]) -> str:
    """Keep failed and successful runs visible without hiding qualifications."""
    rows = []
    for run in runs:
        limits = " ".join(run["limitations"])
        rows.append(
            f"<tr><td><strong>{esc(run['id'])}</strong><br>{esc(run['environment'])}</td>"
            f"<td><code>{esc(run['command'])}</code></td><td>{esc(run['result'])}"
            f"<br><strong>Exit {run['exit_code']}</strong></td>"
            f"<td>{esc(limits)}</td></tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Môi trường</th><th>Lệnh</th>'
        "<th>Kết quả</th><th>Giới hạn</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def build() -> Path:
    """Create the portable page deterministically from current audit records."""
    findings = load("PHAT-HIEN.json")
    manifest = load("MAIN-PHAM-VI.json")
    runs = load("TEST-RUNS.json")
    state = load("STATE.json")
    counts = Counter(f["main_validation"]["status"] for f in findings)
    severity = Counter(f["severity"] for f in findings)
    coverage = Counter(f["status"] for f in manifest["files"])
    code_files = [f for f in manifest["files"] if Path(f["path"]).suffix.lower() in CODE_SUFFIXES]
    code_coverage = Counter(f["status"] for f in code_files)
    report_version = state.get("report_version", "version unavailable")
    round_summary = state.get(
        "report_round_summary",
        "No round-specific summary is recorded in STATE.json.",
    )
    checkpoint = (
        f"Checkpoint {report_version} trên main ghim {manifest['sha']}: "
        f"{len(findings)} hồ sơ ({severity['HIGH']} HIGH, {severity['MEDIUM']} MEDIUM, "
        f"{severity['LOW']} LOW); {counts['still_present_on_main']} còn hiện diện, "
        f"{counts['partially_addressed_on_main']} xử lý một phần, "
        f"{counts['addressed_on_main']} đã có bản sửa trong phạm vi đối chiếu. "
        f"Coverage {len(manifest['files']):,} path: {coverage['read']:,} read, "
        f"{coverage['traced']:,} traced một phần, {coverage['scanned']:,} scanned, "
        f"{coverage['inventoried']:,} inventoried, {coverage['excluded']:,} excluded. "
        f"{round_summary} Full source audit vẫn chưa hoàn tất."
    )
    css = (ROOT / "report.css").read_text()
    script = (ROOT / "report.js").read_text()
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        f"script-src 'sha256-{script_hash}'; base-uri 'none'; form-action 'none'"
    )
    nav = [
        ("nhan-dinh", "01 · Nhận định"),
        ("kien-truc", "02 · Kiến trúc"),
        ("phat-hien", "03 · Phát hiện"),
        ("thiet-ke", "04 · Thiết kế đích"),
        ("lo-trinh", "05 · Lộ trình & cổng bán"),
        ("kiem-chung", "06 · Kiểm chứng"),
        ("pham-vi", "07 · Bao phủ & giới hạn"),
        ("tiep-quan", "08 · Tiếp quản"),
    ]
    nav_html = "".join(f'<a href="#{key}">{label}</a>' for key, label in nav)
    risk_rows = "".join(
        f'<tr data-risk-row="{esc(f["id"])}"><td><a href="#{esc(f["id"])}">'
        f"{esc(f['id'])}</a></td><td>{esc(f['title'])}</td>"
        f"<td>{esc(f['severity'])}</td><td>{esc(MAIN_LABELS[f['main_validation']['status']])}"
        f"<br>{esc(LEVEL_LABELS[f['evidence_level']])}</td></tr>"
        for f in findings
    )
    resume = (
        "Tiếp tục kiểm toán ClinicAI trong repo này. Đọc "
        "docs/kiem-toan-2026-10-19/BAT-DAU-TU-DAY.md, STATE.json, NHAT-KY.md "
        "và MAIN-COMPARISON.json trước. Main đã ghim 956ba4f2; working tree ban đầu "
        "là 543b9787 có WIP. Không nhầm hai phiên bản hoặc kết luận prod từ source. "
        "Đọc checkpoint, tiếp tục phần chưa kiểm, lưu bằng chứng và coverage lên đĩa. "
        "Không sửa code ứng dụng hoặc thay đổi của người khác. Hoàn tất audit, "
        "thiết kế và trang HTML tự chứa; không gọi bất kỳ checkpoint nào là audit toàn code đã xong."
    )
    timestamp = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime(
        "%d/%m/%Y %H:%M GMT+7"
    )
    template = (ROOT / "report.template.html").read_text()
    values = {
        "@@P00@@": str(esc(csp)),
        "@@P01@@": str(css),
        "@@P02@@": str(nav_html),
        "@@P03@@": str(timestamp),
        "@@P04@@": str(format(len(manifest["files"]), ",")),
        "@@P05@@": str(coverage["traced"]),
        "@@P06@@": str(len(findings)),
        "@@P07@@": str(counts["addressed_on_main"]),
        "@@P08@@": str(markdown_section("NHAN-DINH.md")),
        "@@P09@@": str(counts["still_present_on_main"]),
        "@@P10@@": str(counts["partially_addressed_on_main"]),
        "@@P11@@": str(counts["addressed_on_main"]),
        "@@P12@@": str(risk_rows),
        "@@P13@@": str("".join((finding_html(f) for f in findings))),
        "@@P14@@": str(markdown_section("THIET-KE-DICH.md")),
        "@@P15@@": str(markdown_section("LO-TRINH.md")),
        "@@P16@@": str(test_runs_html(runs)),
        "@@P17@@": str(coverage["inventoried"]),
        "@@P18@@": str(coverage["scanned"]),
        "@@P19@@": str(coverage["traced"]),
        "@@P20@@": str(coverage["excluded"]),
        "@@P21@@": str(ledger_html(manifest["files"])),
        "@@P22@@": str(esc(resume)),
        "@@P23@@": str(script),
        "@@P24@@": str(format(len(code_files), ",")),
        "@@P25@@": str(format(code_coverage["traced"], ",")),
        "@@P26@@": str(format(code_coverage["scanned"], ",")),
        "@@P27@@": str(format(code_coverage["inventoried"], ",")),
        "@@P28@@": str(format(coverage["read"], ",")),
        "@@P29@@": str(format(code_coverage["read"], ",")),
        "@@P30@@": str(esc(report_version)),
        "@@P31@@": str(esc(checkpoint)),
    }
    document = re.sub(r"@@P\d{2}@@", lambda match: values[match.group()], template)
    target = ROOT / "BAO-CAO.html"
    target.write_text(document)
    return target


if __name__ == "__main__":
    print(build())
