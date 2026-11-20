// Đọc lời từng cảnh thành tệp tiếng + đo độ dài (giao việc mục 1 "Tiếng trước, hình theo tiếng").
//
// Hai giọng:
//   nháp  — edge-tts, giọng nữ vi-VN-HoaiMyNeural (miễn phí, cần mạng). Cài: pipx install edge-tts
//   chính — Google Cloud Text-to-Speech, khoá ở biến môi trường GOOGLE_TTS_API_KEY.
//           Giọng: GOOGLE_TTS_VOICE nếu đặt; không thì TỰ TRA danh sách giọng vi-VN đang có
//           và chọn giọng nữ chất lượng cao nhất (Chirp3-HD → Neural2 → Wavenet → Standard).
// Lời gửi đi chỉ là kịch bản hướng dẫn (tên khách giả) — không dữ liệu thật nào.
// Tệp tiếng lưu đệm theo băm (giọng + lời đã áp bảng đọc) ⇒ chạy lại không đọc lại.

import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

const chay = promisify(execFile);
export const GIONG_NHAP = "vi-VN-HoaiMyNeural";

/** Áp bảng đọc (`doc-chu.yaml`): khoá dài trước, chỉ thay nguyên từ. */
export function apBangDoc(loi, bang) {
  let s = loi;
  const khoa = Object.keys(bang).sort((a, b) => b.length - a.length);
  for (const k of khoa) {
    const thoat = k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    s = s.replace(new RegExp(`(?<![\\p{L}\\p{N}])${thoat}(?![\\p{L}\\p{N}])`, "gu"), bang[k]);
  }
  return s;
}

export async function doDai(tep) {
  const { stdout } = await chay("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tep]);
  const s = Number.parseFloat(stdout.trim());
  if (!Number.isFinite(s)) throw new Error(`Không đo được độ dài tiếng: ${tep}`);
  return s;
}

function edgeTts() {
  const cho = [join(homedir(), ".local/bin/edge-tts"), "/opt/homebrew/bin/edge-tts", "edge-tts"];
  return cho.find((p) => p === "edge-tts" || existsSync(p));
}

async function docNhap(chu, tep) {
  const mp3 = tep.replace(/\.wav$/, ".mp3");
  // Dịch vụ của edge-tts hay trả "No audio was received" (09/11: lỗi NGẪU NHIÊN, cùng câu
  // lúc được lúc không — kiểu bị giới hạn tần suất) ⇒ thử lại, chờ lâu dần, nghỉ giữa lượt.
  for (let lan = 1; ; lan++) {
    try {
      await chay(edgeTts(), ["--voice", GIONG_NHAP, "--text", chu, "--write-media", mp3]);
      await new Promise((r) => setTimeout(r, 800));
      break;
    } catch (e) {
      rmSync(mp3, { force: true });
      if (lan >= 12) throw new Error(`edge-tts không đọc được sau ${lan} lần: «${chu.slice(0, 60)}…» (${String(e.stderr ?? e.message).trim().split("\n").at(-1)})`);
      await new Promise((r) => setTimeout(r, Math.min(3000 * lan, 15_000)));
    }
  }
  await chay("ffmpeg", ["-y", "-v", "error", "-i", mp3, "-ar", "48000", "-ac", "1", tep]);
}

const UU_TIEN = ["Chirp3-HD", "Chirp-HD", "Neural2", "Wavenet", "Standard"];

async function chonGiongGoogle(khoa) {
  if (process.env.GOOGLE_TTS_VOICE) return process.env.GOOGLE_TTS_VOICE;
  const r = await fetch(`https://texttospeech.googleapis.com/v1/voices?languageCode=vi-VN&key=${khoa}`);
  if (!r.ok) throw new Error(`Google TTS: không tra được danh sách giọng (HTTP ${r.status}).`);
  const ds = ((await r.json()).voices ?? []).filter((v) => v.ssmlGender === "FEMALE");
  for (const loai of UU_TIEN) {
    const g = ds.filter((v) => v.name.includes(loai)).sort((a, b) => a.name.localeCompare(b.name))[0];
    if (g) return g.name;
  }
  throw new Error("Google TTS: không có giọng nữ vi-VN nào.");
}

let giongGoogle = null;

async function docChinh(chu, tep) {
  const khoa = process.env.GOOGLE_TTS_API_KEY;
  if (!khoa) throw new Error("Bản chính cần GOOGLE_TTS_API_KEY (Google Cloud Text-to-Speech). Bản nháp: thêm --nhap.");
  giongGoogle ??= await chonGiongGoogle(khoa);
  const r = await fetch(`https://texttospeech.googleapis.com/v1/text:synthesize?key=${khoa}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      input: { text: chu },
      voice: { languageCode: "vi-VN", name: giongGoogle },
      audioConfig: { audioEncoding: "LINEAR16", sampleRateHertz: 48000 },
    }),
  });
  if (!r.ok) throw new Error(`Google TTS lỗi HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
  writeFileSync(tep, Buffer.from((await r.json()).audioContent, "base64"));
}

/**
 * Đọc mọi cảnh. Trả [{id, loi, doc, tep, giay}] — `loi` = chữ hiện phụ đề (giữ nguyên
 * kịch bản), `doc` = chữ gửi giọng đọc (đã áp bảng đọc).
 */
export async function docCacCanh(canh, bang, { nhap, kho }) {
  const giong = nhap ? `edge:${GIONG_NHAP}` : `google:${process.env.GOOGLE_TTS_VOICE ?? "tu-chon"}`;
  const dem = join(kho, "dem-tieng");
  mkdirSync(dem, { recursive: true });
  const ra = [];
  for (const c of canh) {
    const doc = apBangDoc(c.loi, bang);
    const bam = createHash("sha256").update(`${giong}\n${doc}`).digest("hex").slice(0, 16);
    const tep = join(dem, `${bam}.wav`);
    if (!existsSync(tep)) {
      if (nhap) await docNhap(doc, tep);
      else await docChinh(doc, tep);
    }
    ra.push({ id: c.id, loi: c.loi, doc, tep, giay: await doDai(tep) });
  }
  return { canh: ra, giong: nhap ? GIONG_NHAP : giongGoogle };
}

/** Chia lời thành đoạn phụ đề: ≤ 2 dòng × 42 ký tự mỗi đoạn, ngắt ở khoảng trắng. */
export function chiaPhuDe(loi, cot = 42) {
  const tu = loi.split(/\s+/).filter(Boolean);
  const dong = [];
  let d = "";
  for (const t of tu) {
    if (!d) d = t;
    else if (`${d} ${t}`.length <= cot) d = `${d} ${t}`;
    else {
      dong.push(d);
      d = t;
    }
  }
  if (d) dong.push(d);
  const doan = [];
  for (let i = 0; i < dong.length; i += 2) doan.push(dong.slice(i, i + 2).join("\n"));
  return doan;
}

/** Mốc đổi đoạn phụ đề trong một cảnh: chia thời lượng tiếng theo số ký tự mỗi đoạn. */
export function mocPhuDe(loi, giay) {
  const doan = chiaPhuDe(loi);
  const tong = doan.reduce((s, d) => s + d.length, 0) || 1;
  let t = 0;
  return doan.map((chu) => {
    const m = { chu, tu: t, den: t + (giay * chu.length) / tong };
    t = m.den;
    return m;
  });
}

export function ghiTep(tep, noiDung) {
  writeFileSync(tep, noiDung);
}
