"use client";

// Màn Nhà thuốc (contract tiền–thuốc CP4, 19/09/2026).
//
// Theo LƯỢT KHÁM, không theo từng dòng đơn: tiền thuốc thu theo lượt, nên giai
// đoạn (chờ khám xong → chọn lô → chờ xác minh → đã thu, giao) cũng là của lượt.
// Giai đoạn và các nút được phép đến từ máy chủ; ở đây chỉ vẽ.
//
// V8 (30/09/2026): nút "Khách mua thuốc" mở lượt BÁN LẺ (khách chỉ mua thuốc);
// lượt bán lẻ hiện ngay cả khi chưa có dòng đơn, kèm khối kê + thu tại quầy.
//
// 16/10/2026: mở lượt xong (bán lẻ hay "Bán theo đơn này") màn KHÔNG chỉ thêm một
// dòng nhạt vào danh sách — nó chọn đúng lượt đó, cuộn tới khung chi tiết, viền
// đậm + chip "Vừa mở"; lời báo nối đơn nằm đầu khối bán lẻ (`BanLeThu`).

import { useEffect, useMemo, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import SoLuot from "@/components/ui/SoLuot";
import StatusChip from "@/components/ui/StatusChip";
import XemLuot from "../_lam-viec/XemLuot";
import BanLeThu from "./BanLeThu";
import DongThuoc, { CHAM } from "./DongThuoc";
import KhachMuaThuoc from "./KhachMuaThuoc";
import { INPUT } from "../form-ui";
import OQuetMa, { NHAN_TRANG_THAI_LO, type KetQuaQuet } from "./inventory/OQuetMa";
import { cauLoKhongDungDuoc } from "@/lib/lo-bi-loai";
import { GIAI_DOAN, type LuotThuoc, type ManNhaThuoc } from "./ban-thuoc";
import { anNoiDon } from "./thong-bao-noi-don";
import { sdtDoc } from "@/lib/sdt";

type Tab = "dang_lam" | "xong";

// Lượt chưa có dòng nào (bán lẻ vừa mở) là CHƯA xong — `every` của mảng rỗng
// là true, đừng để nó rơi sang tab "Xong".
const xongHet = (l: LuotThuoc) => l.dong.length > 0 && l.dong.every((d) => d.closed);

export default function PharmacyBoard({
  man,
  chonDau = null,
}: {
  man: ManNhaThuoc;
  /** Lượt chọn sẵn (`/pharmacy?luot=` — từ nút "Khách mua thuốc" ở Kho thuốc). */
  chonDau?: string | null;
}) {
  const [chon, setChon] = useState<string | null>(chonDau);
  const [tab, setTab] = useState<Tab>("dang_lam");
  const [tim, setTim] = useState("");
  const [xemLuot, setXemLuot] = useState<string | null>(null);
  // Lô chọn sẵn do quét (G3b): dòng nào, lô nào. Chỉ điền sẵn ô chọn lô của dòng.
  const [loQuet, setLoQuet] = useState<{ dongId: string; loId: string } | null>(null);
  const [baoQuet, setBaoQuet] = useState<string | null>(null);
  // Lượt người dùng vừa mở (nút "Khách mua thuốc") — đánh dấu + cuộn tới đó.
  // `chonDau` (đi từ Kho thuốc sang) cũng là lượt vừa mở.
  const [vuaMo, setVuaMo] = useState<string | null>(chonDau);
  const canCuon = useRef<string | null>(chonDau);
  const khungLuot = useRef<HTMLDivElement>(null);
  // Câu báo sau khi giao nằm ở đây: giao xong `DongThuoc` dựng lại theo key, câu
  // giữ trong thẻ sẽ mất trước khi người giao kịp đọc.
  const [tinGiao, setTinGiao] = useState<Record<string, string | null>>({});

  const dem = useMemo(
    () => ({
      dang_lam: man.luot.filter((l) => !xongHet(l)).length,
      xong: man.luot.filter(xongHet).length,
    }),
    [man.luot],
  );
  const danhSach = useMemo(() => {
    const q = tim.trim().toLowerCase();
    return man.luot
      .filter((l) => (tab === "xong" ? xongHet(l) : !xongHet(l)))
      .filter(
        (l) =>
          !q ||
          l.ten_khach?.toLowerCase().includes(q) ||
          l.patient_code?.toLowerCase().includes(q) ||
          l.dong.some((d) => d.drug_name_raw?.toLowerCase().includes(q)),
      );
  }, [man.luot, tab, tim]);
  const luot = man.luot.find((l) => l.visit_id === chon) ?? null;

  // Lượt vừa mở có thể chưa nằm trong `man.luot` (đang nạp lại) — cuộn khi nó xuất hiện.
  useEffect(() => {
    if (!luot || canCuon.current !== luot.visit_id) return;
    canCuon.current = null;
    khungLuot.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    khungLuot.current?.focus({ preventScroll: true });
  }, [luot]);

  const khiQuet = (kq: KetQuaQuet) => {
    setLoQuet(null);
    setBaoQuet(null);
    if (!luot || (kq.loai !== "tem" && kq.loai !== "thuoc")) return;
    const idThuoc = kq.loai === "tem" ? kq.lo.drug_catalog_id : kq.thuoc.id;
    const dong = luot.dong.find((d) => d.drug_catalog_id === idThuoc && !d.closed);
    if (!dong) {
      setBaoQuet("Thuốc vừa quét không có trong đơn đang chọn.");
      return;
    }
    let loId: string | undefined;
    if (kq.loai === "tem") {
      if (kq.lo.trang_thai !== "ok") {
        setBaoQuet(`Lô ${kq.lo.batch_code} ${NHAN_TRANG_THAI_LO[kq.lo.trang_thai] ?? "không dùng được"}.`);
        return;
      }
      loId = kq.lo.id;
    } else {
      // Mã vuông có số lô trùng một lô còn bán được thì lấy đúng lô đó; không thì
      // lô FEFO đầu tiên (hạn gần nhất, lô chưa có hạn xếp cuối) — đổi được ở ô chọn.
      loId = kq.lo_theo_ma?.trang_thai === "ok" ? kq.lo_theo_ma.id : kq.goi_y_lo[0]?.id;
    }
    if (!loId || !dong.lo_goi_y.some((b) => b.drug_batch_id === loId)) {
      // Nói ĐÚNG lý do (vd lô tính theo hộp, đơn kê theo gói) — máy chủ trả
      // `lo_bi_loai`; không có lý do thì câu chung như cũ.
      setBaoQuet(cauLoKhongDungDuoc(dong.lo_bi_loai, loId, dong.drug_name_raw ?? "thuốc này"));
      return;
    }
    setLoQuet({ dongId: dong.id, loId });
    const lo = dong.lo_goi_y.find((b) => b.drug_batch_id === loId);
    // Nút kế tiếp tuỳ giai đoạn dòng (máy chủ quyết `thao_tac`): chưa thu → Chọn lô;
    // đã thu chưa phân lô → Giao thuốc giao đúng lô vừa quét.
    const buoc = dong.thao_tac.giao_khong_lo ? "Giao thuốc (giao đúng lô này)" : "Chọn lô";
    setBaoQuet(`Đã điền lô ${lo?.batch_code ?? ""} cho ${dong.drug_name_raw ?? "thuốc"} — kiểm số rồi bấm ${buoc}.`);
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      {man.duoc_mo_ban_le ? (
        <div className="flex flex-wrap items-start gap-2">
          <KhachMuaThuoc
            onMo={(id) => {
              setTab("dang_lam");
              setTim("");
              setChon(id);
              setVuaMo(id);
              canCuon.current = id;
            }}
          />
        </div>
      ) : null}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-3">
        {/* ── Danh sách lượt ── */}
        <section className="flex flex-col rounded-card border border-line bg-surface lg:col-span-1">
          <div className="border-b border-line p-3">
            <h2 className="text-emph font-semibold text-ink">Đơn thuốc</h2>
            <div role="tablist" aria-label="Nhóm lượt" className="mt-2 flex flex-wrap gap-1">
              {(
                [
                  ["dang_lam", "Đang xử lý"],
                  ["xong", "Xong hôm nay"],
                ] as const
              ).map(([ma, nhan]) => (
                <Button className={CHAM}
                  key={ma}
                  size="sm"
                  role="tab"
                  aria-selected={tab === ma}
                  variant={tab === ma ? "primary" : "ghost"}
                  onClick={() => setTab(ma)}
                >
                  {nhan} ({dem[ma]})
                </Button>
              ))}
            </div>
            <input
              value={tim}
              onChange={(e) => setTim(e.target.value)}
              placeholder="Tìm tên / mã khách / thuốc…"
              aria-label="Tìm đơn thuốc"
              className={`${INPUT} mt-2`}
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            {danhSach.length === 0 ? (
              <p className="p-4 text-body text-ink-muted">Không có lượt nào.</p>
            ) : (
              danhSach.map((l) => {
                const gd = GIAI_DOAN[l.giai_doan];
                return (
                  <button
                    key={l.visit_id}
                    type="button"
                    onClick={() => {
                      if (l.visit_id !== chon) {
                        anNoiDon();
                        setVuaMo(null);
                      }
                      setChon(l.visit_id);
                      // Dưới `lg` khung chi tiết nằm sau cả danh sách: không cuộn thì
                      // bấm khách trông như không có gì xảy ra.
                      if (window.matchMedia("(max-width: 1023px)").matches) {
                        if (l.visit_id === chon) {
                          khungLuot.current?.scrollIntoView({ behavior: "smooth", block: "start" });
                        } else {
                          canCuon.current = l.visit_id;
                        }
                      }
                    }}
                    className={`block min-h-10 w-full border-b border-line px-3 py-2 text-left transition-colors hover:bg-surface-muted ${
                      chon === l.visit_id ? "bg-surface-selected" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex min-w-0 flex-wrap items-center gap-1.5 text-emph font-medium text-ink">
                        {l.ten_khach ?? "Chưa có tên"}
                        {sdtDoc(l.phone) ? <span className="text-body font-normal tabular-nums text-ink-muted">{sdtDoc(l.phone)}</span> : null}
                        <SoLuot booking={l.so_booking} checkin={l.so_tiep_don} />
                        {l.ban_le ? <Chip tone="brand">Bán lẻ</Chip> : null}
                      </span>
                      <StatusChip tone={xongHet(l) ? "completed" : gd.tone} label={xongHet(l) ? "Xong" : gd.nhan} />
                    </div>
                    <div className="mt-1 truncate text-meta text-ink-muted">
                      {l.patient_code ?? "—"} ·{" "}
                      {l.dong.length === 0
                        ? "khách mua thuốc — chưa kê"
                        : `${l.dong.length} thuốc: ${l.dong.map((d) => d.drug_name_raw ?? "—").join(", ")}`}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </section>

        {/* ── Chi tiết lượt ── */}
        <section className="flex flex-col gap-3 overflow-y-auto lg:col-span-2">
          {luot ? (
            <div
              ref={khungLuot}
              tabIndex={-1}
              className={`scroll-mt-4 space-y-3 rounded-card border bg-surface p-4 outline-none ${
                vuaMo === luot.visit_id ? "border-brand-600" : "border-line"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="flex flex-wrap items-center gap-2 text-title font-semibold text-ink">
                    {luot.ten_khach ?? "Chưa có tên"}
                    {sdtDoc(luot.phone) ? <span className="text-emph font-medium tabular-nums text-ink-muted">{sdtDoc(luot.phone)}</span> : null}
                    <SoLuot booking={luot.so_booking} checkin={luot.so_tiep_don} />
                    {luot.ban_le ? <Chip tone="brand">Bán lẻ — khách chỉ mua thuốc</Chip> : null}
                    {vuaMo === luot.visit_id ? <Chip tone="brand">Vừa mở</Chip> : null}
                  </h3>
                  <p className="text-meta text-ink-muted">
                    {luot.patient_code ?? "—"}
                  </p>
                </div>
                <StatusChip
                  size="md"
                  tone={GIAI_DOAN[luot.giai_doan].tone}
                  label={GIAI_DOAN[luot.giai_doan].nhan}
                />
              </div>
              <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-soft">
                {GIAI_DOAN[luot.giai_doan].giai_thich}
              </p>
              {!man.co_quyen_ghi ? (
                <p className="text-meta text-ink-muted">
                  Tài khoản của bạn chỉ xem màn Nhà thuốc — không có nút ghi.
                </p>
              ) : null}
              <Button className={CHAM} size="sm" variant="ghost" onClick={() => setXemLuot(luot.visit_id)}>
                Xem chi tiết lượt &amp; lịch sử cấp
              </Button>
              {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
              {/* Lượt bán lẻ: kê thêm + thu tiền thuốc ngay tại quầy (V8). */}
              {luot.ban_le && man.duoc_mo_ban_le ? (
                <BanLeThu key={luot.visit_id} visitId={luot.visit_id} />
              ) : null}
              {man.co_quyen_ghi && luot.dong.length > 0 ? (
                <div className="space-y-1">
                  <OQuetMa
                    nhan="Quét hộp thuốc / tem lô để chọn lô"
                    thuoc={man.danh_muc.map((t) => ({
                      id: t.id,
                      ten: `${t.name_base}${t.variant ? ` (${t.variant})` : ""}`,
                    }))}
                    ghiDuoc={man.co_quyen_ghi}
                    onKetQua={khiQuet}
                  />
                  {baoQuet ? (
                    <p role="status" className="text-meta text-ink-soft">
                      {baoQuet}
                    </p>
                  ) : null}
                </div>
              ) : null}
              {luot.dong.map((d) => (
                // Khoá theo trạng thái của dòng: mỗi lần ghi xong (xác định
                // thuốc, chọn lô, giao…) dòng dựng lại với ô nhập mới — số còn
                // cần chọn / còn phải giao đã đổi, giữ số cũ trong ô là mời sai.
                <DongThuoc
                  key={[
                    d.id,
                    luot.giai_doan,
                    d.drug_catalog_id,
                    d.purchased_qty,
                    d.da_chon,
                    d.dispensed_qty,
                    d.phan_lo.map((p) => `${p.allocation_id}:${p.handed_over_qty}`).join(","),
                    loQuet?.dongId === d.id ? loQuet.loId : "",
                  ].join("|")}
                  loQuet={loQuet?.dongId === d.id ? loQuet.loId : null}
                  tinDau={tinGiao[d.id] ?? null}
                  onTin={(tin) => setTinGiao((cu) => ({ ...cu, [d.id]: tin }))}
                  dong={d}
                  danhMuc={man.danh_muc}
                  chiXem={!man.co_quyen_ghi}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-card border border-dashed border-line p-6 text-body text-ink-faint">
              Chọn một lượt để xem đơn thuốc
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
