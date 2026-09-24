"""Ổ cắm LEGO phải khớp thực tế — nếu không, bản khai chỉ là tờ giấy đẹp.

Bốn bài này là thứ biến "mọi thứ là LEGO" từ khẩu hiệu thành luật kiểm được:

  1. Sự kiện nào cũng có ĐÚNG MỘT module nhận là của mình.
  2. `source_module` ghi trong sự kiện khớp module khai phát nó.
  3. Bên nghe nào cũng thuộc một module, và module ấy khai nghe đúng sự kiện.
  4. Quyền nào cũng thuộc một module — quyền mồ côi là quyền không ai gác.
"""

from __future__ import annotations

import clinicai.events.consumers  # noqa: F401 — đăng ký bên nhận
from clinicai.events.catalogue import DANH_MUC, moi_consumer
from clinicai.modules import MODULE, module_cua_ben_nhan, module_phat
from clinicai.permissions.catalogue import QUYEN


def test_moi_su_kien_co_dung_mot_module_phat() -> None:
    thieu = [ten for ten in DANH_MUC if module_phat(ten) is None]
    assert not thieu, (
        "Sự kiện không module nào nhận là của mình — ai sửa nó sau này?\n  "
        + "\n  ".join(thieu)
    )
    for ten in DANH_MUC:
        chu = [m.ma for m in MODULE.values() if ten in m.phat]
        assert len(chu) == 1, f"Sự kiện {ten} có {len(chu)} module cùng nhận: {chu}"


def test_source_module_khop_ban_khai() -> None:
    """Sự kiện tự khai mình từ module nào; bản khai phải nói y hệt."""
    lech = [
        f"{ten}: sự kiện ghi '{su_kien.source_module}',"
        f" bản khai nói '{module_phat(ten)}'"
        for ten, su_kien in DANH_MUC.items()
        if su_kien.source_module != module_phat(ten)
    ]
    assert not lech, "\n  ".join(lech)


def test_moi_ben_nhan_thuoc_mot_module_va_duoc_khai_nghe() -> None:
    for consumer in moi_consumer():
        ma = module_cua_ben_nhan(consumer)
        assert ma is not None, (
            f"Bên nhận '{consumer}' chưa thuộc module nào"
            " — thêm vào src/clinicai/modules.py"
        )
        nghe = set(MODULE[ma].nghe)
        phai_nghe = {ten for ten, sk in DANH_MUC.items() if consumer in sk.consumers}
        thieu = phai_nghe - nghe
        assert not thieu, (
            f"Module '{ma}' nhận sự kiện {sorted(thieu)} qua '{consumer}' "
            "nhưng chưa khai nghe chúng."
        )


def test_moi_quyen_thuoc_mot_module() -> None:
    da_khai = {q for m in MODULE.values() for q in m.quyen}
    mo_coi = sorted(set(QUYEN) - da_khai)
    assert not mo_coi, (
        "Quyền không thuộc module nào — không ai biết lệnh nào gác bằng nó:\n  "
        + "\n  ".join(mo_coi)
    )


def test_goi_dong_bo_phai_tro_toi_lenh_co_that() -> None:
    """Gọi thẳng sang module khác không bị cấm — nhưng phải khai, và khai đúng.

    Khai sai tên lệnh còn tệ hơn không khai: người đọc tin vào một đường dây
    không tồn tại.
    """
    for m in MODULE.values():
        for goi in m.goi_dong_bo:
            assert "." in goi, f"{m.ma}: '{goi}' phải có dạng 'module.Lenh'"
            ma_module, ten_lenh = goi.split(".", 1)
            assert ma_module in MODULE, f"{m.ma} gọi module không có: {ma_module}"
            assert ten_lenh in MODULE[ma_module].lenh, (
                f"{m.ma} khai gọi '{goi}' nhưng module '{ma_module}' không có "
                f"lệnh ấy (có: {list(MODULE[ma_module].lenh)})"
            )
            assert ma_module != m.ma, f"{m.ma} khai gọi đồng bộ chính mình"


def test_khong_hai_module_cung_giu_mot_bang() -> None:
    """Hai module cùng ghi một bảng là hai LEGO dính keo vào nhau."""
    chu: dict[str, str] = {}
    for m in MODULE.values():
        for bang in m.bang:
            assert bang not in chu, (
                f"Bảng '{bang}' đang thuộc cả '{chu[bang]}' và '{m.ma}'."
            )
            chu[bang] = m.ma


# ── Cổng đọc hồ sơ (cách B, 24/09/2026) ──────────────────────────────────


def test_moi_cong_doc_tro_toi_ham_async_co_that() -> None:
    import inspect

    from clinicai.ho_so.cong_doc import cac_cong, nap_ham

    cong = cac_cong()
    assert cong, "chưa module nào khai cổng đọc hồ sơ"
    for module, ten, _khoa, duong in cong:
        assert inspect.iscoroutinefunction(nap_ham(duong)), f"{module}/{ten}: {duong}"


def test_khong_hai_cong_gianh_mot_khoa() -> None:
    from clinicai.ho_so.cong_doc import cac_cong

    chu: dict[str, str] = {}
    for module, ten, khoa, _duong in cac_cong():
        for k in khoa:
            assert k not in chu, f"khoá {k!r}: {chu.get(k)} và {module}/{ten}"
            chu[k] = f"{module}/{ten}"
    # Đủ các khoá màn bệnh án đang vẽ — thiếu một cổng là màn mất một khối.
    assert set(chu) >= {
        "profile",
        "pregnancy",
        "labs",
        "history_raw",
        "prescriptions",
        "vital_latest",
        "visit",
        "draft",
        "revision",
        "prescription_draft",
    }


def test_ham_rap_ho_so_khong_tu_doc_bang_cua_module() -> None:
    """Hồ sơ chỉ quyết bối cảnh (khách, lượt); nội dung đọc qua cổng. Quay lại
    SELECT thẳng bảng của module là quay lại kiểu "đào sâu"."""
    import inspect
    import re

    from clinicai.services.ho_so_lam_sang_doc import doc_ho_so

    ma = inspect.getsource(doc_ho_so)
    bang_module = {b for m in MODULE.values() for b in m.bang}
    doc = set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+)", ma))
    assert not doc & bang_module, sorted(doc & bang_module)
