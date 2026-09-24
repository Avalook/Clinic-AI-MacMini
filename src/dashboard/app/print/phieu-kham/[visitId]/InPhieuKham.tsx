"use client";

// Bản in phiếu khám v5 — CHỈ ĐỌC, chữ thường thay cho ô nhập (ô nhập bị khoá in
// ra mờ và cắt chữ đoạn văn dài). Khung, nhãn, giá trị lấy nguyên từ máy chủ;
// dải hành chính + sinh hiệu và ghi chú tư vấn dùng lại ĐÚNG khối của Bàn khám
// để giấy in và màn hình không lệch nhau. Ô trống in "—" (DESIGN.md §6.5).

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import {
  NHAN_KET_QUA,
  dongTuDon,
  giaTriDoc,
  gomNhom,
  hienThi,
  type ChiDinhVaKetQua,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DongDonMayChu,
  type MucPhieu,
  type ONhap,
  type ThuThuatNguon,
} from "@/lib/phieu-kham";

import { KhoiHanhChinh, KhoiTuVan } from "../../../(dashboard)/_lam-viec/phieu-kham/KhoiDauPhieu";

interface PhieuLuot extends DinhNghiaPhieu {
  du_lieu: Record<string, ONhap>;
}

interface DuLieuIn {
  phieu: PhieuLuot;
  dau: DauPhieu | null;
  chiDinh: ChiDinhVaKetQua[];
  don: DongDonMayChu[];
  maThuThuat: Set<string>;
}

async function doc<T>(url: string): Promise<T | null> {
  const r = await fetch(url, { cache: "no-store" }).catch(() => null);
  if (!r || !r.ok) return null;
  return (await r.json().catch(() => null)) as T | null;
}

function KhoiO({ m, duLieu }: { m: MucPhieu; duLieu: Record<string, ONhap> }) {
  return (
    <>
      {gomNhom(m.block).map((n, i) => (
        <div key={`${m.ma}-${i}`} className="space-y-1">
          {n.tieu_de ? <p className="font-semibold text-ink">{n.tieu_de}</p> : null}
          {n.don_vi.map((d) =>
            d.loai === "o" ? (
              <div
                key={d.o.ma}
                className="grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] gap-2"
              >
                <dt className="text-ink-muted">{d.o.ten}</dt>
                <dd className="whitespace-pre-wrap">{giaTriDoc(d.o, duLieu[d.o.ma])}</dd>
              </div>
            ) : (
              <table key={d.bang.ma} className="w-full border-collapse text-body">
                <caption className="text-left font-semibold text-ink">{d.bang.ten}</caption>
                <thead>
                  <tr>
                    <th className="border border-line p-1 text-left" />
                    {d.bang.cot.map((c) => (
                      <th key={c} className="border border-line p-1 text-left font-semibold">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.hang.map((h) => (
                    <tr key={h.hang}>
                      <td className="border border-line p-1 text-ink-muted">{h.hang}</td>
                      {h.o.map((o, j) => (
                        <td key={o?.ma ?? j} className="border border-line p-1">
                          {o ? giaTriDoc(o, duLieu[o.ma]) : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ),
          )}
        </div>
      ))}
    </>
  );
}

function DsChiDinh({ ds }: { ds: ChiDinhVaKetQua[] }) {
  if (ds.length === 0) return <p className="text-ink-faint">—</p>;
  return (
    <ul className="list-disc space-y-1 pl-5">
      {ds.map((c) => (
        <li key={c.service_order_id}>
          {c.ten_hien_thi}
          <span className="text-ink-muted"> · {NHAN_KET_QUA[c.ket_qua_trang_thai]}</span>
        </li>
      ))}
    </ul>
  );
}

function DonThuoc({ dong }: { dong: DongDonMayChu[] }) {
  if (dong.length === 0) return <p className="text-ink-faint">—</p>;
  return (
    <table className="w-full border-collapse text-body">
      <thead>
        <tr>
          <th className="border border-line p-1 text-left font-semibold">Thuốc</th>
          <th className="border border-line p-1 text-left font-semibold">Số lượng</th>
          <th className="border border-line p-1 text-left font-semibold">Cách dùng</th>
          <th className="border border-line p-1 text-left font-semibold">Lưu ý</th>
        </tr>
      </thead>
      <tbody>
        {dong.map((r) => {
          const d = dongTuDon(r);
          return (
            <tr key={r.id}>
              <td className="border border-line p-1">{hienThi(d.ten_thuoc)}</td>
              <td className="border border-line p-1">
                {hienThi([d.so_luong, d.don_vi].filter(Boolean).join(" "))}
              </td>
              <td className="border border-line p-1">
                {hienThi([d.duong_dung, d.cach_dung].filter(Boolean).join(" — "))}
              </td>
              <td className="border border-line p-1">{hienThi(d.luu_y)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function InPhieuKham({ visitId }: { visitId: string }) {
  const [dl, setDl] = useState<DuLieuIn | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const [phieu, dau, kq, don, tc] = await Promise.all([
        doc<PhieuLuot & { form_id: string | null }>(
          `/api/phieu-kham?visit_id=${visitId}&xem=phieu`,
        ),
        doc<DauPhieu>(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`),
        doc<{ chi_dinh: ChiDinhVaKetQua[] }>(`/api/phieu-kham?visit_id=${visitId}`),
        doc<{ dong: DongDonMayChu[] }>(`/api/phieu-kham?visit_id=${visitId}&xem=don-thuoc`),
        doc<{ thu_thuat: ThuThuatNguon[] }>("/api/phieu-kham?xem=tham-chieu"),
      ]);
      if (huy) return;
      if (!phieu) {
        setLoi("Không đọc được phiếu khám của lượt này.");
        return;
      }
      if (!phieu.form_id) {
        setLoi("Lượt này chưa mở phiếu khám nào — chưa có gì để in.");
        return;
      }
      setDl({
        phieu,
        dau,
        chiDinh: kq?.chi_dinh ?? [],
        don: don?.dong ?? [],
        maThuThuat: new Set(
          (tc?.thu_thuat ?? []).flatMap((t) => (t.service_code ? [t.service_code] : [])),
        ),
      });
    })();
    return () => {
      huy = true;
    };
  }, [visitId]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!dl) return <p className="p-8 text-body text-ink-muted">Đang tải phiếu…</p>;
  const { phieu, dau } = dl;
  const cls = dl.chiDinh.filter((c) => !dl.maThuThuat.has(c.service_code));
  const thuThuat = dl.chiDinh.filter((c) => dl.maThuThuat.has(c.service_code));
  const ngayKham = dau?.hanh_chinh["encounter.date"] ?? null;

  return (
    <main className="mx-auto max-w-3xl bg-surface p-8 text-body text-ink print:max-w-none print:p-0">
      <div className="mb-6 flex gap-2 print:hidden">
        <Button type="button" variant="primary" onClick={() => window.print()}>
          In phiếu
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      <header className="border-b border-line pb-3">
        <h1 className="text-title font-bold text-ink">{phieu.ten}</h1>
      </header>
      {phieu.khung.map((m) => (
        <section key={m.ma} className="mt-4 space-y-2 break-inside-avoid-page">
          {m.ma === "HANH_CHINH" ? (
            dau ? (
              <KhoiHanhChinh dau={dau} truong={m.lien_ket?.truong ?? []} />
            ) : null
          ) : (
            <h2 className="border-b border-line pb-1 text-emph font-semibold text-ink">
              {m.ten}
            </h2>
          )}
          {m.ma === "A" && dau ? <KhoiTuVan dau={dau} /> : null}
          {m.lien_ket?.loai === "chi_dinh_cls" ? <DsChiDinh ds={cls} /> : null}
          {m.lien_ket?.loai === "chi_dinh_thu_thuat" ? <DsChiDinh ds={thuThuat} /> : null}
          {m.lien_ket?.loai === "don_thuoc" ? <DonThuoc dong={dl.don} /> : null}
          <dl className="space-y-1">
            <KhoiO m={m} duLieu={phieu.du_lieu} />
          </dl>
        </section>
      ))}
      <footer className="mt-10 flex justify-end">
        <div className="text-center">
          <p className="text-meta text-ink-muted">
            {ngayKham ? `Ngày khám ${hienThi(ngayKham)}` : "Ngày …/…/……"}
          </p>
          <p className="font-semibold">Bác sĩ khám</p>
          <p className="mt-12">&nbsp;</p>
        </div>
      </footer>
    </main>
  );
}
