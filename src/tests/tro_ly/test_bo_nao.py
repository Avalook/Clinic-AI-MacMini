"""Vòng lặp bộ não + dịch tin của hai adapter, bằng model GIẢ chạy theo kịch bản.

Không gọi mạng: model giả trả lần lượt các `KetQuaMoHinh` cho trước và ghi lại
tin nó nhận, để kiểm bộ não gửi đúng thứ tự gọi công cụ / kết quả.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from clinicai.adapters.mo_hinh import anthropic as ad_anthropic
from clinicai.adapters.mo_hinh import openai_compat as ad_openai
from clinicai.adapters.mo_hinh import tao_mo_hinh
from clinicai.ports.mo_hinh import (
    CongCu,
    GoiCongCu,
    KetQuaMoHinh,
    MoHinhError,
    Tin,
)
from clinicai.services.tro_ly_khach import bo_nao
from clinicai.services.tro_ly_khach.cong_cu import CongCuMau

LUC = datetime(2026, 10, 30, 10, 15)


class MoHinhGia:
    ten = "gia:kich-ban"

    def __init__(self, kich_ban: list[KetQuaMoHinh | Exception]) -> None:
        self._kich_ban = list(kich_ban)
        self.da_nhan: list[list[Tin]] = []

    async def tra_loi(
        self,
        *,
        he_thong: str,
        tin: Sequence[Tin],
        cong_cu: Sequence[CongCu] = (),
        max_tokens: int = 1024,
        tinh_nang: str = "tro_ly_khach",
    ) -> KetQuaMoHinh:
        self.da_nhan.append(list(tin))
        buoc = self._kich_ban.pop(0)
        if isinstance(buoc, Exception):
            raise buoc
        return buoc

    async def dong(self) -> None:
        return None


def _goi(ten: str, **tham_so: Any) -> GoiCongCu:
    return GoiCongCu(ma=f"id_{ten}", ten=ten, tham_so=tham_so)


async def _chay(mh: MoHinhGia, tin: str, lich_su: Sequence[Tin] = ()) -> Any:
    return await bo_nao.tra_loi(
        mh, tin_khach=tin, lich_su=lich_su, bo_cong_cu=CongCuMau(lambda: LUC), luc=LUC
    )


@pytest.mark.asyncio
async def test_goi_cong_cu_roi_tra_loi() -> None:
    mh = MoHinhGia(
        [
            KetQuaMoHinh("", (_goi("tra_gia_dich_vu", tu_khoa="hpv"),), token_vao=100),
            KetQuaMoHinh("Dạ xét nghiệm HPV 650.000đ ạ.", token_vao=150, token_ra=20),
        ]
    )
    kq = await _chay(mh, "xn hpv bao nhieu")
    assert kq.nhap == "Dạ xét nghiệm HPV 650.000đ ạ."
    assert not kq.chuyen_nguoi
    assert [b.ten for b in kq.buoc] == ["tra_gia_dich_vu"]
    assert kq.token_vao == 250 and kq.so_vong == 2
    # Lượt 2 model nhận: tin khách → lượt gọi → kết quả có giá thật của công cụ.
    lan2 = mh.da_nhan[1]
    assert [t.vai for t in lan2] == ["khach", "tro_ly", "ket_qua_cong_cu"]
    assert json.loads(lan2[2].noi_dung)["dich_vu"][0]["gia_vnd"] == 650000


@pytest.mark.asyncio
async def test_tin_khan_khong_goi_model() -> None:
    mh = MoHinhGia([])
    kq = await _chay(mh, "e dang ra mau nhieu lam")
    assert kq.chan_boi_code == "khan_cap" and kq.chuyen_nguoi
    assert mh.da_nhan == []


@pytest.mark.asyncio
async def test_model_goi_chuyen_nguoi() -> None:
    mh = MoHinhGia(
        [
            KetQuaMoHinh(
                "", (_goi("chuyen_nguoi", ly_do="dat_lich", ghi_chu="9h30 31/10"),)
            ),
            KetQuaMoHinh("Dạ em ghi nhận, nhân viên sẽ xác nhận lại với chị."),
        ]
    )
    kq = await _chay(mh, "chot 9h30 sang mai")
    assert kq.chuyen_nguoi and kq.ly_do_chuyen == "dat_lich"
    assert kq.ghi_chu_chuyen == "9h30 31/10"


@pytest.mark.asyncio
async def test_het_vong_thi_chuyen_nguoi() -> None:
    lap = KetQuaMoHinh("", (_goi("thong_tin_phong_kham"),))
    mh = MoHinhGia([lap] * bo_nao.SO_VONG_TOI_DA)
    kq = await _chay(mh, "o dau vay")
    assert kq.chuyen_nguoi and kq.ly_do_chuyen == "het_vong"
    assert kq.nhap == bo_nao.CAU_CHUYEN_NGUOI


@pytest.mark.asyncio
async def test_model_loi_thi_chuyen_nguoi_khong_nem() -> None:
    kq = await _chay(MoHinhGia([MoHinhError("HTTP 401")]), "alo")
    assert kq.chuyen_nguoi and kq.loi == "HTTP 401"


def test_cat_lich_su_bat_dau_tu_tin_khach() -> None:
    ls = [
        Tin("khach", "a"),
        Tin("tro_ly", "", (_goi("lich_trong"),)),
        Tin("ket_qua_cong_cu", "{}", ma_goi="id_lich_trong"),
        Tin("tro_ly", "b"),
        Tin("khach", "c"),
    ]
    assert [t.noi_dung for t in bo_nao.cat_lich_su(ls, n=3)] == ["c"]


@pytest.mark.parametrize(
    ("chu", "nhan"),
    [
        ("hoi_gia", "hoi_gia"),
        ("Nhãn: dat_lich.", "dat_lich"),
        ("hoi_y_khoa", "hoi_y_khoa"),
        ("không rõ", "khac"),
        ("", "khac"),
    ],
)
def test_doc_nhan(chu: str, nhan: str) -> None:
    assert bo_nao.doc_nhan(chu) == nhan


# --- dịch tin của adapter -------------------------------------------------

_LICH_SU = [
    Tin("khach", "hpv?"),
    Tin(
        "tro_ly",
        "để em xem",
        (_goi("tra_gia_dich_vu", tu_khoa="hpv"), _goi("thong_tin_phong_kham")),
    ),
    Tin("ket_qua_cong_cu", '{"a":1}', ma_goi="id_tra_gia_dich_vu"),
    Tin("ket_qua_cong_cu", '{"b":2}', ma_goi="id_thong_tin_phong_kham"),
]


def test_anthropic_gom_ket_qua_vao_mot_tin_user() -> None:
    m = ad_anthropic.dich_tin(_LICH_SU)
    assert [x["role"] for x in m] == ["user", "assistant", "user"]
    assert [k["type"] for k in m[1]["content"]] == ["text", "tool_use", "tool_use"]
    assert [k["tool_use_id"] for k in m[2]["content"]] == [
        "id_tra_gia_dich_vu",
        "id_thong_tin_phong_kham",
    ]


def test_openai_dich_tin_va_doc_phan_hoi() -> None:
    m = ad_openai.dich_tin("HT", _LICH_SU)
    assert [x["role"] for x in m] == ["system", "user", "assistant", "tool", "tool"]
    assert json.loads(m[2]["tool_calls"][0]["function"]["arguments"]) == {
        "tu_khoa": "hpv"
    }
    chu, goi, _ = ad_openai.doc_phan_hoi(
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "lich_trong",
                                    "arguments": "{hỏng",
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )
    assert chu == "" and goi[0].ten == "lich_trong" and goi[0].tham_so == {}


def test_tao_mo_hinh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRO_LY_THU_MUC_KHOA", str(tmp_path))
    monkeypatch.delenv("TRO_LY_KHOA_ANTHROPIC", raising=False)
    monkeypatch.delenv("TRO_LY_KHOA_OPENAI", raising=False)
    with pytest.raises(MoHinhError):
        tao_mo_hinh("anthropic:claude-haiku-5-5")
    with pytest.raises(MoHinhError):
        tao_mo_hinh("openai:gpt-x")
    with pytest.raises(MoHinhError):
        tao_mo_hinh("khong-co-dau-hai-cham")
    assert tao_mo_hinh("ollama:qwen3").ten == "ollama:qwen3"
    (tmp_path / "tro_ly_khoa_anthropic").write_text("sk-ant-gia\n")
    assert tao_mo_hinh("anthropic:claude-haiku-5-5").ten == "anthropic:claude-haiku-5-5"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kich_ban",
    [
        [MoHinhError("HTTP 500")],
        [KetQuaMoHinh("", (_goi("thong_tin_phong_kham"),))] * bo_nao.SO_VONG_TOI_DA,
        [KetQuaMoHinh("   ")],
    ],
    ids=["model_loi", "het_vong", "tra_rong"],
)
async def test_tin_cuoi_luon_la_nhap(kich_ban: list[Any]) -> None:
    """Nơi lưu lấy tin cuối làm dòng nháp để duyệt — mọi nhánh phải để lại nó."""
    kq = await _chay(MoHinhGia(kich_ban), "o dau vay")
    cuoi = kq.tin_moi[-1]
    assert cuoi.vai == "tro_ly" and not cuoi.goi_cong_cu
    assert cuoi.noi_dung == kq.nhap != ""
