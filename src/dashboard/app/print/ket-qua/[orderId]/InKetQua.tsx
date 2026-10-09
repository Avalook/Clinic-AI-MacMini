"use client";

// Trang in phiếu kết quả. Mẫu KHÔNG có khung bệnh nhân / chữ ký — lấy từ hồ sơ.
// Lát 5 (26/09/2026): A4 theo bản mẫu (KieuInA4), in kèm ẢNH của chỉ định 4 tấm
// một hàng (video / tài liệu chỉ ghi số lượng), không cắt đôi kết luận, chữ ký.
// Chỉ định CHỈ có ảnh (chưa ai điền phiếu) vẫn in được trang ảnh.
// Phiếu chưa Hoàn tất vẫn in được nhưng ghi rõ BẢN NHÁP: giấy ra khỏi phòng
// khám thì không còn ai biết nó chưa được ký.
//
// 27/09/2026 (Y HỆT bản mẫu `manInKq`): đầu trang HAI BÊN (phòng khám + cơ sở +
// địa chỉ | mã dịch vụ, Booking / Check-in, ngày khám); khối "Thông tin bệnh
// nhân" có người thực hiện, GIỜ làm, CHẨN ĐOÁN lâm sàng (nếu bác sĩ chính đã
// ghi) — máy chủ trả sẵn; ẨN Ô / MỤC TRỐNG (trước in "—" từng ô). Ảnh vẫn ở
// TRANG RIÊNG sau phiếu.
//
// 28/09/2026 (Tuyền: "cho kiểu hiển thị ra là 2 bên, mỗi bên có nút in/pdf
// riêng/tải ảnh video riêng … đồng bộ cho tất cả các loại được chỉ định"):
// HAI BÊN — phải: PHIẾU A4 (chọn Có ảnh / Không ảnh) + [In / tải PDF]; trái:
// ẢNH (không thông tin phiếu, chỉ một dòng nhận diện khách) + [In / tải PDF] +
// [Tải tất cả] + tải từng ảnh / video / tài liệu. Mỗi bên in độc lập. Mọi loại
// dịch vụ dùng chung trang này. Màn hẹp / nhúng (CSKH in cả lượt): xếp dọc.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { giaKemDonVi } from "@/lib/phieu-ket-qua";
import { tenPhieuKetQua } from "@/lib/phieu-kham";
import { tenMucHien } from "@/lib/sua-mau";

import { DauTrangIn, KhoiBenhNhanIn, dongSoLuot, gioIn, ngayIn } from "../../KhoiIn";
import { duongXemTep } from "../../../(dashboard)/_lam-viec/AnhKetQua";
import KieuInA4 from "../../KieuInA4";

interface O {
  ma: string;
  ten: string;
  kieu: string;
  goi_y?: string;
  /** Đơn vị (09/10/2026) — in "89.6 mm"; luật ở `giaKemDonVi`. */
  don_vi?: string;
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
  phong_kham: { ten: string | null; dia_chi: string | null; co_so?: string | null };
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
  /** Bác sĩ ký chung của chỉ định (chỉ có ảnh, không phiếu) — máy chủ chọn;
   *  luôn là bác sĩ hoặc null (29/09/2026). */
  bac_si_thuc_hien?: string | null;
  /** Đầu trang hai bên + khối bệnh nhân (27/09/2026). */
  ma_dich_vu?: string | null;
  so_booking?: number | null;
  so_tiep_don?: number | null;
  ngay_kham?: string | null;
  gio_lam?: { bat_dau: string; xong: string | null; nguoi_lam: string | null } | null;
  chan_doan?: string | null;
  phieu: Phieu[];
  /** Ảnh của chỉ định (lát 5) — in 4 tấm một hàng. */
  anh?: { id: string; ten: string | null }[];
  so_tep_khac?: number;
  /** Video / tài liệu / DICOM — không in, tải về được (28/09/2026). */
  tep_khac?: { id: string; ten: string | null; loai_tep: string }[];
}

/** Ô có giá trị để in? Rỗng / mảng rỗng / bảng không cột nào có chữ = không. */
function coGia(v: unknown): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") {
    return Object.values(v as Record<string, unknown>).some((x) => coGia(x));
  }
  return true;
}

function chuO(v: unknown, o: O): string {
  if (Array.isArray(v)) return v.join(", ");
  if (v && typeof v === "object") {
    return Object.values(v as Record<string, unknown>)
      .filter((x) => coGia(x))
      .map((x) => giaKemDonVi(x, o))
      .join(" · ");
  }
  return giaKemDonVi(v, o);
}

/** Một ô của mục dạng BẢNG (mẫu v3): {ma_cột: giá trị}. Hàng đã in mà cột
 *  này trống thì in "—" (DESIGN.md §6.5) — cả hàng trống thì đã bị bỏ. */
function oBang(v: unknown, cot: string, o: O): string {
  if (!v || typeof v !== "object" || Array.isArray(v)) return "—";
  const x = (v as Record<string, unknown>)[cot];
  return coGia(x) ? giaKemDonVi(x, o) : "—";
}

const GIOI: Record<string, string> = { F: "Nữ", M: "Nam", female: "Nữ", male: "Nam" };

/** Năm sinh: ngày sinh đủ ("1984-03-02") → chỉ lấy năm; số → giữ. */
function namSinh(v: string | number | null): string | null {
  if (v === null || v === "") return null;
  if (typeof v === "number") return String(v);
  return /^\d{4}/.exec(v)?.[0] ?? v;
}

/** Đầu trang HAI BÊN + khối BỆNH NHÂN (27/09/2026 — bản mẫu `manInKq`). */
function DauPhieuIn({ dl, p }: { dl: DuLieuIn; p: Phieu | null }) {
  const bn = dl.benh_nhan;
  const gl = dl.gio_lam;
  const gio = [gioIn(gl?.bat_dau), gioIn(gl?.xong)].filter(Boolean).join(" – ");
  // Tên BÁC SĨ thực hiện — máy chủ chọn (bác sĩ hoặc null). KHÔNG BAO GIỜ lùi
  // về người làm / người bấm / người nhập — Tuyền 29/09/2026: "mọi phiếu in ký
  // tên bác sĩ; người nhập chỉ ở lịch sử". Không có bác sĩ → để trống.
  const nguoiLam = p?.thuc_hien ?? dl.bac_si_thuc_hien ?? null;
  const gioi = bn.gioi_tinh ? (GIOI[bn.gioi_tinh] ?? bn.gioi_tinh) : null;
  return (
    <>
      <DauTrangIn
        phongKham={dl.phong_kham.ten}
        trai={[dl.phong_kham.co_so, dl.phong_kham.dia_chi]}
        tieuDe="Phiếu kết quả"
        phai={[
          dl.ma_dich_vu ? `Mã dịch vụ ${dl.ma_dich_vu}` : null,
          dongSoLuot(dl.so_booking, dl.so_tiep_don),
          ngayIn(dl.ngay_kham) ? `Ngày khám ${ngayIn(dl.ngay_kham)}` : null,
        ]}
      />
      <h2 className="mt-4 text-center text-title font-semibold uppercase text-ink">
        {p ? tenPhieuKetQua(p, dl.dich_vu) : "Hình ảnh kết quả"}
      </h2>
      {p?.ban_nhap ? (
        <p className="mt-2 rounded-control border border-warning bg-warning-bg px-3 py-1 text-meta font-semibold text-warning">
          BẢN NHÁP — chưa hoàn tất, chưa phải kết quả chính thức
        </p>
      ) : null}
      <KhoiBenhNhanIn
        tieuDe="Thông tin bệnh nhân"
        dong={[
          { nhan: "Họ và tên", gia: bn.ho_ten ? <b>{bn.ho_ten}</b> : null },
          { nhan: "Năm sinh", gia: [namSinh(bn.nam_sinh), gioi].filter(Boolean).join(" · ") },
          { nhan: "Mã khách", gia: bn.ma_bn },
          { nhan: "Điện thoại", gia: bn.dien_thoai },
          { nhan: "Địa chỉ", gia: bn.dia_chi, rong: true },
          { nhan: "Dịch vụ", gia: dl.dich_vu, rong: true },
          { nhan: "BS chỉ định", gia: dl.bac_si_chi_dinh },
          { nhan: "Người thực hiện", gia: nguoiLam },
          { nhan: "Giờ thực hiện", gia: gio || null },
          { nhan: "Chẩn đoán lâm sàng", gia: dl.chan_doan, rong: true },
        ]}
      />
    </>
  );
}

/** Ảnh của chỉ định, 2 tấm một hàng (đủ to để đọc); video / tài liệu chỉ đếm. */
function AnhIn({ dl }: { dl: DuLieuIn }) {
  const anh = dl.anh ?? [];
  return (
    <>
      {anh.length > 0 ? (
        <section className="mt-4">
          <h2 className="border-b border-line pb-1 text-emph font-bold uppercase text-ink">Hình ảnh kết quả</h2>
          <div className="luoi-anh mt-2 grid grid-cols-2 gap-3">
            {anh.map((a) => (
              <figure key={a.id} className="space-y-0.5">
                {/* eslint-disable-next-line @next/next/no-img-element -- ảnh đi qua cửa XÁC THỰC */}
                <img
                  src={`/api/cskh/ket-qua/${a.id}/noi-dung`}
                  alt={a.ten ?? "Ảnh kết quả"}
                  className="aspect-4/3 w-full rounded-control border border-line bg-surface-sunken object-contain"
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

/** Chân ký "Bác sĩ thực hiện" của một tờ phiếu, chừa chỗ ký tay. */
function ChuKyKetQua({ dl, p }: { dl: DuLieuIn; p: DuLieuIn["phieu"][number] }) {
  const hoanTat = p.hoan_tat_luc
    ? `${gioIn(p.hoan_tat_luc) ?? ""} · ${ngayIn(p.hoan_tat_luc) ?? ""}`
    : null;
  return (
    <footer className="in-giu mt-8 flex justify-end">
      <div className="min-w-48 text-center">
        {hoanTat ? <p className="text-meta text-ink-muted">Hoàn tất {hoanTat}</p> : null}
        <p className="text-ink-muted">Bác sĩ thực hiện</p>
        <p className="mt-12 font-semibold">{p.thuc_hien ?? dl.bac_si_thuc_hien ?? "\u00a0"}</p>
      </div>
    </footer>
  );
}

/** Các tờ phiếu kết quả (A4) — phần "thông tin" của chỉ định.
 *  `kyCuoiSauAnh`: có ảnh in tiếp theo → chữ ký tờ CUỐI để bên gọi đặt SAU ảnh
 *  (Tuyền 30/09/2026: chữ ký luôn ở cuối cùng). */
function CacToPhieu({ dl, kyCuoiSauAnh = false }: { dl: DuLieuIn; kyCuoiSauAnh?: boolean }) {
  return (
    <>
        {dl.phieu.map((p, i) => {
          // ẨN Ô TRỐNG (bản mẫu: "Chỉ in ô đã điền"): mục không còn ô nào có chữ
          // thì bỏ cả mục; mục bảng bỏ hàng trống. Kết luận in trong khung riêng.
          const coO = (o: O) => coGia(p.du_lieu[o.ma]?.gia_tri);
          const muc = p.khung
            .map((m) => ({ ...m, block: m.block.filter(coO) }))
            .filter((m) => m.block.length > 0);
          return (
            <article key={p.form_id} className={i > 0 ? "mt-10 break-before-page" : ""}>
              <DauPhieuIn dl={dl} p={p} />
              {muc.length === 0 ? (
                <p className="mt-4 text-ink-muted">Phiếu chưa ghi nội dung.</p>
              ) : null}
              {muc.map((m) => (
                <section
                  key={m.ma}
                  className={
                    m.ma === "ket_luan"
                      ? "in-giu mt-4 rounded-control border border-line px-3 py-2"
                      : "in-giu mt-4"
                  }
                >
                  {tenMucHien(m.ten) ? (
                    <h3 className="font-semibold text-ink">{tenMucHien(m.ten)}</h3>
                  ) : null}
                  {m.cot ? (
                    <table className="mt-1 w-full border-collapse">
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
                          <tr key={o.ma}>
                            <td className="border border-line px-2 py-1 text-ink-muted">{o.ten}</td>
                            {m.cot?.map((c) => (
                              <td key={c.ma} className="whitespace-pre-wrap border border-line px-2 py-1">
                                {oBang(p.du_lieu[o.ma]?.gia_tri, c.ma, o)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : m.block.length === 1 && m.block[0].ten === m.ten ? (
                    <p className="mt-1 whitespace-pre-wrap">{chuO(p.du_lieu[m.block[0].ma]?.gia_tri, m.block[0])}</p>
                  ) : (
                    <dl className="mt-1 grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] gap-x-3 gap-y-1">
                      {m.block.map((o) => (
                        <div key={o.ma} className="contents">
                          <dt className="text-ink-muted">{o.ten}</dt>
                          <dd className="whitespace-pre-wrap">{chuO(p.du_lieu[o.ma]?.gia_tri, o)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </section>
              ))}
              {kyCuoiSauAnh && i === dl.phieu.length - 1 ? null : <ChuKyKetQua dl={dl} p={p} />}
            </article>
          );
        })}
    </>
  );
}

/** Ảnh / video / tài liệu của chỉ định — tải về từng tệp (không in video). */
const taiVe = (id: string) => `${duongXemTep(id)}?tai=1`;

export default function InKetQua({
  orderId,
  nhung = false,
}: {
  orderId: string;
  /** Nhúng trong trang in cả lượt (CSKH): không nút, phiếu + trang ảnh. */
  nhung?: boolean;
}) {
  const [dl, setDl] = useState<DuLieuIn | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  // HAI BÊN, MỖI BÊN IN RIÊNG (Tuyền 28/09/2026): bên PHIẾU chọn có / không ảnh;
  // bên ẢNH chỉ ảnh. `inTo` = bên đang in (bên kia ẩn khi in).
  const [kemAnh, setKemAnh] = useState(true);
  const [inTo, setInTo] = useState<"phieu" | "anh" | null>(null);

  useEffect(() => {
    const ve = () => setInTo(null);
    window.addEventListener("afterprint", ve);
    return () => window.removeEventListener("afterprint", ve);
  }, []);

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
  const anh = dl.anh ?? [];
  const khac = dl.tep_khac ?? [];
  const coAnh = anh.length > 0;
  const coPhieu = dl.phieu.length > 0;

  // Nhúng (trang in cả lượt của CSKH): phiếu rồi trang ảnh, không nút.
  if (nhung) {
    return (
      <section className="in-a4">
        <KieuInA4 />
        {coPhieu ? <CacToPhieu dl={dl} kyCuoiSauAnh={coAnh} /> : <DauPhieuIn dl={dl} p={null} />}
        {coAnh ? (
          <article className={coPhieu ? "mt-10 break-before-page print:mt-0" : ""}>
            <AnhIn dl={dl} />
            {coPhieu ? <ChuKyKetQua dl={dl} p={dl.phieu[dl.phieu.length - 1]} /> : null}
          </article>
        ) : null}
      </section>
    );
  }

  const inBen = (ben: "phieu" | "anh") => {
    setInTo(ben);
    // Đợi màn vẽ lại (ẩn bên kia) rồi mới mở hộp in.
    window.setTimeout(() => window.print(), 50);
  };
  const taiHet = () => {
    // Tải lần lượt từng tệp (trình duyệt hỏi một lần cho nhiều tệp).
    [...anh.map((a) => a.id), ...khac.map((t) => t.id)].forEach((id, i) => {
      window.setTimeout(() => {
        const a = document.createElement("a");
        a.href = taiVe(id);
        a.download = "";
        document.body.appendChild(a);
        a.click();
        a.remove();
      }, i * 400);
    });
  };
  const TO =
    "rounded-card border border-line bg-surface p-6 shadow-card print:rounded-none print:border-0 print:p-0 print:shadow-none";
  const khach = [dl.benh_nhan.ho_ten, dl.benh_nhan.ma_bn, dl.dich_vu, ngayIn(dl.ngay_kham)]
    .filter(Boolean)
    .join(" · ");

  return (
    <main className="in-a4 mx-auto w-full max-w-7xl p-4 text-body text-ink sm:p-8 print:max-w-none print:p-0">
      <KieuInA4 />
      <div className="mb-4 flex justify-end print:hidden">
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-2 print:block">
        {/* ── BÊN PHẢI: PHIẾU THÔNG TIN (A4) ── */}
        <section
          aria-label="Phiếu kết quả"
          className={`${TO} lg:order-2 ${inTo === "anh" ? "print:hidden" : ""} ${inTo === null ? "print:break-after-page" : ""}`}
        >
          <div className="mb-4 flex flex-wrap items-center gap-2 print:hidden">
            <div role="group" aria-label="Ảnh trong phiếu" className="ml-auto flex gap-1">
              <Button
                type="button"
                size="sm"
                variant={kemAnh ? "primary" : "secondary"}
                aria-pressed={kemAnh}
                disabled={!coAnh}
                onClick={() => setKemAnh(true)}
              >
                Có ảnh
              </Button>
              <Button
                type="button"
                size="sm"
                variant={kemAnh ? "secondary" : "primary"}
                aria-pressed={!kemAnh}
                onClick={() => setKemAnh(false)}
              >
                Không ảnh
              </Button>
            </div>
            <Button type="button" size="sm" variant="primary" disabled={!coPhieu} onClick={() => inBen("phieu")}>
              In / tải PDF
            </Button>
          </div>
          {coPhieu ? (
            <>
              <CacToPhieu dl={dl} kyCuoiSauAnh={kemAnh && coAnh} />
              {/* In Y HỆT khung trên màn (Tuyền 28/09/2026: "in ra ở chế độ có ảnh
                  hoặc không có ảnh phải khớp form như này") — ảnh nằm ngay dưới
                  phiếu, KHÔNG ép sang trang riêng. */}
              {kemAnh && coAnh ? (
                <article className="mt-6">
                  <AnhIn dl={dl} />
                  <ChuKyKetQua dl={dl} p={dl.phieu[dl.phieu.length - 1]} />
                </article>
              ) : null}
            </>
          ) : (
            <p className="text-ink-muted">Chỉ định này chưa có phiếu kết quả — chỉ có ảnh.</p>
          )}
        </section>

        {/* ── BÊN TRÁI: ẢNH / VIDEO (không thông tin phiếu) ── */}
        <section
          aria-label="Ảnh và video"
          className={`${TO} lg:order-1 ${inTo === "phieu" ? "print:hidden" : ""}`}
        >
          <div className="mb-4 flex flex-wrap items-center gap-2 print:hidden">
            <p className="mr-auto text-label font-semibold uppercase text-ink-muted">
              Ảnh · video ({anh.length + khac.length})
            </p>
            <Button
              type="button"
              size="sm"
              disabled={anh.length + khac.length === 0}
              onClick={taiHet}
            >
              Tải tất cả
            </Button>
            <Button type="button" size="sm" variant="primary" disabled={!coAnh} onClick={() => inBen("anh")}>
              In / tải PDF
            </Button>
          </div>
          {/* Một dòng nhận diện khi in rời — không phải thông tin phiếu. */}
          <p className="mb-2 text-meta text-ink-muted">{khach}</p>
          {coAnh ? (
            <div className="grid grid-cols-2 gap-3">
              {anh.map((a) => (
                <figure key={a.id} className="in-giu space-y-1">
                  {/* eslint-disable-next-line @next/next/no-img-element -- ảnh đi qua cửa XÁC THỰC */}
                  <img
                    src={duongXemTep(a.id)}
                    alt={a.ten ?? "Ảnh kết quả"}
                    className="aspect-4/3 w-full rounded-control border border-line bg-surface-sunken object-contain"
                  />
                  <figcaption className="flex items-center justify-between gap-2 text-label text-ink-muted">
                    <span className="truncate">{a.ten}</span>
                    <a href={taiVe(a.id)} download className="shrink-0 font-medium text-brand-700 hover:underline print:hidden">
                      Tải
                    </a>
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <p className="text-ink-muted">Chỉ định này chưa có ảnh.</p>
          )}
          {khac.length > 0 ? (
            <ul className="mt-4 space-y-1 print:hidden">
              <li className="text-label font-semibold uppercase text-ink-muted">
                Video · tài liệu (tải về, không in)
              </li>
              {khac.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2 text-body">
                  <span className="truncate">
                    {t.ten ?? "(không tên)"}{" "}
                    <span className="text-meta text-ink-muted">· {t.loai_tep.toLowerCase()}</span>
                  </span>
                  <a href={taiVe(t.id)} download className="shrink-0 font-medium text-brand-700 hover:underline">
                    Tải
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </div>
    </main>
  );
}
