"use client";

// Màn thử trợ lý AI. Bên trái: khung chat, nhân viên đóng vai khách. Bên phải:
// "bên trong" của nháp đang chọn — model, công cụ đã gọi + kết quả, lý do chuyển
// người, token. Nháp chỉ thành "đã gửi" khi người bấm Duyệt / Sửa; mọi thao tác
// hoàn tác được. Màn chỉ vẽ + gửi lệnh: luật chặn, công cụ, lưu do máy chủ làm.

import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import { fmtTime } from "@/lib/datetime";

interface Buoc {
  ten: string;
  tham_so: Record<string, unknown>;
  ket_qua: unknown;
}

interface Meta {
  buoc: Buoc[];
  chuyen_nguoi: boolean;
  ly_do_chuyen: string | null;
  ghi_chu_chuyen: string | null;
  chan_boi_code: string | null;
  model: string;
  phien_ban_loi_nhac: string;
  token_vao: number;
  token_ra: number;
  thoi_gian_ms: number;
  so_vong: number;
  loi: string | null;
}

interface Tin {
  id: string;
  thu_tu: number;
  vai: "khach" | "tro_ly" | "ket_qua_cong_cu";
  noi_dung: string;
  la_nhap: boolean;
  meta: Meta | null;
  duyet: "duyet" | "sua" | "chuyen" | null;
  noi_dung_gui: string | null;
  tao_luc: string;
}

interface HoiThoai {
  id: string;
  tieu_de: string | null;
  cap_nhat_luc: string;
  so_tin_khach?: number;
  so_nhap_cho?: number;
  tin?: Tin[];
}

const TEN_CONG_CU: Record<string, string> = {
  tra_gia_dich_vu: "Tra giá dịch vụ",
  thong_tin_phong_kham: "Giờ mở cửa & địa chỉ",
  lich_trong: "Khung giờ còn trống",
  chuyen_nguoi: "Chuyển cho nhân viên",
};

const TEN_LY_DO: Record<string, string> = {
  khan_cap: "Triệu chứng khẩn — chặn trước khi hỏi AI",
  y_khoa: "Câu hỏi cần bác sĩ — chặn trước khi hỏi AI",
  dat_lich: "Khách chốt lịch — nhân viên xác nhận",
  het_vong: "AI hỏi công cụ quá nhiều lần",
  mo_hinh_loi: "Không gọi được AI",
};

const TRANG_THAI: Record<string, { ten: string; tone: ChipTone }> = {
  nhap: { ten: "Nháp — chưa gửi", tone: "warning" },
  duyet: { ten: "Đã gửi", tone: "success" },
  sua: { ten: "Đã gửi bản sửa", tone: "success" },
  chuyen: { ten: "Đã chuyển nhân viên", tone: "info" },
};

async function goi<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(String(data.error ?? data.message ?? data.detail ?? `Lỗi ${res.status}`));
  }
  return data as T;
}

export default function TroLyThu() {
  const [bat, setBat] = useState<boolean | null>(null);
  const [dsMoHinh, setDsMoHinh] = useState<string[]>([]);
  const [moHinh, setMoHinh] = useState("");
  const [ds, setDs] = useState<HoiThoai[]>([]);
  const [ht, setHt] = useState<HoiThoai | null>(null);
  const [chon, setChon] = useState<string | null>(null);
  const [nhap, setNhap] = useState("");
  const [banSua, setBanSua] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const taiDs = useCallback(async () => {
    setDs(await goi<HoiThoai[]>("/api/tro-ly?xem=hoi-thoai"));
  }, []);

  const moHt = useCallback(async (id: string) => {
    const h = await goi<HoiThoai>(`/api/tro-ly?xem=hoi-thoai&id=${id}`);
    setHt(h);
    const cuoi = [...(h.tin ?? [])].reverse().find((t) => t.la_nhap);
    setChon(cuoi?.id ?? null);
    setBanSua(null);
  }, []);

  useEffect(() => {
    goi<{ bat: boolean; mo_hinh: string[] }>("/api/tro-ly?xem=trang-thai")
      .then(async (s) => {
        setBat(s.bat);
        setDsMoHinh(s.mo_hinh);
        setMoHinh(s.mo_hinh[0] ?? "");
        if (s.bat) await taiDs();
      })
      .catch((e: Error) => setLoi(e.message));
  }, [taiDs]);

  const lam = async (viec: () => Promise<void>) => {
    setLoi(null);
    try {
      await viec();
    } catch (e) {
      setLoi((e as Error).message);
    }
  };

  const taoMoi = () =>
    lam(async () => {
      const h = await goi<HoiThoai>("/api/tro-ly", { viec: "tao" });
      await taiDs();
      await moHt(h.id);
    });

  const guiTin = () =>
    lam(async () => {
      if (!ht || !nhap.trim()) return;
      setDangGui(true);
      try {
        const h = await goi<HoiThoai>("/api/tro-ly", {
          viec: "gui",
          id: ht.id,
          noi_dung: nhap,
          mo_hinh: moHinh || null,
        });
        setHt(h);
        setNhap("");
        setChon([...(h.tin ?? [])].reverse().find((t) => t.la_nhap)?.id ?? null);
        setBanSua(null);
        await taiDs();
      } finally {
        setDangGui(false);
      }
    });

  const duyet = (tin: Tin, hanhDong: "duyet" | "sua" | "chuyen" | "hoan_tac") =>
    lam(async () => {
      await goi("/api/tro-ly", {
        viec: "duyet",
        tin_id: tin.id,
        hanh_dong: hanhDong,
        noi_dung: hanhDong === "sua" ? banSua : null,
      });
      if (ht) await moHt(ht.id);
      await taiDs();
    });

  const tinHien = useMemo(
    () => (ht?.tin ?? []).filter((t) => t.vai === "khach" || t.la_nhap),
    [ht],
  );
  const dangChon = (ht?.tin ?? []).find((t) => t.id === chon) ?? null;

  if (bat === null && !loi) {
    return <p className="p-4 text-body text-ink-muted">Đang tải…</p>;
  }

  return (
    <div className="flex flex-col gap-4 p-4 lg:p-5">
      <header className="flex flex-wrap items-center gap-3">
        <div className="mr-auto">
          <h1 className="text-title text-ink">Thử trợ lý AI trả lời khách</h1>
          <p className="text-meta text-ink-muted">
            Bạn đóng vai khách nhắn tin. AI chỉ soạn nháp — không gửi gì ra ngoài.
          </p>
        </div>
        {bat && (
          <>
            <label className="flex items-center gap-2 text-body text-ink-muted">
              Model
              <OChon value={moHinh} onChange={(e) => setMoHinh(e.target.value)}>
                {dsMoHinh.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </OChon>
            </label>
            <Button variant="primary" onClick={taoMoi}>
              Cuộc trò chuyện mới
            </Button>
          </>
        )}
      </header>

      {loi && (
        <p role="alert" className="rounded-control bg-surface px-3 py-2 text-body text-ink">
          <Chip tone="danger">Lỗi</Chip> {loi}
        </p>
      )}

      {bat === false && (
        <section className="rounded-card border border-hairline bg-surface p-4 text-body text-ink">
          Trợ lý AI chưa được bật trên máy chủ. Nhờ người quản trị bật lên rồi tải lại
          trang.
        </section>
      )}

      {bat && (
        <div className="grid gap-4 lg:grid-cols-3">
          <section className="flex min-h-96 min-w-0 flex-col lg:col-span-2 rounded-card border border-hairline bg-surface">
            <div className="flex flex-wrap items-center gap-2 border-b border-hairline p-3">
              <OChon
                aria-label="Chọn cuộc trò chuyện"
                className="min-w-0 flex-1"
                value={ht?.id ?? ""}
                onChange={(e) => e.target.value && lam(() => moHt(e.target.value))}
              >
                <option value="">— Chọn cuộc trò chuyện —</option>
                {ds.map((h) => (
                  <option key={h.id} value={h.id}>
                    {(h.tieu_de ?? "Chưa có tin") +
                      (h.so_nhap_cho ? ` · ${h.so_nhap_cho} nháp chờ` : "")}
                  </option>
                ))}
              </OChon>
            </div>

            <ol className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
              {!ht && (
                <li className="text-body text-ink-muted">
                  Chọn hoặc tạo một cuộc trò chuyện để bắt đầu.
                </li>
              )}
              {ht && tinHien.length === 0 && (
                <li className="text-body text-ink-muted">
                  Gõ một tin như khách vẫn nhắn, ví dụ “kham phu khoa bao nhieu tien vay”.
                </li>
              )}
              {tinHien.map((t) =>
                t.vai === "khach" ? (
                  <li key={t.id} className="flex flex-col items-start gap-1">
                    <span className="text-meta text-ink-muted">Khách · {fmtTime(t.tao_luc)}</span>
                    <p className="max-w-xl whitespace-pre-wrap rounded-card bg-surface-muted px-3 py-2 text-body text-ink">
                      {t.noi_dung}
                    </p>
                  </li>
                ) : (
                  <li key={t.id} className="flex flex-col items-end gap-1">
                    <span className="flex items-center gap-2 text-meta text-ink-muted">
                      <Chip tone={TRANG_THAI[t.duyet ?? "nhap"].tone}>
                        {TRANG_THAI[t.duyet ?? "nhap"].ten}
                      </Chip>
                      Trợ lý
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setChon(t.id);
                        setBanSua(null);
                      }}
                      aria-pressed={t.id === chon}
                      className={`max-w-xl whitespace-pre-wrap rounded-card border px-3 py-2 text-left text-body text-ink ${
                        t.id === chon ? "border-brand-600 bg-surface" : "border-hairline bg-surface"
                      }`}
                    >
                      {t.duyet === "sua" && t.noi_dung_gui ? t.noi_dung_gui : t.noi_dung}
                    </button>
                  </li>
                ),
              )}
              {dangGui && <li className="text-meta text-ink-muted">AI đang soạn nháp…</li>}
            </ol>

            {ht && (
              <form
                className="flex gap-2 border-t border-hairline p-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void guiTin();
                }}
              >
                <textarea
                  aria-label="Tin nhắn của khách"
                  value={nhap}
                  onChange={(e) => setNhap(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void guiTin();
                    }
                  }}
                  rows={2}
                  placeholder="Gõ như khách nhắn Zalo…"
                  className="min-h-10 flex-1 resize-y rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
                />
                <Button type="submit" variant="primary" disabled={dangGui || !nhap.trim()}>
                  Gửi
                </Button>
              </form>
            )}
          </section>

          <BenTrong
            tin={dangChon}
            banSua={banSua}
            setBanSua={setBanSua}
            onDuyet={duyet}
          />
        </div>
      )}
    </div>
  );
}

function BenTrong({
  tin,
  banSua,
  setBanSua,
  onDuyet,
}: {
  tin: Tin | null;
  banSua: string | null;
  setBanSua: (v: string | null) => void;
  onDuyet: (t: Tin, h: "duyet" | "sua" | "chuyen" | "hoan_tac") => void;
}) {
  if (!tin || !tin.meta) {
    return (
      <aside className="rounded-card border border-hairline bg-surface p-4 text-body text-ink-muted">
        Bấm vào một câu trả lời của trợ lý để xem AI đã làm gì.
      </aside>
    );
  }
  const m = tin.meta;
  return (
    <aside className="flex flex-col gap-4 rounded-card border border-hairline bg-surface p-4">
      <section className="flex flex-col gap-2">
        <h2 className="text-emph text-ink">Duyệt nháp</h2>
        {tin.duyet === null ? (
          banSua === null ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => onDuyet(tin, "duyet")}>
                Duyệt — gửi nguyên văn
              </Button>
              <Button onClick={() => setBanSua(tin.noi_dung)}>Sửa rồi gửi</Button>
              <Button variant="ghost" onClick={() => onDuyet(tin, "chuyen")}>
                Chuyển nhân viên
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <textarea
                aria-label="Bản sửa"
                value={banSua}
                onChange={(e) => setBanSua(e.target.value)}
                rows={4}
                className="rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
              />
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={!banSua.trim()}
                  onClick={() => onDuyet(tin, "sua")}
                >
                  Gửi bản sửa
                </Button>
                <Button variant="ghost" onClick={() => setBanSua(null)}>
                  Thôi
                </Button>
              </div>
            </div>
          )
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone={TRANG_THAI[tin.duyet].tone}>{TRANG_THAI[tin.duyet].ten}</Chip>
            <Button size="sm" variant="ghost" onClick={() => onDuyet(tin, "hoan_tac")}>
              Hoàn tác
            </Button>
          </div>
        )}
      </section>

      {(m.chuyen_nguoi || m.loi) && (
        <section className="flex flex-col gap-1">
          <h2 className="text-emph text-ink">Vì sao chuyển nhân viên</h2>
          {m.ly_do_chuyen && (
            <p className="text-body text-ink">{TEN_LY_DO[m.ly_do_chuyen] ?? m.ly_do_chuyen}</p>
          )}
          {m.ghi_chu_chuyen && <p className="text-meta text-ink-muted">{m.ghi_chu_chuyen}</p>}
          {m.loi && <p className="text-meta text-ink-muted">Lỗi: {m.loi}</p>}
        </section>
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-emph text-ink">AI đã tra gì</h2>
        {m.buoc.length === 0 ? (
          <p className="text-body text-ink-muted">
            {m.chan_boi_code ? "Không hỏi AI — luật chặn trả lời ngay." : "Không tra công cụ nào."}
          </p>
        ) : (
          <ol className="flex flex-col gap-2">
            {m.buoc.map((b, i) => (
              <li key={i} className="rounded-control border border-hairline p-2">
                <p className="text-body font-semibold text-ink">{TEN_CONG_CU[b.ten] ?? b.ten}</p>
                {Object.keys(b.tham_so).length > 0 && (
                  <p className="text-meta text-ink-muted">Hỏi: {JSON.stringify(b.tham_so)}</p>
                )}
                <details>
                  <summary className="cursor-pointer text-meta text-ink-muted">Kết quả</summary>
                  <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap text-meta text-ink">
                    {JSON.stringify(b.ket_qua, null, 1)}
                  </pre>
                </details>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="grid grid-cols-2 gap-2 text-meta text-ink-muted">
        <span>Model</span>
        <span className="text-ink">{m.model || "—"}</span>
        <span>Lời nhắc</span>
        <span className="text-ink">{m.phien_ban_loi_nhac}</span>
        <span>Token vào / ra</span>
        <span className="tabular-nums text-ink">
          {m.token_vao} / {m.token_ra}
        </span>
        <span>Thời gian</span>
        <span className="tabular-nums text-ink">{(m.thoi_gian_ms / 1000).toFixed(1)} giây</span>
        <span>Số lượt hỏi AI</span>
        <span className="tabular-nums text-ink">{m.so_vong}</span>
      </section>
    </aside>
  );
}
