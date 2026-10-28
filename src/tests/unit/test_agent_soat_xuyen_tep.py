"""Cross-file context uses source evidence and invalidates dependency changes."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.soat_he_thong.nguon import Nguon
from scripts.soat_he_thong.tang_model import doc_xuyen_tep, soat_toan_bo
from scripts.soat_he_thong.tang_model.chi_phi import SoChiPhi
from scripts.soat_he_thong.tang_model.xuyen_tep import BanDo


def test_context_dependency_hash_and_bounds(tmp_path: Path) -> None:
    files = {
        "src/clinicai/api/v1/orders.py": "from clinicai.services.orders import save\n@router.post('/orders')\ndef route():\n    return save()\n",  # noqa: E501
        "src/clinicai/services/orders.py": "def save():\n    return execute('INSERT INTO orders VALUES (1)')\n",  # noqa: E501
        "src/dashboard/app/page.tsx": "fetch('/api/v1/orders')\n",
        "supabase/migrations/001.sql": "CREATE TABLE orders (id int);\n",
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    root = "src/clinicai/api/v1/orders.py"
    bundle = BanDo(Nguon(tmp_path)).goi(root)
    assert set(files) == set(bundle.tep)
    assert "import" in bundle.van_ban
    assert "route" in bundle.van_ban
    assert "table" in bundle.van_ban
    (tmp_path / "src/clinicai/services/orders.py").write_text("def save(): pass\n")
    assert BanDo(Nguon(tmp_path)).goi(root).bam != bundle.bam
    limited = BanDo(Nguon(tmp_path)).goi(root, toi_da_ky_tu=80)
    assert limited.bo_qua
    assert len(limited.van_ban) <= 80


def test_unresolved_and_forbidden(tmp_path: Path) -> None:
    path = tmp_path / "src/clinicai/a.py"
    path.parent.mkdir(parents=True)
    path.write_text("from clinicai.missing import run\n")
    bundle = BanDo(Nguon(tmp_path)).goi("src/clinicai/a.py")
    assert bundle.chua_biet
    assert not BanDo(Nguon(tmp_path)).goi(".env.prod").tep


def test_large_root_preserves_dependencies_metadata_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "src/clinicai/a.py"
    root.parent.mkdir(parents=True)
    root.write_text("from clinicai.b import run\n" + "# padding\n" * 3000)
    (root.parent / "b.py").write_text("def run(): return 123\n")
    (root.parent / "leak.py").symlink_to("/etc/passwd")
    graph = BanDo(Nguon(tmp_path))
    bundle = graph.goi("src/clinicai/a.py", toi_da_ky_tu=3000)
    assert "src/clinicai/b.py" in bundle.tep
    assert "LIÊN KẾT" in bundle.van_ban
    assert "CHƯA BIẾT" in bundle.van_ban
    assert "leak.py" not in graph.txt
    assert "def run" in bundle.van_ban


def test_resume_failure_invalidates_and_rebuttal_keeps_root(tmp_path: Path) -> None:
    root = tmp_path / "src/clinicai/a.py"
    root.parent.mkdir(parents=True)
    root.write_text("from clinicai.b import run\n")
    dep = root.parent / "b.py"
    dep.write_text("def run(): return 123\n")
    out = tmp_path / "out"
    out.mkdir()
    so = SoChiPhi(out / "cost.jsonl", 1, out)
    response = SimpleNamespace(
        van_ban='[{"tep":"src/clinicai/b.py","dong_tu":1,'
        '"trich_dan":"def run(): return 123"}]'
    )
    with patch.object(doc_xuyen_tep, "goi", return_value=response) as call:
        first, _, completed = soat_toan_bo.doc_xuyen_tep(
            Nguon(tmp_path), [root], ["mock"], so, out
        )
        assert completed == 1
        assert first[0].goc_xuyen_tep == "src/clinicai/a.py"
        soat_toan_bo.doc_xuyen_tep(Nguon(tmp_path), [root], ["mock"], so, out)
        assert call.call_count == 1
        dep.write_text("def run(): return 123\n# changed\n")
        soat_toan_bo.doc_xuyen_tep(Nguon(tmp_path), [root], ["mock"], so, out)
        assert call.call_count == 2
        call.return_value = SimpleNamespace(van_ban='{"ket_luan":"khong_chac"}')
        doc_xuyen_tep.bac_bo(Nguon(tmp_path), [[(first[0], 1)]], "mock", so)
        assert "Tệp: src/clinicai/a.py" in call.call_args.args[1][1]["content"]
    root.write_text("# different\n")
    with patch.object(doc_xuyen_tep, "goi", return_value=SimpleNamespace(van_ban="")):
        _, error, completed = soat_toan_bo.doc_xuyen_tep(
            Nguon(tmp_path), [root], ["mock"], so, out
        )
        assert error and completed == 0


def test_offline_flag_requires_cross_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    from scripts.soat_he_thong.chay_model import main

    with pytest.raises(SystemExit):
        main(["soat", "--models", "mock", "--xac-nhan", "mock", "--chi-lap-goi"])


def test_dung_blocks_network_and_no_completion(tmp_path: Path) -> None:
    root = tmp_path / "src/clinicai/a.py"
    root.parent.mkdir(parents=True)
    root.write_text("def run(): return 123\n")
    out = tmp_path / "out"
    out.mkdir()
    (out / "DUNG").write_text("stop")
    so = SoChiPhi(out / "cost.jsonl", 1, out)
    with patch("urllib.request.OpenerDirector.open") as network:
        _, stop, completed = soat_toan_bo.doc_xuyen_tep(
            Nguon(tmp_path), [root], ["avis:mock"], so, out
        )
        assert stop and completed == 0
        network.assert_not_called()
    assert not (out / "da-doc-xuyen-tep.jsonl").exists()


def test_quote_outside_sent_lines_rejected(tmp_path: Path) -> None:
    from scripts.soat_he_thong.tang_model.xuyen_tep import Goi

    bundle = Goi(("a.py",), "hash", "Tệp: a.py\n    1| print(123)", (), ())
    response = SimpleNamespace(
        van_ban='[{"tep":"a.py","dong_tu":999,"trich_dan":"print(123)"}]'
    )
    so = SoChiPhi(tmp_path / "cost.jsonl", 1, tmp_path)
    with patch.object(doc_xuyen_tep, "goi", return_value=response):
        assert doc_xuyen_tep._read("mock", "a.py", bundle, so) == []
