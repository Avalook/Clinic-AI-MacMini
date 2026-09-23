"use client";

// QUYỀN THEO MÀN (Tuyền chốt 23/09/2026): "chọn vai → các màn MẶC ĐỊNH hiện ra,
// thêm/sửa/xoá thoải mái". Màn = khối lego. Bật một màn cho nhóm = thêm các khối
// công việc của màn ấy vào nhóm mẫu (máy chủ tính, `permission.manage`). Sửa nhóm
// KHÔNG đổi quyền người đã cấp — cấp lại theo nhóm ở tab "Quyền của từng người".

import { useCallback, useEffect, useState } from "react";

import Chip from "@/components/ui/Chip";

interface Man {
  ma: string;
  ten: string;
  duong: string;
  mac_dinh_cho: string;
}
interface Nhom {
  ma: string;
  ten: string;
  active: boolean;
  man_bat: string[];
}
interface DuLieu {
  man: Man[];
  man_theo_vai: { ten: string; mac_dinh_cho: string }[];
  nhom: Nhom[];
}

export default function QuyenTheoMan() {
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [chon, setChon] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dang, setDang] = useState(false);

  const doc = useCallback(async (): Promise<DuLieu | string> => {
    const r = await fetch("/api/phan-quyen?man=1", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as (DuLieu & { message?: string }) | null;
    return r.ok && d ? d : (d?.message ?? "Không đọc được quyền theo màn.");
  }, []);

  useEffect(() => {
    let huy = false;
    void doc().then((kq) => {
      if (huy) return;
      if (typeof kq === "string") setLoi(kq);
      else {
        setDl(kq);
        setChon((c) => c ?? kq.nhom.find((n) => n.active)?.ma ?? null);
      }
    });
    return () => {
      huy = true;
    };
  }, [doc]);

  const doi = async (man: Man, bat: boolean) => {
    if (!chon) return;
    setDang(true);
    setLoi(null);
    setXong(null);
    try {
      const r = await fetch("/api/phan-quyen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thao_tac: "doi-man", du_lieu: { nhom: chon, man: man.ma, bat } }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) setLoi(d?.message ?? d?.error ?? "Không lưu được.");
      else setXong(`${bat ? "Đã bật" : "Đã tắt"} màn "${man.ten}" cho nhóm này.`);
      const moi = await doc();
      if (typeof moi !== "string") setDl(moi);
    } catch {
      setLoi("Mất kết nối — CHƯA lưu.");
    } finally {
      setDang(false);
    }
  };

  if (loi && !dl) {
    return (
      <p role="alert" className="text-body text-danger">
        {loi}
      </p>
    );
  }
  if (!dl) return <p className="text-body text-ink-muted">Đang tải…</p>;
  const nhom = dl.nhom.find((n) => n.ma === chon) ?? null;

  return (
    <section className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-body text-ink" htmlFor="chon-nhom-man">
          Nhóm (vai):
        </label>
        <select
          id="chon-nhom-man"
          value={chon ?? ""}
          onChange={(e) => setChon(e.target.value)}
          className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink"
        >
          {dl.nhom.map((n) => (
            <option key={n.ma} value={n.ma}>
              {n.ten}
              {n.active ? "" : " (đã tắt)"}
            </option>
          ))}
        </select>
      </div>
      <p className="text-meta text-ink-muted">
        Sửa nhóm không đổi quyền của người đã được cấp — cấp lại theo nhóm ở tab
        “Quyền của từng người”.
      </p>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? <p className="text-meta text-success">{xong}</p> : null}
      <ul className="divide-y divide-line">
        {dl.man.map((m) => {
          const bat = Boolean(nhom?.man_bat.includes(m.ma));
          return (
            <li key={m.ma} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="min-w-0">
                <span className="text-body text-ink">{m.ten}</span>
                <span className="ml-2 text-meta text-ink-muted">
                  mặc định: {m.mac_dinh_cho}
                </span>
              </span>
              <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
                <input
                  type="checkbox"
                  className="size-4 accent-brand-600"
                  checked={bat}
                  disabled={dang || !nhom}
                  onChange={(e) => void doi(m, e.target.checked)}
                />
                {bat ? "Được vào" : "Không"}
              </label>
            </li>
          );
        })}
      </ul>
      <div>
        <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
          Màn còn đi theo vai (chưa chỉnh ở đây được)
        </p>
        <ul className="mt-1 flex flex-wrap gap-2">
          {dl.man_theo_vai.map((m) => (
            <li key={m.ten}>
              <Chip tone="neutral">
                {m.ten} — {m.mac_dinh_cho}
              </Chip>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
