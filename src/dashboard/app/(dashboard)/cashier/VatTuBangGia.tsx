"use client";

/**
 * VẬT TƯ BÁN THÊM — phần của Bảng giá dịch vụ & phòng (Tuyền 01/10/2026, C13).
 *
 * Vật tư (nhóm "Nguyên liệu tiêu hao" của file KiotViet 01/10) bán thêm ở quầy
 * Thu tiền dịch vụ. Quản lý sửa đơn giá và bật / tắt bán ở đây — KHÔNG có phòng,
 * nhóm việc hay bên thu (vật tư không xếp phòng). Luật file: giá 0 / chưa có giá
 * = KHÔNG được bán (quầy thu không cho thêm); hàng "cần QL duyệt" (vòng Mirena)
 * thu ngân chỉ bán khi quản lý duyệt từng lần.
 *
 * Máy chủ quyết `ban_duoc` / lý do (`vat_tu_service.ly_do_khong_ban`); màn chỉ vẽ
 * và gửi `PATCH /api/service-price` như dịch vụ.
 */

import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import NganGap from "@/components/ui/NganGap";
import { boDauVatTu } from "@/lib/vat-tu";

export interface DongVatTu {
  id: string;
  service_code: string;
  name: string;
  don_vi: string | null;
  unit_price: number | null;
  active: boolean;
  can_ql_duyet: boolean;
  chon_nhanh: boolean;
  ban_duoc: boolean;
  ly_do_khong_ban: string | null;
}

const O_GIA =
  "h-10 w-28 rounded-control border border-line bg-surface px-2 text-right text-body tabular-nums " +
  "text-ink outline-none placeholder:text-ink-faint focus:border-brand-500 lg:h-8";

export default function VatTuBangGia({
  ds,
  ban,
  onSua,
}: {
  ds: DongVatTu[];
  ban: boolean;
  onSua: (id: string, patch: Record<string, unknown>, xong: string) => Promise<boolean>;
}) {
  const [tim, setTim] = useState("");
  const [nhapGia, setNhapGia] = useState<Record<string, string>>({});

  const hien = useMemo(() => {
    const khoa = boDauVatTu(tim.trim());
    return khoa ? ds.filter((d) => boDauVatTu(d.name).includes(khoa)) : ds;
  }, [ds, tim]);
  const banDuoc = ds.filter((d) => d.ban_duoc).length;

  return (
    <section className="rounded-card border border-hairline bg-surface px-4 py-2 shadow-card">
      <NganGap
        tieuDe="Vật tư bán thêm ở quầy thu"
        co="the"
        chip={<Chip tone="brand">{`${banDuoc}/${ds.length} bán được`}</Chip>}
        phu="Giá 0 / chưa có giá = không bán"
      >
        <div className="space-y-3 p-4">
          <p className="text-meta text-ink-muted">
            Danh mục theo file KiotViet 01/10. Điền đơn giá để bán; bỏ tick “Đang bán” để tạm ngưng. Vật tư không có
            phòng làm — thu cùng hoá đơn dịch vụ.
          </p>
          <label className="block">
            <span className="sr-only">Tìm vật tư</span>
            <input
              type="search"
              value={tim}
              onChange={(e) => setTim(e.target.value)}
              placeholder="Tìm vật tư — gõ tên, không dấu cũng được"
              className="h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink outline-none placeholder:text-ink-faint focus:border-brand-500 lg:h-8"
            />
          </label>
          {hien.length === 0 ? (
            <p className="py-6 text-center text-body text-ink-muted">Không có vật tư phù hợp.</p>
          ) : (
            <ul className="overflow-hidden rounded-control border border-line">
              {hien.map((d) => {
                const doiGia = nhapGia[d.id] !== undefined;
                return (
                  <li
                    key={d.id}
                    className={`flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-hairline px-3 py-2 last:border-b-0 ${
                      d.active ? "" : "opacity-60"
                    }`}
                  >
                    <div className="min-w-0 flex-1 basis-48">
                      <p className="text-emph font-medium text-ink">{d.name}</p>
                      <p className="flex flex-wrap items-center gap-1 text-meta text-ink-faint">
                        {d.don_vi ? <span>{d.don_vi}</span> : null}
                        {d.chon_nhanh ? <Chip tone="brand">Chọn nhanh</Chip> : null}
                        {d.can_ql_duyet ? <Chip tone="warning">Cần QL duyệt</Chip> : null}
                        {!d.ban_duoc ? <Chip tone="neutral">{d.ly_do_khong_ban}</Chip> : null}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <input
                        aria-label={`Đơn giá ${d.name}`}
                        inputMode="numeric"
                        value={doiGia ? nhapGia[d.id] : (d.unit_price ?? "")}
                        placeholder="chưa có giá"
                        disabled={ban}
                        onChange={(e) => setNhapGia((c) => ({ ...c, [d.id]: e.target.value }))}
                        className={O_GIA}
                      />
                      {doiGia ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="primary"
                          disabled={ban}
                          onClick={async () => {
                            const v = nhapGia[d.id].trim();
                            const ok = await onSua(
                              d.id,
                              { unit_price: v === "" ? null : v },
                              `Đã lưu giá “${d.name}”.`,
                            );
                            if (ok) setNhapGia((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== d.id)));
                          }}
                        >
                          Lưu
                        </Button>
                      ) : null}
                    </div>
                    <label className="flex min-h-10 items-center gap-2 text-meta text-ink-soft lg:min-h-0">
                      <input
                        type="checkbox"
                        checked={d.active}
                        disabled={ban}
                        onChange={() =>
                          void onSua(
                            d.id,
                            { active: !d.active },
                            d.active ? `Đã tạm ngưng “${d.name}”.` : `Đã bán lại “${d.name}”.`,
                          )
                        }
                        className="size-4 accent-brand-600"
                      />
                      <span>{d.active ? "Đang bán" : "Tạm ngưng"}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </NganGap>
    </section>
  );
}
