import os
from unittest.mock import patch

from clinicai.services.traffic_service import doc_du_lieu_traffic, xac_thuc_ma_pin


def test_chua_dat_pin_thi_tat_han():
    """Không có mã mặc định: chưa đặt OPS_TRAFFIC_PIN thì mọi mã đều sai."""
    with patch.dict(os.environ, {}, clear=True):
        assert xac_thuc_ma_pin("12345678") is False
        assert xac_thuc_ma_pin("wrong") is False
        assert xac_thuc_ma_pin("") is False


def test_xac_thuc_ma_pin_custom_env():
    with patch.dict(os.environ, {"OPS_TRAFFIC_PIN": "mysecret99"}):
        assert xac_thuc_ma_pin("mysecret99") is True
        assert xac_thuc_ma_pin("12345678") is False


def test_doc_du_lieu_traffic_not_found(tmp_path):
    fake_file = tmp_path / "non_existent.json"
    with patch.dict(os.environ, {"OPS_TRAFFIC_SUMMARY_FILE": str(fake_file)}):
        assert doc_du_lieu_traffic() is None


def test_doc_du_lieu_traffic_success(tmp_path):
    summary_file = tmp_path / "traffic-summary.json"
    summary_file.write_text('{"total": 100, "status": "ok"}', encoding="utf-8")
    with patch.dict(os.environ, {"OPS_TRAFFIC_SUMMARY_FILE": str(summary_file)}):
        data = doc_du_lieu_traffic()
        assert data == {"total": 100, "status": "ok"}
