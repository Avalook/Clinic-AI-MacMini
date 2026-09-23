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
import Button, { buttonClass } from "@/components/ui/Button";

export interface MauKetQua {
  ma: string;
  ten: string;
  nhom?: string | null;
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
}

interface Phieu {
  id: string;
  form_id: string;
  version: number;
  trang_thai: "DRAFT" | "READY";
  dang_sua: boolean;
  revision: number;
  khung: Muc[];
  du_lieu: Record<string, { gia_tri: string; nguon: string }>;
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
}: {
  serviceOrderId: string;
  /** Mẫu kết quả đã gắn cho dịch vụ này. Rỗng = chưa ai gắn. */
  mau: MauKetQua[];
  /** Mẫu chọn sẵn (phiếu đang điền dở, hoặc mẫu gợi ý của phiếu khám v5). */
  mauMacDinh?: string | null;
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
    setGia(
      Object.fromEntries(
        Object.entries(p.du_lieu).map(([k, v]) => [k, v.gia_tri ?? ""]),
      ),
    );
  }, []);

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
            du_lieu: Object.fromEntries(
              Object.entries(moi)
                .filter(([, v]) => v !== "")
                .map(([k, v]) => [k, { gia_tri: v, nguon: "USER" }]),
            ),
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
      <p className="rounded-control border border-line bg-surface-muted px-3 py-2 text-sm text-ink-soft">
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
        <h3 className="text-sm font-semibold text-ink">Phiếu kết quả</h3>
        {mau.length > 1 ? (
          <label className="text-sm">
            <span className="sr-only">Chọn mẫu kết quả</span>
            <select
              value={chonMau ?? ""}
              onChange={(e) => setChonMau(e.target.value || null)}
              className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
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
          <span className="text-sm text-ink-muted">{mau[0].ten}</span>
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

      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-sm text-danger"
        >
          {loi}
        </p>
      ) : null}

      {!chonMau ? (
        <p className="text-sm text-ink-muted">Chọn mẫu để bắt đầu điền.</p>
      ) : phieu === null ? (
        <p className="text-sm text-ink-muted">Đang mở phiếu…</p>
      ) : daChot ? (
        <div className="space-y-2">
          <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-sm text-success">
            Phiếu đã hoàn tất — đây là kết quả chính thức.
          </p>
          <dl className="space-y-2 rounded-control bg-surface-muted px-3 py-2 text-sm">
            {phieu.khung.map((muc) =>
              (muc.block ?? []).map((o) => (
                <div key={o.ma}>
                  <dt className="text-xs font-semibold text-ink-muted">{o.ten}</dt>
                  <dd className="whitespace-pre-line text-ink">
                    {gia[o.ma] || "—"}
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
              <legend className="text-sm font-semibold text-ink">
                {muc.ten}
              </legend>
              <div className="mt-1 space-y-3">
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
            </fieldset>
          ))}

          {nguoiCoThe && nguoiCoThe.length > 0 ? (
            <label className="block">
              <span className="text-xs font-semibold text-ink">
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
                className="mt-1 min-h-10 w-full max-w-sm rounded-control border border-line bg-surface px-3 text-sm text-ink"
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
                <span className="text-xs font-semibold text-ink">
                  Vì sao sửa kết quả này
                </span>
                <input
                  value={lyDoSua}
                  onChange={(e) => setLyDoSua(e.target.value)}
                  placeholder="Ví dụ: nhầm bên phải/trái khi gõ kết luận"
                  className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
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
            {phieu.con_trong.length > 0 ? (
              <span className="text-label text-warning">
                Còn {phieu.con_trong.length} mục chưa điền — vẫn hoàn tất được.
              </span>
            ) : null}
            <span className="text-label text-ink-muted">
              Hoàn tất = xác nhận toàn bộ nội dung đang thấy, kể cả câu điền sẵn.
            </span>
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
    <span className="text-xs font-semibold text-ink">
      {o.ten}
      {nguon === "TEMPLATE_DEFAULT" ? (
        <span className="ml-2 font-normal text-ink-muted">(câu điền sẵn)</span>
      ) : null}
    </span>
  );

  if (o.kieu === "chon" && Array.isArray(o.chon)) {
    return (
      <label className="block">
        {nhan}
        <select
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          className="mt-1 min-h-10 w-full max-w-sm rounded-control border border-line bg-surface px-3 text-sm text-ink"
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
      <label className="block">
        {nhan}
        <textarea
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          rows={4}
          placeholder={o.goi_y ?? ""}
          className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink"
        />
      </label>
    );
  }

  return (
    <label className="block">
      {nhan}
      <input
        type={o.kieu === "so" ? "number" : o.kieu === "ngay" ? "date" : "text"}
        value={giaTri}
        onChange={(e) => onDoi(e.target.value)}
        placeholder={o.goi_y ?? ""}
        className="mt-1 min-h-10 w-full max-w-md rounded-control border border-line bg-surface px-3 text-sm text-ink"
      />
    </label>
  );
}
