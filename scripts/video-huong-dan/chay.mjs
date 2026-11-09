#!/usr/bin/env node
// Làm video hướng dẫn từ kịch bản YAML — MỘT lệnh, không chỉnh tay khâu nào.
//
//   node scripts/video-huong-dan/chay.mjs --chuong 2 --nhap   # một chương, bản nháp
//   node scripts/video-huong-dan/chay.mjs --tat-ca             # bản chính mọi chương đợt 1
//
// Ra ~/ClinicAI-video/<YYYYMMDD>/: <so>-<ten>.mp4 · .srt · .png (bìa) · .moc.json · bao-cao.md
// Cách chạy, biến môi trường, cách thêm chương: docs/huong-dan-video/README.md.

import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join } from "node:path";

import { REPO } from "./api.mjs";
import { dungDuLieu } from "./dung-du-lieu.mjs";
import { anhBia, catKhung, doAmLuong, doDaiVideo, doanPhuDe, ghepTronBo, ghepVideo, ghiSrt } from "./ghep.mjs";
import { chiaPhuDe, docCacCanh } from "./loi.mjs";
import { LoiCanh, quayChuong } from "./quay.mjs";

const require = createRequire(join(REPO, "src/dashboard/package.json"));
const yaml = require("js-yaml");

const KICH_BAN = join(REPO, "docs/huong-dan-video/kich-ban");
const DOT_1 = [0, 1, 2, 3, 4];

function thamSo(argv) {
  const ts = { nhap: argv.includes("--nhap"), tatCa: argv.includes("--tat-ca"), chuong: null };
  const i = argv.indexOf("--chuong");
  if (i >= 0) ts.chuong = Number(argv[i + 1]);
  if (!ts.tatCa && !Number.isInteger(ts.chuong)) {
    throw new Error("Dùng: --chuong <số> [--nhap]  hoặc  --tat-ca [--nhap]");
  }
  return ts;
}

function docKichBan(so) {
  const tep = readdirSync(KICH_BAN).find((t) => t.startsWith(`${String(so).padStart(2, "0")}-`) && t.endsWith(".yaml"));
  if (!tep) throw new Error(`Chưa có kịch bản chương ${so} trong ${KICH_BAN}.`);
  const kb = yaml.load(readFileSync(join(KICH_BAN, tep), "utf8"));
  for (const c of kb.canh) {
    const tu = c.loi.trim().split(/\s+/).length;
    if (tu > 25) throw new Error(`Kịch bản ${tep}, cảnh «${c.id}»: ${tu} từ (tối đa 25).`);
  }
  return { ...kb, ten_tep: basename(tep, ".yaml") };
}

const ngayHomNay = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date()).replaceAll("-", "");

/** `{khach_<khoá>}` trong kịch bản ⇒ tên khách mẫu dữ liệu vừa dựng (chương 3 đổi khách
 *  mỗi lần quay vì Hoàn tiền không bù được). Thiếu tên ⇒ dừng, không quay chữ "{…}". */
function thayTen(x, ten) {
  if (typeof x === "string") {
    return x.replace(/\{(khach_\w+)\}/g, (_m, k) => {
      if (!ten[k]) throw new Error(`Kịch bản dùng {${k}} mà dữ liệu chương này không dựng khách đó.`);
      return ten[k];
    });
  }
  if (Array.isArray(x)) return x.map((y) => thayTen(y, ten));
  if (x && typeof x === "object") return Object.fromEntries(Object.entries(x).map(([k, v]) => [k, thayTen(v, ten)]));
  return x;
}

async function lamChuong(so, { nhap, ra, bang }) {
  const goc0 = docKichBan(so);
  console.log(`\n▶ Chương ${so} — ${goc0.ten} (${nhap ? "nháp" : "bản chính"})`);
  const kb = thayTen(goc0, await dungDuLieu(so));
  const loiCanh = [
    { id: "_mo", loi: `${kb.ten}. ${kb.mo_dau}.` },
    ...kb.canh,
    { id: "_ket", loi: `Xong. ${kb.ket_thuc ?? ""}`.trim() },
  ];
  const { canh: tieng, giong } = await docCacCanh(loiCanh, bang, { nhap, kho: join(homedir(), "ClinicAI-video") });
  console.log(`  · đọc ${tieng.length} đoạn lời (${giong}), tổng ${tieng.reduce((s, t) => s + t.giay, 0).toFixed(1)}s`);

  const tam = join(ra, `.quay-${kb.ten_tep}`);
  rmSync(tam, { recursive: true, force: true });
  mkdirSync(tam, { recursive: true });
  const { video, moc } = await quayChuong(kb, tieng, { ai: kb.tai_khoan, thuMuc: tam, duongDau: kb.mo_tu ?? "/home" });
  console.log(`  · quay xong ${(moc.het - moc.bat_dau).toFixed(1)}s`);

  const goc = join(ra, kb.ten_tep);
  await ghepVideo({ video, moc, tieng, ra: `${goc}.mp4`, nhap });
  ghiSrt(`${goc}.srt`, doanPhuDe(moc, tieng));
  await anhBia(`${goc}.mp4`, `${goc}.png`);
  rmSync(tam, { recursive: true, force: true });
  writeFileSync(`${goc}.moc.json`, JSON.stringify({ chuong: so, giong, moc, tieng }, null, 2));
  return { kb, goc, moc, tieng, giong };
}

/** Soi một chương: khung giữa từng cảnh, âm lượng, lặng, lệch, phụ đề. */
async function soi({ goc, moc, tieng }) {
  const khung = join(goc + ".khung");
  rmSync(khung, { recursive: true, force: true });
  mkdirSync(khung, { recursive: true });
  const dong = [];
  for (const [i, c] of moc.canh.entries()) {
    const giua = (c.tu + c.den) / 2 - moc.bat_dau;
    const png = join(khung, `${String(i).padStart(2, "0")}-${c.id}.png`);
    await catKhung(`${goc}.mp4`, giua, png);
    const lang = i + 1 < moc.canh.length ? moc.canh[i + 1].tu - (c.tu + c.giay_tieng) : 0;
    dong.push({ i, id: c.id, tu: c.tu - moc.bat_dau, dai: c.den - c.tu, tieng: c.giay_tieng, lang, tran: c.tran, png });
  }
  const am = await doAmLuong(`${goc}.mp4`);
  const dai = await doDaiVideo(`${goc}.mp4`);
  // Lệch tiếng–hình: tiếng đặt đúng mốc đầu cảnh; hình là khung CDP mang dấu giờ của Chrome
  // (cùng đồng hồ). Lệch = trễ lớn nhất từ mốc đầu cảnh tới khung đầu tiên sau mốc, cộng
  // sai số làm tròn khung 30 fps (≤ 1/30 s).
  const lech = (moc.tre_khung ?? 0) + 1 / 30;
  const pdQuaDai = tieng.flatMap((t) => chiaPhuDe(t.loi)).flatMap((d) => d.split("\n")).filter((l) => l.length > 42);
  return { dong, am, dai, lech, pdQuaDai, khung };
}

function baoCao(kq, tep) {
  const s = (n) => `${n.toFixed(1)}s`;
  const md = [`# Báo cáo video hướng dẫn — ${new Date().toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })}`, ""];
  for (const { lam, soi: x } of kq) {
    const { kb, giong, goc } = lam;
    const langLon = x.dong.filter((d) => d.lang > 1.5);
    md.push(
      `## Chương ${kb.chuong} — ${kb.ten}`,
      "",
      `- Tệp: \`${goc}.mp4\` · ${s(x.dai)} · giọng \`${giong}\``,
      `- Âm lượng: ${x.am.I} LUFS (đích −16), đỉnh ${x.am.TP} dBFS (≤ −1,5)`,
      `- Lệch tiếng–hình ước: ${x.lech.toFixed(2)}s (đích ≤ 0,3s) ${x.lech <= 0.3 ? "✅" : "⚠️"}`,
      `- Khoảng lặng > 1,5s: ${langLon.length ? langLon.map((d) => `${d.id} ${s(d.lang)}`).join(", ") + " ⚠️" : "không ✅"}`,
      `- Phụ đề quá 42 ký tự/dòng: ${x.pdQuaDai.length ? x.pdQuaDai.join(" | ") + " ⚠️" : "không ✅"}`,
      "",
      "| # | Cảnh | Bắt đầu | Dài | Tiếng | Thao tác quá tiếng | Khung giữa cảnh | Soi bằng mắt |",
      "|---|---|---|---|---|---|---|---|",
      ...x.dong.map(
        (d) =>
          `| ${d.i} | ${d.id} | ${s(d.tu)} | ${s(d.dai)} | ${s(d.tieng)} | ${d.tran > 0.05 ? s(d.tran) : "—"} | \`${basename(d.png)}\` | _(điền sau khi xem)_ |`,
      ),
      "",
      "### Lỗi thấy khi quay",
      "",
      "_(chưa có)_",
      "",
    );
  }
  writeFileSync(tep, md.join("\n"));
}

async function main() {
  const ts = thamSo(process.argv.slice(2));
  const ra = join(homedir(), "ClinicAI-video", ngayHomNay());
  mkdirSync(ra, { recursive: true });
  const bangTep = join(REPO, "docs/huong-dan-video/doc-chu.yaml");
  const bang = existsSync(bangTep) ? (yaml.load(readFileSync(bangTep, "utf8")) ?? {}) : {};
  const ds = ts.tatCa ? DOT_1 : [ts.chuong];
  const kq = [];
  for (const so of ds) {
    const lam = await lamChuong(so, { nhap: ts.nhap, ra, bang });
    kq.push({ lam, soi: await soi(lam) });
  }
  if (ts.tatCa) {
    const tron = join(ra, "00-tron-bo.mp4");
    const muc = await ghepTronBo(
      kq.map(({ lam }) => ({ mp4: `${lam.goc}.mp4`, ten: `Chương ${lam.kb.chuong} — ${lam.kb.ten}` })),
      tron,
      ra,
    );
    const mm = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
    const mucLuc = muc.map((m) => `${mm(m.tu)} ${m.ten}`).join("\n");
    writeFileSync(join(ra, "00-muc-luc.txt"), `${mucLuc}\n`);
    for (const t of ["tron-bo.ffconcat", "tron-bo.ffmeta"]) rmSync(join(ra, t), { force: true });
    console.log(`\nVideo gộp: ${tron}\n${mucLuc}`);
  }
  baoCao(kq, join(ra, "bao-cao.md"));
  console.log(`\nXong → ${ra}`);
  for (const { lam } of kq) console.log(`  ${lam.goc}.mp4`);
}

main().catch((e) => {
  console.error(`\n${e instanceof LoiCanh ? "KỊCH BẢN HỎNG (không quay tiếp)" : "LỖI"}: ${e.message}`);
  process.exit(1);
});
