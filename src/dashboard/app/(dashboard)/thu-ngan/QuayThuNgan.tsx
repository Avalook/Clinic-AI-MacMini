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
import NutCheckOut from "../_lam-viec/NutCheckOut";
import ChinhDonQuay from "./ChinhDonQuay";
import ChonDichVu, { type ChoKhachQuyet } from "./ChonDichVu";
import XepPhongDaThu, { type DaTraChoPhong } from "./XepPhongDaThu";
import ChonDichVuKham from "../_lam-viec/ChonDichVuKham";
import PhuThuKem from "./PhuThuKem";
import { useNgheBang } from "../dung-nghe-bang";
import HoaDonMot, { type LenhThuMot, type QuayThu } from "./HoaDonMot";
import Chip from "@/components/ui/Chip";
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

interface DongDoiTac extends DongHoaDon {
  /** Đối tác đã ghi nhận thu tiền khách (bàn đối tác) — null = chưa. */
  doi_tac_da_thu?: { so_tien: number; hinh_thuc: string; luc: string } | null;
}

interface HoaDon {
  tong: number;
  revision: string;
  thu_duoc: boolean;
  van_de: string[];
  dong: DongHoaDon[];
  /** Khách trả TRỰC TIẾP cho đối tác (27/09/2026): hiện, không cộng. */
  dong_doi_tac?: DongDoiTac[];
  /** Phòng khám không còn khoản nào — chỉ còn dịch vụ khách trả đối tác. */
  chi_doi_tac_thu?: boolean;
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
  /** Quầy một hoá đơn (27/09): hoá đơn dịch vụ dựng sẵn ở máy chủ. */
  quay_thu?: QuayThu | null;
  loai_kham?: string | null;
  bac_si?: string | null;
  cho_tu?: string | null;
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
  const [phuThuDangLuu, setPhuThuDangLuu] = useState<Set<string>>(() => new Set());
  const [chonVisit, setChonVisit] = useState<string | null>(null);
  // Lượt vừa thu xong — để mời Check-out ngay dưới câu "Đã thu…" (27/09/2026,
  // đợt 3). Nút tự ẩn nếu tài khoản không có quyền đóng lượt.
  // Gắn với ĐÚNG câu báo của lần thu ấy (`cau`): câu báo đổi sang việc khác
  // (chốt dịch vụ, chỉnh đơn…) thì nút tự ẩn, không treo dưới câu của người khác.
  const [vuaThu, setVuaThu] = useState<{
    visitId: string;
    ten: string | null;
    cau: string;
  } | null>(null);

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

  // NGHE SỰ KIỆN (28/09/2026): trước đây quầy nạp MỘT lần khi mở. Hệ thống tự
  // xếp phòng (dây H4) ngay sau khi thu — màn vẫn hiện "chưa xếp phòng" với số
  // phiên bản cũ, bấm "Xếp phòng" thì bị báo "vừa được điều phối bởi người khác".
  useNgheBang(
    ["service_order", "visit", "queue_entry", "payment", "payment_cycle", "prescription"],
    () => void tai(),
  );

  useEffect(() => {
    let huy = false;
    void doc().then((kq) => {
      if (!huy) nhan(kq);
    });
    return () => {
      huy = true;
    };
  }, [doc, nhan]);

  /** Gửi một lệnh thu ngân; trả `true` nếu máy chủ nhận VÀ tiền đã tính là thu
   *  (không phải "chờ xác minh"). Luôn tải lại sau đó. */
  const gui = useCallback(
    async (
      khoa: string,
      noiDung: Record<string, unknown>,
      xongCau: string,
      thaoTac?: string,
    ): Promise<boolean> => {
      setDangThu(khoa);
      setLoi(null);
      setXong(null);
      setVuaThu(null);
      let daThuThat = false;
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
          daThuThat = d?.status !== "PENDING_VERIFICATION";
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
      return daThuThat;
    },
    [tai],
  );

  const thu = useCallback(
    async (l: Luot, kind: "dich_vu" | "thuoc", hd: HoaDon, pt: PhuongThuc) => {
      const cau = `Đã thu ${tien(hd.tong)} (${TEN_PT[pt]}) của ${l.full_name ?? "khách"}.`;
      const ok = await gui(
        `${l.visit_id}:${kind}`,
        {
          visitId: l.visit_id,
          clinicPatientId: l.clinic_patient_id,
          kind,
          billRevision: hd.revision,
          amount: hd.tong,
          method: pt,
        },
        cau,
        dinhDanhThaoTac("thu", l.visit_id, kind, hd.revision, pt, String(hd.tong)),
      );
      if (ok) setVuaThu({ visitId: l.visit_id, ten: l.full_name, cau });
    },
    [gui],
  );

  /** Thu một lệnh: máy chủ chốt lựa chọn dịch vụ + ghi sổ (quầy một hoá đơn). */
  const thuMot = useCallback(
    async (l: Luot, p: LenhThuMot) => {
      const cau =
        p.amount === undefined
          ? `Đã chốt dịch vụ của ${l.full_name ?? "khách"} (không có khoản thu tại quầy).`
          : `Đã thu ${tien(p.tong)} (${TEN_PT[p.method]}) của ${l.full_name ?? "khách"}.`;
      const ok = await gui(
        `${l.visit_id}:dich_vu`,
        {
          visitId: l.visit_id,
          clinicPatientId: l.clinic_patient_id,
          kind: "dich_vu",
          billRevision: p.billRevision,
          amount: p.amount,
          method: p.method,
          chon: p.chon,
        },
        cau,
        dinhDanhThaoTac(l.visit_id, p.khoa),
      );
      if (ok) setVuaThu({ visitId: l.visit_id, ten: l.full_name, cau });
    },
    [gui],
  );

  /** V10 LÀM TRƯỚC, THU SAU (Tuyền 30/09/2026): chốt dịch vụ khách làm, KHÔNG
   *  thu — máy chủ xếp phòng ngay (dây H4), khách đi làm, cuối buổi quay lại
   *  quầy thu. Cùng lệnh xác nhận lựa chọn của ô "Khách chọn dịch vụ". */
  const chotThuSau = useCallback(
    async (l: Luot, chon: NonNullable<LenhThuMot["chon"]>) => {
      const khoa = `${l.visit_id}:dich_vu`;
      const thaoTac = dinhDanhThaoTac(
        "chon-dich-vu",
        l.visit_id,
        String(chon.expected_selection_revision),
        chon.selected_order_ids.join(","),
      );
      setDangThu(khoa);
      setLoi(null);
      setXong(null);
      setVuaThu(null);
      try {
        const r = await fetch("/api/luot-kham", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": khoaThaoTac(thaoTac) },
          body: JSON.stringify({ thao_tac: "chon-dich-vu", id: l.visit_id, du_lieu: chon }),
        });
        const d = (await r.json().catch(() => null)) as { error?: string; message?: string } | null;
        if (r.ok) {
          xongThaoTac(thaoTac);
          setXong(
            `Đã chốt dịch vụ của ${l.full_name ?? "khách"} — khách đi làm trước, thu tiền sau (còn nợ ở quầy).`,
          );
        } else {
          setLoi(d?.message ?? d?.error ?? "Không chốt được dịch vụ.");
        }
        await tai();
      } catch {
        setLoi("Mất kết nối — CHƯA chốt được dịch vụ.");
      } finally {
        setDangThu(null);
      }
    },
    [tai],
  );

  /** "Đã nhận tiền" của lần chờ xác minh — cũng là lúc tiền đã đủ. */
  const xacMinh = useCallback(
    async (l: Luot, kind: "dich_vu" | "thuoc", ma: string) => {
      const cau = `Đã xác minh — khoản này đã thu (${l.full_name ?? "khách"}).`;
      const ok = await gui(
        `${l.visit_id}:${kind}`,
        {
          action: "xac-minh",
          // Nhắm ĐÚNG lần thu đang hiện (review CP2 #1).
          paymentCycleId: cho.find((p) => p.visit_id === l.visit_id && p.kind === kind)
            ?.payment_cycle_id,
          visitId: l.visit_id,
          kind,
          reference: ma,
        },
        cau,
      );
      if (ok) setVuaThu({ visitId: l.visit_id, ten: l.full_name, cau });
    },
    [gui, cho],
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

  const dangXem = conCho.find((l) => l.visit_id === chonVisit) ?? conCho[0] ?? null;

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
        <div className="space-y-2 rounded-control border border-success bg-success-bg px-3 py-2">
          <p className="text-meta text-success">{xong}</p>
          {/* SAU "ĐÃ NHẬN ĐỦ" (27/09/2026, đợt 3): khách thường về ngay sau
              quầy thu — mời check-out tại chỗ thay vì phải nhớ mở màn Check-out.
              CHỈ tài khoản có quyền đóng lượt thấy nút (NutCheckOut tự ẩn). */}
          {vuaThu && vuaThu.cau === xong ? (
            <NutCheckOut
              key={vuaThu.visitId}
              visitId={vuaThu.visitId}
              ten={vuaThu.ten}
              onXong={() => void tai()}
            />
          ) : null}
        </div>
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
        <div className="grid items-start gap-3 lg:grid-cols-[minmax(260px,340px)_minmax(0,1fr)]">
          <ul
            aria-label="Khách chờ thu"
            className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
          >
            {conCho.map((l) => {
              const on = l.visit_id === dangXem?.visit_id;
              const soTien = l.quay_thu?.tong ?? l.hoa_don?.dich_vu?.tong ?? l.hoa_don?.thuoc?.tong ?? null;
              return (
                <li key={l.visit_id} className="border-b border-line last:border-b-0">
                  <button
                    type="button"
                    aria-current={on ? "true" : undefined}
                    onClick={() => setChonVisit(l.visit_id)}
                    className={`flex w-full items-center gap-2.5 border-l-3 px-2.5 py-2.5 text-left ${
                      on ? "border-l-brand-500 bg-surface-selected" : "border-l-transparent hover:bg-surface-sunken"
                    }`}
                  >
                    <SoLuot dang="tron" checkin={l.so_tiep_don} booking={l.so_booking} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-emph font-semibold text-ink">{l.full_name ?? "—"}</span>
                      <span className="block truncate text-meta text-ink-muted">
                        {[l.loai_kham, l.bac_si].filter(Boolean).join(" · ") || (l.patient_code ?? "")}
                      </span>
                    </span>
                    {soTien != null ? (
                      <span className="shrink-0 text-body font-semibold tabular-nums text-ink">{tien(soTien)}</span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        {(dangXem ? [dangXem] : []).map((l) => (
          <article
            key={l.visit_id}
            className="min-w-0 rounded-card border border-line bg-surface shadow-card"
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

            {/* Tick dịch vụ khám ngay tại quầy khi người khám chưa tick (28/09/2026)
                — máy chủ khoá khi tiền khám đã thu; tự ẩn với lượt đi thẳng phòng. */}
            {quay !== "thuoc" && !daThuCua(l.visit_id, "dich_vu") ? (
              <ChonDichVuKham visitId={l.visit_id} onDoi={() => void tai()} />
            ) : null}
            {/* Món kèm dịch vụ (đầu dò…) — tick + sửa giá, vào hoá đơn dịch vụ
                (28/09/2026). Tự ẩn khi lượt không có dịch vụ nào có món kèm. */}
            {quay !== "thuoc" && !daThuCua(l.visit_id, "dich_vu") ? (
              <PhuThuKem
                visitId={l.visit_id}
                reloadToken={l.quay_thu?.revision}
                onDoi={tai}
                onDangLuu={(dang) =>
                  setPhuThuDangLuu((cu) => {
                    const moi = new Set(cu);
                    if (dang) moi.add(l.visit_id);
                    else moi.delete(l.visit_id);
                    return moi;
                  })
                }
              />
            ) : null}
            {quay !== "thuoc" &&
            l.quay_thu &&
            !daThuCua(l.visit_id, "dich_vu") &&
            !choCua(l.visit_id, "dich_vu") ? (
              <HoaDonMot
                key={`${l.visit_id}:${l.quay_thu.lua_chon.order_ids_seen.join(",")}:${l.quay_thu.lua_chon.revision}`}
                qt={l.quay_thu}
                dangThu={dangThu === `${l.visit_id}:dich_vu`}
                dangLuuPhuThu={phuThuDangLuu.has(l.visit_id)}
                onThu={(p) => void thuMot(l, p)}
                onChotThuSau={(c) => void chotThuSau(l, c)}
                onDoiPhong={() => void tai()}
              />
            ) : (
            <>
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
                onXacMinh={(ma) => void xacMinh(l, "dich_vu", ma)}
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
            </>
            )}

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
                onXacMinh={(ma) => void xacMinh(l, "thuoc", ma)}
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
        ))}
        </div>
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
      {hd?.chi_doi_tac_thu ? (
        <p className="mt-2 text-meta text-ink-muted">
          Phòng khám không còn khoản nào — dịch vụ dưới đây là thu hộ đối tác.
        </p>
      ) : daThu ? (
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

      {hd && (hd.dong_doi_tac?.length ?? 0) > 0 ? (
        <DongDoiTacThu ds={hd.dong_doi_tac ?? []} />
      ) : null}

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
        {daThu || hd?.chi_doi_tac_thu ? (
          <span className="inline-flex min-h-10 items-center rounded-control border border-success bg-success-bg px-4 text-sm font-semibold text-success">
            {hd?.chi_doi_tac_thu ? "Không còn khoản thu" : "Đã thu"}
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

/** Dịch vụ khách trả TRỰC TIẾP cho đối tác (Tuyền chốt 27/09/2026): hiện giá
 *  tham khảo + đối tác đã thu hay chưa. Không cộng vào tổng — máy chủ đã tách
 *  (`dong_doi_tac`), màn chỉ đọc. */
function DongDoiTacThu({ ds }: { ds: DongDoiTac[] }) {
  return (
    <div className="mt-2 rounded-control bg-surface-muted px-3 py-2">
      <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
        Thu hộ đối tác — không cộng
      </p>
      <ul className="mt-1 space-y-1">
        {ds.map((d) => (
          <li key={d.source_id} className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="min-w-0 text-body text-ink">
              {d.ten}
              <span className="ml-2">
                {d.doi_tac_da_thu ? (
                  <Chip tone="success">Đã thu hộ cho đối tác {tien(d.doi_tac_da_thu.so_tien)}</Chip>
                ) : (
                  <Chip tone="neutral">Chưa thu hộ cho đối tác</Chip>
                )}
              </span>
            </span>
            <span className="shrink-0 text-meta tabular-nums text-ink-muted">
              {d.thanh_tien !== null ? `tham khảo ${tien(d.thanh_tien)}` : "chưa có giá"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
