"""Mẫu kết quả cận lâm sàng: dịch vụ nào điền vào mẫu nào.

TRÊN TỜ GIẤY, quan hệ này là nút "📄 Xem mẫu" đứng cạnh từng dịch vụ trong phiếu
chỉ định. Trong hệ thống, nó phải là DỮ LIỆU: đổi mẫu cho một dịch vụ là việc của
quản lý trên màn, không phải việc của người sửa code.

KHÔNG GẮN BẰNG TÊN. Tờ giấy chỉ có tên gọi ("SÂ tuyến vú"), còn bảng giá dùng mã
do KiotViet cấp. Đoán mã từ tên là cách gắn nhầm mẫu kết quả cho bệnh nhân — và
gắn nhầm thì bác sĩ điền đúng vào chỗ sai. Nên máy chỉ ĐỀ XUẤT, người xác nhận.

GẮN LÀ THAY ĐỔI CÓ THẬT, không phải cấu hình vặt: nó đổi cái mà bác sĩ nhìn thấy
lúc trả kết quả. Vì vậy mỗi lần gắn/gỡ đều ghi ai làm, lúc nào.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.permissions.can import doi_quyen

QUYEN_GAN_MAU = "catalogue.result_template.manage"


class MauKetQuaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def danh_muc(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Mọi mẫu đang dùng, kèm những dịch vụ đã gắn vào mẫu ấy."""
        async with self._pool.acquire() as conn:
            mau = await conn.fetch(
                "SELECT ma, nhom, ten FROM ket_qua_mau"
                " WHERE clinic_id = $1::uuid AND active ORDER BY nhom, ten",
                identity.clinic_id,
            )
            gan = await conn.fetch(
                "SELECT g.mau, g.service_code, p.name"
                "  FROM dich_vu_mau_ket_qua g"
                "  LEFT JOIN service_price p"
                "    ON p.clinic_id = g.clinic_id AND p.service_code = g.service_code"
                " WHERE g.clinic_id = $1::uuid ORDER BY g.mau, g.service_code",
                identity.clinic_id,
            )
        theo_mau: dict[str, list[dict[str, Any]]] = {}
        for r in gan:
            theo_mau.setdefault(r["mau"], []).append(
                {"ma_dich_vu": r["service_code"], "ten_dich_vu": r["name"]}
            )
        return {
            "mau": [
                {
                    "ma": m["ma"],
                    "nhom": m["nhom"],
                    "ten": m["ten"],
                    "dich_vu": theo_mau.get(m["ma"], []),
                }
                for m in mau
            ]
        }

    async def mau_cua_dich_vu(
        self, *, service_code: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Bác sĩ trả kết quả cho dịch vụ này thì điền vào mẫu nào.

        Một dịch vụ có thể có nhiều mẫu (siêu âm thai theo quý), nên trả danh
        sách; màn hình để bác sĩ chọn, không tự đoán hộ.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT m.ma, m.nhom, m.ten FROM dich_vu_mau_ket_qua g"
                "  JOIN ket_qua_mau m"
                "    ON m.clinic_id = g.clinic_id AND m.ma = g.mau AND m.active"
                " WHERE g.clinic_id = $1::uuid AND g.service_code = $2"
                " ORDER BY m.ten",
                identity.clinic_id,
                service_code,
            )
        return {
            "service_code": service_code,
            "mau": [dict(r) for r in rows],
        }

    async def gan(
        self, *, service_code: str, mau: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`BindResultTemplate` — gắn một mẫu cho một dịch vụ."""
        ma_dv = service_code.strip()
        if not ma_dv:
            raise ValidationError("Thiếu mã dịch vụ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_GAN_MAU)
            co_dv = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_price"
                " WHERE clinic_id = $1::uuid AND service_code = $2)",
                identity.clinic_id,
                ma_dv,
            )
            if not co_dv:
                raise ValidationError(
                    f"Không có dịch vụ mã “{ma_dv}” ở phòng khám này."
                )
            # Mẫu không tồn tại thì khoá ngoại chặn — không cần kiểm tay.
            them = await conn.fetchval(
                "INSERT INTO dich_vu_mau_ket_qua"
                " (clinic_id, service_code, mau, gan_boi)"
                " VALUES ($1::uuid, $2, $3, $4::uuid)"
                " ON CONFLICT DO NOTHING RETURNING service_code",
                identity.clinic_id,
                ma_dv,
                mau,
                identity.staff_id,
            )
        return {"ok": True, "service_code": ma_dv, "mau": mau, "moi": them is not None}

    async def go(
        self, *, service_code: str, mau: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`UnbindResultTemplate` — gỡ mẫu khỏi một dịch vụ."""
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_GAN_MAU)
            da_go = await conn.fetchval(
                "DELETE FROM dich_vu_mau_ket_qua"
                " WHERE clinic_id = $1::uuid AND service_code = $2 AND mau = $3"
                " RETURNING service_code",
                identity.clinic_id,
                service_code,
                mau,
            )
        return {"ok": True, "da_go": da_go is not None}

    async def de_xuat(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Máy ĐỀ XUẤT mẫu cho các dịch vụ chưa gắn — người xác nhận.

        Cách so: bỏ dấu, bỏ chữ viết tắt hay gặp, rồi tìm mẫu có nhiều từ chung
        nhất. Không tự gắn, vì "SÂ tuyến vú" với "SÂ tuyến giáp" chỉ khác một từ.
        """
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN_GAN_MAU)
            dich_vu = await conn.fetch(
                "SELECT p.service_code, p.name FROM service_price p"
                " WHERE p.clinic_id = $1::uuid AND p.active"
                "   AND NOT EXISTS (SELECT 1 FROM dich_vu_mau_ket_qua g"
                "                    WHERE g.clinic_id = p.clinic_id"
                "                      AND g.service_code = p.service_code)"
                " ORDER BY p.name",
                identity.clinic_id,
            )
            mau = await conn.fetch(
                "SELECT ma, ten FROM ket_qua_mau WHERE clinic_id = $1::uuid AND active",
                identity.clinic_id,
            )

        de_xuat = []
        for dv in dich_vu:
            tu_dv = _tu_khoa(dv["name"])
            if not tu_dv:
                continue
            diem = [(len(tu_dv & _tu_khoa(m["ten"])), m["ma"], m["ten"]) for m in mau]
            diem.sort(reverse=True)
            if diem and diem[0][0] >= 2:
                de_xuat.append(
                    {
                        "ma_dich_vu": dv["service_code"],
                        "ten_dich_vu": dv["name"],
                        "mau": diem[0][1],
                        "ten_mau": diem[0][2],
                        "so_tu_trung": diem[0][0],
                    }
                )
        return {"de_xuat": de_xuat, "so_dich_vu_chua_gan": len(dich_vu)}


_BO_QUA = frozenset(
    {"ket", "qua", "phieu", "sa", "sieu", "am", "xn", "xet", "nghiem", "cua", "va"}
)


def _tu_khoa(ten: str) -> frozenset[str]:
    """Tách tên thành các từ có nghĩa để so, bỏ dấu và bỏ từ đệm."""
    khong_dau = "".join(
        c
        for c in unicodedata.normalize("NFD", ten.lower())
        if unicodedata.category(c) != "Mn"
    )
    tu = {t.strip("()-*•.") for t in khong_dau.replace("/", " ").split()}
    return frozenset(t for t in tu if len(t) >= 2 and t not in _BO_QUA)


__all__ = ["QUYEN_GAN_MAU", "MauKetQuaService"]
