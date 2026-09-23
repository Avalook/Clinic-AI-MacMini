"use client";

// Danh sách người bên trái, khối công việc bên phải.
//
// BẬT CẢ KHỐI, không tick từng quyền (Tuyền #133). Quyền con vẫn nằm dưới
// "▾ Chi tiết" để ai cần biết thì xem, nhưng không bắt quản lý phải hiểu.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import NhomQuyenMau from "./NhomQuyenMau";

interface Nguoi {
  id: string;
  ten: string;
  vai: string;
}

interface QuyenCon {
  ma: string;
  ten: string;
  rui_ro: string;
  chung_chi_lam_sang: boolean;
}

interface Khoi {
  ma: string;
  ten: string;
  mo_ta: string;
  quyen: QuyenCon[];
}

interface DanhMuc {
  khoi: Khoi[];
  preset: Record<string, string[]>;
}

interface QuyenCuaNguoi {
  khoi: { ma: string; ten: string; quyen: { quyen: string; ten: string }[] }[];
}

const MUC_RUI_RO: Record<string, string> = {
  operational: "vận hành",
  financial: "đụng tiền",
  clinical: "lâm sàng",
  admin: "quản trị",
};

export default function BangPhanQuyen({
  nhanSu,
  chonTruoc,
}: {
  nhanSu: Nguoi[];
  chonTruoc?: string;
}) {
  const [danhMuc, setDanhMuc] = useState<DanhMuc | null>(null);
  const [chon, setChon] = useState<Nguoi | null>(
    nhanSu.find((n) => n.id === chonTruoc) ?? nhanSu[0] ?? null,
  );
  const [dangCo, setDangCo] = useState<Set<string>>(new Set());
  const [bung, setBung] = useState<Set<string>>(new Set());
  const [dangLam, setDangLam] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [tim, setTim] = useState("");
  // Hai việc khác nhau trên cùng một màn: cấp quyền CHO MỘT NGƯỜI, và sửa các
  // NHÓM MẪU dùng để cấp cho nhanh. Gộp vào một danh sách là mời người dùng
  // tưởng sửa nhóm thì quyền của người cũng đổi theo.
  const [tab, setTab] = useState<"nguoi" | "nhom">("nguoi");

  useEffect(() => {
    let huy = false;
    void fetch("/api/phan-quyen", { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<DanhMuc>) : null))
      .then((kq) => {
        if (huy) return;
        if (kq) setDanhMuc(kq);
        else setLoi("Không đọc được danh mục quyền.");
      });
    return () => {
      huy = true;
    };
  }, []);

  const doc = useCallback(async (id: string): Promise<Set<string> | null> => {
    const r = await fetch(`/api/phan-quyen?staff=${id}`, { cache: "no-store" });
    if (!r.ok) return null;
    const kq = (await r.json()) as QuyenCuaNguoi;
    return new Set(kq.khoi.map((k) => k.ma));
  }, []);

  const docQuyen = useCallback(
    async (nguoi: Nguoi) => {
      const kq = await doc(nguoi.id);
      if (kq === null) {
        setLoi("Không đọc được quyền của người này.");
        return;
      }
      setLoi(null);
      setDangCo(kq);
    },
    [doc],
  );

  useEffect(() => {
    if (!chon) return;
    let huy = false;
    void doc(chon.id).then((kq) => {
      if (huy) return;
      if (kq === null) setLoi("Không đọc được quyền của người này.");
      else {
        setLoi(null);
        setDangCo(kq);
      }
    });
    return () => {
      huy = true;
    };
  }, [chon, doc]);

  const doiKhoi = async (khoi: Khoi, bat: boolean) => {
    if (!chon) return;
    setDangLam(khoi.ma);
    const r = await fetch("/api/phan-quyen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thao_tac: bat ? "cap" : "thu",
        staff_id: chon.id,
        du_lieu: { khoi: khoi.ma },
      }),
    });
    setDangLam(null);
    if (!r.ok) {
      const chi_tiet = (await r.json().catch(() => null)) as {
        message?: string;
        detail?: string;
      } | null;
      setLoi(chi_tiet?.message ?? chi_tiet?.detail ?? "Không đổi được quyền.");
      return;
    }
    await docQuyen(chon);
  };

  const themPreset = async (vai: string) => {
    if (!chon) return;
    setDangLam("preset");
    const r = await fetch("/api/phan-quyen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thao_tac: "them-preset",
        staff_id: chon.id,
        du_lieu: { vai },
      }),
    });
    setDangLam(null);
    if (!r.ok) {
      setLoi("Không thêm được preset.");
      return;
    }
    await docQuyen(chon);
  };

  const hienRa = nhanSu.filter((n) =>
    n.ten.toLocaleLowerCase("vi").includes(tim.trim().toLocaleLowerCase("vi")),
  );

  if (tab === "nhom") {
    return (
      <div className="grid gap-4">
        <ThanhChon tab={tab} onDoi={setTab} />
        <NhomQuyenMau
          khoiCo={(danhMuc?.khoi ?? []).map((k) => ({ ma: k.ma, ten: k.ten }))}
        />
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
      <div className="lg:col-span-2">
        <ThanhChon tab={tab} onDoi={setTab} />
      </div>
      <section
        aria-label="Nhân sự"
        className="rounded-card bg-surface-muted p-3 shadow-card"
      >
        <input
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tìm tên…"
          className="min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
        />
        <ul className="mt-2 flex max-h-[32rem] flex-col gap-1 overflow-y-auto">
          {hienRa.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => setChon(n)}
                aria-current={chon?.id === n.id}
                className={`w-full rounded-control px-3 py-2 text-left text-sm ${
                  chon?.id === n.id
                    ? "bg-brand-50 font-semibold text-brand-700"
                    : "text-ink hover:bg-surface"
                }`}
              >
                {n.ten}
                <span className="block text-label text-ink-muted">{n.vai}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-label="Khối công việc"
        className="rounded-card bg-surface-muted p-3.5 shadow-card"
      >
        {loi ? (
          <p role="alert" className="mb-2 text-sm text-danger">
            {loi}
          </p>
        ) : null}

        {chon === null || danhMuc === null ? (
          <p className="text-sm text-ink-muted">Chọn một người để xem quyền.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-ink">{chon.ten}</h2>
                <p className="text-label text-ink-muted">
                  Vai {chon.vai} — vai chỉ là gợi ý, không phải giới hạn.
                </p>
              </div>
              <Button
                type="button"
                variant="secondary"
                disabled={dangLam !== null}
                onClick={() => void themPreset(chon.vai)}
              >
                {dangLam === "preset"
                  ? "Đang thêm…"
                  : `+ Thêm preset ${chon.vai}`}
              </Button>
            </div>

            <ul className="mt-3 flex flex-col gap-2">
              {danhMuc.khoi.map((k) => {
                const co = dangCo.has(k.ma);
                const daBung = bung.has(k.ma);
                return (
                  <li
                    key={k.ma}
                    className="rounded-control border border-line bg-surface px-3 py-2.5"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">{k.ten}</p>
                        <p className="text-label text-ink-muted">{k.mo_ta}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setBung((cu) => {
                              const moi = new Set(cu);
                              if (moi.has(k.ma)) moi.delete(k.ma);
                              else moi.add(k.ma);
                              return moi;
                            })
                          }
                          className="rounded-chip px-2 py-1 text-label text-ink-muted hover:bg-surface-muted"
                        >
                          {daBung ? "▴ Thu gọn" : "▾ Chi tiết"}
                        </button>
                        <Button
                          type="button"
                          variant={co ? "secondary" : "primary"}
                          disabled={dangLam !== null}
                          onClick={() => void doiKhoi(k, !co)}
                        >
                          {dangLam === k.ma
                            ? "Đang lưu…"
                            : co
                              ? "Đang bật — tắt"
                              : "Bật khối này"}
                        </Button>
                      </div>
                    </div>

                    {daBung ? (
                      <ul className="mt-2 flex flex-col gap-1 border-t border-line pt-2">
                        {k.quyen.map((q) => (
                          <li key={q.ma} className="text-label text-ink-muted">
                            {q.ten}
                            <span className="ml-1 text-ink-muted">
                              ({MUC_RUI_RO[q.rui_ro] ?? q.rui_ro}
                              {q.chung_chi_lam_sang
                                ? " · cần chứng chỉ hành nghề"
                                : ""}
                              )
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}

/** Đổi giữa "cấp cho một người" và "sửa nhóm mẫu". */
function ThanhChon({
  tab,
  onDoi,
}: {
  tab: "nguoi" | "nhom";
  onDoi: (t: "nguoi" | "nhom") => void;
}) {
  const nut = (ma: "nguoi" | "nhom", chu: string) => (
    <button
      type="button"
      onClick={() => onDoi(ma)}
      aria-current={tab === ma}
      className={`min-h-10 rounded-control px-4 text-sm ${
        tab === ma
          ? "bg-brand-600 font-semibold text-white"
          : "border border-line bg-surface text-ink-soft hover:bg-surface-muted"
      }`}
    >
      {chu}
    </button>
  );
  return (
    <div className="flex flex-wrap gap-2">
      {nut("nguoi", "Quyền của từng người")}
      {nut("nhom", "Nhóm quyền mẫu")}
    </div>
  );
}
