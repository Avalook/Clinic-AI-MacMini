"use client";

// DỊCH VỤ LÀM THÊM TẠI QUẦY — quản lý gắn / bớt nút "+ dịch vụ" (Tuyền 01/10/2026).
//
// "Để sau này phòng khám muốn thêm loại khác (lấy máu…) không phải code lại:
// QUẢN LÝ ĐIỀU KHIỂN được nút này — gắn thêm hay bớt." Mỗi dòng là một nút ở
// màn Tiếp đón và / hoặc Đo sinh hiệu: lễ tân / người đo tick là chỉ định ngay,
// không cần bác sĩ.
//
// MÀN CHỈ VẼ + GỬI LỆNH. Dịch vụ chọn được (đang bán, đã gắn bước làm), kiểm
// "bật mà không hiện ở đâu", quyền `config.wiring.manage` — máy chủ quyết
// (`lam_them_tai_quay_service.py`). Lưu là áp ngay: nút ở quầy hiện / ẩn theo
// dòng SSE chung.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import { useNgheBang } from "../../dung-nghe-bang";

interface Muc {
  service_code: string;
  nhan: string | null;
  nhan_hien: string;
  ten: string | null;
  gia: number | null;
  bat: boolean;
  thu_tu: number;
  o_tiep_don: boolean;
  o_sinh_hieu: boolean;
  dang_ban: boolean;
}

interface DichVu {
  service_code: string;
  ten: string;
  gia: number | null;
}

interface DuLieu {
  muc: Muc[];
  dich_vu: DichVu[];
}

const O_NHAP = "min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink";

function tien(n: number | null): string {
  return n == null ? "chưa có giá" : `${n.toLocaleString("vi-VN")}đ`;
}

type Luu = (ma: string, du: Partial<Muc>, cau: string) => Promise<void>;

export default function LamThemTaiQuayCauHinh() {
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [lan, setLan] = useState(0);
  useNgheBang(["lam_them_tai_quay"], () => setLan((n) => n + 1));

  useEffect(() => {
    let huy = false;
    void (async () => {
      try {
        const r = await fetch("/api/lam-them?cau_hinh=1", { cache: "no-store" });
        const d = (await r.json().catch(() => null)) as (DuLieu & { message?: string }) | null;
        if (huy) return;
        if (!r.ok || !d || !Array.isArray(d.muc)) {
          setLoi(d?.message ?? "Không đọc được danh sách dịch vụ làm thêm.");
          return;
        }
        setDl(d);
      } catch {
        if (!huy) setLoi("Mất kết nối — không đọc được danh sách.");
      }
    })();
    return () => {
      huy = true;
    };
  }, [lan]);

  const gui = useCallback(
    async (thao_tac: "luu-muc" | "bo-muc", ma: string, du_lieu: unknown, cau: string) => {
      setDang(true);
      setLoi(null);
      setXong(null);
      try {
        const r = await fetch("/api/lam-them", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ thao_tac, service_code: ma, du_lieu }),
        });
        const d = (await r.json().catch(() => null)) as
          | (Partial<DuLieu> & { message?: string; error?: string })
          | null;
        if (!r.ok) {
          setLoi(d?.message ?? d?.error ?? "Không lưu được.");
          return false;
        }
        setXong(cau);
        if (d && Array.isArray(d.muc)) {
          const muc = d.muc;
          setDl((cu) => (cu ? { ...cu, muc } : cu));
        }
        return true;
      } catch {
        setLoi("Mất kết nối — CHƯA lưu.");
        return false;
      } finally {
        setDang(false);
      }
    },
    [],
  );

  const luu: Luu = async (ma, du, cau) => {
    const m = dl?.muc.find((x) => x.service_code === ma);
    const goc = m ?? { nhan: null, bat: true, thu_tu: undefined, o_tiep_don: true, o_sinh_hieu: true };
    await gui(
      "luu-muc",
      ma,
      {
        nhan: du.nhan !== undefined ? du.nhan : goc.nhan,
        bat: du.bat ?? goc.bat,
        thu_tu: du.thu_tu ?? goc.thu_tu,
        o_tiep_don: du.o_tiep_don ?? goc.o_tiep_don,
        o_sinh_hieu: du.o_sinh_hieu ?? goc.o_sinh_hieu,
      },
      cau,
    );
  };

  // Đổi chỗ với dòng trên / dưới: hai lần lưu thứ tự.
  const doiCho = async (i: number, j: number) => {
    if (!dl) return;
    const a = dl.muc[i];
    const b = dl.muc[j];
    if (!a || !b) return;
    const ta = a.thu_tu === b.thu_tu ? a.thu_tu + (j > i ? 1 : -1) : b.thu_tu;
    await luu(a.service_code, { thu_tu: Math.max(0, ta) }, "Đã đổi thứ tự.");
    await luu(b.service_code, { thu_tu: a.thu_tu }, "Đã đổi thứ tự.");
  };

  return (
    <section
      aria-label="Dịch vụ làm thêm tại quầy"
      className="rounded-card border border-line bg-surface p-4 shadow-card"
    >
      <h2 className="text-emph font-semibold text-ink">Dịch vụ làm thêm tại quầy</h2>
      <p className="mb-3 text-meta text-ink-muted">
        Mỗi dòng là một nút “+ dịch vụ” ở màn Tiếp đón và / hoặc Đo sinh hiệu: lễ tân hay
        người đo tick là chỉ định ngay cho khách, không cần bác sĩ — quầy thu thấy dòng, phòng
        làm thấy khách, hành trình ghi “làm thêm tại quầy”. Lưu là áp ngay.
      </p>
      {loi ? (
        <p role="alert" className="mb-3 rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p role="status" className="mb-3 rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}
      {!dl ? (
        loi ? null : <p className="text-body text-ink-muted">Đang tải…</p>
      ) : (
        <>
          {dl.muc.length === 0 ? (
            <p className="text-body text-ink-muted">Chưa có nút nào — thêm ở dưới.</p>
          ) : (
            <ul className="divide-y divide-line">
              {dl.muc.map((m, i) => (
                <DongMuc
                  key={m.service_code}
                  m={m}
                  dang={dang}
                  luu={luu}
                  len={i > 0 ? () => void doiCho(i, i - 1) : undefined}
                  xuong={i < dl.muc.length - 1 ? () => void doiCho(i, i + 1) : undefined}
                  bo={() =>
                    void gui("bo-muc", m.service_code, {}, `Đã bỏ nút “${m.nhan_hien}” khỏi quầy.`)
                  }
                />
              ))}
            </ul>
          )}
          <ThemMuc dl={dl} dang={dang} luu={luu} />
        </>
      )}
    </section>
  );
}

function DongMuc({
  m,
  dang,
  luu,
  len,
  xuong,
  bo,
}: {
  m: Muc;
  dang: boolean;
  luu: Luu;
  len?: () => void;
  xuong?: () => void;
  bo: () => void;
}) {
  const [nhan, setNhan] = useState(m.nhan ?? "");
  const ten = m.nhan_hien;
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 text-body text-ink">
          <span className="font-semibold">{ten}</span>
          <span className="text-meta text-ink-muted">
            {" "}
            · {m.ten ?? m.service_code} · {tien(m.gia)}
          </span>
        </span>
        {!m.dang_ban ? <Chip tone="warning">Bảng giá đã ngừng bán — nút đang ẩn</Chip> : null}
        <Button
          size="lg"
          variant={m.bat ? "primary" : "secondary"}
          disabled={dang}
          onClick={() => void luu(m.service_code, { bat: !m.bat }, m.bat ? `Đã tắt nút “${ten}”.` : `Đã bật nút “${ten}”.`)}
        >
          {m.bat ? "Đang bật" : "Đang tắt"}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={m.o_tiep_don}
            disabled={dang}
            onChange={(e) => void luu(m.service_code, { o_tiep_don: e.target.checked }, `Đã đổi chỗ hiện của “${ten}”.`)}
          />
          Tiếp đón
        </label>
        <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={m.o_sinh_hieu}
            disabled={dang}
            onChange={(e) => void luu(m.service_code, { o_sinh_hieu: e.target.checked }, `Đã đổi chỗ hiện của “${ten}”.`)}
          />
          Đo sinh hiệu
        </label>
        <span className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={nhan}
            maxLength={40}
            placeholder={m.ten ?? "Chữ trên nút"}
            aria-label={`Chữ trên nút ${ten}`}
            onChange={(e) => setNhan(e.target.value)}
            className={`${O_NHAP} w-40`}
          />
          <Button
            size="lg"
            disabled={dang || nhan.trim() === (m.nhan ?? "")}
            onClick={() => void luu(m.service_code, { nhan: nhan.trim() || null }, `Đã đổi chữ trên nút “${ten}”.`)}
          >
            Lưu chữ
          </Button>
        </span>
        <span className="ml-auto flex items-center gap-1">
          <Button size="lg" variant="ghost" disabled={dang || !len} onClick={len} aria-label={`Đưa “${ten}” lên trên`}>
            ↑
          </Button>
          <Button size="lg" variant="ghost" disabled={dang || !xuong} onClick={xuong} aria-label={`Đưa “${ten}” xuống dưới`}>
            ↓
          </Button>
          <Button size="lg" variant="danger" disabled={dang} onClick={bo}>
            Bỏ khỏi quầy
          </Button>
        </span>
      </div>
    </li>
  );
}

function ThemMuc({ dl, dang, luu }: { dl: DuLieu; dang: boolean; luu: Luu }) {
  const [ma, setMa] = useState("");
  const [nhan, setNhan] = useState("");
  const daCo = new Set(dl.muc.map((m) => m.service_code));
  const chonDuoc = dl.dich_vu.filter((d) => !daCo.has(d.service_code));
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <span className="text-body font-semibold text-ink">Thêm nút</span>
      <select
        value={ma}
        onChange={(e) => setMa(e.target.value)}
        aria-label="Dịch vụ cho nút mới"
        className={`${O_NHAP} min-w-0 flex-1 sm:max-w-sm`}
      >
        <option value="">— Chọn dịch vụ trong bảng giá —</option>
        {chonDuoc.map((d) => (
          <option key={d.service_code} value={d.service_code}>
            {d.ten} · {tien(d.gia)}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={nhan}
        maxLength={40}
        placeholder="Chữ trên nút (vd Lấy máu)"
        aria-label="Chữ trên nút mới"
        onChange={(e) => setNhan(e.target.value)}
        className={`${O_NHAP} w-48`}
      />
      <Button
        size="lg"
        variant="primary"
        disabled={dang || !ma}
        onClick={() => {
          const ten = dl.dich_vu.find((d) => d.service_code === ma)?.ten ?? ma;
          void luu(
            ma,
            { nhan: nhan.trim() || null, bat: true, o_tiep_don: true, o_sinh_hieu: true },
            `Đã thêm nút “${nhan.trim() || ten}” — hiện ở Tiếp đón và Đo sinh hiệu.`,
          ).then(() => {
            setMa("");
            setNhan("");
          });
        }}
      >
        Thêm
      </Button>
    </div>
  );
}
