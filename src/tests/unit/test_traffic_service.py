import os
from unittest.mock import patch
from clinicai.services.traffic_service import xac_thuc_ma_pin, doc_bao_cao_traffic


def test_xac_thuc_ma_pin_default():
    # Khi không có env, fallback là 12345678
    with patch.dict(os.environ, {}, clear=True):
        assert xac_thuc_ma_pin("12345678") is True
        assert xac_thuc_ma_pin("wrong") is False
        assert xac_thuc_ma_pin("") is False


def test_xac_thuc_ma_pin_custom_env():
    with patch.dict(os.environ, {"OPS_TRAFFIC_PIN": "mysecret99"}):
        assert xac_thuc_ma_pin("mysecret99") is True
        assert xac_thuc_ma_pin("12345678") is False


def test_doc_bao_cao_traffic_not_found(tmp_path):
    fake_file = tmp_path / "non_existent.html"
    with patch.dict(os.environ, {"OPS_TRAFFIC_REPORT_FILE": str(fake_file)}):
        assert doc_bao_cao_traffic() is None


def test_doc_bao_cao_traffic_success(tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<html><body>GoAccess Report</body></html>", encoding="utf-8")
    with patch.dict(os.environ, {"OPS_TRAFFIC_REPORT_FILE": str(report)}):
        content = doc_bao_cao_traffic()
        assert content == "<html><body>GoAccess Report</body></html>"
