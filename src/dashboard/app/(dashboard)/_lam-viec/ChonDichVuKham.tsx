"use client";

// DỊCH VỤ KHÁM — tick đúng dịch vụ khám theo mã KiotViet (Tuyền 28/09/2026):
// "tiền phát sinh khi bác sĩ khám cho họ là khám cái gì … tick để chọn loại dịch
// vụ chính xác của dịch vụ khám, lúc đó tiền mới tính, không còn bịa giá nữa".
//
// Máy chủ quyết TẤT CẢ: danh sách chọn được (theo loại khám của lượt), giá, ai
// tick được, và khoá khi tiền khám đã thu (`GET/POST /luot-kham/visits/{id}/
// phi-kham`). Màn chỉ vẽ ô tick và gửi tập đã chọn. Dùng ở Bàn khám (dưới "Bác
// sĩ tư vấn ghi") và ở quầy thu (khi dòng tiền khám chưa chọn).

import { useCallback, useEffect, useState } from "react";

import { docBang, guiThaoTac } from "./api";

interface LuaChon {
  id: string;
  ma_kiotviet: string | null;
  ten: string;
  gia: number | null;
}

interface PhiKham {
  loai_kham: string | null;
  di_thang_phong: boolean;
  khong_kham: boolean;
  lua_chon: LuaChon[];
  da_chon: string[];
  khoa: boolean;
  duoc_tick: boolean;
}

const tien = (n: number | null) =>
  n == null ? "chưa có giá" : `${new Intl.NumberFormat("vi-VN").format(n)}đ`;

export default function ChonDichVuKham({
  visitId,
  onDoi,
}: {
  visitId: string;
  /** Gọi sau khi lưu xong (vd quầy tải lại hoá đơn). */
  onDoi?: () => void;
}) {
  const [pk, setPk] = useState<PhiKham | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState(false);

  const nap = useCallback(async () => {
    const kq = await docBang<PhiKham>("phi-kham", { luot: visitId });
    if (kq.ok) setPk(kq.data);
    else setLoi(kq.loi);
  }, [visitId]);

  useEffect(() => {
    // Nạp lần đầu khi mở lượt — dữ liệu ngoài (máy chủ), không phải state suy ra.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void nap();
  }, [nap]);

  if (!pk) return loi ? <p className="text-meta text-danger">{loi}</p> : null;
  // Loại khám đi thẳng phòng: không có tiền khám — dịch vụ thêm ở quầy.
  if (pk.khong_kham || pk.lua_chon.length === 0) return null;

  async function doi(id: string, bat: boolean) {
    if (!pk) return;
    const ids = bat ? [...pk.da_chon, id] : pk.da_chon.filter((x) => x !== id);
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("phi-kham", visitId, { ids });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setPk(kq.data as unknown as PhiKham);
    onDoi?.();
  }

  const moTick = pk.duoc_tick && !dangGui;
  return (
    <section className="space-y-2 rounded-control border border-line bg-surface p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-body font-semibold text-ink">
          Dịch vụ khám{pk.loai_kham ? ` — ${pk.loai_kham}` : ""}
        </h3>
        <span className="text-meta text-ink-muted">
          {pk.da_chon.length === 0
            ? "Chưa chọn — đang tính giá mặc định"
            : "Tiền khám tính theo dịch vụ đã chọn"}
        </span>
      </div>
      <ul className="space-y-1">
        {pk.lua_chon.map((c) => {
          const chon = pk.da_chon.includes(c.id);
          return (
            <li key={c.id}>
              <label
                className={`flex min-h-10 items-center gap-3 rounded-control px-2 py-1.5 ${
                  moTick ? "cursor-pointer hover:bg-surface-muted" : "opacity-70"
                }`}
              >
                <input
                  type="checkbox"
                  checked={chon}
                  disabled={!moTick}
                  onChange={(e) => void doi(c.id, e.target.checked)}
                  className="size-4 accent-brand-600"
                />
                <span className="min-w-0 flex-1 text-body text-ink">
                  {c.ten}
                  {c.ma_kiotviet ? (
                    <span className="text-meta text-ink-muted"> · {c.ma_kiotviet}</span>
                  ) : null}
                </span>
                <span className="shrink-0 text-meta text-ink-soft">{tien(c.gia)}</span>
              </label>
            </li>
          );
        })}
      </ul>
      {loi ? <p className="text-meta text-danger">{loi}</p> : null}
    </section>
  );
}
