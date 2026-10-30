"use client";

// Kiểm kê đầu / cuối ca ở QUẦY (G6, 14/10/2026). Đếm tồn THẬT trên kệ quầy — kể cả
// thuốc đã thu tiền mà chưa giao (vẫn nằm trên kệ). Phiếu NHÁP → CHỐT; từ 31/10 CHỐT
// là tồn cập nhật theo số đếm ngay, dòng lệch bắt lý do riêng, hoàn tác được. Mọi luật
// ở máy chủ — màn chỉ gửi lệnh và hiện câu trả lời; KHÔNG hiện sổ trước khi đếm xong
// (đếm mù cho khách quan), bấm Chốt mới hiện dòng lệch để ghi lý do. Giờ gõ từng ô
// gửi kèm số: giao thuốc sau lúc đếm không bị tính là lệch.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import type { InvBatch } from "./InventoryBoard";
import { soKho } from "./gui-kho";

type Ca = "SANG" | "CHIEU" | "TOI";
type Loai = "DAU" | "CUOI" | "DOT_XUAT";

const NHAN_CA: Record<Ca, string> = { SANG: "Ca sáng", CHIEU: "Ca chiều", TOI: "Ca tối" };
const NHAN_LOAI: Record<Loai, string> = {
  DAU: "Đầu ca",
  CUOI: "Cuối ca",
  DOT_XUAT: "Đột xuất",
};
const boDauThuoc = (s: string) =>
  s.normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/đ/gi, "d").toLowerCase();

interface DongKiem {
  drug_catalog_id: string;
  ten: string;
  ma_hang: string | null;
  don_vi: string;
  dem: number;
  ton_may: number | null;
  lech: number | null;
  giao_chua_gan_lo: number | null;
  ly_do: string | null;
  chua_ap: number | null;
  chua_ap_ly_do: string | null;
  /** Có giá trị = phiếu từ 31/10: chốt đã ghi sổ, không còn bước điều chỉnh riêng. */
  giao_da_tach: number | null;
}

/** Dòng lệch máy chủ tính trước khi chốt. */
interface DongLech {
  drug_catalog_id: string;
  don_vi: string;
  ten: string;
  dem: number;
  ton_may: number;
  giao_chua_gan_lo: number;
  lech: number;
}

interface Phieu {
  id: string;
  ngay: string;
  ca: Ca;
  loai: Loai;
  trang_thai: "NHAP" | "CHOT";
  phien_ban: number;
  phieu_truoc_id: string | null;
  phieu_sau_id: string | null;
  ly_do_sua: string | null;
  mot_phan: boolean;
  dung_so_ca_truoc: boolean;
  chot_luc: string | null;
  moc_ton_luc: string | null;
  dieu_chinh_luc: string | null;
  dieu_chinh_ly_do: string | null;
  hoan_tac_luc: string | null;
  nguoi_chot: string | null;
  nguoi_dieu_chinh: string | null;
  dong: DongKiem[];
}

interface TomTat {
  id: string;
  ca: Ca;
  loai: Loai;
  trang_thai: "NHAP" | "CHOT";
  phien_ban: number;
  phieu_truoc_id: string | null;
  phieu_sau_id: string | null;
  ly_do_sua: string | null;
  so_lech: number;
  so_chua_ap: number;
  dieu_chinh_luc: string | null;
  hoan_tac_luc: string | null;
}

interface Nhac {
  ca: Ca;
  thieu_dau_ca: boolean;
  thieu_cuoi_ca_truoc: boolean;
}

interface KetQuaDieuChinh {
  bo_qua: { ly_do: string }[];
}

type KetQua<T> = { ok: true; data: T } | { ok: false; loi: string | null };

async function goi<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<KetQua<T>> {
  try {
    const r = await fetch(url, {
      method,
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const d = (await r.json().catch(() => null)) as
      | (T & { message?: string; detail?: unknown; error?: string })
      | null;
    if (r.ok && d) return { ok: true, data: d };
    const ct = typeof d?.detail === "string" ? d.detail : null;
    const thongDiep = d?.message ?? ct ?? d?.error ?? "Máy chủ từ chối.";
    const loiKyThuat = /mã lỗi\s*[a-f\d-]+|lỗi chưa lường trước/i.test(thongDiep);
    return {
      ok: false,
      loi: loiKyThuat ? null : thongDiep,
    };
  } catch {
    return { ok: false, loi: "Mất kết nối — CHƯA lưu." };
  }
}

const homNayVn = () => new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" });
const khoaDong = (thuoc: string, dv: string) => `${thuoc}|${dv.trim().toLowerCase()}`;
const URL_GOC = "/api/pharmacy/kiem-ke-ca";

export default function KiemKeCa({
  batches,
  ghiDuoc = false,
  ngayDau,
  caDau,
  loaiCoDinh,
}: {
  batches: InvBatch[];
  /** Có quyền ghi kho — chỉ ẩn / hiện nút, máy chủ vẫn kiểm. */
  ghiDuoc?: boolean;
  /** Mở sẵn ngày / ca này (link từ báo cáo hàng hoá) thay vì hôm nay + ca hiện tại. */
  ngayDau?: string;
  caDau?: Ca;
  /** 16/10: "Kiểm đầu ca" và "Kiểm cuối ca" là hai tab riêng — tab đã chọn loại, ẩn ô Loại. */
  loaiCoDinh?: Loai;
}) {
  const [ngay, setNgay] = useState(() => ngayDau ?? homNayVn());
  const [ca, setCa] = useState<Ca>(caDau ?? "SANG");
  // Ca mở từ link được giữ cho tới khi người dùng tự đổi ngày; không thì "ca hiện
  // tại" máy chủ nhắc sẽ đè lên ca của báo cáo đang xem.
  const giuCaDau = useRef(caDau !== undefined);
  const daTuMoPhieu = useRef<string | null>(null);
  const [loai, setLoai] = useState<Loai>(loaiCoDinh ?? "CUOI");
  const [ds, setDs] = useState<TomTat[] | null>(null);
  const [phieu, setPhieu] = useState<Phieu | null>(null);
  const [nhap, setNhap] = useState<Record<string, string>>({});
  // Lúc gõ từng ô: số đếm đúng tại lúc ấy, có thể bấm lưu sau một lúc.
  const gioGo = useRef<Record<string, string>>({});
  const [lechCho, setLechCho] = useState<DongLech[] | null>(null);
  const [lyDoDong, setLyDoDong] = useState<Record<string, string>>({});
  const [timThuoc, setTimThuoc] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [lyDoSua, setLyDoSua] = useState("");
  const [ketQuaDC, setKetQuaDC] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Mã phiếu đang hỏi "Chốt kiểm kê?" (xác nhận TẠI CHỖ, không dùng hộp của trình
  // duyệt). Lưu mã phiếu để đổi / mở phiếu khác tự tắt câu hỏi, không cần effect.
  const [hoiChot, setHoiChot] = useState<string | null>(null);

  const taiDs = useCallback(async (n: string) => {
    const r = await goi<{ items: TomTat[] }>("GET", `${URL_GOC}?ngay=${n}`);
    if (r.ok) setDs(r.data.items);
  }, []);

  useEffect(() => {
    let bo = false;
    void (async () => {
      const [n, d] = await Promise.all([
        goi<Nhac>("GET", `${URL_GOC}?nhac=1&ngay=${ngay}`),
        goi<{ items: TomTat[] }>("GET", `${URL_GOC}?ngay=${ngay}`),
      ]);
      if (bo) return;
      if (n.ok) {
        if (!giuCaDau.current) setCa(n.data.ca);
      }
      if (d.ok) setDs(d.data.items);
    })();
    return () => {
      bo = true;
    };
  }, [ngay]);

  // Dòng cần đếm: mọi (thuốc, đơn vị) có lô ở QUẦY + dòng đã nằm trong phiếu.
  const dong = useMemo(() => {
    const m = new Map<string, { khoa: string; thuoc: string; ten: string; dv: string }>();
    for (const b of batches) {
      if (b.noi_chua === "KHO" || !b.drug_catalog_id) continue;
      const k = khoaDong(b.drug_catalog_id, b.unit);
      if (!m.has(k)) {
        const bien = b.drug?.variant ? ` (${b.drug.variant})` : "";
        m.set(k, {
          khoa: k,
          thuoc: b.drug_catalog_id,
          ten: `${b.drug?.name_base ?? b.drug?.name_raw ?? "—"}${bien}`,
          dv: b.unit,
        });
      }
    }
    for (const d of phieu?.dong ?? []) {
      const k = khoaDong(d.drug_catalog_id, d.don_vi);
      if (!m.has(k)) m.set(k, { khoa: k, thuoc: d.drug_catalog_id, ten: d.ten, dv: d.don_vi });
    }
    return [...m.values()].sort((a, b) => a.ten.localeCompare(b.ten, "vi"));
  }, [batches, phieu]);

  const nap = (p: Phieu) => {
    setPhieu(p);
    setNhap(
      Object.fromEntries(p.dong.map((d) => [khoaDong(d.drug_catalog_id, d.don_vi), String(d.dem)])),
    );
  };

  const docLai = async (id: string) => {
    const r = await goi<Phieu>("GET", `${URL_GOC}/${id}`);
    if (!r.ok) {
      setLoi(r.loi);
      return;
    }
    nap(r.data);
  };

  const chay = async (viec: () => Promise<void>) => {
    setDang(true);
    setLoi(null);
    await viec();
    setDang(false);
  };

  const moCu = (id: string) =>
    chay(async () => {
      setKetQuaDC(null);
      await docLai(id);
    });

  const loaiDangKiem = loaiCoDinh ?? loai;

  useEffect(() => {
    if (!ghiDuoc || ds === null) return;
    const khoa = `${ngay}:${ca}:${loaiDangKiem}`;
    if (daTuMoPhieu.current === khoa) return;
    daTuMoPhieu.current = khoa;

    void (async () => {
      setDang(true);
      setLoi(null);
      const coSan = ds.find((p) => p.ca === ca && p.loai === loaiDangKiem);
      const r = coSan
        ? await goi<Phieu>("GET", `${URL_GOC}/${coSan.id}`)
        : await goi<Phieu>("POST", URL_GOC, { ngay, ca, loai: loaiDangKiem });
      // Strict Mode có thể chạy effect hai lượt khi mount. Giữ kết quả lượt đầu
      // nếu vẫn đúng ca; bỏ kết quả cũ khi người dùng đã đổi ca / ngày.
      if (daTuMoPhieu.current !== khoa) return;
      setDang(false);
      if (!r.ok) {
        setLoi(r.loi);
        return;
      }
      nap(r.data);
      if (!coSan) void taiDs(ngay);
    })();
  }, [ca, ds, ghiDuoc, loaiDangKiem, ngay, taiDs]);

  /** Lưu nháp: gửi dòng có số + dòng đã có mà người dùng xoá trống (= bỏ dòng). */
  const luu = async (): Promise<boolean> => {
    if (!phieu) return false;
    const gui = dong
      .filter(
        (d) =>
          (nhap[d.khoa] ?? "").trim() !== "" ||
          phieu.dong.some((x) => khoaDong(x.drug_catalog_id, x.don_vi) === d.khoa),
      )
      .map((d) => ({
        drug_catalog_id: d.thuoc,
        don_vi: d.dv,
        dem: (nhap[d.khoa] ?? "").trim() || null,
        dem_luc: gioGo.current[d.khoa] ?? null,
      }));
    if (gui.length === 0) {
      setLoi("Chưa đếm thuốc nào — nhập số đếm rồi mới lưu.");
      return false;
    }
    const r = await goi<Phieu>("POST", `${URL_GOC}/${phieu.id}/dem`, { dong: gui });
    if (!r.ok) {
      setLoi(r.loi);
      return false;
    }
    nap(r.data);
    return true;
  };

  const buocPhieu = async (b: string, body: unknown = {}): Promise<Phieu | null> => {
    if (!phieu) return null;
    const r = await goi<Phieu>("POST", `${URL_GOC}/${phieu.id}/${b}`, body);
    if (!r.ok) {
      setLoi(r.loi);
      return null;
    }
    return r.data;
  };

  /** Bấm Chốt: lưu rồi xem dòng lệch; không lệch thì hỏi xác nhận như thường. */
  const batDauChot = () =>
    chay(async () => {
      if (!phieu || !(await luu())) return;
      const r = await goi<{ dong: DongLech[] }>("GET", `${URL_GOC}/${phieu.id}/xem-lech`);
      if (!r.ok) {
        setLoi(r.loi);
        return;
      }
      setLechCho(r.data.dong);
      setHoiChot(phieu.id);
    });

  const chot = () =>
    chay(async () => {
      const p = await buocPhieu("chot", {
        ly_do_dong: (lechCho ?? []).map((d) => ({
          drug_catalog_id: d.drug_catalog_id,
          don_vi: d.don_vi,
          ly_do: (lyDoDong[khoaDong(d.drug_catalog_id, d.don_vi)] ?? "").trim() || null,
        })),
      });
      if (p) {
        nap(p);
        setLechCho(null);
        setLyDoDong({});
        void taiDs(ngay);
      }
    });

  const dungSoTruoc = () =>
    chay(async () => {
      const p = await buocPhieu("dung-so-cuoi-ca-truoc");
      if (p) nap(p);
    });

  const dieuChinh = () =>
    chay(async () => {
      if (!phieu) return;
      const r = await goi<KetQuaDieuChinh>("POST", `${URL_GOC}/${phieu.id}/dieu-chinh`, {
        ly_do: lyDo.trim(),
      });
      if (!r.ok) {
        setLoi(r.loi);
        return;
      }
      const bo = r.data.bo_qua;
      setKetQuaDC(
        bo.length
          ? `Đã điều chỉnh, riêng ${bo.length} dòng chưa áp hết: ${bo.map((b) => b.ly_do).join("; ")}.`
          : "Đã điều chỉnh tồn quầy theo số đếm.",
      );
      setLyDo("");
      await docLai(phieu.id);
      void taiDs(ngay);
    });

  const hoanTac = () =>
    chay(async () => {
      if (!phieu) return;
      const r = await goi<unknown>("POST", `${URL_GOC}/${phieu.id}/hoan-tac-dieu-chinh`, {});
      if (!r.ok) {
        setLoi(r.loi);
        return;
      }
      setKetQuaDC("Đã hoàn tác điều chỉnh.");
      await docLai(phieu.id);
      void taiDs(ngay);
    });

  const suaSoDem = () =>
    chay(async () => {
      const p = await buocPhieu("sua-so-dem", { ly_do: lyDoSua.trim() });
      if (p) {
        nap(p);
        setLyDoSua("");
        void taiDs(ngay);
      }
    });

  const daChot = phieu?.trang_thai === "CHOT";
  const coLech = (phieu?.dong ?? []).some(
    (d) => d.lech !== null && d.lech !== 0 && d.giao_da_tach === null,
  );
  const hang = daChot
    ? (phieu?.dong ?? []).map((d) => ({
        khoa: khoaDong(d.drug_catalog_id, d.don_vi),
        ten: d.ten,
        dv: d.don_vi,
      }))
    : phieu?.phieu_truoc_id
      ? phieu.dong.map((d) => ({ khoa: khoaDong(d.drug_catalog_id, d.don_vi), ten: d.ten, dv: d.don_vi }))
      : dong;
  const tuKhoa = boDauThuoc(timThuoc.trim());
  // Chỉ lọc những gì đang nhìn thấy; `luu()` vẫn gửi mọi số đã nhập trong nháp.
  const hangHien = hang.filter((d) => !tuKhoa || boDauThuoc(d.ten).includes(tuKhoa));
  const soDaDem = hang.filter((d) => (nhap[d.khoa] ?? "").trim() !== "").length;

  return (
    <div className="flex flex-col gap-4">
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      <section aria-label="Ca kiểm kê" className="flex flex-wrap items-end gap-2">
        <label className="block">
          <span className="mb-1 block text-meta text-ink-soft">Ngày</span>
          <input
            type="date"
            value={ngay}
            onChange={(e) => {
              giuCaDau.current = false;
              daTuMoPhieu.current = null;
              setNgay(e.target.value || homNayVn());
              setPhieu(null);
              setDs(null);
              setLoi(null);
              setKetQuaDC(null);
            }}
            className={INPUT}
          />
        </label>
        <div
          role="group"
          aria-label="Ca và phiếu kiểm kê"
          className="w-fit min-w-[24rem] max-w-full flex-none"
        >
          <span className="mb-1 block text-meta text-ink-soft">Ca</span>
          <div className="flex min-h-11 flex-wrap items-center gap-1.5 rounded-lg border border-line bg-surface px-1.5 py-1 shadow-card">
            <select
              aria-label="Ca"
              value={ca}
              onChange={(e) => {
                giuCaDau.current = true;
                daTuMoPhieu.current = null;
                setCa(e.target.value as Ca);
                setPhieu(null);
                setLoi(null);
                setKetQuaDC(null);
              }}
              className="min-h-9 w-40 shrink-0 rounded-md border-0 bg-transparent px-2 text-sm font-medium text-ink outline-none focus:ring-2 focus:ring-brand-600/15"
            >
              {(Object.keys(NHAN_CA) as Ca[]).map((c) => (
                <option key={c} value={c}>
                  {NHAN_CA[c]}
                </option>
              ))}
            </select>
            <ul aria-label="Phiếu kiểm trong ca này" className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
              {ds === null
                ? null
                : ds.filter((p) => !loaiCoDinh || p.loai === loaiCoDinh).map((p) => (
                    <li key={p.id}>
                      <Button
                        type="button"
                        size="sm"
                        variant={phieu?.id === p.id ? "primary" : "secondary"}
                        onClick={() => {
                          daTuMoPhieu.current = `${ngay}:${p.ca}:${p.loai}`;
                          setCa(p.ca);
                          void moCu(p.id);
                        }}
                      >
                        {NHAN_CA[p.ca]} · {NHAN_LOAI[p.loai]} ·{" "}
                        {p.trang_thai === "CHOT" ? `đã chốt (${p.so_lech} lệch)` : "đang nhập — chưa chốt"}
                        {p.phien_ban > 1 ? ` · bản sửa ${p.phien_ban}` : ""}
                        {p.phieu_sau_id ? " · có bản sửa" : ""}
                        {p.so_chua_ap > 0 ? " · còn dòng chưa khớp" : ""}
                        {p.hoan_tac_luc ? " · đã hoàn tác" : ""}
                      </Button>
                    </li>
                  ))}
            </ul>
          </div>
        </div>
        {loaiCoDinh ? null : (
          <label className="block">
            <span className="mb-1 block text-meta text-ink-soft">Loại</span>
            <select value={loai} onChange={(e) => setLoai(e.target.value as Loai)} className={INPUT}>
              {(Object.keys(NHAN_LOAI) as Loai[]).map((l) => (
                <option key={l} value={l}>
                  {NHAN_LOAI[l]}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>

      {loaiCoDinh && ds?.some((p) => p.loai === "DOT_XUAT") ? (
        <details className="rounded-control border border-line bg-surface p-3">
          <summary className="cursor-pointer text-body font-medium text-ink">
            Phiếu kiểm đột xuất trong ngày
          </summary>
          <ul className="mt-2 flex flex-wrap gap-2">
            {ds.filter((p) => p.loai === "DOT_XUAT").map((p) => (
              <li key={p.id}>
                <Button
                  type="button"
                  size="sm"
                  variant={phieu?.id === p.id ? "primary" : "secondary"}
                  onClick={() => void moCu(p.id)}
                >
                  {NHAN_CA[p.ca]} · Kiểm đột xuất ·{" "}
                  {p.trang_thai === "CHOT"
                    ? `đã chốt (${p.so_lech} lệch)`
                    : "đang nhập — chưa chốt"}
                </Button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {phieu ? (
        <section
          aria-label="Phiếu kiểm kê"
          className="space-y-3 rounded-card border border-line bg-surface p-3"
        >
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-title text-ink">
              {NHAN_CA[phieu.ca]} · {NHAN_LOAI[phieu.loai]} · {phieu.ngay.split("-").reverse().join("/")}
            </h3>
            <Chip tone={daChot ? "success" : "warning"}>{daChot ? "Đã chốt" : "Nháp"}</Chip>
            {daChot && phieu.mot_phan ? <Chip tone="neutral">Kiểm một phần</Chip> : null}
            {phieu.dung_so_ca_truoc ? <Chip tone="neutral">Dùng số cuối ca trước</Chip> : null}
            {phieu.dong.some((d) => d.chua_ap) ? <Chip tone="danger">Còn dòng chưa khớp</Chip> : null}
            {phieu.dieu_chinh_luc ? (
              <Chip tone={phieu.hoan_tac_luc ? "neutral" : "success"}>
                {phieu.hoan_tac_luc ? "Đã hoàn tác" : "Tồn đã cập nhật theo số đếm"}
              </Chip>
            ) : null}
          </div>

          {!daChot && ghiDuoc ? (
            <div className="flex flex-wrap gap-2">
              {phieu.loai === "DAU" && !phieu.phieu_truoc_id ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={dang}
                  onClick={() => void dungSoTruoc()}
                >
                  Dùng số cuối ca trước
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={dang}
                onClick={() => void chay(async () => void (await luu()))}
              >
                Lưu nháp
              </Button>
              <Button
                type="button"
                size="sm"
                variant="primary"
                disabled={dang || hoiChot === phieu.id}
                onClick={() => void batDauChot()}
              >
                Chốt kiểm kê
              </Button>
            </div>
          ) : null}
          {!daChot && ghiDuoc && hoiChot === phieu.id ? (
            <XacNhanTaiCho
              cau={
                lechCho && lechCho.length > 0
                  ? `Có ${lechCho.length} dòng lệch. Ghi lý do từng dòng rồi chốt: tồn cập nhật theo số đếm ngay, hoàn tác được.`
                  : "Chốt kiểm kê? Khớp sổ, tồn không đổi."
              }
              nhanDongY="Chốt"
              dangGui={dang}
              choDongY={(lechCho ?? []).every(
                (d) => (lyDoDong[khoaDong(d.drug_catalog_id, d.don_vi)] ?? "").trim() !== "",
              )}
              onDongY={() => {
                setHoiChot(null);
                void chot();
              }}
              onThoi={() => {
                setHoiChot(null);
                setLechCho(null);
              }}
            >
              {(lechCho ?? []).length > 0 ? (
                <ul className="space-y-2">
                  {(lechCho ?? []).map((d) => {
                    const k = khoaDong(d.drug_catalog_id, d.don_vi);
                    return (
                      <li key={k} className="space-y-1">
                        <p className="text-meta text-ink">
                          <span className="font-medium">{d.ten}</span> · đếm {soKho(d.dem)} {d.don_vi}, sổ{" "}
                          {soKho(d.ton_may)}
                          {d.giao_chua_gan_lo ? `, đã giao chưa gắn lô ${soKho(d.giao_chua_gan_lo)}` : ""} · lệch{" "}
                          <span className="font-semibold text-danger">
                            {d.lech > 0 ? "+" : ""}
                            {soKho(d.lech)}
                          </span>
                        </p>
                        <input
                          value={lyDoDong[k] ?? ""}
                          maxLength={500}
                          aria-label={`Lý do lệch — ${d.ten}`}
                          placeholder="Vỡ, thất lạc, đếm nhầm…"
                          onChange={(e) => setLyDoDong({ ...lyDoDong, [k]: e.target.value })}
                          className={INPUT}
                        />
                      </li>
                    );
                  })}
                </ul>
              ) : null}
            </XacNhanTaiCho>
          ) : null}

          <div className={`${TBL_WRAP} overflow-x-auto`}>
            <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
              <label className="flex min-w-56 flex-1 items-center gap-2 text-meta text-ink-muted">
                <span className="shrink-0">Tìm thuốc</span>
                <input
                  type="search"
                  value={timThuoc}
                  onChange={(e) => setTimThuoc(e.target.value)}
                  placeholder="Gõ tên thuốc để lọc…"
                  aria-label="Tìm thuốc cần kiểm kê"
                  className={INPUT}
                />
              </label>
              <span className="text-meta text-ink-muted">Đã đếm {soDaDem} / {hang.length} mặt hàng</span>
            </div>
            <table className="w-full min-w-xl text-left text-body">
              <thead className={TBL_HEAD}>
                <tr>
                  <th className="px-3 py-2">Thuốc</th>
                  <th className="px-3 py-2">Đơn vị</th>
                  <th className="px-3 py-2 text-right">Số lượng</th>
                  {daChot ? (
                    <>
                      <th className="px-3 py-2 text-right">Sổ lúc đếm</th>
                      <th className="px-3 py-2 text-right">Lệch</th>
                      <th className="px-3 py-2 text-right">Đã giao chưa gắn lô</th>
                      <th className="px-3 py-2">Lý do</th>
                    </>
                  ) : null}
                </tr>
              </thead>
              <tbody className={TBL_DIV}>
                {hangHien.length === 0 ? (
                  <tr>
                    <td colSpan={daChot ? 7 : 3} className="px-3 py-6 text-center text-ink-muted">
                      Không tìm thấy thuốc phù hợp.
                    </td>
                  </tr>
                ) : hangHien.map((d) => {
                  const k = phieu.dong.find(
                    (x) => khoaDong(x.drug_catalog_id, x.don_vi) === d.khoa,
                  );
                  return (
                    <tr key={d.khoa}>
                      <td className="px-3 py-2 font-medium text-ink">{d.ten}</td>
                      <td className="px-3 py-2 text-ink-muted">{d.dv}</td>
                      <td className="px-3 py-2 text-right">
                        {daChot ? (
                          <span className="tabular-nums">{soKho(k?.dem)}</span>
                        ) : (
                          <input
                            value={nhap[d.khoa] ?? ""}
                            inputMode="decimal"
                            aria-label={`Số đếm — ${d.ten}`}
                            disabled={!ghiDuoc}
                            onChange={(e) => {
                              gioGo.current[d.khoa] = new Date().toISOString();
                              setNhap({ ...nhap, [d.khoa]: e.target.value });
                            }}
                            className={`${INPUT} w-24 text-right`}
                          />
                        )}
                      </td>
                      {daChot ? (
                        <>
                          <td className="px-3 py-2 text-right tabular-nums text-ink-muted">
                            {soKho(k?.ton_may)}
                          </td>
                          <td
                            className={`px-3 py-2 text-right font-semibold tabular-nums ${
                              k?.lech ? "text-danger" : "text-ink-muted"
                            }`}
                          >
                            {k?.lech ? `${k.lech > 0 ? "+" : ""}${soKho(k.lech)}` : "0"}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums text-ink-muted">
                            {k?.giao_chua_gan_lo ? soKho(k.giao_chua_gan_lo) : "—"}
                          </td>
                          <td className="px-3 py-2 text-ink-muted">
                            {k?.ly_do ?? "—"}
                            {k?.chua_ap ? (
                              <span className="block text-meta text-danger">
                                Chưa khớp {soKho(k.chua_ap)}: {k.chua_ap_ly_do}
                              </span>
                            ) : null}
                          </td>
                        </>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {daChot ? (
            <div className="space-y-2">
              <p className="text-meta text-ink-muted">
                Sổ lúc đếm là số trong sổ kho tại lúc đếm từng dòng; thuốc giao sau đó không tính là lệch.
                Chốt lúc{" "}
                {phieu.moc_ton_luc
                  ? new Date(phieu.moc_ton_luc).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })
                  : "—"}
                {phieu.nguoi_chot ? `, ${phieu.nguoi_chot}` : ""}. Thuốc đã giao mà chưa gắn lô sổ chưa trừ
                nên đã tính riêng: lệch = đếm + đã giao chưa gắn lô − sổ.
              </p>
              {ketQuaDC ? (
                <p role="status" className="text-meta text-ink">
                  {ketQuaDC}
                </p>
              ) : null}
              {phieu.dieu_chinh_luc ? (
                <p className="text-meta text-ink-muted">
                  Điều chỉnh: “{phieu.dieu_chinh_ly_do}”
                  {phieu.nguoi_dieu_chinh ? ` — ${phieu.nguoi_dieu_chinh}` : ""}.
                </p>
              ) : null}
              {phieu.ly_do_sua ? (
                <p className="text-meta text-ink-muted">
                  Bản sửa {phieu.phien_ban}: {phieu.ly_do_sua}. So với sổ của lần chốt gốc.
                </p>
              ) : null}
              {phieu.phieu_sau_id ? (
                <Button type="button" variant="secondary" disabled={dang}
                  onClick={() => void chay(() => docLai(phieu.phieu_sau_id!))}>
                  Xem bản sửa tiếp theo
                </Button>
              ) : ghiDuoc && (!phieu.dieu_chinh_luc || phieu.hoan_tac_luc) ? (
                <div className="flex flex-wrap items-end gap-2">
                  <label className="block min-w-0 flex-1">
                    <span className="mb-1 block text-meta text-ink-soft">Lý do sửa số đếm đã chốt</span>
                    <input value={lyDoSua} maxLength={1000} onChange={(e) => setLyDoSua(e.target.value)}
                      placeholder="Nhập nhầm số đếm…" className={INPUT} />
                  </label>
                  <Button type="button" variant="secondary" disabled={dang || !lyDoSua.trim()}
                    onClick={() => void suaSoDem()}>Sửa số đếm</Button>
                </div>
              ) : ghiDuoc ? (
                <p className="text-meta text-ink-muted">Muốn sửa số đếm, hoàn tác phiếu trước.</p>
              ) : null}
              {ghiDuoc && coLech && !phieu.dieu_chinh_luc && !phieu.phieu_sau_id ? (
                <div className="flex flex-wrap items-end gap-2">
                  <label className="block min-w-0 flex-1">
                    <span className="mb-1 block text-meta text-ink-soft">
                      Lý do điều chỉnh theo kiểm kê
                    </span>
                    <input
                      value={lyDo}
                      onChange={(e) => setLyDo(e.target.value)}
                      placeholder="Đếm lại cuối ca…"
                      className={INPUT}
                    />
                  </label>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={dang || !lyDo.trim()}
                    onClick={() => void dieuChinh()}
                  >
                    Điều chỉnh theo kiểm kê
                  </Button>
                </div>
              ) : null}
              {ghiDuoc && phieu.dieu_chinh_luc && !phieu.hoan_tac_luc ? (
                <Button type="button" variant="secondary" disabled={dang} onClick={() => void hoanTac()}>
                  Hoàn tác phiếu kiểm
                </Button>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
