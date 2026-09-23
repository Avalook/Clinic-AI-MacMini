"use client";

// Khách làm dịch vụ nào — bước giữa "bác sĩ chỉ định" và "thu tiền".
//
// VÌ SAO CÓ Ô NÀY (nhóm 2, 24/09/2026). Chỉ định mới của bác sĩ ở trạng thái
// "chờ khách quyết" và KHÔNG vào hoá đơn cho tới khi có người xác nhận khách
// làm. Lệnh xác nhận (ConfirmServiceSelection) đã có từ Lifecycle v1 nhưng chưa
// màn nào gọi — nên ngoài đời, chỉ định mới không bao giờ tới được quầy thu.
// Luồng chuẩn của Tuyền: "khách xuống lễ tân TRẢ TIỀN dịch vụ thực làm".
//
// Màn KHÔNG tự suy cái gì còn chọn được: danh sách, trạng thái và `revision`
// đều do máy chủ trả (`chon_dich_vu` trên bảng thu ngân), cùng luật với lệnh.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";

export interface ChiDinhChoQuyet {
  id: string;
  ten: string;
  selection_status: "PENDING" | "SELECTED" | "NOT_SELECTED" | null;
  gia: number | null;
  mang_sang: boolean;
}

export interface ChoKhachQuyet {
  revision: number;
  chi_dinh: ChiDinhChoQuyet[];
}

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

export default function ChonDichVu({
  visitId,
  cho,
  onXong,
}: {
  visitId: string;
  cho: ChoKhachQuyet;
  onXong: (cau: string | null, loi: string | null) => Promise<void>;
}) {
  const conCho = cho.chi_dinh.some((c) => c.selection_status === "PENDING");
  const [mo, setMo] = useState(conCho);
  // Mặc định: khách làm mọi chỉ định chưa từ chối — lễ tân bỏ tick cái khách
  // không làm. Chỉ định khách đã từ chối lần trước giữ nguyên là không làm.
  const [chon, setChon] = useState<Set<string>>(
    () =>
      new Set(
        cho.chi_dinh
          .filter((c) => c.selection_status !== "NOT_SELECTED")
          .map((c) => c.id),
      ),
  );
  const [dang, setDang] = useState(false);

  if (!mo) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
        <p className="text-meta text-ink-muted">
          Đã chốt dịch vụ khách làm — sửa được tới khi thu tiền.
        </p>
        <Button size="sm" variant="ghost" onClick={() => setMo(true)}>
          Sửa dịch vụ khách làm
        </Button>
      </div>
    );
  }

  const chot = async () => {
    setDang(true);
    const ds = cho.chi_dinh.map((c) => c.id);
    const daChon = ds.filter((id) => chon.has(id));
    const thaoTac = dinhDanhThaoTac(
      "chon-dich-vu",
      visitId,
      String(cho.revision),
      daChon.join(","),
    );
    try {
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": khoaThaoTac(thaoTac),
        },
        body: JSON.stringify({
          thao_tac: "chon-dich-vu",
          id: visitId,
          du_lieu: {
            order_ids_seen: ds,
            selected_order_ids: daChon,
            expected_selection_revision: cho.revision,
          },
        }),
      });
      const d = (await r.json().catch(() => null)) as
        | { message?: string; error?: string }
        | null;
      if (r.ok) {
        xongThaoTac(thaoTac);
        await onXong(
          daChon.length
            ? `Đã chốt ${daChon.length} dịch vụ khách làm — hoá đơn đã cập nhật.`
            : "Đã ghi: khách không làm dịch vụ nào.",
          null,
        );
      } else {
        await onXong(null, d?.message ?? d?.error ?? "Không chốt được dịch vụ.");
      }
    } catch {
      await onXong(null, "Mất kết nối — CHƯA chốt được dịch vụ khách làm.");
    } finally {
      setDang(false);
    }
  };

  return (
    <div className="border-b border-line px-4 py-3">
      <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
        Khách làm dịch vụ nào?
      </p>
      <ul className="mt-2 space-y-1">
        {cho.chi_dinh.map((c) => (
          <li key={c.id}>
            <label className="flex min-h-10 items-center gap-3">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={chon.has(c.id)}
                onChange={(e) => {
                  const moi = new Set(chon);
                  if (e.target.checked) moi.add(c.id);
                  else moi.delete(c.id);
                  setChon(moi);
                }}
              />
              <span className="min-w-0 flex-1 text-body text-ink">
                {c.ten}
                {c.mang_sang ? (
                  <span className="ml-2">
                    <Chip tone="brand">hẹn từ lượt trước</Chip>
                  </span>
                ) : null}
              </span>
              <span className="text-body text-ink-muted">
                {c.gia !== null ? tien(c.gia) : "chưa có giá"}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button variant="primary" size="lg" disabled={dang} onClick={() => void chot()}>
          Chốt dịch vụ khách làm
        </Button>
        {!conCho ? (
          <Button size="lg" variant="ghost" disabled={dang} onClick={() => setMo(false)}>
            Để nguyên
          </Button>
        ) : null}
      </div>
    </div>
  );
}
