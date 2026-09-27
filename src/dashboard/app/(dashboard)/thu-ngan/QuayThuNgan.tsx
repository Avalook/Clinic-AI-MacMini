"use client";

// Quầy thu ngân: ai đang chờ, họ dùng gì, hết bao nhiêu, bấm một nút là xong.
//
// THAY CHO MÀN "ĐỐI SOÁT CHI PHÍ" cũ. Màn ấy dựng một quy trình đối soát đầy
// đủ — checklist trước khi đối soát, nguồn sai lệch, biên bản nguồn ngoài, nút
// "Bắt đầu đối soát" — mà phần lớn nút đều `disabled` kèm title "Chưa có API".
// Tuyền chốt 16/09: "thu ngân thì cần gì đối soát, nó là thu ngân dịch vụ
// luôn, hiện các dịch vụ khách đó khám ra và tính tiền là xong á".
//
// TIỀN DO MÁY CHỦ TÍNH (contract tiền–thuốc C3, 19/09/2026). Màn này KHÔNG tự
// cộng nữa: nó hiện `hoa_don` máy chủ dựng (số lượng × đơn giá từng dòng, tổng,
// lý do chưa thu được) và gửi lại `revision` của đúng hoá đơn ấy. Bản trước
// cộng đơn giá thuốc mà quên nhân số lượng.
//
// GIÁ TRỐNG PHẢI HIỆN RA LÀ TRỐNG, không được hiện thành 0đ. Hôm nay bảng giá
// mới có 1/39 dịch vụ và 0/80 thuốc có giá (phòng khám chưa gửi bảng giá). Một
// dòng "0đ" trông như miễn phí; một dòng "chưa có giá" trông như thiếu dữ liệu.
// Chỉ cái sau là sự thật, và chỉ cái sau khiến có người đi hỏi.

import { useCallback, useEffect, useState } from "react";

import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import NutXemLuot from "../_lam-viec/NutXemLuot";
import ChinhDonQuay from "./ChinhDonQuay";
import ChonDichVu, { type ChoKhachQuyet } from "./ChonDichVu";
import XepPhongDaThu, { type DaTraChoPhong } from "./XepPhongDaThu";
import SoLuot from "@/components/ui/SoLuot";

interface Dong {
  id: string;
  name: string;
  price: number | null;
  quantity?: string | null;
  dosage?: string | null;
}

interface DongHoaDon {
  source_id: string;
  ten: string;
  so_luong: number;
  don_vi: string | null;
  don_gia: number | null;
  thanh_tien: number | null;
  ben_thu: "CLINIC" | "EXTERNAL_PARTNER";
  van_de: string | null;
}

interface HoaDon {
  tong: number;
  revision: string;
  thu_duoc: boolean;
  van_de: string[];
  dong: DongHoaDon[];
}

interface Luot {
  visit_id: string;
  clinic_patient_id: string;
  full_name: string | null;
  patient_code: string | null;
  phone: string | null;
  so_booking?: number | null;
  so_tiep_don?: number | null;
  services: Dong[];
  drugs: Dong[];
  hoa_don?: { dich_vu?: HoaDon; thuoc?: HoaDon };
  /** Chỉ định còn chờ khách quyết làm hay không (máy chủ tính). */
  chon_dich_vu?: ChoKhachQuyet | null;
  /** Đã trả, chưa bắt đầu — xếp / đổi phòng sau khi thu (máy chủ tính). */
  xep_phong?: DaTraChoPhong[];
}

interface DaThu {
  visit_id: string;
  kind: string;
}

interface ChoXacMinh {
  payment_cycle_id: string;
  visit_id: string;
  kind: string;
  so_tien: number;
  phuong_thuc: "TRANSFER" | "QR";
  luc: string;
}

type PhuongThuc = "CASH" | "TRANSFER" | "QR";

const TEN_PT: Record<PhuongThuc, string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
  QR: "QR",
};

export type Quay = "dich_vu" | "thuoc" | "ca_hai";

const MODES: Record<Quay, string> = {
  dich_vu: "dich_vu",
  thuoc: "thuoc",
  ca_hai: "dich_vu,thuoc",
};

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

export default function QuayThuNgan({ quay }: { quay: Quay }) {
  const [ds, setDs] = useState<Luot[] | null>(null);
  const [daThu, setDaThu] = useState<DaThu[]>([]);
  const [cho, setCho] = useState<ChoXacMinh[]>([]);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dangThu, setDangThu] = useState<string | null>(null);

  const doc = useCallback(async () => {
    try {
      const r = await fetch(`/api/cashier?modes=${MODES[quay]}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as
        | { items?: Luot[]; paid?: DaThu[]; cho_xac_minh?: ChoXacMinh[]; error?: string }
        | null;
      if (!r.ok) return { loi: d?.error ?? "Không đọc được danh sách chờ thu." };
      return { items: d?.items ?? [], paid: d?.paid ?? [], cho: d?.cho_xac_minh ?? [] };
    } catch {
      return { loi: "Mất kết nối tới máy chủ." };
    }
  }, [quay]);

  const nhan = useCallback(
    (kq: { items?: Luot[]; paid?: DaThu[]; cho?: ChoXacMinh[]; loi?: string }) => {
      if (kq.loi) {
        setLoi(kq.loi);
        return;
      }
      setLoi(null);
      setDs(kq.items ?? []);
      setDaThu(kq.paid ?? []);
      setCho(kq.cho ?? []);
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

  /** Gửi một lệnh thu ngân; trả `true` nếu máy chủ nhận. Luôn tải lại sau đó. */
  const gui = useCallback(
    async (
      khoa: string,
      noiDung: Record<string, unknown>,
      xongCau: string,
      thaoTac?: string,
    ) => {
      setDangThu(khoa);
      setLoi(null);
      setXong(null);
      try {
        // Một THAO TÁC một khoá gửi lại: mất phản hồi rồi bấm lại thì mang đúng
        // khoá cũ, máy chủ trả kết quả lần đầu thay vì thu lần hai.
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (thaoTac) headers["Idempotency-Key"] = khoaThaoTac(thaoTac);
        const r = await fetch("/api/payment", {
          method: "POST",
          headers,
          body: JSON.stringify(noiDung),
        });
        if (r.ok && thaoTac) xongThaoTac(thaoTac);
        const d = (await r.json().catch(() => null)) as
          | { error?: string; message?: string; status?: string }
          | null;
        if (!r.ok) {
          setLoi(d?.message ?? d?.error ?? "Không ghi được.");
        } else {
          setXong(
            d?.status === "PENDING_VERIFICATION"
              ? "Đã ghi CHỜ XÁC MINH — chưa tính là đã thu cho tới khi nhập mã giao dịch."
              : xongCau,
          );
        }
        // Hoá đơn đổi (BILL_CHANGED) hay bị từ chối: tải lại để thấy số mới.
        await tai();
      } catch {
        setLoi("Mất kết nối — CHƯA ghi được thao tác này.");
      } finally {
        setDangThu(null);
      }
    },
    [tai],
  );

  const thu = useCallback(
    (l: Luot, kind: "dich_vu" | "thuoc", hd: HoaDon, pt: PhuongThuc) =>
      gui(
        `${l.visit_id}:${kind}`,
        {
          visitId: l.visit_id,
          clinicPatientId: l.clinic_patient_id,
          kind,
          billRevision: hd.revision,
          amount: hd.tong,
          method: pt,
        },
        `Đã thu ${tien(hd.tong)} (${TEN_PT[pt]}) của ${l.full_name ?? "khách"}.`,
        dinhDanhThaoTac("thu", l.visit_id, kind, hd.revision, pt, String(hd.tong)),
      ),
    [gui],
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
  const choCua = (visitId: string, kind: string) =>
    cho.find((p) => p.visit_id === visitId && p.kind === kind);

  const choQuyet = (l: Luot) =>
    Boolean(l.chon_dich_vu?.chi_dinh.some((c) => c.selection_status === "PENDING"));
  const conCho = ds.filter(
    (l) =>
      (quay !== "thuoc" &&
        ((l.services.length > 0 && !daThuCua(l.visit_id, "dich_vu")) || choQuyet(l))) ||
      (quay !== "dich_vu" && l.drugs.length > 0 && !daThuCua(l.visit_id, "thuoc")),
  );

  const daThuChoPhong =
    quay === "thuoc"
      ? []
      : ds.filter((l) => !conCho.includes(l) && (l.xep_phong?.length ?? 0) > 0);

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
            Khách hiện ở đây ngay khi bác sĩ chỉ định dịch vụ (tiền thuốc: sau khi
            khám xong).
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
                <p className="flex flex-wrap items-center gap-1.5 text-body font-semibold text-ink">
                  {l.full_name ?? "—"}
                  <SoLuot booking={l.so_booking} checkin={l.so_tiep_don} />
                </p>
                <p className="text-meta text-ink-muted">{l.patient_code ?? ""}</p>
              </div>
              {/* Thu xong, hệ thống tự xếp phòng (dây H4): lễ tân mở đây để
                  báo khách phòng nào, hoặc đổi sang phòng vắng hơn. */}
              <NutXemLuot visitId={l.visit_id} nhan="Xem hành trình · đổi phòng" />
            </header>

            {quay !== "thuoc" && l.chon_dich_vu ? (
              <ChonDichVu
                // Danh sách chỉ định đổi thì dựng lại ô để lấy mặc định mới. KHÔNG
                // gắn revision: mỗi lần tick là một lần lưu (revision tăng) — dựng
                // lại sẽ thu gọn ô giữa lúc lễ tân đang bỏ tick tiếp.
                key={`${l.visit_id}:${l.chon_dich_vu.chi_dinh.map((c) => c.id).join(",")}`}
                visitId={l.visit_id}
                cho={l.chon_dich_vu}
                onXong={async (cau, loiMoi) => {
                  setXong(cau);
                  setLoi(loiMoi);
                  await tai();
                }}
              />
            ) : null}

            {quay !== "thuoc" && l.services.length > 0 ? (
              <NhomThu
                tieu_de="Tiền dịch vụ"
                hd={l.hoa_don?.dich_vu}
                daThu={daThuCua(l.visit_id, "dich_vu")}
                cho={choCua(l.visit_id, "dich_vu")}
                dangThu={dangThu === `${l.visit_id}:dich_vu`}
                onThu={(hd, pt) => void thu(l, "dich_vu", hd, pt)}
                onXacMinh={(ma) =>
                  void gui(
                    `${l.visit_id}:dich_vu`,
                    {
                      action: "xac-minh",
                      // Nhắm ĐÚNG lần thu đang hiện (review CP2 #1).
                      paymentCycleId: choCua(l.visit_id, "dich_vu")?.payment_cycle_id,
                      visitId: l.visit_id,
                      kind: "dich_vu",
                      reference: ma,
                    },
                    "Đã xác minh — khoản này đã thu.",
                  )
                }
                onHuyCho={(lyDo) =>
                  void gui(
                    `${l.visit_id}:dich_vu`,
                    {
                      action: "huy-cho",
                      // Nhắm ĐÚNG lần thu đang hiện (review CP2 #1).
                      paymentCycleId: choCua(l.visit_id, "dich_vu")?.payment_cycle_id,
                      visitId: l.visit_id,
                      kind: "dich_vu",
                      reason: lyDo,
                    },
                    "Đã huỷ lần chờ xác minh.",
                  )
                }
              />
            ) : null}

            {quay !== "thuoc" ? (
              <XepPhongDaThu ds={l.xep_phong ?? []} onDoi={() => void tai()} />
            ) : null}

            {/* CHỈNH ĐƠN BÁN trước khi thu (Tuyền 24/09/2026): tích / bỏ tick,
                số lượng, lấy thêm thuốc. Thu rồi (hoặc đang chờ xác minh) thì
                khoá — huỷ phiếu thu trước rồi mới chỉnh. */}
            {quay !== "dich_vu" &&
            l.drugs.length > 0 &&
            !daThuCua(l.visit_id, "thuoc") &&
            !choCua(l.visit_id, "thuoc") ? (
              <ChinhDonQuay
                visitId={l.visit_id}
                onDoi={async (cau, loiMoi) => {
                  setXong(cau);
                  setLoi(loiMoi);
                  await tai();
                }}
              />
            ) : null}

            {quay !== "dich_vu" && l.drugs.length > 0 ? (
              <NhomThu
                tieu_de="Thuốc đã kê"
                hd={l.hoa_don?.thuoc}
                daThu={daThuCua(l.visit_id, "thuoc")}
                cho={choCua(l.visit_id, "thuoc")}
                dangThu={dangThu === `${l.visit_id}:thuoc`}
                onThu={(hd, pt) => void thu(l, "thuoc", hd, pt)}
                onXacMinh={(ma) =>
                  void gui(
                    `${l.visit_id}:thuoc`,
                    {
                      action: "xac-minh",
                      // Nhắm ĐÚNG lần thu đang hiện (review CP2 #1).
                      paymentCycleId: choCua(l.visit_id, "thuoc")?.payment_cycle_id,
                      visitId: l.visit_id,
                      kind: "thuoc",
                      reference: ma,
                    },
                    "Đã xác minh — khoản này đã thu.",
                  )
                }
                onHuyCho={(lyDo) =>
                  void gui(
                    `${l.visit_id}:thuoc`,
                    {
                      action: "huy-cho",
                      // Nhắm ĐÚNG lần thu đang hiện (review CP2 #1).
                      paymentCycleId: choCua(l.visit_id, "thuoc")?.payment_cycle_id,
                      visitId: l.visit_id,
                      kind: "thuoc",
                      reason: lyDo,
                    },
                    "Đã huỷ lần chờ xác minh.",
                  )
                }
              />
            ) : null}
          </article>
        ))
      )}

      {/* Thu đủ rồi thì lượt rời danh sách chờ thu — nhưng khách chưa vào phòng
          vẫn cần chỗ để xếp / đổi phòng (Tuyền 24/09/2026). */}
      {daThuChoPhong.length > 0 ? (
        <div className="space-y-3">
          <p className="text-body font-semibold text-ink">
            Đã thu — chờ vào phòng ({daThuChoPhong.length})
          </p>
          {daThuChoPhong.map((l) => (
            <article
              key={l.visit_id}
              className="rounded-card border border-line bg-surface shadow-card"
            >
              <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-1.5 text-body font-semibold text-ink">
                    {l.full_name ?? "—"}
                    <SoLuot booking={l.so_booking} checkin={l.so_tiep_don} />
                  </p>
                  <p className="text-meta text-ink-muted">{l.patient_code ?? ""}</p>
                </div>
                <NutXemLuot visitId={l.visit_id} nhan="Xem hành trình" />
              </header>
              <XepPhongDaThu ds={l.xep_phong ?? []} onDoi={() => void tai()} />
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function NhomThu({
  tieu_de,
  hd,
  daThu,
  cho,
  dangThu,
  onThu,
  onXacMinh,
  onHuyCho,
}: {
  tieu_de: string;
  hd: HoaDon | undefined;
  daThu: boolean;
  cho: ChoXacMinh | undefined;
  dangThu: boolean;
  onThu: (hd: HoaDon, pt: PhuongThuc) => void;
  onXacMinh: (ma: string) => void;
  onHuyCho: (lyDo: string) => void;
}) {
  const [pt, setPt] = useState<PhuongThuc>("CASH");
  const [ma, setMa] = useState("");
  const [lyDo, setLyDo] = useState("");
  if (cho) {
    // CHỜ XÁC MINH: bấm "Đã nhận tiền" là xong. Mã giao dịch TUỲ CHỌN (Tuyền
    // 24/09/2026: "không được bắt buộc điền mã mới cho thanh toán xong, open đi").
    return (
      <div className="border-b border-line px-4 py-3 last:border-b-0">
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
          {tieu_de}
        </p>
        <p className="mt-2 text-body text-warning">
          {TEN_PT[cho.phuong_thuc]} {tien(cho.so_tien)} — CHỜ XÁC MINH, chưa tính là đã thu.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            value={ma}
            onChange={(e) => setMa(e.target.value)}
            placeholder="Mã giao dịch (không bắt buộc)"
            aria-label="Mã giao dịch ngân hàng (không bắt buộc)"
            className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
          />
          <button
            type="button"
            disabled={dangThu}
            onClick={() => onXacMinh(ma.trim())}
            className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            Đã nhận tiền
          </button>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            placeholder="Lý do huỷ lần chờ (khách không chuyển…)"
            aria-label="Lý do huỷ lần chờ"
            className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
          />
          <button
            type="button"
            disabled={dangThu || lyDo.trim().length < 5}
            onClick={() => onHuyCho(lyDo.trim())}
            className="inline-flex min-h-10 items-center rounded-control border border-line bg-surface px-4 text-sm font-semibold text-ink disabled:opacity-50"
          >
            Huỷ lần chờ
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="border-b border-line px-4 py-3 last:border-b-0">
      <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
        {tieu_de}
      </p>
      {daThu ? (
        <p className="mt-2 text-meta text-ink-muted">Không còn khoản nào phải thu.</p>
      ) : !hd ? (
        <p className="mt-2 text-meta text-ink-muted">Đang tính hoá đơn…</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {hd.dong.map((d) => (
            <li key={d.source_id} className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 text-body text-ink">
                {d.ten}
                {d.so_luong !== 1 || d.don_vi ? (
                  <span className="text-ink-muted">
                    {" "}
                    × {d.so_luong.toLocaleString("vi-VN")}
                    {d.don_vi ? ` ${d.don_vi}` : ""}
                    {d.don_gia !== null ? ` × ${tien(d.don_gia)}` : ""}
                  </span>
                ) : null}
                {d.ben_thu === "EXTERNAL_PARTNER" ? (
                  <span className="text-meta text-ink-muted"> · đối tác tự thu, không cộng</span>
                ) : null}
              </span>
              <span
                className={
                  d.van_de
                    ? "shrink-0 text-meta text-warning"
                    : "shrink-0 text-body tabular-nums text-ink"
                }
              >
                {d.van_de ?? (d.thanh_tien !== null ? tien(d.thanh_tien) : "—")}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div>
          <p className="text-body font-semibold text-ink">
            Tổng: <span className="tabular-nums">{hd ? tien(hd.tong) : "—"}</span>
          </p>
          {hd && hd.van_de.length > 0 ? (
            // KHÔNG cho bấm thu khi còn dòng chưa thu được (thiếu giá, giá mâu
            // thuẫn, chưa xác định thuốc kho): máy chủ cũng từ chối y như vậy.
            <p className="text-meta text-warning">
              {hd.van_de.length} dòng chưa thu được — xem lý do từng dòng.
            </p>
          ) : null}
        </div>
        {daThu ? (
          <span className="inline-flex min-h-10 items-center rounded-control border border-success bg-success-bg px-4 text-sm font-semibold text-success">
            Đã thu
          </span>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={pt}
              onChange={(e) => setPt(e.target.value as PhuongThuc)}
              aria-label="Phương thức thanh toán"
              className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
            >
              {(Object.keys(TEN_PT) as PhuongThuc[]).map((k) => (
                <option key={k} value={k}>
                  {TEN_PT[k]}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={dangThu || !hd || !hd.thu_duoc}
              onClick={() => hd && onThu(hd, pt)}
              className="inline-flex min-h-10 items-center rounded-control border border-brand-500 bg-brand-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
            >
              {dangThu
                ? "Đang ghi…"
                : pt === "CASH"
                  ? "Đã nhận đủ tiền mặt"
                  : "Ghi chờ xác minh"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
