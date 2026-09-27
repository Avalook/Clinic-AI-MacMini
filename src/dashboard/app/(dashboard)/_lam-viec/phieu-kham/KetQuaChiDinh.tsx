"use client";

// Mục C — "ĐÃ CHỈ ĐỊNH & KẾT QUẢ" theo từng chỉ định của lượt.
//
// Y HỆT bản giao diện mẫu (Tuyền chốt 27/09/2026; M/app.js `dongChiDinh`,
// `tomTatKq`, `noiDungKq`, `dsChiDinh`): mỗi chỉ định một thẻ — tên + mã SP,
// "Trên phiếu giấy: …", chip trạng thái MỘT trục (Chờ thu tiền → Đã thu — chờ làm
// → Đang làm → Có kết quả) + chip mẫu + giá. Có kết quả thì TÓM TẮT LUÔN HIỆN (2
// cột, bỏ ô rỗng, ≤14 dòng), hộp KẾT LUẬN, ⤢ ở góc mở hộp chia đôi, khối "ẢNH ·
// VIDEO". Gom theo lần chỉ định (lần mới nhất ở trên). Bản mẫu gọi là "Lượt n" —
// hệ thống thật dùng "Lần n" vì "lượt" ở đây là lượt khám (check-in → check-out).
//
// Gắn bằng `service_order_id` (máy chủ đã nối). Tên dịch vụ chỉ để đọc. Nháp kết
// quả không hiện nội dung — chưa ai chịu trách nhiệm về chữ trong đó.
//
// ĐÃ XEM: tóm tắt tự hiện ⇒ mở khối 2 là XEM (bản mẫu tự đánh dấu khi mở khối 2).
// Màn gọi máy chủ ghi một lần cho mỗi kết quả chưa xem; máy chủ tự quyết vai nào
// được tính (bác sĩ / thư ký / BS siêu âm).
//
// BÁC SĨ ĐIỀN KẾT QUẢ NGAY ĐÂY (Tuyền 23/09/2026): [Mở phiếu kết quả] mở đúng
// phiếu của chỉ định (cùng engine như phòng dịch vụ).
//
// XEM LẠI LẦN CŨ (bản mẫu `nutLuotMoi` · `.chip-luot` · `data-act="xem-luot"`, làm
// 27/09/2026 — mục 13): lượt có từ hai lần chỉ định trở lên thì hiện hàng chip
// "Lần 1 · Lần 2 …". Mặc định là LẦN HIỆN TẠI (mới nhất); bấm lần cũ = chỉ hiện
// chỉ định của lần đó, CHỈ XEM (không mở phiếu kết quả để sửa, không tải tệp) +
// dải "Đang xem lần k — [Về lần n (đang mở)]". Lần cũ có kết quả chưa xem thì chip
// có chấm nhắc. "Đã xem" chỉ ghi cho chỉ định đang HIỆN.

import { useEffect, useRef, useState } from "react";

import KhungTep from "../KhungTep";
import AnhKetQua, { tepXem } from "../AnhKetQua";
import PhieuKetQua from "../PhieuKetQua";
import Button, { buttonClass } from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import Lightbox from "@/components/ui/Lightbox";
import { fmtTime } from "@/lib/datetime";
import {
  NHAN_DOI_TAC,
  NHAN_KET_QUA,
  dongKetQua,
  tienVn,
  type ChiDinhVaKetQua,
  type MauKetQuaNgan,
} from "@/lib/phieu-kham";

/** Tệp kết quả của một chỉ định → mục xem (ảnh / video / tài liệu). */
function tepCua(d: ChiDinhVaKetQua) {
  // Thứ tự CHỤP (cũ trước) — máy chủ trả mới nhất trước cho danh sách kết quả.
  return d.ket_qua
    .filter((k) => k.loai === "TEP" && k.tep_id)
    .sort((a, b) => (a.tai_len_luc ?? "").localeCompare(b.tai_len_luc ?? ""))
    .map((k) =>
      tepXem({
        id: k.tep_id!,
        ten: k.ten,
        loai_tep: k.loai_tep ?? "",
        phu: k.tai_len_luc ? fmtTime(k.tai_len_luc) : undefined,
      }),
    );
}

function ghiDaXem(orderId: string) {
  // Chỉ để máy chủ ghi "đã xem"; nội dung đã có sẵn ở đây. Hỏng thì thôi.
  void fetch(`/api/phieu?xem=${orderId}`, { cache: "no-store" }).catch(() => undefined);
}

/** Trục trạng thái MỘT chiều của bản mẫu (`TT`). */
function trangThai(d: ChiDinhVaKetQua): { nhan: string; tone: ChipTone } {
  if (d.ket_qua_trang_thai === "CO_KET_QUA") return { nhan: "Có kết quả", tone: "success" };
  const th = (d.thuc_hien ?? "").toUpperCase();
  if (th === "COMPLETED" || th === "PERFORMED") {
    // Đối tác: làm xong phần phòng khám (lấy mẫu) nhưng kết quả chưa về.
    return d.doi_tac ? { nhan: NHAN_DOI_TAC[d.doi_tac], tone: "run" } : { nhan: "Đã làm", tone: "success" };
  }
  if (d.ket_qua_trang_thai === "DANG_NHAP" || th === "IN_PROGRESS") {
    return { nhan: d.doi_tac ? "Đã gửi đối tác" : "Đang làm", tone: "run" };
  }
  if (d.da_thu) {
    return d.doi_tac ? { nhan: NHAN_DOI_TAC[d.doi_tac], tone: "info" } : { nhan: "Đã thu — chờ làm", tone: "info" };
  }
  return { nhan: "Chờ thu tiền", tone: "warning" };
}

/** Chip mẫu kết quả (`badgeMau`): mẫu PDF · tự do · đối tác · N mẫu. */
function chipMau(d: ChiDinhVaKetQua): { nhan: string; tone: ChipTone } | null {
  if (d.doi_tac) return { nhan: "đối tác · nhập nhanh", tone: "info" };
  const m = d.mau_ket_qua ?? [];
  if (m.length === 0) return null;
  if (m.length > 1) return { nhan: `${m.length} mẫu`, tone: "brand" };
  return m[0].ma === "CHUNG" ? { nhan: "tự do", tone: "neutral" } : { nhan: "mẫu PDF", tone: "brand" };
}

function HopKetLuan({ chu }: { chu: string }) {
  return (
    <div className="mt-2 rounded-control bg-brand-50 px-3 py-2">
      <span className="block text-label font-semibold uppercase tracking-wide text-ink-muted">Kết luận</span>
      <div className="whitespace-pre-wrap text-body text-ink">{chu}</div>
    </div>
  );
}

/** Tóm tắt kết quả (≤ `gioiHan` dòng; 0 = đủ hết, dùng trong hộp xem). */
function NoiDungKetQua({ d, gioiHan }: { d: ChiDinhVaKetQua; gioiHan: number }) {
  const phieu = d.ket_qua.filter((k) => k.loai === "PHIEU" && k.trang_thai === "READY" && k.khung);
  if (phieu.length === 0) {
    return <p className="text-body text-ink-faint">Phòng chưa ghi phiếu — kết quả là tệp bên dưới.</p>;
  }
  return (
    <div className="space-y-3">
      {phieu.map((k) => {
        const { dong, ketLuan } = dongKetQua(k);
        const n = gioiHan || dong.length;
        return (
          <div key={k.phieu_id}>
            <p className={phieu.length > 1 ? "mb-2 text-emph font-semibold text-ink" : "mb-1.5 text-meta text-ink-muted"}>
              {k.ten}
              {k.ban_thu && k.ban_thu > 1 ? ` · bản ${k.ban_thu}` : ""}
            </p>
            <dl className={`grid gap-x-6 gap-y-1 ${gioiHan ? "sm:grid-cols-2" : ""}`}>
              {dong.slice(0, n).map((x, i) => (
                <div key={`${x.nhan}-${i}`} className="flex gap-2 py-0.5">
                  <dt className="max-w-[55%] shrink-0 text-ink-muted">{x.nhan}</dt>
                  <dd className="whitespace-pre-wrap font-medium text-ink">{x.gia}</dd>
                </div>
              ))}
            </dl>
            {dong.length > n ? (
              <p className="text-meta text-ink-muted">+ {dong.length - n} dòng nữa — bấm ⤢ để xem đủ</p>
            ) : null}
            {ketLuan ? <HopKetLuan chu={ketLuan} /> : null}
          </div>
        );
      })}
    </div>
  );
}

export default function KetQuaChiDinh({
  ds,
  mauDuPhong = [],
  goiYMau = {},
  choDien = false,
  clinicPatientId,
  onDoi,
  nhanGiay = {},
  onDoiBatBuoc,
}: {
  ds: ChiDinhVaKetQua[];
  /** Bật / tắt "Bắt buộc" của chỉ định CHƯA thu tiền (25/09/2026; 27/09 chuyển
   *  từ hộp tóm tắt ở đầu danh mục vào đây). Không truyền = chỉ xem chip. */
  onDoiBatBuoc?: (
    orderId: string,
    batBuoc: boolean,
  ) => Promise<{ ok: true } | { ok: false; loi: string }>;
  /** 18 mẫu kết quả đang bật — khi dịch vụ chưa gắn mẫu nào. */
  mauDuPhong?: MauKetQuaNgan[];
  /** service_code → mã mẫu gợi ý từ phiếu v5 (không kèm `KQ_`). */
  goiYMau?: Record<string, string>;
  /** Người đang mở có quyền điền kết quả (máy chủ vẫn kiểm lại). */
  choDien?: boolean;
  /** Có thì mở được khung ảnh / video / tệp kết quả của từng chỉ định. */
  clinicPatientId?: string;
  onDoi?: () => void;
  /** service_code → nhãn trên phiếu chỉ định giấy ("SÂ 2D TC-BT"). */
  nhanGiay?: Record<string, string>;
}) {
  const [dien, setDien] = useState<string | null>(null);
  const [tep, setTep] = useState<string | null>(null);
  // Hộp xem CHIA ĐÔI: kết quả trái, ảnh phải — mở từ ảnh nhỏ hoặc ⤢.
  const [hop, setHop] = useState<{ id: string; i: number; luoi: boolean } | null>(null);
  const [loiBatBuoc, setLoiBatBuoc] = useState<{ id: string; loi: string } | null>(null);
  const doiBatBuoc = async (d: ChiDinhVaKetQua, co: boolean) => {
    if (!onDoiBatBuoc) return;
    setLoiBatBuoc(null);
    const kq = await onDoiBatBuoc(d.service_order_id, co);
    if (!kq.ok) setLoiBatBuoc({ id: d.service_order_id, loi: kq.loi });
  };
  /** Lần đang xem; null = lần hiện tại (mới nhất). */
  const [xemLan, setXemLan] = useState<number | null>(null);
  const daGhi = useRef(new Set<string>());

  // Các lần — lần mới nhất lên đầu; chỉ định mang sang (lần 0) để cuối.
  const cacLan = [...new Set(ds.map((d) => d.lan ?? 0))].sort((a, b) => (b || -1) - (a || -1));
  const nhieuLan = cacLan.length > 1;
  const lanHienTai = cacLan.find((l) => l > 0) ?? cacLan[0] ?? 0;
  const lanXem = xemLan !== null && cacLan.includes(xemLan) ? xemLan : lanHienTai;
  const chiXem = nhieuLan && lanXem !== lanHienTai;
  const dsHien = nhieuLan ? ds.filter((d) => (d.lan ?? 0) === lanXem) : ds;
  const choSua = choDien && !chiXem;

  // Tóm tắt luôn hiện ⇒ khối 2 mở ra là đã xem: ghi MỘT lần mỗi kết quả chưa xem
  // — chỉ những chỉ định đang HIỆN (lần cũ chưa bấm xem thì chưa tính là xem).
  useEffect(() => {
    for (const d of ds) {
      if (nhieuLan && (d.lan ?? 0) !== lanXem) continue;
      if (d.ket_qua_trang_thai !== "CO_KET_QUA" || d.da_xem_luc) continue;
      if (daGhi.current.has(d.service_order_id)) continue;
      daGhi.current.add(d.service_order_id);
      ghiDaXem(d.service_order_id);
    }
  }, [ds, nhieuLan, lanXem]);

  const mauCho = (d: ChiDinhVaKetQua): MauKetQuaNgan[] => {
    if (d.mau_ket_qua && d.mau_ket_qua.length > 0) return d.mau_ket_qua;
    const g = goiYMau[d.service_code];
    const goiY = g ? mauDuPhong.filter((m) => m.ma === g) : [];
    return goiY.length > 0 ? [...goiY, ...mauDuPhong.filter((m) => m.ma !== g)] : mauDuPhong;
  };
  if (ds.length === 0) {
    return <p className="text-body text-ink-faint">Chưa có chỉ định nào trong lượt này.</p>;
  }
  const dHop = hop ? ds.find((d) => d.service_order_id === hop.id) : undefined;
  const tenLan = (lan: number) => (lan ? `Lần ${lan}` : "Mang sang");

  const theChiDinh = (d: ChiDinhVaKetQua) => {
    const tt = trangThai(d);
    const mau = chipMau(d);
    const giay = nhanGiay[d.service_code];
    const cacTep = tepCua(d);
    const coKq = d.ket_qua_trang_thai === "CO_KET_QUA";
    const coPhieu = d.ket_qua.some((k) => k.loai === "PHIEU");
    return (
      <li key={d.service_order_id} className="rounded-card border border-hairline bg-surface">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 px-3 py-2.5">
          <div className="min-w-0">
            <span className="font-semibold text-ink">{d.ten_hien_thi}</span>{" "}
            {d.ma_kiotviet ? <span className="text-meta text-ink-muted">{d.ma_kiotviet}</span> : null}
            {giay && giay !== d.ten_hien_thi ? (
              <div className="text-meta text-ink-muted">Trên phiếu giấy: {giay}</div>
            ) : null}
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Chip tone={tt.tone}>{tt.nhan}</Chip>
              {mau ? <Chip tone={mau.tone}>{mau.nhan}</Chip> : null}
              {d.ket_qua.some((k) => k.dang_sua) ? (
                <Chip tone="warning">Đang sửa lại — bản dưới vẫn chính thức</Chip>
              ) : null}
              {/* Chưa thu tiền: bác sĩ bật/tắt được (máy chủ chặn khi đã thu —
                  SERVICE_ALREADY_PAID). Đã thu: chỉ còn chip. */}
              {onDoiBatBuoc && !d.da_thu ? (
                <label className="inline-flex min-h-8 items-center gap-1 text-meta text-ink">
                  <input
                    type="checkbox"
                    className="size-3.5 accent-brand-600"
                    checked={Boolean(d.bat_buoc)}
                    onChange={(e) => void doiBatBuoc(d, e.target.checked)}
                  />
                  bắt buộc
                </label>
              ) : d.bat_buoc ? (
                <Chip tone="warning">bắt buộc</Chip>
              ) : null}
              <span className="text-meta text-ink-muted">{d.gia != null ? tienVn(d.gia) : "chưa có giá"}</span>
            </div>
            {loiBatBuoc?.id === d.service_order_id ? (
              <p role="alert" className="mt-1 text-meta text-danger">
                {loiBatBuoc.loi}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap justify-end gap-1">
            {choSua ? (
              <Button
                type="button"
                size="sm"
                variant="soft"
                aria-expanded={dien === d.service_order_id}
                onClick={() => setDien(dien === d.service_order_id ? null : d.service_order_id)}
              >
                {dien === d.service_order_id ? "Đóng phiếu kết quả" : "Mở phiếu kết quả"}
              </Button>
            ) : null}
            {coPhieu ? (
              <a
                href={`/print/ket-qua/${d.service_order_id}`}
                target="_blank"
                rel="noopener"
                className={buttonClass("ghost", "sm")}
              >
                In
              </a>
            ) : null}
            {clinicPatientId ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-expanded={tep === d.service_order_id}
                onClick={() => setTep(tep === d.service_order_id ? null : d.service_order_id)}
              >
                {tep === d.service_order_id ? "Ẩn tải tệp" : "Ảnh · tệp"}
              </Button>
            ) : null}
          </div>
        </div>

        {coKq ? (
          <div className="relative rounded-b-card border-t border-hairline bg-surface-muted/50 p-3">
            <button
              type="button"
              onClick={() => setHop({ id: d.service_order_id, i: 0, luoi: false })}
              title="Mở rộng — kết quả bên trái, ảnh/video bên phải"
              aria-label={`Xem kết quả và ảnh cạnh nhau — ${d.ten_hien_thi}`}
              className="absolute right-2 top-2 grid size-7 place-items-center rounded-control bg-surface text-ink-muted ring-1 ring-inset ring-line hover:bg-surface-sunken"
            >
              ⤢
            </button>
            <div className={cacTep.length > 0 ? "grid gap-4 2xl:grid-cols-[minmax(0,1fr)_18rem]" : ""}>
              <div className="min-w-0 pr-9">
                <NoiDungKetQua d={d} gioiHan={14} />
              </div>
              {cacTep.length > 0 && tep !== d.service_order_id ? (
                <div className="border-t border-dashed border-hairline pt-3 2xl:border-t-0 2xl:pt-0">
                  <AnhKetQua
                    dau
                    tep={cacTep}
                    onMo={(i, luoi) => setHop({ id: d.service_order_id, i, luoi: Boolean(luoi) })}
                  />
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        {tep === d.service_order_id && clinicPatientId ? (
          <div className="border-t border-hairline p-3">
            <KhungTep
              clinicPatientId={clinicPatientId}
              serviceOrderId={d.service_order_id}
              choTaiLen={choSua}
              onDaTaiLen={() => onDoi?.()}
            />
          </div>
        ) : null}
        {dien === d.service_order_id ? (
          <div className="border-t border-hairline p-3">
            <PhieuKetQua
              serviceOrderId={d.service_order_id}
              mau={mauCho(d)}
              mauMacDinh={
                d.ket_qua.find((k) => k.loai === "PHIEU")?.form_id?.replace(/^KQ_/, "") ??
                (d.mau_ket_qua?.[0]?.ma || goiYMau[d.service_code] || null)
              }
              onHoanTat={() => onDoi?.()}
            />
          </div>
        ) : null}
      </li>
    );
  };

  return (
    <>
      {dHop && hop ? (
        <Lightbox
          tieuDe={dHop.ten_hien_thi}
          phuDe={NHAN_KET_QUA[dHop.ket_qua_trang_thai]}
          tep={tepCua(dHop)}
          batDau={hop.i}
          luoiBanDau={hop.luoi}
          trai={<NoiDungKetQua d={dHop} gioiHan={0} />}
          onDong={() => setHop(null)}
        />
      ) : null}
      <div className="space-y-2">
        {nhieuLan ? (
          <ChipLoc
            nhan="Xem theo lần chỉ định"
            chon={lanXem}
            onChon={(l) => setXemLan(l === lanHienTai ? null : l)}
            muc={[...cacLan].reverse().map((l) => ({
              ma: l,
              nhan: tenLan(l),
              title: l === lanHienTai ? "Lần đang mở" : `Xem lại ${tenLan(l).toLowerCase()} (chỉ xem)`,
              nhac:
                l !== lanHienTai &&
                ds.some(
                  (d) =>
                    (d.lan ?? 0) === l && d.ket_qua_trang_thai === "CO_KET_QUA" && !d.da_xem_luc,
                ),
            }))}
          />
        ) : null}
        {chiXem ? (
          <div className="flex flex-wrap items-center gap-2 rounded-control bg-warning-bg px-3 py-2 text-body text-warning">
            <span>
              Đang xem <b>{tenLan(lanXem).toLowerCase()}</b> — chỉ xem, không sửa được.
            </span>
            <Button type="button" size="sm" variant="secondary" onClick={() => setXemLan(null)}>
              Về {tenLan(lanHienTai).toLowerCase()} (đang mở)
            </Button>
          </div>
        ) : null}
        {nhieuLan ? (
          <p className="text-meta text-ink-muted">
            {(() => {
              const gui = dsHien.map((d) => d.chi_dinh_luc).filter(Boolean).sort()[0];
              return `${tenLan(lanXem)} · ${gui ? `gửi ${fmtTime(gui)}` : "chưa gửi"} · ${dsHien.length} chỉ định`;
            })()}
          </p>
        ) : null}
        <ul className="space-y-2">{dsHien.map((d) => theChiDinh(d))}</ul>
      </div>
    </>
  );
}
