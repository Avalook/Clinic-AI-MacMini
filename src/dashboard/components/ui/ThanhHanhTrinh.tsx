/**
 * Thanh HÀNH TRÌNH nhiều mốc nằm ngang — đúng hình bản mẫu "Việc của đối tác" (Tuyền
 * duyệt 05/11/2026, `.ht/.htn` của bản mẫu): chấm nhỏ, đường nối mảnh; mốc XONG chấm
 * teal đặc + đường teal, mốc ĐANG LÀM chấm xanh dương + chữ xanh, mốc CHƯA TỚI vòng
 * xám rỗng + đường xám. Giờ của mốc nằm dưới tên.
 *
 * Khác `Stepper` (chấm to có ✓, dùng ở các màn điều phối): không thay `Stepper` — hai
 * hình cho hai chỗ, mỗi màn giữ hình đã duyệt của nó. Component chỉ VẼ: mốc nào xong /
 * đang làm do nơi gọi truyền vào (bàn XN: máy chủ tính).
 *
 * Đường nối: mỗi mốc vẽ nửa trái (màu của CHÍNH mốc đó — "đã tới đây") và nửa phải
 * (màu của mốc kế tiếp), xếp bằng flex nên luôn đi đúng tâm chấm, không đặt toạ độ tay.
 */

export type TrangThaiMocHT = "done" | "current" | "upcoming";

export interface MocHanhTrinh {
  ten: string;
  trangThai: TrangThaiMocHT;
  /** "09:05" — để trống khi mốc chưa có giờ. */
  gio?: string;
}

const CHAM: Record<TrangThaiMocHT, string> = {
  done: "bg-status-ready",
  current: "bg-status-in-progress",
  upcoming: "bg-surface ring-2 ring-inset ring-line-strong",
};

const DUONG: Record<TrangThaiMocHT, string> = {
  done: "bg-status-ready",
  current: "bg-status-ready",
  upcoming: "bg-line",
};

const TEN: Record<TrangThaiMocHT, string> = {
  done: "font-semibold text-ink",
  current: "font-semibold text-status-in-progress",
  upcoming: "font-medium text-ink-muted",
};

const DOC: Record<TrangThaiMocHT, string> = {
  done: "đã xong",
  current: "đang làm",
  upcoming: "chưa tới",
};

export default function ThanhHanhTrinh({ moc, nhan = "Hành trình" }: { moc: readonly MocHanhTrinh[]; nhan?: string }) {
  return (
    <ol aria-label={nhan} className="flex py-2">
      {moc.map((m, i) => (
        <li key={`${i}-${m.ten}`} className="flex min-w-0 flex-1 basis-0 flex-col items-center gap-1 text-center">
          <div className="flex w-full items-center" aria-hidden>
            <span className={`h-0.5 flex-1 ${i === 0 ? "" : DUONG[m.trangThai]}`} />
            <span className={`relative size-4 shrink-0 rounded-full ${CHAM[m.trangThai]}`}>
              {/* Mốc ĐANG LÀM toả sóng (bản mẫu `toa`) để kéo mắt; tắt khi người dùng
                  chọn giảm chuyển động. */}
              {m.trangThai === "current" ? (
                <span className="absolute inset-0 rounded-full bg-status-in-progress opacity-60 motion-safe:animate-ping" />
              ) : null}
            </span>
            <span className={`h-0.5 flex-1 ${i === moc.length - 1 ? "" : DUONG[moc[i + 1].trangThai]}`} />
          </div>
          <span className={`text-meta ${TEN[m.trangThai]}`}>
            {m.ten}
            <span className="sr-only"> — {DOC[m.trangThai]}</span>
          </span>
          {m.gio ? <span className="text-label tabular-nums text-ink-muted">{m.gio}</span> : null}
        </li>
      ))}
    </ol>
  );
}
