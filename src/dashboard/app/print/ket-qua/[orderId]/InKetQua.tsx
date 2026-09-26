"use client";

// Trang in phiếu kết quả. Mẫu KHÔNG có khung bệnh nhân / chữ ký — lấy từ hồ sơ.
// Lát 5 (26/09/2026): A4 theo bản mẫu (KieuInA4), in kèm ẢNH của chỉ định 4 tấm
// một hàng (video / tài liệu chỉ ghi số lượng), không cắt đôi kết luận, chữ ký.
// Chỉ định CHỈ có ảnh (chưa ai điền phiếu) vẫn in được trang ảnh.
// Ô trống in "—" (DESIGN.md §6.5). Phiếu chưa Hoàn tất vẫn in được nhưng ghi rõ
// BẢN NHÁP: giấy ra khỏi phòng khám thì không còn ai biết nó chưa được ký.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";

import KieuInA4 from "../../KieuInA4";

interface O {
  ma: string;
  ten: string;
  kieu: string;
}
interface Muc {
  ma: string;
  ten: string;
  block: O[];
  /** Mục dạng bảng (mẫu v3) — giá trị ô là {ma_cột: giá trị}. */
  cot?: { ma: string; ten: string }[];
}
interface Phieu {
  form_id: string;
  ten: string;
  khung: Muc[];
  du_lieu: Record<string, { gia_tri: unknown }>;
  ban_nhap: boolean;
  thuc_hien: string | null;
  hoan_tat_boi: string | null;
  hoan_tat_luc: string | null;
}
interface DuLieuIn {
  phong_kham: { ten: string | null; dia_chi: string | null };
  benh_nhan: {
    ho_ten: string | null;
    ma_bn: string | null;
    nam_sinh: string | number | null;
    gioi_tinh: string | null;
    dien_thoai: string | null;
    dia_chi: string | null;
  };
  dich_vu: string | null;
  bac_si_chi_dinh: string | null;
  phieu: Phieu[];
  /** Ảnh của chỉ định (lát 5) — in 4 tấm một hàng. */
  anh?: { id: string; ten: string | null }[];
  so_tep_khac?: number;
}

function chuO(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
  if (typeof v === "object") {
    const ds = Object.values(v as Record<string, unknown>).filter((x) => x !== "" && x != null);
    return ds.length ? ds.join(" · ") : "—";
  }
  return String(v);
}

/** Một ô của mục dạng BẢNG (mẫu v3): {ma_cột: giá trị}. */
function oBang(v: unknown, cot: string): string {
  if (!v || typeof v !== "object" || Array.isArray(v)) return "—";
  const x = (v as Record<string, unknown>)[cot];
  return x === "" || x == null ? "—" : String(x);
}

function ngayVn(iso: string | number | null): string {
  if (iso === null || iso === "") return "—";
  if (typeof iso === "number") return String(iso);
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? String(iso)
    : d.toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
}

const GIOI: Record<string, string> = { F: "Nữ", M: "Nam", female: "Nữ", male: "Nam" };

/** Khung bệnh nhân + dịch vụ (lấy từ hồ sơ — mẫu không có). */
function KhoiBenhNhan({ dl }: { dl: DuLieuIn }) {
  const bn = dl.benh_nhan;
  return (
    <section className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1 rounded-card border border-line p-3">
      <p>
        <b>Họ và tên:</b> {chuO(bn.ho_ten)}
      </p>
      <p>
        <b>Mã BN:</b> {chuO(bn.ma_bn)}
      </p>
      <p>
        <b>Năm sinh:</b> {ngayVn(bn.nam_sinh)}
      </p>
      <p>
        <b>Giới tính:</b> {bn.gioi_tinh ? (GIOI[bn.gioi_tinh] ?? bn.gioi_tinh) : "—"}
      </p>
      <p>
        <b>Điện thoại:</b> {chuO(bn.dien_thoai)}
      </p>
      <p>
        <b>Địa chỉ:</b> {chuO(bn.dia_chi)}
      </p>
      <p className="col-span-2">
        <b>Dịch vụ:</b> {chuO(dl.dich_vu)}
        {dl.bac_si_chi_dinh ? ` · BS chỉ định: ${dl.bac_si_chi_dinh}` : ""}
      </p>
    </section>
  );
}

/** Ảnh của chỉ định, 4 tấm một hàng; video / tài liệu chỉ đếm. */
function AnhIn({ dl }: { dl: DuLieuIn }) {
  const anh = dl.anh ?? [];
  return (
    <>
      {anh.length > 0 ? (
        <section className="mt-4">
          <h2 className="text-emph font-semibold text-ink">Hình ảnh</h2>
          <div className="mt-1 grid grid-cols-4 gap-2">
            {anh.map((a) => (
              <figure key={a.id} className="space-y-0.5">
                {/* eslint-disable-next-line @next/next/no-img-element -- ảnh đi qua cửa XÁC THỰC */}
                <img
                  src={`/api/cskh/ket-qua/${a.id}/noi-dung`}
                  alt={a.ten ?? "Ảnh kết quả"}
                  className="aspect-video w-full rounded-control border border-line object-cover"
                />
                <figcaption className="truncate text-label text-ink-muted">{a.ten}</figcaption>
              </figure>
            ))}
          </div>
        </section>
      ) : null}
      {(dl.so_tep_khac ?? 0) > 0 ? (
        <p className="mt-2 text-meta text-ink-muted">
          + {dl.so_tep_khac} video / tài liệu xem trên hệ thống
        </p>
      ) : null}
    </>
  );
}

export default function InKetQua({ orderId }: { orderId: string }) {
  const [dl, setDl] = useState<DuLieuIn | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/phieu?in=${orderId}`, { cache: "no-store" })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as (DuLieuIn & { message?: string }) | null;
        if (huy) return;
        if (!r.ok || !d) setLoi(d?.message ?? "Không đọc được phiếu kết quả.");
        else setDl(d);
      })
      .catch(() => !huy && setLoi("Mất kết nối."));
    return () => {
      huy = true;
    };
  }, [orderId]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!dl) return <p className="p-8 text-body text-ink-muted">Đang tải phiếu…</p>;
  return (
    <main className="in-a4 mx-auto max-w-3xl bg-surface p-8 text-body text-ink print:max-w-none print:p-0">
      <KieuInA4 />
      <div className="mb-6 flex gap-2 print:hidden">
        <Button type="button" variant="primary" onClick={() => window.print()}>
          In phiếu
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      {dl.phieu.length === 0 && (dl.anh?.length ?? 0) === 0 ? (
        <p className="text-ink-muted">Chỉ định này chưa có phiếu kết quả nào để in.</p>
      ) : null}
      {dl.phieu.length === 0 && (dl.anh?.length ?? 0) > 0 ? (
        <article>
          <header className="border-b border-line pb-3">
            <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
              {dl.phong_kham.ten ?? "Phòng khám"}
            </p>
            <h1 className="mt-2 text-title font-bold text-ink">Hình ảnh kết quả</h1>
          </header>
          <KhoiBenhNhan dl={dl} />
          <AnhIn dl={dl} />
        </article>
      ) : null}
      {dl.phieu.map((p, i) => (
        <article key={p.form_id} className={i > 0 ? "mt-10 break-before-page" : ""}>
          <header className="border-b border-line pb-3">
            <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
              {dl.phong_kham.ten ?? "Phòng khám"}
              {dl.phong_kham.dia_chi ? ` · ${dl.phong_kham.dia_chi}` : ""}
            </p>
            <h1 className="mt-2 text-title font-bold text-ink">{p.ten}</h1>
            {p.ban_nhap ? (
              <p className="mt-2 rounded-control border border-warning bg-warning-bg px-3 py-1 text-meta font-semibold text-warning">
                BẢN NHÁP — chưa hoàn tất, chưa phải kết quả chính thức
              </p>
            ) : null}
          </header>
          <KhoiBenhNhan dl={dl} />
          {p.khung.map((m) => (
            <section
              key={m.ma}
              className={
                m.ma === "ket_luan"
                  ? "in-giu mt-4 rounded-card border border-line p-3"
                  : "mt-4"
              }
            >
              <h2 className="text-emph font-semibold text-ink">{m.ten}</h2>
              {m.cot ? (
                <table className="mt-1 w-full border-collapse text-body">
                  <thead>
                    <tr>
                      <th className="border border-line px-2 py-1 text-left font-semibold" />
                      {m.cot.map((c) => (
                        <th key={c.ma} className="border border-line px-2 py-1 text-left font-semibold">
                          {c.ten}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {m.block.map((o) => (
                      <tr key={o.ma} className="break-inside-avoid">
                        <td className="border border-line px-2 py-1 text-ink-muted">{o.ten}</td>
                        {m.cot?.map((c) => (
                          <td key={c.ma} className="border border-line px-2 py-1 whitespace-pre-wrap">
                            {oBang(p.du_lieu[o.ma]?.gia_tri, c.ma)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
              <dl className="mt-1 space-y-1">
                {m.block.map((o) =>
                  m.block.length === 1 && o.ten === m.ten ? (
                    <dd key={o.ma} className="whitespace-pre-wrap">
                      {chuO(p.du_lieu[o.ma]?.gia_tri)}
                    </dd>
                  ) : (
                    <div key={o.ma} className="grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] gap-2">
                      <dt className="text-ink-muted">{o.ten}</dt>
                      <dd className="whitespace-pre-wrap">{chuO(p.du_lieu[o.ma]?.gia_tri)}</dd>
                    </div>
                  ),
                )}
              </dl>
              )}
            </section>
          ))}
          {i === 0 ? <AnhIn dl={dl} /> : null}
          <footer className="in-giu mt-10 flex justify-end">
            <div className="text-center">
              <p className="text-meta text-ink-muted">
                {p.hoan_tat_luc ? `Ngày ${ngayVn(p.hoan_tat_luc)}` : "Ngày …/…/……"}
              </p>
              <p className="font-semibold">Bác sĩ thực hiện</p>
              <p className="mt-12">{p.hoan_tat_boi ?? p.thuc_hien ?? ""}</p>
            </div>
          </footer>
        </article>
      ))}
    </main>
  );
}
