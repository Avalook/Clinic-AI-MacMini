"""Bounded source bundles; edges carry literal evidence, never name guesses.

Imports prove a module dependency, not that every exported function is called.
Literal routes/tables prove shared contracts, not runtime reachability. Dynamic
dispatch, SQL generated at runtime and unresolved imports remain unknown.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass

from ..nguon import Nguon
from . import che_du_lieu


@dataclass(frozen=True)
class Goi:
    tep: tuple[str, ...]
    bam: str
    van_ban: str
    bo_qua: tuple[str, ...]
    chua_biet: tuple[str, ...]


class BanDo:
    """Index source-only imports and literal route/table/event contracts."""

    def __init__(self, nguon: Nguon) -> None:
        self.nguon = nguon
        paths = nguon.py_nguon() + nguon.ts_dashboard() + nguon.migrations()
        self.txt = {
            nguon.tuong_doi(p): nguon.doc(p)
            for p in paths
            if che_du_lieu.duoc_gui(nguon.tuong_doi(p))
            and not p.is_symlink()
            and p.resolve().is_relative_to(nguon.goc.resolve())
        }
        self.canh: dict[str, list[tuple[str, str]]] = {p: [] for p in self.txt}
        self.unknown: dict[str, list[str]] = {p: [] for p in self.txt}
        contracts: dict[tuple[str, str], list[tuple[str, int]]] = {}
        for rel, text in self.txt.items():
            self._imports(rel, text)
            for number, line in enumerate(text.splitlines(), 1):
                for kind, pattern in (
                    (
                        "table",
                        r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+(?:public\.)?([a-zA-Z_]\w*)",  # noqa: E501
                    ),
                    ("event", r"\b(?:pg_notify|LISTEN)\s*\(?\s*['\"]?([a-zA-Z_]\w*)"),
                    ("route", r"['\"](/api/v1/[^'\"?{}]+)['\"]"),
                ):
                    for match in re.finditer(pattern, line, re.I):
                        contracts.setdefault((kind, match[1]), []).append((rel, number))
            if rel.endswith(".py"):
                self._routes(rel, contracts)
        for (kind, value), refs in contracts.items():
            for left, source_line in refs:
                for right, other_line in refs:
                    if left != right:
                        self._edge(
                            left,
                            right,
                            f"{kind} {value}: {left}:{source_line}"
                            f" ↔ {right}:{other_line}",
                        )

    def _edge(self, left: str, right: str, evidence: str) -> None:
        self.canh[left].append((right, evidence))
        self.canh[right].append((left, evidence))

    def _resolve(self, rel: str, module: str) -> str | None:
        from pathlib import PurePosixPath

        if module.startswith("clinicai"):
            base = "src/" + module.replace(".", "/")
        elif module.startswith("@/"):
            base = "src/dashboard/" + module[2:]
        elif module.startswith("."):
            parent = PurePosixPath(rel).parent
            if rel.endswith(".py"):
                dots = len(module) - len(module.lstrip("."))
                for _ in range(dots - 1):
                    parent = parent.parent
                base = str(parent / module.lstrip(".").replace(".", "/"))
            else:
                base = str(parent / module)
                # Normalize relative TS imports without reading outside the repo.
                from posixpath import normpath

                base = normpath(base)
        else:
            return None
        return next(
            (
                p
                for p in (
                    base + ".py",
                    base + "/__init__.py",
                    base + ".ts",
                    base + ".tsx",
                    base + "/index.ts",
                    base + "/index.tsx",
                )
                if p in self.txt
            ),
            None,
        )

    def _imports(self, rel: str, text: str) -> None:
        modules: list[tuple[str, int]] = []
        if rel.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                self.unknown[rel].append(f"{rel}: không parse được Python")
                return
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.extend((a.name, node.lineno) for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = "." * node.level + (node.module or "")
                    modules.append((module, node.lineno))
                    modules.extend(
                        (
                            module + ("" if module.endswith(".") else ".") + a.name,
                            node.lineno,
                        )
                        for a in node.names
                    )
        elif rel.endswith((".ts", ".tsx")):
            modules = [
                (m[1], text[: m.start()].count("\n") + 1)
                for m in re.finditer(
                    r"(?:from\s*|import\s*\()['\"]([^'\"]+)['\"]", text
                )
            ]
        for module, line in modules:
            target = self._resolve(rel, module)
            if target:
                self._edge(rel, target, f"import {module}: {rel}:{line}")
            elif module.startswith(("clinicai", ".", "@/")):
                self.unknown[rel].append(f"{rel}:{line}: chưa phân giải {module}")

    def _routes(
        self, rel: str, contracts: dict[tuple[str, str], list[tuple[str, int]]]
    ) -> None:
        # Nguon.routes extracts literal APIRouter prefix + decorators only.
        for route in self.nguon.routes:
            if self.nguon.tuong_doi(route.tep) == rel:
                contracts.setdefault(("route", route.duong), []).append(
                    (rel, route.dong)
                )

    def goi(
        self, root: str, toi_da_ky_tu: int = 48000, toi_da_tep: int = 12, sau: int = 3
    ) -> Goi:
        """Include both callers and dependencies, recording every omitted part."""
        visited: set[str] = set()
        pending = [(root, 0)]
        evidence: set[str] = set()
        while pending:
            rel, depth = pending.pop(0)
            if rel in visited or rel not in self.txt:
                continue
            visited.add(rel)
            if depth < sau:
                for target, reason in sorted(set(self.canh[rel])):
                    evidence.add(reason)
                    pending.append((target, depth + 1))
        ordered = ([root] if root in visited else []) + sorted(visited - {root})
        parts: list[str] = []
        included: list[str] = []
        skipped: list[str] = []
        budget = max(0, toi_da_ky_tu - min(toi_da_ky_tu // 3, 12000))
        per_file = max(1, budget // max(1, min(toi_da_tep, len(ordered))))
        for rel in ordered:
            block = f"\nTệp: {rel}\n" + "\n".join(
                f"{i:>5}| {line}"
                for i, line in enumerate(self.txt[rel].splitlines(), 1)
            )
            if len(included) >= toi_da_tep or budget <= 0:
                skipped.append(rel + ": bỏ toàn bộ do giới hạn context")
                continue
            included.append(rel)
            allowance = min(budget, per_file)
            parts.append(block[:allowance])
            if len(block) > allowance:
                skipped.append(rel + ": bỏ phần cuối do giới hạn context")
            budget -= allowance
        metadata = (
            "\nLIÊN KẾT (chỉ chứng minh import/hợp đồng, không chứng minh runtime):\n"
            + "\n".join(sorted(evidence))
        )
        unknown = tuple(
            sorted(
                {u for rel in visited for u in self.unknown[rel]}
                | {
                    "Không phân giải dispatch động, route động, SQL động; chưa kiểm toàn hệ thống. SQL migration chỉ là bằng chứng lịch sử, chưa chứng minh schema runtime. Route giả định mount /api/v1; chưa xác minh main.py. Event chỉ nối literal pg_notify/LISTEN, chưa xác minh consumer động."  # noqa: E501
                }
            )
        )
        metadata = (
            "\nCHƯA BIẾT:\n"
            + "\n".join(unknown)
            + "\nBỎ QUA:\n"
            + "\n".join(skipped)
            + metadata
        )
        content = "".join(parts)
        content = (content + metadata)[: max(0, toi_da_ky_tu)]
        # Hash all reachable dependencies, including omitted files and graph evidence.
        digest = hashlib.sha256(
            json.dumps(
                [
                    "xuyen-tep-v1",
                    toi_da_ky_tu,
                    toi_da_tep,
                    sau,
                    [(p, self.txt[p]) for p in ordered],
                    sorted(evidence),
                    unknown,
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        return Goi(tuple(included), digest, content, tuple(skipped), unknown)
