"use client";

// Tab "Agent giám sát" (09/10/2026 — Layer 1, giai đoạn shadow).
//
// Agent chạy mỗi phút trong người đưa tin sự kiện (services/agent_giam_sat.py),
// chỉ đọc hiện trạng và ghi nhận định của chính nó. Giai đoạn này CHƯA réo ai:
// chỉ quản lý thấy ở đây và chấm Đúng / Sai — số đo để quyết lên giai đoạn sau
// (hiện cho trưởng ca). Công tắc theo loại và công tắc tắt hết đều hoàn tác được.
// Màn chỉ vẽ + gửi lệnh; mọi luật (ngưỡng, độ đúng, chế độ) do máy chủ quyết.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import CongTac from "@/components/ui/CongTac";
import ONhap from "@/components/ui/ONhap";
import { fmtTime } from "@/lib/datetime";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

type DanhGia = "dung" | "sai" | "khong_ro";

interface NhanDinh {
  id: string;
  loai: string;
  ten_loai: string;
  muc: "warning" | "critical";
  noi_dung: string;
  muc_bang_chung: "quan_sat" | "suy_ra";
  so_lan: number;
  mo_luc: string;
  lan_cuoi: string;
  dong_luc: string | null;
  ly_do_dong: "HET" | "TAT" | null;
  danh_gia: DanhGia | null;
  danh_gia_ghi_chu: string | null;
}

interface ThongKe {
  loai: string;
  ten: string;
  che_do: "tat" | "shadow";
  dang_mo: number;
  tong_14_ngay: number;
  dung: number;
  sai: number;
  khong_ro: number;
  do_dung: number | null;
}

interface DuLieu {
  phien_ban: string;
  tat_het: boolean;
  thong_ke: ThongKe[];
  nhan_dinh: NhanDinh[];
  bi_cat: boolean;
  tran: number;
}

const NHAN_DANH_GIA: Record<DanhGia, string> = {
  dung: "Đúng",
  sai: "Sai",
  khong_ro: "Không rõ",
};

function ngayGio(iso: string): string {
  const d = new Date(iso);
  const hom = new Date().toDateString() === d.toDateString();
  return hom ? fmtTime(iso) : `${d.getDate()}/${d.getMonth() + 1} ${fmtTime(iso)}`;
}

async function gui(body: Record<string, unknown>): Promise<boolean> {
  const r = await fetch("/api/ops/agent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);
  return Boolean(r && r.ok);
}

export default function AgentGiamSat() {
  const [duLieu, setDuLieu] = useState<DuLieu | null>(null);
  const [chiMo, setChiMo] = useState(true);
  const [dang, setDang] = useState<string | null>(null);
  const [ghiChu, setGhiChu] = useState<Record<string, string>>({});
  const [baoLoi, setBaoLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    const r = await fetch(`/api/ops/agent${chiMo ? "?chi_mo=1" : ""}`, {
      cache: "no-store",
    }).catch(() => null);
    if (!r || !r.ok) {
      setBaoLoi("Không đọc được nhận định của agent — thử tải lại.");
      return;
    }
    setBaoLoi(null);
    setDuLieu((await r.json()) as DuLieu);
  }, [chiMo]);

  useEffect(() => {
    let huy = false;
    const chay = () => {
      if (!huy) void nap();
    };
    chay();
    const goNhip = nhipKhiHien(chay, 30000);
    return () => {
      huy = true;
      goNhip();
    };
  }, [nap]);

  const doiCheDo = async (loai: string, bat: boolean) => {
    setDang(`che-do:${loai}`);
    const ok = await gui({ hanh_dong: "che-do", loai, che_do: bat ? "shadow" : "tat" });
    setDang(null);
    if (!ok) setBaoLoi("Không đổi được công tắc.");
    await nap();
  };

  const cham = async (n: NhanDinh, gt: DanhGia) => {
    setDang(n.id);
    // Bấm lại đúng ô đang chọn = bỏ chấm (hoàn tác).
    const ok = await gui({
      hanh_dong: "danh-gia",
      id: n.id,
      danh_gia: n.danh_gia === gt ? null : gt,
      ghi_chu: ghiChu[n.id] ?? n.danh_gia_ghi_chu ?? null,
    });
    setDang(null);
    if (!ok) setBaoLoi("Không lưu được đánh giá.");
    await nap();
  };

  return (
    <div className="space-y-5 p-4 lg:p-5">
      {baoLoi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {baoLoi}
        </p>
      ) : null}

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-emph font-semibold text-ink">
            Agent giám sát vận hành{" "}
            <Chip tone={duLieu?.tat_het ? "neutral" : "info"}>
              {duLieu?.tat_het ? "Đã tắt hết" : "Chạy thử ngầm"}
            </Chip>
          </h2>
          {duLieu ? (
            <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
              <CongTac
                bat={!duLieu.tat_het}
                nhan="Bật agent giám sát"
                disabled={dang === "che-do:*"}
                onDoi={(bat) => void doiCheDo("*", bat)}
              />
              Bật agent
            </label>
          ) : null}
        </div>
        <p className="text-meta text-ink-muted">
          Mỗi phút agent đọc hiện trạng (cùng nguồn với màn Trưởng ca) và ghi lại điều nó thấy. Giai
          đoạn này chưa báo cho ai — chỉ quản lý xem ở đây. Hãy chấm <b>Đúng / Sai</b>: đủ số chấm
          và đủ đúng thì mới cho agent báo trưởng ca. Nhận định không chứa tên khách.
          {duLieu ? ` Phiên bản luật: ${duLieu.phien_ban}.` : ""}
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-emph font-semibold text-ink">Từng loại nhận định · 14 ngày</h2>
        {duLieu === null ? (
          <p className="text-body text-ink-muted">Đang tải…</p>
        ) : (
          <ul className="grid gap-2 lg:grid-cols-2">
            {duLieu.thong_ke.map((t) => (
              <li key={t.loai} className="rounded-card border border-hairline bg-surface p-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 text-body font-semibold text-ink">{t.ten}</span>
                  <CongTac
                    bat={t.che_do !== "tat"}
                    nhan={`Bật loại: ${t.ten}`}
                    disabled={duLieu.tat_het || dang === `che-do:${t.loai}`}
                    onDoi={(bat) => void doiCheDo(t.loai, bat)}
                  />
                </div>
                <p className="mt-1 text-meta text-ink-muted">
                  Đang mở {t.dang_mo} · 14 ngày {t.tong_14_ngay} · Đúng {t.dung} · Sai {t.sai} ·
                  Không rõ {t.khong_ro} · Độ đúng{" "}
                  <b className="text-ink">
                    {t.do_dung === null ? "chưa chấm" : `${Math.round(t.do_dung * 100)}%`}
                  </b>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-emph font-semibold text-ink">Nhận định</h2>
          <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={chiMo}
              onChange={(e) => setChiMo(e.target.checked)}
            />
            Chỉ cái đang mở
          </label>
        </div>
        {duLieu === null ? (
          <p className="text-body text-ink-muted">Đang tải…</p>
        ) : duLieu.nhan_dinh.length === 0 ? (
          <p className="rounded-control bg-success-bg px-3 py-2 text-body text-success">
            Agent chưa thấy chuyện gì cần xem.
          </p>
        ) : (
          <ul className="space-y-2">
            {duLieu.bi_cat ? (
              <li className="rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
                Đang hiện {duLieu.tran} nhận định đầu (đang mở trước) — còn nữa nhưng không vẽ hết.
              </li>
            ) : null}
            {duLieu.nhan_dinh.map((n) => (
              <li key={n.id} className="rounded-card border border-hairline bg-surface p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={n.muc === "critical" ? "danger" : "warning"}>
                    {n.muc === "critical" ? "Nghiêm trọng" : "Cần xem"}
                  </Chip>
                  <Chip tone="neutral">{n.ten_loai}</Chip>
                  {n.muc_bang_chung === "suy_ra" ? <Chip tone="info">Suy luận</Chip> : null}
                  {n.dong_luc ? (
                    <Chip tone="success">{n.ly_do_dong === "TAT" ? "Đã tắt" : "Đã hết"}</Chip>
                  ) : null}
                </div>
                <p className="mt-1 text-body text-ink">{n.noi_dung}</p>
                <p className="mt-1 text-meta text-ink-muted">
                  mở {ngayGio(n.mo_luc)} · thấy {n.so_lan} lượt · lần cuối {ngayGio(n.lan_cuoi)}
                  {n.dong_luc ? ` · đóng ${ngayGio(n.dong_luc)}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  {(["dung", "sai", "khong_ro"] as const).map((gt) => (
                    <Button
                      key={gt}
                      type="button"
                      size="sm"
                      variant={n.danh_gia === gt ? "primary" : "ghost"}
                      aria-pressed={n.danh_gia === gt}
                      disabled={dang === n.id}
                      onClick={() => void cham(n, gt)}
                    >
                      {NHAN_DANH_GIA[gt]}
                    </Button>
                  ))}
                  <ONhap
                    className="min-w-0 flex-1 basis-48"
                    placeholder="Ghi chú khi chấm (không bắt buộc)"
                    aria-label="Ghi chú đánh giá"
                    maxLength={500}
                    value={ghiChu[n.id] ?? n.danh_gia_ghi_chu ?? ""}
                    onChange={(e) => setGhiChu((g) => ({ ...g, [n.id]: e.target.value }))}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
