"use client";

// Cột giữa + cột phải của màn Check-out: toàn cảnh MỘT lượt khám.
//
// Bốn mục theo bản thiết kế Quang gửi 06/08, đều đọc dữ liệu thật. Mục "Hồ sơ
// trả bệnh nhân" liệt kê tệp kết quả của lượt và trạng thái từng tệp (bản
// 06/08 báo "chưa có kho lưu tệp" — đúng hồi đó, sai từ khi tệp lưu thật;
// smoke 18/09). Không vẽ nút "In bộ hồ sơ": chưa có gì đứng sau nó.

import { useEffect, useState } from "react";

import { fmtDateTimeOrDate } from "../../../../lib/datetime";

export interface Blocker {
  type: string;
  message: string;
  chan?: boolean;
}

interface DichVu {
  ten: string;
  nguoi_lam: string | null;
  vai: string | null;
  status: string;
  xong_luc: string | null;
}

interface KhoanTien {
  loai: string;
  so_tien: number | null;
  status: string;
  da_huy: boolean;
  luc: string | null;
}

interface TheoDoi {
  id: string;
  status: string;
  ly_do: string | null;
  chu_so_huu: string | null;
  han: string | null;
}

interface TepTra {
  ten: string | null;
  loai_tep: string;
  trang_thai: "CHO_BAC_SI" | "DUOC_GUI" | "DA_GUI";
  gui_kenh: string | null;
  tai_len_luc: string;
}

const TRANG_THAI_TEP: Record<TepTra["trang_thai"], string> = {
  CHO_BAC_SI: "Chờ bác sĩ cho phép gửi",
  DUOC_GUI: "Bác sĩ đã cho gửi · CSKH chưa gửi",
  DA_GUI: "Đã gửi khách",
};

interface MocThoiGian {
  luc: string;
  ten: string;
  lenh: string;
  den_trang_thai: string | null;
  nguoi_lam: string | null;
}

export interface ChiTiet {
  ok: boolean;
  visit_id: string;
  patient_name: string | null;
  patient_code: string | null;
  visit_status: string | null;
  checked_in_at: string | null;
  room_name: string | null;
  /** "nơi · việc" từ hành trình khách (29/09) — thay room_name. */
  dang_o?: string | null;
  /** Trạng thái khám suy từ phiên khám (chờ khám / đang khám / đã khám xong /
   *  chờ đọc kết quả) — chỉ khi lượt còn mở. */
  trang_thai_kham?: string | null;
  already_closed: boolean;
  blockers: Blocker[];
  can_close: boolean;
  dich_vu: DichVu[];
  tai_chinh: KhoanTien[];
  ho_so_tra: { muc: TepTra[]; vi_sao_rong: string };
  theo_doi: TheoDoi[];
  moc_thoi_gian: MocThoiGian[];
}

/** Trạng thái lượt khám → chữ người đọc được.
 *
 * Đủ NĂM giá trị. Thiếu INCOMPLETE thì ô "Trạng thái" hiện chữ `INCOMPLETE`
 * trần cho một lượt khám dở — đúng loại chỗ mà bài canh
 * `test_trang_thai_luot_kham_khong_bo_sot` sinh ra để bắt.
 */
const TEN_TRANG_THAI: Record<string, string> = {
  OPEN: "Đã đến, chưa khám",
  IN_PROGRESS: "Đang khám",
  INCOMPLETE: "Khám dở — chờ gọi lại",
  FINALIZED: "Đã chốt hồ sơ",
  AMENDED: "Đã bổ sung hồ sơ",
};

const TEN_KHOAN: Record<string, string> = {
  dich_vu: "Khám & dịch vụ",
  thuoc: "Thuốc",
};

function tien(v: number | null): string {
  return v == null ? "—" : `${v.toLocaleString("vi-VN")}đ`;
}

function gio(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Đầu mỗi mục: tên + "đã xong mấy / tổng mấy". */
function DauMuc({
  so,
  ten,
  xong,
  tong,
}: {
  so: number;
  ten: string;
  xong: number;
  tong: number;
}) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line bg-surface-muted px-4 py-2.5">
      <h3 className="text-sm font-semibold text-ink">
        {so}. {ten}
      </h3>
      <span
        className={`text-xs font-medium ${
          tong > 0 && xong === tong ? "text-success" : "text-ink-muted"
        }`}
      >
        {xong}/{tong} hoàn tất
      </span>
    </div>
  );
}

function Dau({ xong }: { xong: boolean }) {
  return (
    <span
      className={`inline-flex size-4 shrink-0 items-center justify-center rounded-full text-label font-bold ${
        xong ? "bg-success text-white" : "border border-line text-ink-faint"
      }`}
      aria-hidden
    >
      {xong ? "✓" : ""}
    </span>
  );
}

export default function ChiTietLuot({ visitId }: { visitId: string }) {
  const [d, setD] = useState<ChiTiet | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    // KHÔNG đặt lại state ở đây. Component nhận `key={visit_id}` từ bảng cha
    // nên đổi lượt là dựng lại từ đầu — state đã sạch. Gọi setState ngay trong
    // effect còn làm React vẽ thừa một lượt (và trình biên dịch chặn thẳng).
    fetch(`/api/reception/checkout?chi_tiet=1&visit_id=${visitId}`)
      .then((r) => r.json())
      .then((j: ChiTiet) => {
        if (huy) return;
        // `ok: false` = backend không trả lời. Nói ra, đừng vẽ một lượt trống
        // trông y hệt "lượt này chẳng có gì".
        if (!j?.ok) setLoi("Chưa đọc được chi tiết lượt khám từ máy chủ.");
        else setD(j);
      })
      .catch(() => {
        if (!huy) setLoi("Chưa đọc được chi tiết lượt khám từ máy chủ.");
      });
    return () => {
      huy = true;
    };
  }, [visitId]);

  if (loi) {
    return (
      <p className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
        {loi}
      </p>
    );
  }
  if (!d) {
    return (
      <p className="rounded-card border border-line bg-surface px-4 py-10 text-center text-sm text-ink-muted">
        Đang đọc lượt khám…
      </p>
    );
  }

  // Không làm được cũng là đã giải quyết (bác sĩ đã quyết) — đếm vào "hoàn tất"
  // nhưng hiện chữ riêng, không đánh dấu ✓ như đã làm.
  const dvXong = d.dich_vu.filter(
    (x) => x.status === "COMPLETED" || x.status === "NOT_PERFORMED",
  ).length;
  const tienDaThu = d.tai_chinh.filter((x) => !x.da_huy && x.status === "PAID");
  const tdXong = d.theo_doi.filter((x) => x.status !== "OPEN").length;

  return (
    <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1.6fr)_minmax(260px,0.9fr)]">
      {/* ── Cột giữa: bốn mục đối soát ─────────────────────────────────── */}
      <div className="min-w-0 space-y-3">
        <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <DauMuc so={1} ten="Dịch vụ" xong={dvXong} tong={d.dich_vu.length} />
          {d.dich_vu.length === 0 ? (
            <p className="px-4 py-4 text-sm text-ink-muted">
              Lượt này chưa có bước nào trong luồng khám.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {d.dich_vu.map((x, i) => (
                <li
                  key={`${x.ten}-${i}`}
                  className="flex items-center gap-3 px-4 py-2.5 text-sm"
                >
                  <Dau xong={x.status === "COMPLETED"} />
                  <span className="min-w-0 flex-1 truncate text-ink">{x.ten}</span>
                  <span className="hidden shrink-0 text-xs text-ink-muted sm:block">
                    {x.nguoi_lam ?? "—"}
                  </span>
                  <span
                    className={`w-24 shrink-0 text-right text-xs font-medium ${
                      x.status === "COMPLETED"
                        ? "text-success"
                        : x.status === "NOT_PERFORMED"
                          ? "text-ink-muted"
                          : "text-warning"
                    }`}
                  >
                    {x.status === "COMPLETED"
                      ? `Xong ${gio(x.xong_luc)}`
                      : x.status === "NOT_PERFORMED"
                        ? "Không làm"
                        : x.status === "IN_PROGRESS"
                        ? "Đang làm"
                        : "Chưa làm"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <DauMuc
            so={2}
            ten="Tài chính"
            xong={tienDaThu.length}
            tong={d.tai_chinh.length}
          />
          {d.tai_chinh.length === 0 ? (
            <p className="px-4 py-4 text-sm text-ink-muted">
              Chưa có phiếu thu nào cho lượt này.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {d.tai_chinh.map((x, i) => (
                <li
                  key={`${x.loai}-${i}`}
                  className="flex items-center gap-3 px-4 py-2.5 text-sm"
                >
                  <Dau xong={!x.da_huy && x.status === "PAID"} />
                  <span className="min-w-0 flex-1 truncate text-ink">
                    Nghĩa vụ: {TEN_KHOAN[x.loai] ?? x.loai}
                  </span>
                  <span className="shrink-0 text-xs text-ink-muted">
                    {x.da_huy ? "Đã huỷ phiếu" : "Đã thanh toán"}
                  </span>
                  <span
                    className={`w-28 shrink-0 text-right font-semibold tabular-nums ${
                      x.da_huy ? "text-ink-faint line-through" : "text-ink"
                    }`}
                  >
                    {tien(x.so_tien)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <DauMuc
            so={3}
            ten="Hồ sơ trả bệnh nhân"
            xong={d.ho_so_tra.muc.filter((t) => t.trang_thai !== "CHO_BAC_SI").length}
            tong={d.ho_so_tra.muc.length}
          />
          {/* Tệp kết quả THẬT của lượt, kèm trạng thái từng tệp. Gửi khách là
              việc của CSKH sau khi bác sĩ cho phép — không chặn đóng lượt. */}
          {d.ho_so_tra.muc.length === 0 ? (
            <p className="px-4 py-4 text-sm text-ink-muted">{d.ho_so_tra.vi_sao_rong}</p>
          ) : (
            <ul className="divide-y divide-line">
              {d.ho_so_tra.muc.map((t, i) => (
                <li key={`${t.ten}-${i}`} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <Dau xong={t.trang_thai !== "CHO_BAC_SI"} />
                  <span className="min-w-0 flex-1 truncate text-ink">{t.ten ?? "(không tên)"}</span>
                  <span
                    className={`shrink-0 text-right text-xs font-medium ${
                      t.trang_thai === "CHO_BAC_SI" ? "text-warning" : "text-success"
                    }`}
                  >
                    {TRANG_THAI_TEP[t.trang_thai]}
                    {t.trang_thai === "DA_GUI" && t.gui_kenh ? ` (${t.gui_kenh})` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          <DauMuc
            so={4}
            ten="Theo dõi sau khám"
            xong={tdXong}
            tong={d.theo_doi.length}
          />
          {d.theo_doi.length === 0 ? (
            <p className="px-4 py-4 text-sm text-ink-muted">
              Lượt này chưa sinh việc theo dõi nào.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {d.theo_doi.map((x) => (
                <li key={x.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <Dau xong={x.status !== "OPEN"} />
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {x.ly_do ?? "Theo dõi sau khám"}
                  </span>
                  <span className="shrink-0 text-xs text-ink-muted">
                    {x.chu_so_huu ?? "—"}
                  </span>
                  <span className="w-28 shrink-0 text-right text-xs text-ink-muted">
                    {x.han ? `Hạn ${fmtDateTimeOrDate(x.han)}` : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Kết luận đối soát — câu cuối cùng Lễ tân đọc trước khi bấm. */}
        <div
          className={`rounded-card border px-4 py-3 text-sm ${
            d.can_close
              ? "border-success bg-success-bg text-success"
              : "border-warning bg-warning-bg text-warning"
          }`}
        >
          {d.can_close ? (
            <>
              <b>Đối soát điều kiện hoàn tất.</b> Không có chặn — đóng lượt được.
            </>
          ) : (
            <>
              <b>Còn {d.blockers.length} việc chưa xong.</b>{" "}
              {d.blockers.some((b) => b.chan)
                ? "Khách còn nợ: phải thu hoặc ghi nợ trước — các việc khác vẫn cho về được:"
                : "Vẫn cho khách về được — việc còn dở được ghi lại:"}
              <ul className="mt-1 list-disc pl-5">
                {d.blockers.map((b) => (
                  <li key={b.type}>{b.message}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>

      {/* ── Cột phải: thông tin lượt + dòng thời gian ───────────────────── */}
      <aside className="min-w-0 space-y-3">
        <section className="rounded-card border border-line bg-surface p-4 shadow-card">
          <h3 className="text-sm font-semibold text-ink">Thông tin lượt khám</h3>
          <dl className="mt-3 space-y-1.5 text-sm">
            <Hang nhan="Bệnh nhân" giaTri={d.patient_name} />
            <Hang nhan="Mã bệnh nhân" giaTri={d.patient_code} />
            <Hang nhan="Giờ check-in" giaTri={gio(d.checked_in_at)} />
            <Hang nhan="Đang ở" giaTri={d.dang_o ?? d.room_name} />
            <Hang
              nhan="Trạng thái"
              giaTri={
                d.trang_thai_kham ??
                (d.visit_status
                  ? (TEN_TRANG_THAI[d.visit_status] ?? d.visit_status)
                  : null)
              }
            />
          </dl>
        </section>

        <section className="rounded-card border border-line bg-surface p-4 shadow-card">
          <h3 className="text-sm font-semibold text-ink">Dòng thời gian</h3>
          {/* CHỈ việc đã xảy ra (nhật ký sự kiện) — không có bước dự kiến tạo
              sẵn lúc check-in; bước còn chờ nằm ở mục "1. Dịch vụ". */}
          {d.moc_thoi_gian.length === 0 ? (
            <p className="mt-2 text-sm text-ink-muted">Chưa có mốc nào.</p>
          ) : (
            <ol className="mt-3 space-y-2.5">
              {d.moc_thoi_gian.map((m, i) => (
                <li key={i} className="flex gap-2.5 text-xs">
                  <span className="w-10 shrink-0 tabular-nums text-ink-muted">
                    {gio(m.luc)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-ink">{m.ten}</span>
                    {m.nguoi_lam ? (
                      <span className="block text-ink-faint">{m.nguoi_lam}</span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </aside>
    </div>
  );
}

function Hang({ nhan, giaTri }: { nhan: string; giaTri?: string | null }) {
  const co = Boolean(giaTri && String(giaTri).trim());
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-xs text-ink-muted">{nhan}</dt>
      <dd className={`text-right ${co ? "text-ink" : "text-ink-faint"}`}>
        {co ? giaTri : "—"}
      </dd>
    </div>
  );
}
