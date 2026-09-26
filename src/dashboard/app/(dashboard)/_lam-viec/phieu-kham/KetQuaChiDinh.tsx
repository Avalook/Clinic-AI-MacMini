"use client";

// Mục C — KẾT QUẢ CẬN LÂM SÀNG theo từng chỉ định của lượt.
//
// Gắn bằng `service_order_id` (máy chủ đã nối). Hai chỉ định cùng tên là hai
// dòng riêng, kết quả không bao giờ chạy sang nhau. Tên dịch vụ chỉ để đọc.
//
// Hai lớp trạng thái đứng cạnh nhau, không gộp: "thực hiện" (đã làm chưa) và
// "kết quả" (đã có chưa). Nháp kết quả không hiện nội dung — chưa ai chịu
// trách nhiệm về chữ trong đó.
//
// BÁC SĨ ĐIỀN KẾT QUẢ NGAY ĐÂY (Tuyền 23/09/2026 tối: "không cần cái duyệt kết
// quả nữa, duyệt làm gì khi ta có thể tự điền vào đây"). [Điền kết quả] mở đúng
// phiếu kết quả của chỉ định (cùng engine, cùng [Hoàn tất] như phòng dịch vụ).
// Mẫu: mẫu đã gắn cho dịch vụ → mẫu gợi ý của phiếu v5 → 18 mẫu dự phòng.
// Mở [Xem kết quả] là "đã xem" (như nút ở Bàn khám) — máy chủ ghi, màn không tự
// quyết ai được tính.

import { useState } from "react";

import KhungTep from "../KhungTep";
import AnhKetQua, { tepXem } from "../AnhKetQua";
import PhieuKetQua from "../PhieuKetQua";
import Button, { buttonClass } from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import Lightbox from "@/components/ui/Lightbox";
import { fmtTime } from "@/lib/datetime";
import {
  giaTriDoc,
  NHAN_DOI_TAC,
  NHAN_KET_QUA,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
  type MauKetQuaNgan,
} from "@/lib/phieu-kham";

const TONE: Record<ChiDinhVaKetQua["ket_qua_trang_thai"], ChipTone> = {
  CO_KET_QUA: "success",
  DANG_NHAP: "warning",
  CHUA_CO: "neutral",
};

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
  // Chỉ để máy chủ ghi "đã xem" (bác sĩ / thư ký / BS siêu âm); nội dung đã có
  // sẵn ở đây. Hỏng thì thôi — không chặn việc đọc.
  void fetch(`/api/phieu?xem=${orderId}`, { cache: "no-store" }).catch(() => undefined);
}

export default function KetQuaChiDinh({
  ds,
  mauDuPhong = [],
  goiYMau = {},
  choDien = false,
  clinicPatientId,
  onDoi,
}: {
  ds: ChiDinhVaKetQua[];
  /** 18 mẫu kết quả đang bật — khi dịch vụ chưa gắn mẫu nào. */
  mauDuPhong?: MauKetQuaNgan[];
  /** service_code → mã mẫu gợi ý từ phiếu v5 (không kèm `KQ_`). */
  goiYMau?: Record<string, string>;
  /** Người đang mở có quyền điền kết quả (máy chủ vẫn kiểm lại). */
  choDien?: boolean;
  /** Có thì mở được khung ảnh / video / tệp kết quả của từng chỉ định. */
  clinicPatientId?: string;
  onDoi?: () => void;
}) {
  const [mo, setMo] = useState<string | null>(null);
  const [dien, setDien] = useState<string | null>(null);
  const [tep, setTep] = useState<string | null>(null);
  // Hộp xem CHIA ĐÔI (lát 5): kết quả trái, ảnh phải — mở từ ảnh nhỏ hoặc ⤢.
  const [hop, setHop] = useState<{ id: string; i: number; luoi: boolean } | null>(null);
  const mauCho = (d: ChiDinhVaKetQua): MauKetQuaNgan[] => {
    if (d.mau_ket_qua && d.mau_ket_qua.length > 0) return d.mau_ket_qua;
    const g = goiYMau[d.service_code];
    const goiY = g ? mauDuPhong.filter((m) => m.ma === g) : [];
    return goiY.length > 0 ? [...goiY, ...mauDuPhong.filter((m) => m.ma !== g)] : mauDuPhong;
  };
  if (ds.length === 0) {
    return <p className="text-body text-ink-faint">Chưa có chỉ định nào trong lượt này.</p>;
  }
  const moHop = (d: ChiDinhVaKetQua, i: number, luoi: boolean) => {
    // Mở hộp là XEM kết quả — cùng nghĩa với nút "Xem kết quả".
    if (d.ket_qua_trang_thai === "CO_KET_QUA") ghiDaXem(d.service_order_id);
    setHop({ id: d.service_order_id, i, luoi });
  };
  const dHop = hop ? ds.find((d) => d.service_order_id === hop.id) : undefined;
  return (
    <>
    {dHop && hop ? (
      <Lightbox
        tieuDe={dHop.ten_hien_thi}
        phuDe={NHAN_KET_QUA[dHop.ket_qua_trang_thai]}
        tep={tepCua(dHop)}
        batDau={hop.i}
        luoiBanDau={hop.luoi}
        trai={
          <div className="space-y-3">
            {dHop.ket_qua.some((k) => k.loai === "PHIEU") ? (
              dHop.ket_qua
                .filter((k) => k.loai === "PHIEU")
                .map((k) => <MotKetQua key={k.phieu_id} k={k} />)
            ) : (
              <p className="text-body text-ink-muted">Chưa có phiếu kết quả — chỉ có tệp.</p>
            )}
          </div>
        }
        onDong={() => setHop(null)}
      />
    ) : null}
    <ul className="divide-y divide-hairline rounded-card border border-hairline bg-surface">
      {ds.map((d) => {
        const dangMo = mo === d.service_order_id;
        return (
          <li key={d.service_order_id} className="px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-body font-medium text-ink">{d.ten_hien_thi}</span>
              {d.ket_qua_trang_thai === "CHUA_CO" &&
              (d.thuc_hien === "COMPLETED" || d.thuc_hien === "performed") ? (
                // Thủ thuật không có phiếu kết quả (tháo vòng…): đã làm là xong
                // việc — đừng treo "Chưa có kết quả" mãi (bấm thật 23/09 khuya).
                <Chip tone="success">Đã làm</Chip>
              ) : (
                <Chip tone={TONE[d.ket_qua_trang_thai]}>
                  {NHAN_KET_QUA[d.ket_qua_trang_thai]}
                </Chip>
              )}
              {d.doi_tac && d.ket_qua_trang_thai !== "CO_KET_QUA" ? (
                <Chip tone={d.doi_tac === "CHO_TAI_LIEU" ? "warning" : "neutral"}>
                  {NHAN_DOI_TAC[d.doi_tac]}
                </Chip>
              ) : null}
              {d.ket_qua.some((k) => k.dang_sua) ? (
                <Chip tone="warning">Đang sửa lại — bản dưới vẫn chính thức</Chip>
              ) : null}
              <span className="ml-auto" />
              {d.ket_qua.length > 0 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`Xem kết quả và ảnh cạnh nhau — ${d.ten_hien_thi}`}
                  title="Kết quả trái, ảnh phải"
                  onClick={() => moHop(d, 0, false)}
                >
                  ⤢
                </Button>
              ) : null}
              {d.ket_qua.length > 0 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-expanded={dangMo}
                  onClick={() => {
                    if (!dangMo && d.ket_qua_trang_thai === "CO_KET_QUA") {
                      ghiDaXem(d.service_order_id);
                    }
                    setMo(dangMo ? null : d.service_order_id);
                  }}
                >
                  {dangMo ? "Thu gọn" : "Xem kết quả"}
                </Button>
              ) : null}
              {d.ket_qua.some((k) => k.loai === "PHIEU") ? (
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
                  onClick={() =>
                    setTep(tep === d.service_order_id ? null : d.service_order_id)
                  }
                >
                  {tep === d.service_order_id ? "Ẩn ảnh · tệp" : "Ảnh · tệp"}
                </Button>
              ) : null}
              {choDien ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  aria-expanded={dien === d.service_order_id}
                  onClick={() =>
                    setDien(dien === d.service_order_id ? null : d.service_order_id)
                  }
                >
                  {dien === d.service_order_id ? "Đóng phiếu kết quả" : "Điền kết quả"}
                </Button>
              ) : null}
            </div>
            {/* Khung tệp đang mở thì nó đã hiện đủ ảnh — không vẽ hai lần. */}
            {tepCua(d).length > 0 && tep !== d.service_order_id ? (
              <div className="mt-2">
                <AnhKetQua tep={tepCua(d)} onMo={(i, luoi) => moHop(d, i, Boolean(luoi))} />
              </div>
            ) : null}
            {tep === d.service_order_id && clinicPatientId ? (
              <div className="mt-2">
                <KhungTep
                  clinicPatientId={clinicPatientId}
                  serviceOrderId={d.service_order_id}
                  choTaiLen={choDien}
                  onDaTaiLen={() => onDoi?.()}
                />
              </div>
            ) : null}
            {dien === d.service_order_id ? (
              <div className="mt-2">
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
            {dangMo ? (
              <div className="mt-2 space-y-3">
                {d.ket_qua.map((k) => (
                  <MotKetQua key={k.phieu_id ?? k.tep_id} k={k} />
                ))}
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
    </>
  );
}

function MotKetQua({ k }: { k: KetQuaMotChiDinh }) {
  if (k.loai === "TEP") {
    // Tệp (kể cả của đối tác) mở thẳng ở tab mới — không bước xác nhận
    // (Tuyền 23/09 khuya: "hiện ra đó luôn là được"). Mở = tự ghi đã xem.
    return (
      <p className="text-body text-ink">
        Tệp {k.loai_tep}:{" "}
        <a
          href={`/api/cskh/ket-qua/${k.tep_id}/noi-dung`}
          target="_blank"
          rel="noopener"
          className="font-medium text-brand-700 underline underline-offset-4"
        >
          {k.ten ?? "(không tên)"}
        </a>
      </p>
    );
  }
  if (k.trang_thai !== "READY" || !k.khung || !k.du_lieu) {
    return <p className="text-body text-ink-muted">{k.ten}: đang nhập kết quả.</p>;
  }
  const duLieu = k.du_lieu;
  return (
    <div className="rounded-control bg-surface-muted p-3">
      <p className="text-meta font-semibold text-ink-muted">
        {k.ten}
        {k.ban_thu && k.ban_thu > 1 ? ` · bản ${k.ban_thu}` : ""}
      </p>
      <dl className="mt-1 space-y-1">
        {k.khung.flatMap((m) =>
          m.block.map((o) => (
            <div key={o.ma} className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
              <dt className="text-meta text-ink-muted sm:w-40 sm:shrink-0">{o.ten}</dt>
              <dd className="whitespace-pre-wrap text-body text-ink">
                {giaTriDoc(o, duLieu[o.ma], m.cot)}
              </dd>
            </div>
          )),
        )}
      </dl>
    </div>
  );
}
