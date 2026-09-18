"use client";

// Quầy thu ngân: ai đang chờ, họ dùng gì, hết bao nhiêu, bấm một nút là xong.
//
// THAY CHO MÀN "ĐỐI SOÁT CHI PHÍ" cũ. Màn ấy dựng một quy trình đối soát đầy
// đủ — checklist trước khi đối soát, nguồn sai lệch, biên bản nguồn ngoài, nút
// "Bắt đầu đối soát" — mà phần lớn nút đều `disabled` kèm title "Chưa có API".
// Tuyền chốt 16/09: "thu ngân thì cần gì đối soát, nó là thu ngân dịch vụ
// luôn, hiện các dịch vụ khách đó khám ra và tính tiền là xong á".
//
// GIÁ TRỐNG PHẢI HIỆN RA LÀ TRỐNG, không được hiện thành 0đ. Hôm nay bảng giá
// mới có 1/39 dịch vụ và 0/80 thuốc có giá (phòng khám chưa gửi bảng giá). Một
// dòng "0đ" trông như miễn phí; một dòng "chưa có giá" trông như thiếu dữ liệu.
// Chỉ cái sau là sự thật, và chỉ cái sau khiến có người đi hỏi.

import { useCallback, useEffect, useState } from "react";

interface Dong {
  id: string;
  name: string;
  price: number | null;
  quantity?: string | null;
  dosage?: string | null;
}

interface Luot {
  visit_id: string;
  clinic_patient_id: string;
  full_name: string | null;
  patient_code: string | null;
  phone: string | null;
  services: Dong[];
  drugs: Dong[];
}

interface DaThu {
  visit_id: string;
  kind: string;
}

export type Quay = "dich_vu" | "thuoc" | "ca_hai";

const MODES: Record<Quay, string> = {
  dich_vu: "dich_vu",
  thuoc: "thuoc",
  ca_hai: "dich_vu,thuoc",
};

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

/** Cộng tiền một nhóm dòng. Trả về cả số dòng CHƯA có giá — xem chú thích đầu tệp. */
function congDong(ds: Dong[]): { tong: number; thieuGia: number } {
  let tong = 0;
  let thieuGia = 0;
  for (const d of ds) {
    if (d.price === null || d.price === undefined) thieuGia += 1;
    else tong += Number(d.price) || 0;
  }
  return { tong, thieuGia };
}

export default function QuayThuNgan({ quay }: { quay: Quay }) {
  const [ds, setDs] = useState<Luot[] | null>(null);
  const [daThu, setDaThu] = useState<DaThu[]>([]);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dangThu, setDangThu] = useState<string | null>(null);

  const doc = useCallback(async () => {
    try {
      const r = await fetch(`/api/cashier?modes=${MODES[quay]}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as
        | { items?: Luot[]; paid?: DaThu[]; error?: string }
        | null;
      if (!r.ok) return { loi: d?.error ?? "Không đọc được danh sách chờ thu." };
      return { items: d?.items ?? [], paid: d?.paid ?? [] };
    } catch {
      return { loi: "Mất kết nối tới máy chủ." };
    }
  }, [quay]);

  const nhan = useCallback(
    (kq: { items?: Luot[]; paid?: DaThu[]; loi?: string }) => {
      if (kq.loi) {
        setLoi(kq.loi);
        return;
      }
      setLoi(null);
      setDs(kq.items ?? []);
      setDaThu(kq.paid ?? []);
    },
    [],
  );

  const tai = useCallback(async () => nhan(await doc()), [doc, nhan]);

  useEffect(() => {
    let huy = false;
    void doc().then((kq) => {
      if (!huy) nhan(kq);
    });
    return () => {
      huy = true;
    };
  }, [doc, nhan]);

  const thu = useCallback(
    async (l: Luot, kind: "dich_vu" | "thuoc", amount: number) => {
      setDangThu(`${l.visit_id}:${kind}`);
      setLoi(null);
      setXong(null);
      try {
        const r = await fetch("/api/payment", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            visitId: l.visit_id,
            clinicPatientId: l.clinic_patient_id,
            kind,
            amount,
          }),
        });
        const d = (await r.json().catch(() => null)) as
          | { error?: string; message?: string }
          | null;
        if (!r.ok) {
          setLoi(d?.message ?? d?.error ?? "Không thu được.");
          return;
        }
        setXong(`Đã thu ${tien(amount)} của ${l.full_name ?? "khách"}.`);
        await tai();
      } catch {
        setLoi("Mất kết nối — CHƯA thu được khoản này.");
      } finally {
        setDangThu(null);
      }
    },
    [tai],
  );

  if (loi && ds === null) {
    return (
      <section className="rounded-card border border-line bg-surface p-4 shadow-card">
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      </section>
    );
  }
  if (ds === null) return <p className="text-body text-ink-muted">Đang tải…</p>;

  const daThuCua = (visitId: string, kind: string) =>
    daThu.some((p) => p.visit_id === visitId && p.kind === kind);

  const conCho = ds.filter(
    (l) =>
      (quay !== "thuoc" && l.services.length > 0 && !daThuCua(l.visit_id, "dich_vu")) ||
      (quay !== "dich_vu" && l.drugs.length > 0 && !daThuCua(l.visit_id, "thuoc")),
  );

  return (
    <section className="space-y-3">
      <p className="text-body font-semibold text-ink">
        {conCho.length} khách đang chờ thu
        {ds.length !== conCho.length ? (
          <span className="ml-2 font-normal text-meta text-ink-muted">
            ({ds.length - conCho.length} lượt đã thu xong)
          </span>
        ) : null}
      </p>

      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger"
        >
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}

      {conCho.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-6 text-center shadow-card">
          <p className="text-body text-ink">Không có ai đang chờ thu.</p>
          <p className="mt-1 text-meta text-ink-muted">
            Khách hiện ở đây sau khi bác sĩ khám xong.
          </p>
        </div>
      ) : (
        conCho.map((l) => (
          <article
            key={l.visit_id}
            className="rounded-card border border-line bg-surface shadow-card"
          >
            <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3">
              <div className="min-w-0">
                <p className="text-body font-semibold text-ink">
                  {l.full_name ?? "—"}
                </p>
                <p className="text-meta text-ink-muted">{l.patient_code ?? ""}</p>
              </div>
            </header>

            {quay !== "thuoc" && l.services.length > 0 ? (
              <NhomThu
                tieu_de="Dịch vụ đã khám"
                dong={l.services}
                daThu={daThuCua(l.visit_id, "dich_vu")}
                dangThu={dangThu === `${l.visit_id}:dich_vu`}
                onThu={(t) => thu(l, "dich_vu", t)}
              />
            ) : null}

            {quay !== "dich_vu" && l.drugs.length > 0 ? (
              <NhomThu
                tieu_de="Thuốc đã kê"
                dong={l.drugs}
                daThu={daThuCua(l.visit_id, "thuoc")}
                dangThu={dangThu === `${l.visit_id}:thuoc`}
                onThu={(t) => thu(l, "thuoc", t)}
              />
            ) : null}
          </article>
        ))
      )}
    </section>
  );
}

function NhomThu({
  tieu_de,
  dong,
  daThu,
  dangThu,
  onThu,
}: {
  tieu_de: string;
  dong: Dong[];
  daThu: boolean;
  dangThu: boolean;
  onThu: (tong: number) => void;
}) {
  const { tong, thieuGia } = congDong(dong);
  return (
    <div className="border-b border-line px-4 py-3 last:border-b-0">
      <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
        {tieu_de}
      </p>
      <ul className="mt-2 space-y-1">
        {dong.map((d) => (
          <li key={d.id} className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 text-body text-ink">
              {d.name}
              {d.quantity ? (
                <span className="text-ink-muted"> × {d.quantity}</span>
              ) : null}
            </span>
            <span
              className={
                d.price === null || d.price === undefined
                  ? "shrink-0 text-meta text-warning"
                  : "shrink-0 text-body tabular-nums text-ink"
              }
            >
              {d.price === null || d.price === undefined
                ? "chưa có giá"
                : tien(Number(d.price))}
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div>
          <p className="text-body font-semibold text-ink">
            Tổng: <span className="tabular-nums">{tien(tong)}</span>
          </p>
          {thieuGia > 0 ? (
            // KHÔNG cho bấm thu khi còn dòng chưa có giá: thu thiếu rồi ghi sổ
            // là đã thu đủ thì sai lệch ấy không còn chỗ nào lộ ra nữa.
            <p className="text-meta text-warning">
              {thieuGia} dòng chưa có giá — chưa thu được. Cần bảng giá của phòng khám.
            </p>
          ) : null}
        </div>
        {daThu ? (
          <span className="inline-flex min-h-10 items-center rounded-control border border-success bg-success-bg px-4 text-sm font-semibold text-success">
            Đã thu
          </span>
        ) : (
          <button
            type="button"
            disabled={dangThu || thieuGia > 0 || tong <= 0}
            onClick={() => onThu(tong)}
            className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {dangThu ? "Đang thu…" : "Đã nhận đủ"}
          </button>
        )}
      </div>
    </div>
  );
}
