"""Khuôn một PHÁT HIỆN của agent soát hệ thống.

Mỗi phát hiện mang đủ 10 mục của hiến pháp §13 (`docs/ai/HIEN-PHAP-AGENT.md`),
cộng ba thứ riêng của việc soát code:

* `muc_bang_chung` — §3.3 sự thật ≠ suy luận. `quan_sat` = script thấy tận mắt
  trong code (vd mã quyền dùng mà không khai); `suy_ra` = phân tích tĩnh không
  chắc (vd "đường này không để lại dấu vết" — có thể dấu vết đi qua lối script
  không theo được); `chua_biet` = nêu ra để người xem, agent không dám kết.
* `trich_dan` — vị trí `tệp:dòng` + đoạn trích. Script `kiem_trich_dan` mở lại
  tệp kiểm từng cái; phát hiện không có trích dẫn đúng bị loại, KHÔNG đến tay người.
* `id` — băm từ (bộ quét, khoá ổn định). Cùng một vấn đề ở hai lần quét ra cùng
  id, nên quyết định của người ("bỏ qua vì…") còn hiệu lực lần sau.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MucBangChung(str, Enum):
    QUAN_SAT = "quan_sat"
    SUY_RA = "suy_ra"
    CHUA_BIET = "chua_biet"


class UuTien(str, Enum):
    """§2 của hiến pháp. Chỉ dùng P0–P6 khi soát code; P7 (kinh doanh) không phải
    việc của bộ soát."""

    P0 = "P0"  # an toàn, toàn vẹn dữ liệu, bóp méo thực tế
    P1 = "P1"  # hệ thống tin khác với thực tế
    P2 = "P2"  # việc/khách có thể rơi
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"  # lego/điều phối đứt
    P6 = "P6"  # thừa, rác, hiệu suất


class LoaiVanDe(str, Enum):
    LEGO_THIEU_LIEN_KET = "lego_thieu_lien_ket"
    DU_LIEU_SAI = "du_lieu_sai"
    MAT_DU_LIEU = "mat_du_lieu"
    LOGIC_CO_VAN_DE = "logic_co_van_de"
    DE_XUAT_CAI_TIEN = "de_xuat_cai_tien"


@dataclass(frozen=True)
class TrichDan:
    tep: str  # tương đối gốc repo
    dong: int  # 1-based
    doan: str  # đoạn chữ phải còn nằm trong tệp, gần dòng này


@dataclass
class PhatHien:
    bo_quet: str
    khoa: str  # ổn định giữa các lần quét
    loai: LoaiVanDe
    uu_tien: UuTien
    muc_bang_chung: MucBangChung
    do_chac: float  # 0–1
    tinh_huong: str  # §13.1
    bang_chung: list[str]  # §13.2
    rui_ro: str  # §13.3
    de_xuat: str  # §13.4
    nguoi_chiu_trach_nhiem: str  # §13.5 — vai gợi ý, không phải tên người
    thoi_diem: str  # §13.6
    ket_qua_mong_doi: str  # §13.7
    cach_xac_nhan: str  # §13.8 — thường là một bài test / lệnh quét chạy lại
    phuong_an_khac: str = ""  # §13.10
    trich_dan: list[TrichDan] = field(default_factory=list)
    #: Việc sửa này có đụng migration / tiền / kho / quyền không (mức 3 của CLAUDE.md).
    muc_viec: int = 2
    #: Chỉ đọc code là đủ để người kiểm hay phải xem dữ liệu thật.
    can_du_lieu_that: bool = False

    @property
    def id(self) -> str:
        return hashlib.sha1(f"{self.bo_quet}|{self.khoa}".encode()).hexdigest()[:12]

    @classmethod
    def tu_dict(cls, d: dict[str, Any]) -> PhatHien:
        """Đọc lại từ `phat-hien.jsonl` (máy xem dựng lại báo cáo mỗi lần mở)."""
        d = {k: v for k, v in d.items() if k != "id"}
        d["loai"] = LoaiVanDe(d["loai"])
        d["uu_tien"] = UuTien(d["uu_tien"])
        d["muc_bang_chung"] = MucBangChung(d["muc_bang_chung"])
        d["trich_dan"] = [TrichDan(**t) for t in d.get("trich_dan", [])]
        return cls(**d)

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        d["loai"] = self.loai.value
        d["uu_tien"] = self.uu_tien.value
        d["muc_bang_chung"] = self.muc_bang_chung.value
        return d


@dataclass
class DoPhu:
    """Sổ ĐỘ PHỦ của một bộ quét: nó đã nhìn gì, nên 'không thấy gì' nghĩa là gì.

    Thiếu sổ này thì "0 phát hiện" đọc thành "sạch", trong khi có thể là bộ quét
    không nhìn tới chỗ đó (§3.2 "không biết cũng là một trạng thái hợp lệ")."""

    bo_quet: str
    da_nhin: dict[str, int] = field(default_factory=dict)  # tên nhóm → số mục
    khong_nhin_duoc: list[str] = field(default_factory=list)  # nói thẳng điều mù
    ghi_chu: list[str] = field(default_factory=list)
