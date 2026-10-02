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
//
// CHỌN PHÒNG TRƯỚC KHI CHỐT (Tuyền 24/09/2026): "phải cho chọn phòng để chỉ
// định xem khách đó khám ở đâu rồi mới chốt và thanh toán". V10 (30/09/2026,
// làm trước, thu sau): chốt xong máy chủ XẾP PHÒNG NGAY (dây H4), không chờ thu
// — ô này ghi phòng khách chọn (`phong-du-kien`: đã chốt thì xếp thật luôn).
// Danh sách phòng cũng do máy chủ trả (`phong_chon_duoc`, cùng tập H4 dùng).
//
// BỎ TICK LÀ TRỪ TIỀN NGAY (Tuyền 24/09/2026): "bỏ tick dịch vụ không làm mà
// tổng vẫn tính". Hoá đơn do máy chủ tính theo lựa chọn ĐÃ LƯU; trước đây ô tick
// chỉ đổi trên màn, phải bấm "Chốt" tổng mới trừ. Giờ mỗi lần tích / bỏ tick /
// đổi phòng là lưu luôn (cùng lệnh chốt) rồi nạp lại hoá đơn.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import ChonBacSiLam, { coChonBacSi, type LuaChonBacSi } from "../_lam-viec/ChonBacSiLam";

export interface PhongChonDuoc {
  id: string;
  ten: string;
  dang_cho: number;
  /** Phòng nhiều bác sĩ (30/09/2026): bác sĩ trực hôm nay — chỉ khi ≥2. */
  bac_si?: LuaChonBacSi[];
}

export interface ChiDinhChoQuyet {
  id: string;
  ten: string;
  selection_status: "PENDING" | "SELECTED" | "NOT_SELECTED" | null;
  gia: number | null;
  mang_sang: boolean;
  phong_du_kien_id?: string | null;
  /** Bác sĩ quầy đã chọn trong phòng nhiều bác sĩ. */
  bac_si_lam_id?: string | null;
  phong_chon_duoc?: PhongChonDuoc[];
  /** Làm bên ngoài — việc tự sang bàn đối tác (sự kiện). */
  doi_tac?: boolean;
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026, máy chủ nói) — giá chỉ để
   *  tham khảo, không cộng vào tiền phòng khám. */
  doi_tac_thu?: boolean;
  /** Bác sĩ đánh dấu BẮT BUỘC (25/09/2026) — quầy không bỏ được (máy chủ chặn). */
  bat_buoc?: boolean;
  /** Làm thêm tại quầy (01/10/2026) — câu máy chủ viết; null = bác sĩ chỉ định. */
  lam_them?: string | null;
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
  // "" = chưa chọn phòng (ô hiện "Vui lòng chọn phòng"); máy chủ quyết khi xếp.
  const [phong, setPhong] = useState<Record<string, string>>(() =>
    Object.fromEntries(cho.chi_dinh.map((c) => [c.id, c.phong_du_kien_id ?? ""])),
  );
  // Bác sĩ trong phòng nhiều bác sĩ ("" = bác sĩ nào rảnh cũng được).
  const [bacSi, setBacSi] = useState<Record<string, string>>(() =>
    Object.fromEntries(cho.chi_dinh.map((c) => [c.id, c.bac_si_lam_id ?? ""])),
  );
  const [dang, setDang] = useState(false);

  if (!mo) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
        <p className="text-meta text-ink-muted">
          Đã chốt dịch vụ khách làm — khách đi làm được ngay, thu tiền sau.
        </p>
        <Button size="sm" variant="ghost" onClick={() => setMo(true)}>
          Sửa dịch vụ khách làm
        </Button>
      </div>
    );
  }

  const bsCuaPhong = (c: ChiDinhChoQuyet, roomId: string) =>
    (c.phong_chon_duoc ?? []).find((ph) => ph.id === roomId)?.bac_si;

  const chot = async (
    chonMoi: Set<string> = chon,
    phongMoi: Record<string, string> = phong,
    bacSiMoi: Record<string, string> = bacSi,
  ) => {
    setDang(true);
    const ds = cho.chi_dinh.map((c) => c.id);
    const daChon = ds.filter((id) => chonMoi.has(id));
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
        // Ghi phòng khách chọn cho từng dịch vụ khách làm (chỉ cái đổi).
        const loiPhong: string[] = [];
        for (const c of cho.chi_dinh) {
          const muon = phongMoi[c.id] ?? "";
          const bs = bacSiMoi[c.id] ?? "";
          const doiPhong = muon !== (c.phong_du_kien_id ?? "");
          const doiBs = bs !== (c.bac_si_lam_id ?? "");
          if (!chonMoi.has(c.id) || (!doiPhong && !doiBs)) continue;
          // Bác sĩ chỉ gửi khi phòng có ô chọn (≥2 bác sĩ); không gửi thì máy
          // chủ giữ / tự gán phòng một bác sĩ.
          const coBs = muon !== "" && coChonBacSi(bsCuaPhong(c, muon));
          const rp = await fetch("/api/luot-kham", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              thao_tac: "phong-du-kien",
              id: c.id,
              du_lieu: { room_id: muon || null, ...(coBs ? { bac_si_lam_id: bs || null } : {}) },
            }),
          });
          if (!rp.ok) {
            const dp = (await rp.json().catch(() => null)) as
              | { message?: string; error?: string }
              | null;
            loiPhong.push(`${c.ten}: ${dp?.message ?? dp?.error ?? "không ghi được phòng"}`);
          }
        }
        if (loiPhong.length) {
          await onXong(null, "Đã chốt dịch vụ nhưng CHƯA ghi được phòng — " + loiPhong.join("; "));
          return;
        }
        await onXong(
          daChon.length
            ? `Đã lưu ${daChon.length} dịch vụ khách làm — tổng tiền đã cập nhật.`
            : "Đã ghi: khách không làm dịch vụ nào.",
          null,
        );
      } else {
        // Không lưu được → trả ô tick về như cũ, khỏi hiện sai với hoá đơn.
        setChon(chon);
        setPhong(phong);
        setBacSi(bacSi);
        await onXong(null, d?.message ?? d?.error ?? "Không chốt được dịch vụ.");
      }
    } catch {
      setChon(chon);
      setPhong(phong);
      setBacSi(bacSi);
      await onXong(null, "Mất kết nối — CHƯA chốt được dịch vụ khách làm.");
    } finally {
      setDang(false);
    }
  };

  return (
    <div className="border-b border-line px-4 py-3">
      <ul className="space-y-1">
        {cho.chi_dinh.map((c) => (
          <li key={c.id}>
            <label className="flex min-h-10 items-center gap-3">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={chon.has(c.id)}
                // Bắt buộc: khoá bỏ chọn — khách không chịu thì quay lại người
                // chỉ định bỏ tick (máy chủ chặn `SERVICE_REQUIRED`).
                disabled={dang || (Boolean(c.bat_buoc) && chon.has(c.id))}
                onChange={(e) => {
                  const moi = new Set(chon);
                  if (e.target.checked) moi.add(c.id);
                  else moi.delete(c.id);
                  setChon(moi);
                  void chot(moi, phong);
                }}
              />
              <span className="min-w-0 flex-1 text-body text-ink">
                {c.ten}
                {c.bat_buoc ? (
                  <span
                    className="ml-2"
                    title="Bác sĩ đánh dấu bắt buộc — muốn bỏ phải quay lại người chỉ định"
                  >
                    <Chip tone="warning">Bắt buộc</Chip>
                  </span>
                ) : null}
                {c.mang_sang ? (
                  <span className="ml-2">
                    <Chip tone="brand">hẹn từ lượt trước</Chip>
                  </span>
                ) : null}
                {c.lam_them ? (
                  <span className="ml-2">
                    <Chip tone="info">{c.lam_them}</Chip>
                  </span>
                ) : null}
                {c.doi_tac ? (
                  <span className="ml-2" title="Việc tự sang bàn đối tác">
                    <Chip tone="neutral">Đối tác làm</Chip>
                  </span>
                ) : null}
                {c.doi_tac_thu ? (
                  <span className="block text-meta text-ink-muted">
                    Thu hộ đối tác — không cộng
                  </span>
                ) : null}
              </span>
              <span className="text-body text-ink-muted">
                {c.gia !== null
                  ? c.doi_tac_thu
                    ? `tham khảo ${tien(c.gia)}`
                    : tien(c.gia)
                  : "chưa có giá"}
              </span>
            </label>
            {chon.has(c.id) && (c.phong_chon_duoc?.length ?? 0) > 0 ? (
              <label className="ml-7 flex flex-wrap items-center gap-2 pb-1">
                <span className="text-meta text-ink-muted">Làm ở phòng</span>
                <select
                  value={phong[c.id] ?? ""}
                  disabled={dang}
                  onChange={(e) => {
                    const moi = { ...phong, [c.id]: e.target.value };
                    // Đổi phòng → bỏ bác sĩ của phòng cũ (máy chủ cũng xoá).
                    const bsMoi = { ...bacSi, [c.id]: "" };
                    setPhong(moi);
                    setBacSi(bsMoi);
                    void chot(chon, moi, bsMoi);
                  }}
                  className="min-h-10 rounded-control border border-line bg-surface px-2 text-body text-ink"
                >
                  <option value="">— Vui lòng chọn phòng —</option>
                  {(c.phong_chon_duoc ?? []).map((ph) => (
                    <option key={ph.id} value={ph.id}>
                      {ph.ten} · {ph.dang_cho} người chờ
                    </option>
                  ))}
                </select>
                {(() => {
                  const ds = bsCuaPhong(c, phong[c.id] ?? "");
                  return coChonBacSi(ds) ? (
                    <ChonBacSiLam
                      ds={ds}
                      value={bacSi[c.id] ?? ""}
                      disabled={dang}
                      onChon={(id) => {
                        const bsMoi = { ...bacSi, [c.id]: id };
                        setBacSi(bsMoi);
                        void chot(chon, phong, bsMoi);
                      }}
                    />
                  ) : null;
                })()}
              </label>
            ) : null}
          </li>
        ))}
      </ul>
      {/* Tuyền 27/09 (đợt 3): bỏ tiêu đề + câu hướng dẫn — chỉ báo lúc đang lưu. */}
      {dang ? <p className="mt-2 text-meta text-ink-muted">Đang lưu…</p> : null}
      <div className="mt-2 flex flex-wrap gap-2">
        {conCho ? (
          <Button variant="primary" size="lg" disabled={dang} onClick={() => void chot()}>
            Chốt dịch vụ khách làm
          </Button>
        ) : (
          <Button size="lg" variant="ghost" disabled={dang} onClick={() => setMo(false)}>
            Xong
          </Button>
        )}
      </div>
    </div>
  );
}
