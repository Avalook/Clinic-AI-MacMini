export type OExcel = string | number | null | undefined;

const oCsv = (giaTri: OExcel): string => {
  const raw = giaTri == null ? "" : String(giaTri);
  const laSoAm = /^-\d+(?:[.,]\d+)?$/.test(raw);
  const anToan = /^[\s]*[=+@]/.test(raw) || (raw.trimStart().startsWith("-") && !laSoAm) ? `'${raw}` : raw;
  return `"${anToan.replace(/"/g, '""')}"`;
};

export function taoCsvExcel(tieuDe: readonly OExcel[], dong: readonly (readonly OExcel[])[]): string {
  return `\uFEFF${[tieuDe, ...dong].map((hang) => hang.map(oCsv).join(",")).join("\r\n")}`;
}

const noiDungO = (o: Element): string => {
  const banSao = o.cloneNode(true) as Element;
  const oGoc = Array.from(o.querySelectorAll("input, select, textarea"));
  banSao.querySelectorAll("input, select, textarea").forEach((nut, i) => {
    const goc = oGoc[i] as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    const giaTri = goc instanceof HTMLInputElement && (goc.type === "checkbox" || goc.type === "radio")
      ? (goc.checked ? "Có" : "Không")
      : goc.value;
    nut.replaceWith(document.createTextNode(giaTri));
  });
  banSao.querySelectorAll("button, input, select, textarea").forEach((nut) => nut.remove());
  return (banSao.textContent ?? "").replace(/\s+/g, " ").trim();
};

function cacBang(container: HTMLElement): { tieuDe: string[]; dong: string[][] }[] {
  const bang: { tieuDe: string[]; dong: string[][] }[] = [];
  const nguonRieng = container.querySelectorAll("table[data-excel-source]");
  for (const table of Array.from(nguonRieng.length ? nguonRieng : container.querySelectorAll("table"))) {
    const header = Array.from(table.querySelectorAll("thead tr")).at(-1);
    if (!header) continue;
    const tieuDe = Array.from(header.querySelectorAll("th:not([data-excel-ignore]), td:not([data-excel-ignore])")).map(noiDungO);
    if (!tieuDe.some(Boolean)) continue;
    const dong = Array.from(table.querySelectorAll("tbody tr"))
      .filter((tr) => !tr.hasAttribute("data-excel-ignore") && getComputedStyle(tr).display !== "none")
      .map((tr) => Array.from(tr.querySelectorAll(":scope > td:not([data-excel-ignore]), :scope > th:not([data-excel-ignore])"), noiDungO))
      .filter((cells) => cells.some(Boolean));
    bang.push({ tieuDe: tieuDe.map((x, i) => x || `Cột ${i + 1}`), dong });
  }
  for (const list of Array.from(nguonRieng.length ? [] : container.querySelectorAll("ul.rounded-card, ul.space-y-3"))) {
    const items = Array.from(list.querySelectorAll(":scope > li")).map(noiDungO).filter(Boolean);
    if (items.length) bang.push({ tieuDe: ["Nội dung"], dong: items.map((item) => [item]) });
  }
  return bang;
}

export function xuatBangDangXem(container: HTMLElement, tenTep: string): boolean {
  const cacDong = cacBang(container);
  if (!cacDong.length) return false;
  const hang: OExcel[][] = [];
  cacDong.forEach((bang, index) => {
    if (index) hang.push([]);
    if (cacDong.length > 1) hang.push([`Bảng ${index + 1}`]);
    hang.push(bang.tieuDe, ...bang.dong);
  });
  const [tieuDe = [], ...dong] = hang;
  const blob = new Blob([taoCsvExcel(tieuDe, dong)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${tenTep}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  return true;
}
