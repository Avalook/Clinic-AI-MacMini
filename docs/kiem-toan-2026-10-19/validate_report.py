"""Validate report consistency and offline HTML structure, without network."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Page(HTMLParser):
    """Collect structure without executing any HTML or embedded script."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.resources: list[str] = []
        self.findings: list[str] = []
        self.csp = ""

    def handle_starttag(self, tag: str, attributes: list[tuple]) -> None:
        attrs = dict(attributes)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if attrs.get("src") or tag == "link":
            self.resources.append(str(attrs))
        if tag == "article" and "finding" in attrs.get("class", "").split():
            self.findings.append(attrs.get("id", ""))
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs["content"]


class ReportChecks(unittest.TestCase):
    """Check drift, invented counts, portability and injection boundaries."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = (ROOT / "BAO-CAO.html").read_text()
        cls.page = Page()
        cls.page.feed(cls.content)
        cls.findings = json.loads((ROOT / "PHAT-HIEN.json").read_text())

    def test_identifiers_and_internal_links(self) -> None:
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        for href in self.page.hrefs:
            if href.startswith("#"):
                self.assertIn(href[1:], self.page.ids)

    def test_assessment_section_is_rendered_and_template_is_resolved(self) -> None:
        self.assertIn("Nhận định theo các lát cắt đã kiểm", self.content)
        self.assertRegex(self.content, r"id=\"kien-truc\"")
        self.assertNotRegex(self.content, r"@@P\d+@@")

    def test_every_record_is_present_exactly_once(self) -> None:
        ids = [f["id"] for f in self.findings]
        self.assertCountEqual(ids, self.page.findings)
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_external_resources_and_script_hash_matches(self) -> None:
        self.assertFalse(self.page.resources)
        script = re.search(r"<script>(.*?)</script>", self.content, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("sha256-" + digest, self.page.csp)
        self.assertIn("default-src 'none'", self.page.csp)
        for forbidden in ["fetch(", "XMLHttpRequest", "eval(", ".innerHTML"]:
            self.assertNotIn(forbidden, script)

    def test_version_and_incompletion_are_explicit(self) -> None:
        self.assertIn("CHƯA PHẢI AUDIT TOÀN CODE ĐÃ XONG", self.content)
        self.assertIn("956ba4f2", self.content)
        self.assertIn("543b9787", self.content)
        self.assertIn("30 passed, 1 failed", self.content)
        self.assertEqual(self.content.count('data-main-status="addressed_on_main"'), 2)

    def test_main_evidence_hashes_and_line_ranges(self) -> None:
        snapshot = Path(
            json.loads((ROOT / "MAIN-PHAM-VI.json").read_text())["snapshot"]
        )
        for finding in self.findings:
            for evidence in finding["main_validation"]["evidence"]:
                path = snapshot / evidence["path"]
                content = path.read_bytes()
                actual = hashlib.sha256(content).hexdigest()
                self.assertEqual(actual, evidence["sha256"], finding["id"])
                lines = path.read_text().splitlines()
                self.assertLessEqual(evidence["end_line"], len(lines))
                expected_excerpt = "\n".join(
                    f"{number}: {lines[number - 1]}"
                    for number in range(evidence["line"], evidence["end_line"] + 1)
                )
                self.assertEqual(
                    evidence["excerpt"], expected_excerpt,
                    f"inexact evidence excerpt: {finding['id']} {evidence['path']}:{evidence['line']}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
