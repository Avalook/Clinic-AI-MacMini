"use client";

// Một dòng đơn thuốc ở màn Nhà thuốc (contract tiền–thuốc CP4).
//
// Nút nào hiện là do MÁY CHỦ quyết (`dong.thao_tac`, `phan_lo[].thao_tac`) —
// component này không đọc giai đoạn hay trạng thái để tự suy. Máy chủ vẫn kiểm
// lại từng lệnh; câu từ chối của nó đã là tiếng Việt có số liệu nên hiện
// nguyên văn.
//
// Thứ tự trên màn đi theo đúng việc của dược sĩ:
//   xác định thuốc kho → số khách mua → chọn lô → (thu ngân thu) → giao.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import { INPUT } from "../form-ui";
import { dinhDanhThaoTac, khoaThaoTac, xongThaoTac } from "../customers/khoa-mot-lan";
import {
  NHAN_CAP,
  fmtNgay,
  fmtSo,
  type DongDon,
  type LoGoiY,
  type ThuocDanhMuc,
} from "./ban-thuoc";

interface Props {
  dong: DongDon;
  danhMuc: ThuocDanhMuc[];
  /** Người xem không có quyền ghi — câu "chưa có thao tác" không nói về giai đoạn. */
  chiXem?: boolean;
}

const O_NHAP = `${INPUT} mt-1`;
const NHAN = "block text-xs text-ink-muted";
/** Trên điện thoại ô bấm tối thiểu 40px (DESIGN.md §7) = đúng cỡ `lg` của thang. */
export const CHAM = "max-sm:h-10 max-sm:px-4";

function nhanLo(b: LoGoiY): string {
  return (
    `${b.batch_code} · HSD ${fmtNgay(b.expiry_date)} · ` +
    `Tồn vật lý ${fmtSo(b.ton_vat_ly)} · Có thể phân lô lúc này ${fmtSo(b.co_the_phan_lo)} ${b.unit}`
  );
}

export default function DongThuoc({ dong, danhMuc, chiXem = false }: Props) {
  const router = useRouter();
  const tt = dong.thao_tac;
  const [thuocId, setThuocId] = useState(dong.drug_catalog_id ?? "");
  const [soMua, setSoMua] = useState(
    dong.purchased_qty !== null ? String(dong.purchased_qty) : "",
  );
  const conCanLo = Math.max(0, dong.can_lo - dong.da_chon);
  // Rơi về lô đầu tiên khi chưa chọn: trình duyệt tô sẵn option đầu, nên giá
  // trị bên trong cũng phải là nó — không thì nút bị khoá mà không ai biết vì
  // sao (bấm thử 19/09: xác định thuốc xong, ô lô hiện X nhưng state còn rỗng).
  const [loChonTay, setLoChon] = useState("");
  const loChon = loChonTay || (dong.lo_goi_y[0]?.drug_batch_id ?? "");
  const [soChon, setSoChon] = useState(conCanLo > 0 ? String(conCanLo) : "");
  const [soGiao, setSoGiao] = useState<Record<string, string>>({});
  const [loDoi, setLoDoi] = useState<Record<string, string>>({});
  const [soCu, setSoCu] = useState("");
  // Giao không lô: mặc định phần bán chưa giao (máy chủ vẫn chặn quá số bán).
  const conGiao = Math.max((dong.purchased_qty ?? dong.quantity_num ?? 0) - dong.dispensed_qty, 0);
  const [soKhongLo, setSoKhongLo] = useState(conGiao > 0 ? String(conGiao) : "");
  const [lyDo, setLyDo] = useState("");
  const [soTra, setSoTra] = useState<Record<string, string>>({});
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function goi(action: string, body: Record<string, unknown>) {
    setDangGui(true);
    setLoi(null);
    // Một THAO TÁC một khoá (không phải một lần bấm): bấm lại hay gửi lại sau
    // khi mất mạng đều mang khoá cũ → máy chủ không giao / trả / huỷ hai lần.
    const thaoTac = dinhDanhThaoTac(action, JSON.stringify(body));
    try {
      const res = await fetch(`/api/pharmacy/${action}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": khoaThaoTac(thaoTac),
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
          detail?: string;
        } | null;
        setLoi(d?.message ?? d?.detail ?? d?.error ?? "Không lưu được. Thử lại giúp em.");
        return;
      }
      setLyDo("");
      setSoCu("");
      setSoGiao({});
      setSoTra({});
      xongThaoTac(thaoTac);
      router.refresh();
    } finally {
      setDangGui(false);
    }
  }

  const khongCoNutNao =
    !Object.values(tt).some(Boolean) &&
    !dong.xuat.some((x) => x.thao_tac.tra) &&
    !dong.phan_lo.some((p) => p.thao_tac.bo || p.thao_tac.doi || p.thao_tac.giao);

  return (
    <div className="space-y-3 rounded-card border border-line bg-surface p-3">
      {/* ── Thuốc kê ── */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-emph font-medium text-ink">{dong.drug_name_raw ?? "—"}</div>
          <div className="text-meta text-ink-muted">
            Kê {dong.quantity_text ?? "—"}
            {dong.dosage_instructions ? ` · ${dong.dosage_instructions}` : ""}
          </div>
        </div>
        <span className="text-meta text-ink-soft">
          {NHAN_CAP[dong.dispense_status ?? ""] ?? dong.dispense_status}
          {dong.dispensed_qty > 0 && ` · đã giao ${fmtSo(dong.dispensed_qty)}`}
        </span>
      </div>

      {dong.closed ? (
        <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-soft">
          Dòng này đã chốt
          {dong.refusal_reason ? ` — khách không lấy: ${dong.refusal_reason}` : ""}.
        </p>
      ) : null}

      {/* ── Thuốc trong kho ── */}
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <span className={NHAN}>Thuốc trong kho</span>
          {tt.xac_dinh_thuoc ? (
            <div className="flex flex-wrap items-end gap-2">
              <select
                aria-label="Thuốc trong kho"
                value={thuocId}
                onChange={(e) => setThuocId(e.target.value)}
                className={`${O_NHAP} flex-1`}
              >
                <option value="">— Chọn thuốc —</option>
                {danhMuc.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name_base}
                    {t.variant ? ` (${t.variant})` : ""}
                  </option>
                ))}
              </select>
              <Button className={CHAM}
                size="md"
                disabled={dangGui || !thuocId || thuocId === dong.drug_catalog_id}
                onClick={() =>
                  goi("xac-dinh-thuoc", {
                    prescription_id: dong.id,
                    drug_catalog_id: thuocId,
                  })
                }
              >
                Xác định
              </Button>
            </div>
          ) : (
            <div className="text-body text-ink">
              {dong.ten_thuoc_kho ?? <span className="text-ink-faint">Chưa xác định</span>}
            </div>
          )}
        </div>
        <div>
          <span className={NHAN}>Khách mua</span>
          {tt.khai_so_mua ? (
            <div className="flex flex-wrap items-end gap-2">
              <input
                aria-label="Số lượng khách mua"
                type="number"
                min="0"
                step="any"
                value={soMua}
                placeholder={dong.quantity_num !== null ? `= số kê ${fmtSo(dong.quantity_num)}` : ""}
                onChange={(e) => setSoMua(e.target.value)}
                className={`${O_NHAP} flex-1`}
              />
              <Button className={CHAM}
                size="md"
                disabled={dangGui || soMua === ""}
                onClick={() =>
                  goi("so-luong-mua", { prescription_id: dong.id, so_luong: Number(soMua) })
                }
              >
                Lưu số mua
              </Button>
            </div>
          ) : (
            <div className="text-body text-ink">
              {fmtSo(dong.purchased_qty ?? dong.quantity_num)} {dong.unit ?? ""}
              {/* C14: bác sĩ quên số lượng — thu ngân thuốc điền ở quầy, không chờ bác sĩ. */}
              {dong.quantity_num === null ? (
                <span className="ml-2 text-meta text-warning">
                  chưa có số lượng — thu ngân thuốc điền ở màn Thu tiền thuốc
                </span>
              ) : null}
              {/* Hai bản đơn (Tuyền 24/09): bác sĩ kê ↔ khách chốt mua. */}
              {dong.purchased_qty !== null &&
              dong.quantity_num !== null &&
              dong.purchased_qty !== dong.quantity_num ? (
                <span className="ml-2 text-meta text-warning">
                  khác số kê {fmtSo(dong.quantity_num)}
                </span>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {/* ── Lô đã chọn ── */}
      {dong.phan_lo.length > 0 ? (
        <div>
          <span className={NHAN}>
            Lô đã chọn · {fmtSo(dong.da_chon)}
            {/* "Còn cần lô" chỉ có nghĩa trước khi thu — sau khi giao, số bán
                trừ số đã giao không còn là mẫu số (bấm thử 19/09: "10/7"). */}
            {tt.chon_lo ? `/${fmtSo(dong.can_lo)}` : ""} {dong.unit ?? ""}
          </span>
          <ul className="mt-1 divide-y divide-line rounded-control border border-line">
            {dong.phan_lo.map((p) => (
              <li key={p.allocation_id} className="space-y-2 px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-body">
                  <span className="text-ink">
                    Lô {p.batch_code} · HSD {fmtNgay(p.expiry_date)} ·{" "}
                    <span className="font-medium">{fmtSo(p.quantity)}</span>
                  </span>
                  <span className="text-meta text-ink-muted">
                    {p.dang_giu
                      ? "Đang giữ cho lần chuyển khoản"
                      : p.da_ban
                        ? `Đã bán · đã giao ${fmtSo(p.handed_over_qty)} · còn ${fmtSo(p.con_giao)}`
                        : p.co_sale
                          ? `Đã bán · đã giao ${fmtSo(p.handed_over_qty)} · phần còn lại đã huỷ`
                          : "Đã chọn, chưa thu"}
                  </span>
                </div>
                {p.thao_tac.giao ? (
                  <div className="flex flex-wrap items-end gap-2">
                    <label className={`${NHAN} w-28`}>
                      Giao
                      <input
                        type="number"
                        min="0"
                        step="any"
                        value={soGiao[p.allocation_id] ?? String(p.con_giao)}
                        onChange={(e) =>
                          setSoGiao((s) => ({ ...s, [p.allocation_id]: e.target.value }))
                        }
                        className={O_NHAP}
                      />
                    </label>
                    <Button className={CHAM}
                      disabled={dangGui}
                      onClick={() =>
                        goi("dispense", {
                          prescription_id: dong.id,
                          drug_batch_id: p.drug_batch_id,
                          so_luong: Number(soGiao[p.allocation_id] ?? p.con_giao),
                        })
                      }
                    >
                      Giao thuốc
                    </Button>
                  </div>
                ) : null}
                {p.thao_tac.doi ? (
                  <div className="flex flex-wrap items-end gap-2">
                    <label className={`${NHAN} flex-1`}>
                      Đổi sang lô
                      <select
                        value={loDoi[p.allocation_id] ?? ""}
                        onChange={(e) =>
                          setLoDoi((s) => ({ ...s, [p.allocation_id]: e.target.value }))
                        }
                        className={O_NHAP}
                      >
                        <option value="">— Chọn lô khác —</option>
                        {dong.lo_goi_y
                          .filter((b) => b.drug_batch_id !== p.drug_batch_id)
                          .map((b) => (
                            <option key={b.drug_batch_id} value={b.drug_batch_id}>
                              {nhanLo(b)}
                            </option>
                          ))}
                      </select>
                    </label>
                    <Button className={CHAM}
                      disabled={dangGui || !loDoi[p.allocation_id] || !lyDo.trim()}
                      onClick={() =>
                        goi("doi-lo", {
                          allocation_id: p.allocation_id,
                          drug_batch_id: loDoi[p.allocation_id],
                          ly_do: lyDo,
                        })
                      }
                    >
                      Đổi lô
                    </Button>
                  </div>
                ) : null}
                {p.thao_tac.bo ? (
                  <Button className={CHAM}
                    size="sm"
                    variant="ghost"
                    disabled={dangGui || !lyDo.trim()}
                    onClick={() =>
                      goi("bo-phan-lo", { allocation_id: p.allocation_id, ly_do: lyDo })
                    }
                  >
                    Bỏ lô này
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ── Chọn lô ── */}
      {tt.chon_lo ? (
        dong.lo_goi_y.length === 0 ? (
          <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-muted">
            Kho chưa có lô cho thuốc này — không sao: thu tiền và giao luôn được, gán lô
            sau ở Kho thuốc.
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <label className={`${NHAN} flex-1`}>
              Chọn lô (còn cần {fmtSo(conCanLo)} {dong.unit ?? ""})
              <select value={loChon} onChange={(e) => setLoChon(e.target.value)} className={O_NHAP}>
                {dong.lo_goi_y.map((b) => (
                  <option key={b.drug_batch_id} value={b.drug_batch_id}>
                    {nhanLo(b)}
                  </option>
                ))}
              </select>
            </label>
            <label className={`${NHAN} w-28`}>
              Số lượng
              <input
                type="number"
                min="0"
                step="any"
                value={soChon}
                onChange={(e) => setSoChon(e.target.value)}
                className={O_NHAP}
              />
            </label>
            <Button className={CHAM}
              variant="primary"
              disabled={dangGui || !loChon || !soChon}
              onClick={() =>
                goi("phan-lo", {
                  prescription_id: dong.id,
                  drug_batch_id: loChon,
                  so_luong: Number(soChon),
                })
              }
            >
              Chọn lô
            </Button>
          </div>
        )
      ) : null}
      {tt.chon_lo || dong.phan_lo.some((p) => p.thao_tac.doi) ? (
        <p className="text-meta text-ink-faint">
          “Có thể phân lô lúc này” là số hệ thống dùng để chống bán trùng: tồn vật lý trừ phần
          đang giữ cho lần chuyển khoản và phần đã bán chưa giao.
        </p>
      ) : null}

      {/* ── Luồng cũ: lần thu trước khi có phân lô ── */}
      {/* ── Giao không cần lô (28/09/2026): máy chủ quyết nút, kho trừ khi gán lô ── */}
      {tt.giao_khong_lo ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className={`${NHAN} w-28`}>
            Giao
            <input
              type="number"
              min="0"
              step="any"
              value={soKhongLo}
              onChange={(e) => setSoKhongLo(e.target.value)}
              className={O_NHAP}
            />
          </label>
          <Button
            className={CHAM}
            variant="primary"
            disabled={dangGui || !soKhongLo}
            onClick={() =>
              goi("dispense", { prescription_id: dong.id, so_luong: Number(soKhongLo) })
            }
          >
            Giao thuốc
          </Button>
          <span className="text-meta text-ink-muted">Chưa cần lô — gán lô sau ở Kho thuốc.</span>
        </div>
      ) : null}

      {tt.giao_luong_cu ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className={`${NHAN} flex-1`}>
            Lô thuốc
            <select value={loChon} onChange={(e) => setLoChon(e.target.value)} className={O_NHAP}>
              {dong.lo_goi_y.map((b) => (
                <option key={b.drug_batch_id} value={b.drug_batch_id}>
                  {b.batch_code} · HSD {fmtNgay(b.expiry_date)} · còn {fmtSo(b.ton_vat_ly)} {b.unit}
                </option>
              ))}
            </select>
          </label>
          <label className={`${NHAN} w-28`}>
            Số lượng
            <input
              type="number"
              min="0"
              step="any"
              value={soCu}
              onChange={(e) => setSoCu(e.target.value)}
              className={O_NHAP}
            />
          </label>
          <Button className={CHAM}
            variant="primary"
            disabled={dangGui || !loChon || !soCu}
            onClick={() =>
              goi("dispense", {
                prescription_id: dong.id,
                drug_batch_id: loChon,
                so_luong: Number(soCu),
              })
            }
          >
            Cấp thuốc
          </Button>
        </div>
      ) : null}

      {/* ── CP5: đã giao → khách trả thuốc (chỉ ghi nhận, chưa quyết xử lý) ── */}
      {dong.xuat.length > 0 ? (
        <div>
          <span className={NHAN}>Đã giao</span>
          <ul className="mt-1 divide-y divide-line rounded-control border border-line">
            {dong.xuat.map((x) => (
              <li key={x.dispense_txn_id} className="flex flex-wrap items-end gap-2 px-3 py-2">
                <span className="min-w-0 flex-1 text-body text-ink">
                  Lô {x.batch_code} · giao {fmtSo(x.so_luong)}
                  {x.da_tra > 0 ? ` · khách đã trả ${fmtSo(x.da_tra)}` : ""}
                </span>
                {x.thao_tac.tra ? (
                  <>
                    <label className={`${NHAN} w-24`}>
                      Khách trả
                      <input
                        type="number"
                        min="0"
                        max={x.con_tra}
                        step="any"
                        value={soTra[x.dispense_txn_id] ?? ""}
                        onChange={(e) =>
                          setSoTra((s) => ({ ...s, [x.dispense_txn_id]: e.target.value }))
                        }
                        className={O_NHAP}
                      />
                    </label>
                    <Button className={CHAM}
                      disabled={
                        dangGui || !soTra[x.dispense_txn_id] || lyDo.trim().length < 3
                      }
                      onClick={() =>
                        goi("khach-tra", {
                          dispense_txn_id: x.dispense_txn_id,
                          so_luong: Number(soTra[x.dispense_txn_id]),
                          ly_do: lyDo,
                        })
                      }
                    >
                      Ghi nhận khách trả
                    </Button>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
          {dong.xuat.some((x) => x.da_tra > 0) ? (
            <p className="mt-1 text-meta text-ink-faint">
              Thuốc khách trả đã về quầy nhưng CHƯA bán lại được — chờ quyết định xử lý của phòng
              khám. Ghi nhận khách trả không tự hoàn tiền.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* ── CP5: phần đã bán mà chưa giao ── */}
      {dong.chua_giao > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
          <span className="min-w-0 flex-1">
            Còn {fmtSo(dong.chua_giao)} {dong.unit ?? ""} đã bán mà chưa giao.
            {dong.can_hoan > 0
              ? ` Muốn thôi giao: Quản lý hoàn tiền ${fmtSo(dong.can_hoan)} ${dong.unit ?? ""} ở Lịch sử giao dịch (hoặc huỷ phiếu) trước.`
              : ""}
          </span>
          {tt.huy_chua_giao ? (
            <Button className={CHAM}
              variant="danger"
              disabled={dangGui || lyDo.trim().length < 1}
              onClick={() => goi("huy-phan-chua-giao", { prescription_id: dong.id, ly_do: lyDo })}
            >
              Huỷ phần chưa giao
            </Button>
          ) : null}
        </div>
      ) : null}

      {/* ── Lý do + khách không lấy / chốt ── */}
      {tt.tu_choi ||
      tt.chot ||
      tt.huy_chua_giao ||
      dong.xuat.some((x) => x.thao_tac.tra) ||
      dong.phan_lo.some((p) => p.thao_tac.bo || p.thao_tac.doi) ? (
        <div className="flex flex-wrap items-end gap-2 border-t border-line pt-3">
          <label className={`${NHAN} flex-1`}>
            Lý do (bắt buộc khi khách không lấy, bỏ lô, đổi lô, khách trả, huỷ phần chưa giao)
            <input
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              placeholder="Khách đã có thuốc ở nhà…"
              className={O_NHAP}
            />
          </label>
          {tt.tu_choi ? (
            <Button className={CHAM}
              variant="danger"
              disabled={dangGui || !lyDo.trim()}
              onClick={() => goi("refuse", { prescription_id: dong.id, ly_do: lyDo })}
            >
              Khách không lấy
            </Button>
          ) : null}
          {tt.chot ? (
            <Button className={CHAM}
              variant="ghost"
              disabled={dangGui}
              title="Dùng khi khách lấy một phần rồi thôi, hoặc đã giao đủ"
              onClick={() =>
                goi("close-line", { prescription_id: dong.id, ly_do: lyDo.trim() || null })
              }
            >
              Chốt — không giao thêm
            </Button>
          ) : null}
        </div>
      ) : null}

      {khongCoNutNao && !dong.closed && !chiXem ? (
        <p className="text-meta text-ink-faint">Chưa có thao tác nào ở giai đoạn này.</p>
      ) : null}

      {loi ? (
        <p className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
