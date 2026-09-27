"use client";

// PHIẾU KẾT QUẢ — một màn điền cho MỌI biểu mẫu.
//
// Không có "màn siêu âm", "màn xét nghiệm", "màn thủ thuật" riêng. Máy chủ trả
// về `khung` (mục → ô), màn này vẽ đúng cái khung ấy. Phòng khám đưa ruột 18
// mẫu sau thì chỉ thêm ô vào dữ liệu — tệp này không phải sửa một dòng nào.
//
// Ba điều màn này phải nói ra, vì chúng là luật chứ không phải chi tiết:
//
//   "Đã lưu 10:32"   nháp tự lưu, và nháp KHÔNG phải kết quả — chưa ai chịu
//                    trách nhiệm về nó.
//   [Hoàn tất]       xác nhận TOÀN BỘ nội dung đang thấy, kể cả câu mẫu không
//                    ai sửa. Đây là lúc người nhận trách nhiệm — và là nút
//                    DUY NHẤT kết thúc: nó đóng luôn dịch vụ đang làm dở và
//                    phát "đã có kết quả" nếu dịch vụ có kết quả ngay tại
//                    phòng (ChatGPT tin số 156, Tuyền tin số 157 "nút chỉ 1").
//   "còn N mục…"     nhắc, KHÔNG chặn. Bắt buộc chuyên môn chỉ bật khi phòng
//                    khám chốt, không phải khi lập trình viên thấy nên thế.
//
// Người gõ ≠ người thực hiện: điều dưỡng nhập thay bác sĩ là chuyện thường
// ngày, nên có ô chọn riêng "người thực hiện" chứ không suy từ ai đăng nhập.
//
// HOÀN TẤT RỒI VẪN SỬA ĐƯỢC (Tuyền 23/09: *"vẫn cho sửa được vì audit log
// được mà"*). [Sửa lại] → gõ → [Xác nhận sửa], kèm LÝ DO bắt buộc. Đổi ý giữa
// chừng thì [Huỷ sửa].
//
// TRONG SUỐT LÚC SỬA, BẢN CŨ VẪN LÀ KẾT QUẢ CHÍNH THỨC — và từ 23/09 câu này
// là sự thật chứ không còn là lời hứa: tự lưu ghi vào `du_lieu_dang_sua`, bản
// chính thức `du_lieu` đứng yên tới lúc chốt. Trước đó tự lưu ghi thẳng vào
// bản chính thức, nên câu trên màn sai ngay từ phím đầu tiên.

import { useCallback, useEffect, useRef, useState } from "react";

import { nhanLoi } from "@/lib/loi-api";
import { tenMucHien } from "@/lib/sua-mau";
import Button, { buttonClass } from "@/components/ui/Button";
import OSo from "@/components/ui/OSo";

export interface MauKetQua {
  ma: string;
  ten: string;
  nhom?: string | null;
  /** Mẫu của CHÍNH dịch vụ đang làm (máy chủ tính). false = của dịch vụ khác. */
  cua_dich_vu?: boolean;
}

interface O {
  ma: string;
  ten: string;
  kieu: string;
  mac_dinh?: string;
  goi_y?: string;
  chon?: string[];
}

interface Muc {
  ma: string;
  ten: string;
  block: O[];
  /** Mục dạng BẢNG (mẫu v3, 26/09/2026): Thai A | Thai B, trái | phải… Giá trị
   *  một ô là {ma_cột: giá trị} — lưu theo `ma`, không theo vị trí. */
  cot?: { ma: string; ten: string }[];
}

/** Ô chiếm nửa hàng hay trọn hàng trong lưới hai cột: đoạn văn và ô bảng
 *  (nhiều cột ghép một dòng) chiếm trọn hàng. */
function lopCot(o: { kieu: string }, laBang: boolean): string {
  return o.kieu === "doan_van" || laBang ? "md:col-span-2" : "";
}

/** Khoá phẳng của một ô bảng trong trạng thái màn hình. */
const KHOA_BANG = "::";

/** Máy chủ → màn: ô bảng {cột: giá trị} tách thành các khoá `ma::cột`. */
function tachGiaTri(
  duLieu: Record<string, { gia_tri: unknown; nguon: string }>,
): Record<string, string> {
  const ra: Record<string, string> = {};
  for (const [k, v] of Object.entries(duLieu)) {
    const g = v.gia_tri;
    if (g && typeof g === "object" && !Array.isArray(g)) {
      for (const [c, x] of Object.entries(g as Record<string, unknown>)) {
        ra[`${k}${KHOA_BANG}${c}`] = x == null ? "" : String(x);
      }
    } else ra[k] = g == null ? "" : String(g);
  }
  return ra;
}

/** Màn → máy chủ: gộp `ma::cột` về {ma: {gia_tri: {cột: giá trị}}}; bỏ ô rỗng. */
function gopGiaTri(
  moi: Record<string, string>,
): Record<string, { gia_tri: unknown; nguon: string }> {
  const ra: Record<string, { gia_tri: unknown; nguon: string }> = {};
  const bang: Record<string, Record<string, string>> = {};
  for (const [k, v] of Object.entries(moi)) {
    if (v === "") continue;
    const i = k.indexOf(KHOA_BANG);
    if (i < 0) ra[k] = { gia_tri: v, nguon: "USER" };
    else (bang[k.slice(0, i)] ??= {})[k.slice(i + KHOA_BANG.length)] = v;
  }
  for (const [k, cot] of Object.entries(bang)) ra[k] = { gia_tri: cot, nguon: "USER" };
  return ra;
}

interface Phieu {
  id: string;
  form_id: string;
  version: number;
  trang_thai: "DRAFT" | "READY";
  dang_sua: boolean;
  revision: number;
  khung: Muc[];
  du_lieu: Record<string, { gia_tri: unknown; nguon: string }>;
  con_trong: string[];
  /** Người thực hiện của BẢN ĐANG SỬA — tải lại trang không mất lựa chọn. */
  thuc_hien_boi: string | null;
}

/** Khoảng lặng trước khi tự lưu. Gõ liên tục thì không bắn từng phím. */
const CHO_TU_LUU_MS = 1500;

async function goi<T>(
  than: Record<string, unknown>,
): Promise<{ ok: true; data: T } | { ok: false; loi: string }> {
  try {
    const r = await fetch("/api/phieu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Không lưu được phiếu.") };
    return { ok: true, data: d as T };
  } catch {
    return { ok: false, loi: "Mất kết nối — nội dung CHƯA được lưu." };
  }
}

function gioVn(iso: string): string {
  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function PhieuKetQua({
  serviceOrderId,
  mau,
  mauMacDinh,
  nguoiCoThe,
  onHoanTat,
  onCacBen,
}: {
  serviceOrderId: string;
  /** Mẫu kết quả đã gắn cho dịch vụ này. Rỗng = chưa ai gắn. */
  mau: MauKetQua[];
  /** Mẫu chọn sẵn (phiếu đang điền dở, hoặc mẫu gợi ý của phiếu khám v5). */
  mauMacDinh?: string | null;
  /** Mẫu HAI BÊN (mục bảng đầu tiên: Thai A | Thai B, trái | phải…) → tên các
   *  bên, để màn phòng dựng hai ô tải riêng (26/09/2026). null = mẫu một bên. */
  onCacBen?: (ben: string[] | null) => void;
  /** Danh sách chọn "người thực hiện". Bỏ trống thì mặc định là người gõ. */
  nguoiCoThe?: { id: string; ten: string }[];
  /** Phiếu vừa hoàn tất — màn cha nạp lại hàng chờ. */
  onHoanTat?: (ketQua: {
    daDongDichVu: boolean;
    viSao: string | null;
    laLanSua: boolean;
  }) => void;
}) {
  const [chonMau, setChonMau] = useState<string | null>(
    mauMacDinh && mau.some((m) => m.ma === mauMacDinh)
      ? mauMacDinh
      : mau.length === 1
        ? mau[0].ma
        : null,
  );
  const [phieu, setPhieu] = useState<Phieu | null>(null);
  const [gia, setGia] = useState<Record<string, string>>({});
  const [thucHienBoi, setThucHienBoi] = useState<string>("");
  // Sửa một kết quả ĐÃ IN RA GIẤY VÀ GIAO CHO KHÁCH mà không nói vì sao là để
  // lại một câu hỏi không ai trả lời được. Máy chủ cũng từ chối nếu bỏ trống.
  const [lyDoSua, setLyDoSua] = useState("");
  const [luuLuc, setLuuLuc] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [dangHoanTat, setDangHoanTat] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Chọn mẫu của dịch vụ KHÁC (Tuyền 24/09/2026): không chuyển phiếu, báo khách
  // chưa thanh toán dịch vụ ấy — muốn làm thì bác sĩ chỉ định + khách trả tiền.
  const [baoKhacDv, setBaoKhacDv] = useState<string | null>(null);

  // Revision giữ trong ref: mỗi lần tự lưu phải gửi số MỚI NHẤT, không phải số
  // mà closure của lần gõ trước nhìn thấy.
  const revision = useRef(0);
  const hen = useRef<ReturnType<typeof setTimeout> | null>(null);

  const nhan = useCallback((p: Phieu) => {
    revision.current = p.revision;
    setPhieu(p);
    // Máy chủ là nguồn: đang sửa thì trả lựa chọn của bản nháp, chưa sửa thì
    // trả lựa chọn của bản chính thức.
    setThucHienBoi(p.thuc_hien_boi ?? "");
    setGia(tachGiaTri(p.du_lieu));
  }, []);

  useEffect(() => {
    const bang = phieu?.khung.find((m) => m.cot && m.cot.length > 1);
    onCacBen?.(bang?.cot ? bang.cot.map((c) => c.ten) : null);
  }, [phieu, onCacBen]);

  useEffect(() => {
    if (!chonMau) return;
    let huy = false;
    void goi<Phieu>({
      thao_tac: "mo",
      du_lieu: { service_order_id: serviceOrderId, form_id: `KQ_${chonMau}` },
    }).then((kq) => {
      if (huy) return;
      if (kq.ok) {
        setLoi(null);
        nhan(kq.data);
      } else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [chonMau, serviceOrderId, nhan]);

  // Gỡ hẹn khi rời màn: một lần tự lưu bắn sau khi component đã chết là một
  // lần ghi đè mà không ai nhìn thấy kết quả.
  useEffect(() => {
    return () => {
      if (hen.current) clearTimeout(hen.current);
    };
  }, []);

  const tuLuu = useCallback(
    (moi: Record<string, string>, p: Phieu, nguoi: string) => {
      if (hen.current) clearTimeout(hen.current);
      hen.current = setTimeout(() => {
        setDangLuu(true);
        void goi<{ revision: number; luu_luc: string }>({
          thao_tac: "luu",
          phieu_id: p.id,
          du_lieu: {
            expected_revision: revision.current,
            thuc_hien_boi: nguoi || null,
            du_lieu: gopGiaTri(moi),
          },
        }).then((kq) => {
          setDangLuu(false);
          if (!kq.ok) {
            setLoi(kq.loi);
            return;
          }
          setLoi(null);
          revision.current = kq.data.revision;
          setLuuLuc(kq.data.luu_luc);
        });
      }, CHO_TU_LUU_MS);
    },
    [],
  );

  const doi = (maO: string, v: string) => {
    if (!phieu) return;
    const moi = { ...gia, [maO]: v };
    setGia(moi);
    tuLuu(moi, phieu, thucHienBoi);
  };

  const hoanTat = async () => {
    if (!phieu) return;
    if (hen.current) clearTimeout(hen.current);
    setDangHoanTat(true);
    setLoi(null);
    // Lưu lần cuối trước khi chốt: nội dung vừa gõ chưa kịp tới máy chủ mà
    // bấm Hoàn tất thì phiếu chốt thiếu đúng câu vừa viết.
    const luu = await goi<{ revision: number; luu_luc: string }>({
      thao_tac: "luu",
      phieu_id: phieu.id,
      du_lieu: {
        expected_revision: revision.current,
        thuc_hien_boi: thucHienBoi || null,
        du_lieu: Object.fromEntries(
          Object.entries(gia)
            .filter(([, v]) => v !== "")
            .map(([k, v]) => [k, { gia_tri: v, nguon: "USER" }]),
        ),
      },
    });
    if (!luu.ok) {
      setDangHoanTat(false);
      setLoi(luu.loi);
      return;
    }
    revision.current = luu.data.revision;

    const kq = await goi<{
      con_trong: string[];
      revision: number;
      la_lan_sua?: boolean;
      dich_vu?: { da_dong: boolean; vi_sao: string | null };
    }>({
      thao_tac: "hoan-tat",
      phieu_id: phieu.id,
      du_lieu: {
        expected_revision: revision.current,
        thuc_hien_boi: thucHienBoi || null,
        ly_do_sua: lyDoSua.trim() || null,
      },
    });
    setDangHoanTat(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    revision.current = kq.data.revision;
    setPhieu({
      ...phieu,
      trang_thai: "READY",
      dang_sua: false,
      revision: kq.data.revision,
    });
    onHoanTat?.({
      daDongDichVu: kq.data.dich_vu?.da_dong ?? false,
      viSao: kq.data.dich_vu?.vi_sao ?? null,
      laLanSua: kq.data.la_lan_sua ?? false,
    });
  };

  // NHẬN TOÀN BỘ PHIẾU TỪ MÁY CHỦ, không tự suy ra từ state đang có.
  //
  // Bản trước chỉ lấy `revision` rồi giữ nguyên nội dung trên màn. Khoảng hở ấy
  // chết người: A mở sửa và gõ vài ô; B vẫn đang nhìn bản cũ, bấm [Sửa lại],
  // nhận SỐ mới nhưng NỘI DUNG cũ — rồi lần tự lưu kế tiếp của B ghi đè những
  // gì A vừa gõ, bằng đúng một số hợp lệ nên không lớp nào bắt được.
  const moSua = async () => {
    if (!phieu) return;
    setDangHoanTat(true);
    setLoi(null);
    const kq = await goi<Phieu>({ thao_tac: "mo-sua", phieu_id: phieu.id });
    setDangHoanTat(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    nhan(kq.data);
  };

  const huySua = async () => {
    if (!phieu) return;
    if (hen.current) clearTimeout(hen.current);
    setDangHoanTat(true);
    setLoi(null);
    const kq = await goi<{ revision: number }>({
      thao_tac: "huy-sua",
      phieu_id: phieu.id,
      // Bản nháp là của CHUNG: huỷ bằng số cũ là xoá cái người khác vừa gõ.
      du_lieu: { expected_revision: revision.current },
    });
    setDangHoanTat(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    revision.current = kq.data.revision;
    setLyDoSua("");
    // Quay về bản chính thức — nó chưa từng bị đụng tới.
    void goi<Phieu>({
      thao_tac: "mo",
      du_lieu: { service_order_id: serviceOrderId, form_id: `KQ_${chonMau}` },
    }).then((r) => {
      if (r.ok) nhan(r.data);
    });
  };

  if (mau.length === 0) {
    return (
      <p className="rounded-control border border-line bg-surface-muted px-3 py-2 text-body text-ink-soft">
        Dịch vụ này chưa gắn mẫu kết quả nào. Quản lý gắn ở màn danh mục mẫu,
        rồi phiếu sẽ hiện ở đây.
      </p>
    );
  }

  const daChot = phieu?.trang_thai === "READY" && !phieu.dang_sua;
  const dangSuaLai = phieu?.trang_thai === "READY" && phieu.dang_sua;

  return (
    <section aria-label="Phiếu kết quả" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-body font-semibold text-ink">Phiếu kết quả</h3>
        {mau.length > 1 ? (
          <label className="text-body">
            <span className="sr-only">Chọn mẫu kết quả</span>
            <select
              value={chonMau ?? ""}
              onChange={(e) => {
                const ma = e.target.value || null;
                const m = mau.find((x) => x.ma === ma);
                if (m && m.cua_dich_vu === false) {
                  setBaoKhacDv(
                    `“${m.ten}” là dịch vụ khác — khách chưa thanh toán dịch vụ này. ` +
                      "Muốn làm thì bác sĩ chỉ định và khách thanh toán trước.",
                  );
                  return;
                }
                setBaoKhacDv(null);
                setChonMau(ma);
              }}
              className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink"
            >
              <option value="">— chọn mẫu —</option>
              {mau.map((m) => (
                <option key={m.ma} value={m.ma}>
                  {m.ten}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="text-body text-ink-muted">{mau[0].ten}</span>
        )}
        {dangSuaLai ? (
          <span className="text-label font-semibold text-warning">
            Đang sửa lại — bản cũ vẫn là kết quả chính thức
          </span>
        ) : null}
        {dangLuu ? (
          <span className="text-label text-ink-muted">Đang lưu…</span>
        ) : luuLuc && !daChot ? (
          <span className="text-label text-ink-muted">
            Đã lưu {gioVn(luuLuc)} · nháp, chưa phải kết quả
          </span>
        ) : null}
      </div>

      {baoKhacDv ? (
        <p
          role="alert"
          className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning"
        >
          {baoKhacDv}
        </p>
      ) : null}
      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-body text-danger"
        >
          {loi}
        </p>
      ) : null}

      {!chonMau ? (
        <p className="text-body text-ink-muted">Chọn mẫu để bắt đầu điền.</p>
      ) : phieu === null ? (
        <p className="text-body text-ink-muted">Đang mở phiếu…</p>
      ) : daChot ? (
        <div className="space-y-2">
          <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-body text-success">
            Phiếu đã hoàn tất — đây là kết quả chính thức.
          </p>
          <dl className="grid gap-x-4 gap-y-2 rounded-control bg-surface-muted px-3 py-2 text-body md:grid-cols-2">
            {phieu.khung.map((muc) =>
              (muc.block ?? []).map((o) => (
                <div key={o.ma} className={lopCot(o, !!muc.cot)}>
                  <dt className="text-meta font-semibold text-ink-muted">{o.ten}</dt>
                  <dd className="whitespace-pre-line text-ink">
                    {muc.cot
                      ? muc.cot
                          .map((c) => `${c.ten}: ${gia[`${o.ma}${KHOA_BANG}${c.ma}`] || "—"}`)
                          .join(" · ")
                      : gia[o.ma] || "—"}
                  </dd>
                </div>
              )),
            )}
          </dl>
          <Button
            size="md"
            variant="secondary"
            disabled={dangHoanTat}
            onClick={() => void moSua()}
          >
            {dangHoanTat ? "Đang mở…" : "Sửa lại"}
          </Button>
          <a
            href={`/print/ket-qua/${serviceOrderId}`}
            target="_blank"
            rel="noopener"
            className={`ml-2 ${buttonClass("ghost", "md")}`}
          >
            In phiếu
          </a>
          <p className="text-label text-ink-muted">
            Sửa được, và mỗi lần sửa đều được ghi lại — ai sửa, lúc nào, bản thứ
            mấy.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {phieu.khung.map((muc) => (
            <fieldset key={muc.ma} className="min-w-0">
              {/* Tên mục giữ chỗ / rỗng (mẫu cũ) thì không vẽ tiêu đề — 27/09. */}
              {tenMucHien(muc.ten) ? (
                <legend className="text-body font-semibold text-ink">
                  {tenMucHien(muc.ten)}
                </legend>
              ) : null}
              {muc.cot ? (
                <BangMuc muc={muc} cot={muc.cot} gia={gia} onDoi={doi} />
              ) : (
                // HAI CỘT ở màn rộng, MỘT cột ở 375 (27/09/2026 — bản mẫu
                // `luoi hai`); đoạn văn chiếm trọn hàng.
                <div className="mt-1 grid gap-3 md:grid-cols-2">
                  {(muc.block ?? []).map((o) => (
                    <OPhieu
                      key={o.ma}
                      o={o}
                      giaTri={gia[o.ma] ?? ""}
                      nguon={phieu.du_lieu[o.ma]?.nguon ?? null}
                      onDoi={(v) => doi(o.ma, v)}
                    />
                  ))}
                </div>
              )}
            </fieldset>
          ))}

          {nguoiCoThe && nguoiCoThe.length > 0 ? (
            <label className="block">
              <span className="text-meta font-semibold text-ink">
                Người thực hiện (khác người đang gõ thì chọn lại)
              </span>
              <select
                value={thucHienBoi}
                onChange={(e) => {
                  const ai = e.target.value;
                  setThucHienBoi(ai);
                  // Người thực hiện là DỮ LIỆU NGHIỆP VỤ, không phải trạng
                  // thái màn hình. Không lưu thì đổi lựa chọn rồi tải lại
                  // trang là mất — tự lưu mới lưu nửa cái phiếu.
                  if (phieu) tuLuu(gia, phieu, ai);
                }}
                className="mt-1 min-h-10 w-full max-w-sm rounded-control border border-line bg-surface px-3 text-body text-ink"
              >
                <option value="">— tôi, người đang gõ —</option>
                {nguoiCoThe.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.ten}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            {dangSuaLai ? (
              <label className="w-full">
                <span className="text-meta font-semibold text-ink">
                  Vì sao sửa kết quả này
                </span>
                <input
                  value={lyDoSua}
                  onChange={(e) => setLyDoSua(e.target.value)}
                  placeholder="Ví dụ: nhầm bên phải/trái khi gõ kết luận"
                  className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
                />
              </label>
            ) : null}
            <Button
              size="md"
              variant="primary"
              // KHÔNG khoá nút khi chưa gõ lý do. Máy chủ hỏi "có đổi gì
              // không" TRƯỚC rồi mới đòi lý do; khoá ở đây là bắt người ta gõ
              // lý do cho một thay đổi không tồn tại, rồi mới được nghe câu
              // "thực ra không thay gì". Frontend không dựng bộ so thứ hai.
              disabled={dangHoanTat}
              onClick={() => void hoanTat()}
            >
              {dangHoanTat
                ? "Đang chốt…"
                : dangSuaLai
                  ? "Xác nhận sửa"
                  : "Hoàn tất phiếu"}
            </Button>
            {dangSuaLai ? (
              <Button
                size="md"
                variant="ghost"
                disabled={dangHoanTat}
                onClick={() => void huySua()}
              >
                Huỷ sửa
              </Button>
            ) : null}
            {/* In được cả khi chưa Hoàn tất — trang in ghi rõ BẢN NHÁP. */}
            <a
              href={`/print/ket-qua/${serviceOrderId}`}
              target="_blank"
              rel="noopener"
              className={buttonClass("ghost", "md")}
            >
              In phiếu
            </a>
          </div>
        </div>
      )}
    </section>
  );
}

function OPhieu({
  o,
  giaTri,
  nguon,
  onDoi,
}: {
  o: O;
  giaTri: string;
  nguon: string | null;
  onDoi: (v: string) => void;
}) {
  const nhan = (
    <span className="text-meta font-semibold text-ink">
      {o.ten}
      {nguon === "TEMPLATE_DEFAULT" ? (
        <span className="ml-2 font-normal text-ink-muted">(câu điền sẵn)</span>
      ) : null}
    </span>
  );

  if (o.kieu === "chon" && Array.isArray(o.chon)) {
    return (
      <label className="block min-w-0">
        {nhan}
        <select
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
        >
          <option value="">— chưa chọn —</option>
          {o.chon.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (o.kieu === "doan_van") {
    return (
      <label className="block min-w-0 md:col-span-2">
        {nhan}
        <textarea
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          rows={4}
          placeholder={o.goi_y ?? ""}
          className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
        />
      </label>
    );
  }

  // Ô số (27/09/2026, `components/ui/OSo`): trước là `type="number"` — chặn
  // "12 x 8", lăn chuột lướt qua đổi số, bước 1 làm sai số thập phân. Phiếu kết
  // quả lưu chữ nguyên văn nên cho gõ kích thước.
  if (o.kieu === "so") {
    const donVi = o.goi_y && o.goi_y.length <= 16 ? o.goi_y : null;
    return (
      <label className="block">
        {nhan}
        <span className="mt-1 flex">
          <OSo
            kichThuoc
            value={giaTri}
            onChange={onDoi}
            donVi={donVi}
            placeholder={donVi ? undefined : (o.goi_y ?? "")}
          />
        </span>
      </label>
    );
  }

  return (
    <label className="block min-w-0">
      {nhan}
      <span className="mt-1 flex items-center gap-2">
        <input
          type={o.kieu === "ngay" ? "date" : "text"}
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          placeholder={o.goi_y ?? ""}
          className="min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
        />
        {o.goi_y && o.goi_y.length <= 16 ? (
          <span className="shrink-0 text-meta text-ink-muted">{o.goi_y}</span>
        ) : null}
      </span>
    </label>
  );
}

/** Mục dạng BẢNG (mẫu v3): hàng = ô của mục, cột = Thai A | Thai B, trái | phải… */
function BangMuc({
  muc,
  cot,
  gia,
  onDoi,
}: {
  muc: Muc;
  cot: { ma: string; ten: string }[];
  gia: Record<string, string>;
  onDoi: (ma: string, v: string) => void;
}) {
  const oNhap = (o: O, c: { ma: string; ten: string }) => {
    const khoa = `${o.ma}${KHOA_BANG}${c.ma}`;
    const nhanO = `${o.ten} — ${c.ten}`;
    if (o.kieu === "chon" && Array.isArray(o.chon)) {
      return (
        <select
          aria-label={nhanO}
          value={gia[khoa] ?? ""}
          onChange={(e) => onDoi(khoa, e.target.value)}
          className="min-h-10 w-full rounded-control border border-line bg-surface px-2 text-body text-ink"
        >
          <option value="">—</option>
          {o.chon.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </select>
      );
    }
    if (o.kieu === "doan_van") {
      return (
        <textarea
          aria-label={nhanO}
          value={gia[khoa] ?? ""}
          onChange={(e) => onDoi(khoa, e.target.value)}
          rows={2}
          className="w-full rounded-control border border-line bg-surface px-2 py-1.5 text-body text-ink"
        />
      );
    }
    if (o.kieu === "so") {
      return (
        <OSo
          kichThuoc
          rong="day"
          aria-label={nhanO}
          value={gia[khoa] ?? ""}
          onChange={(v) => onDoi(khoa, v)}
        />
      );
    }
    return (
      <input
        aria-label={nhanO}
        value={gia[khoa] ?? ""}
        onChange={(e) => onDoi(khoa, e.target.value)}
        placeholder={o.goi_y ?? ""}
        className="min-h-10 w-full rounded-control border border-line bg-surface px-2 text-body text-ink"
      />
    );
  };
  return (
    <div className="mt-1 overflow-x-auto">
      <table className="w-full min-w-[28rem] border-collapse text-body">
        <thead>
          <tr className="text-left text-meta text-ink-muted">
            <th className="py-1.5 pr-3 font-medium">{muc.ten}</th>
            {cot.map((c) => (
              <th key={c.ma} className="py-1.5 pr-3 font-medium">
                {c.ten}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {(muc.block ?? []).map((o) => (
            <tr key={o.ma}>
              <td className="py-1.5 pr-3 align-top text-ink">
                {o.ten}
                {o.goi_y ? <span className="ml-1 text-meta text-ink-muted">({o.goi_y})</span> : null}
              </td>
              {cot.map((c) => (
                <td key={c.ma} className="py-1.5 pr-3 align-top">
                  {oNhap(o, c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
