// Ghép tệp quay + tiếng từng cảnh ⇒ MP4 H.264 1920×1080 30fps, AAC 192k, + .srt + ảnh bìa.
// Tiếng đặt đúng mốc bằng `adelay` (mốc từ quay.mjs), cộng bằng `amix`, chuẩn hoá
// `loudnorm` I=-16 LUFS, TP=-1.5 (giao việc mục 1). Phụ đề đã vẽ trong hình lúc quay
// (lop-trang.js) — tệp .srt sinh từ CHÍNH lời + mốc, để người xem bật/tắt ở máy khác.

import { execFile } from "node:child_process";
import { writeFileSync } from "node:fs";
import { promisify } from "node:util";

import { mocPhuDe } from "./loi.mjs";

const chay = promisify(execFile);

function giaySrt(s) {
  const ms = Math.max(0, Math.round(s * 1000));
  const h = String(Math.floor(ms / 3_600_000)).padStart(2, "0");
  const m = String(Math.floor((ms % 3_600_000) / 60_000)).padStart(2, "0");
  const g = String(Math.floor((ms % 60_000) / 1000)).padStart(2, "0");
  return `${h}:${m}:${g},${String(ms % 1000).padStart(3, "0")}`;
}

/** Đoạn phụ đề trên trục thời gian của VIDEO RA (gốc = thẻ mở). */
export function doanPhuDe(moc, tieng) {
  const ra = [];
  for (const [i, c] of moc.canh.entries()) {
    const goc = c.tu - moc.bat_dau;
    for (const d of mocPhuDe(tieng[i].loi, tieng[i].giay)) {
      ra.push({ canh: c.id, chu: d.chu, tu: goc + d.tu, den: goc + d.den });
    }
  }
  return ra;
}

export function ghiSrt(tep, doan) {
  writeFileSync(
    tep,
    doan.map((d, i) => `${i + 1}\n${giaySrt(d.tu)} --> ${giaySrt(d.den)}\n${d.chu}\n`).join("\n"),
  );
}

/** `video` = danh sách ffconcat khung PNG đã cắt sẵn từ thẻ mở tới hết (quay.mjs). */
export async function ghepVideo({ video, moc, tieng, ra, nhap }) {
  const dai = moc.het - moc.bat_dau;
  const vao = ["-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", video];
  for (const t of tieng) vao.push("-i", t.tep);
  const loc = tieng.map((_t, i) => {
    const tre = Math.round((moc.canh[i].tu - moc.bat_dau) * 1000);
    return `[${i + 1}:a]aresample=48000,adelay=${tre}:all=1[a${i}]`;
  });
  const tron = tieng.map((_t, i) => `[a${i}]`).join("");
  loc.push(
    `${tron}amix=inputs=${tieng.length}:normalize=0:dropout_transition=0,apad,atrim=0:${dai.toFixed(3)},` +
      "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[am]",
  );
  loc.push(`[0:v]fps=30,scale=1920:1080:flags=lanczos,format=yuv420p,trim=0:${dai.toFixed(3)}[v]`);
  await chay(
    "ffmpeg",
    [
      ...vao,
      "-filter_complex",
      loc.join(";"),
      "-t",
      dai.toFixed(3),
      "-map",
      "[v]",
      "-map",
      "[am]",
      "-c:v",
      "libx264",
      "-preset",
      nhap ? "veryfast" : "slow",
      "-crf",
      "18",
      "-tune",
      "stillimage",
      "-c:a",
      "aac",
      "-b:a",
      "192k",
      "-movflags",
      "+faststart",
      ra,
    ],
    { maxBuffer: 1 << 26 },
  );
}

/** Ảnh bìa = khung giữa thẻ mở. */
export async function anhBia(mp4, png) {
  await chay("ffmpeg", ["-y", "-v", "error", "-ss", "1.5", "-i", mp4, "-frames:v", "1", png]);
}

/** Một khung hình ở giây `s` của video ra (để soi). */
export async function catKhung(mp4, s, png) {
  await chay("ffmpeg", ["-y", "-v", "error", "-ss", s.toFixed(2), "-i", mp4, "-frames:v", "1", png]);
}

/** Âm lượng tích hợp (LUFS) + đỉnh thật, đo bằng ebur128. */
export async function doAmLuong(mp4) {
  const { stderr } = await chay(
    "ffmpeg",
    ["-hide_banner", "-nostats", "-i", mp4, "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
    { maxBuffer: 1 << 26 },
  );
  const tom = stderr.slice(stderr.lastIndexOf("Summary:"));
  const I = Number.parseFloat(tom.match(/I:\s+(-?[\d.]+) LUFS/)?.[1] ?? "NaN");
  const TP = Number.parseFloat(tom.match(/Peak:\s+(-?[\d.]+) dBFS/)?.[1] ?? "NaN");
  return { I, TP };
}

/**
 * Video gộp cả đợt: nối các chương (cùng mã hoá ⇒ chép luồng, không nén lại) + gắn
 * CHƯƠNG vào tệp (trình xem như QuickTime/VLC hiện danh sách chương để nhảy tới).
 * `chuong` = [{mp4, ten}] theo thứ tự. Trả [{ten, tu}] (giây) để in mục lục.
 */
export async function ghepTronBo(chuong, ra, thuMucTam) {
  const muc = [];
  let tu = 0;
  for (const c of chuong) {
    const dai = await doDaiVideo(c.mp4);
    muc.push({ ten: c.ten, tu, den: tu + dai });
    tu += dai;
  }
  const ds = `${thuMucTam}/tron-bo.ffconcat`;
  writeFileSync(ds, ["ffconcat version 1.0", ...chuong.map((c) => `file '${c.mp4}'`)].join("\n") + "\n");
  const meta = `${thuMucTam}/tron-bo.ffmeta`;
  const thoat = (s) => s.replace(/[=;#\\\n]/g, (k) => `\\${k}`);
  writeFileSync(
    meta,
    [
      ";FFMETADATA1",
      "title=Hướng dẫn Việc của đối tác",
      ...muc.flatMap((m) => [
        "[CHAPTER]",
        "TIMEBASE=1/1000",
        `START=${Math.round(m.tu * 1000)}`,
        `END=${Math.round(m.den * 1000)}`,
        `title=${thoat(m.ten)}`,
      ]),
    ].join("\n") + "\n",
  );
  await chay(
    "ffmpeg",
    ["-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", ds, "-i", meta, "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", "-movflags", "+faststart", ra],
    { maxBuffer: 1 << 26 },
  );
  return muc;
}

export async function doDaiVideo(mp4) {
  const { stdout } = await chay("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]);
  return Number.parseFloat(stdout.trim());
}
