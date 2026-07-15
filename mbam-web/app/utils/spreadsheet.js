// 엑셀(.xlsx)/CSV 파일을 2차원 문자열 배열(행×열)로 파싱.
// 새 의존성 없이 이미 설치된 jszip 으로 .xlsx(zip+XML)를 직접 해석한다.
import JSZip from "jszip";

const xmlDoc = (str) => new DOMParser().parseFromString(str, "application/xml");

// "B3" → 1 (0-based 열 인덱스)
function colIndex(ref) {
  const m = /^([A-Z]+)/.exec(ref || "");
  if (!m) return 0;
  let n = 0;
  for (const ch of m[1]) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n - 1;
}

function parseSharedStrings(xml) {
  const doc = xmlDoc(xml);
  const sis = doc.getElementsByTagName("si");
  const out = [];
  for (let i = 0; i < sis.length; i++) {
    const ts = sis[i].getElementsByTagName("t");
    let s = "";
    for (let j = 0; j < ts.length; j++) s += ts[j].textContent;
    out.push(s);
  }
  return out;
}

function parseSheet(xml, shared) {
  const doc = xmlDoc(xml);
  const rows = doc.getElementsByTagName("row");
  const out = [];
  for (let i = 0; i < rows.length; i++) {
    const cells = rows[i].getElementsByTagName("c");
    const rowArr = [];
    for (let j = 0; j < cells.length; j++) {
      const c = cells[j];
      const idx = colIndex(c.getAttribute("r"));
      const t = c.getAttribute("t");
      let val = "";
      if (t === "inlineStr") {
        const ts = c.getElementsByTagName("t");
        for (let k = 0; k < ts.length; k++) val += ts[k].textContent;
      } else {
        const v = c.getElementsByTagName("v")[0];
        const raw = v ? v.textContent : "";
        val = t === "s" ? (shared[parseInt(raw, 10)] ?? "") : raw;
      }
      rowArr[idx] = (val == null ? "" : String(val)).trim();
    }
    out.push(rowArr);
  }
  return out;
}

function parseCSV(text) {
  const rows = [];
  const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  for (const line of lines) {
    if (line.trim() === "") continue;
    const cells = [];
    let cur = "", q = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (q) {
        if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else q = false; }
        else cur += ch;
      } else {
        if (ch === '"') q = true;
        else if (ch === ",") { cells.push(cur); cur = ""; }
        else cur += ch;
      }
    }
    cells.push(cur);
    rows.push(cells.map((c) => c.trim()));
  }
  return rows;
}

// 파일 → 2차원 배열. 빈 행 제거. 헤더가 있으면(첫 행에 '아이디/카페/블로그/url/주소' 등) 자동 제외.
export async function parseSpreadsheet(file) {
  const name = (file.name || "").toLowerCase();
  let rows;
  if (name.endsWith(".csv") || file.type === "text/csv") {
    rows = parseCSV(await file.text());
  } else {
    const zip = await JSZip.loadAsync(await file.arrayBuffer());
    const ss = zip.file("xl/sharedStrings.xml");
    const shared = ss ? parseSharedStrings(await ss.async("string")) : [];
    let sheet = zip.file("xl/worksheets/sheet1.xml");
    if (!sheet) {
      const names = Object.keys(zip.files)
        .filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n)).sort();
      if (names.length) sheet = zip.file(names[0]);
    }
    if (!sheet) throw new Error("시트를 찾을 수 없습니다. 올바른 .xlsx 파일인지 확인하세요.");
    rows = parseSheet(await sheet.async("string"), shared);
  }
  // 빈 행 제거
  rows = rows.filter((r) => r && r.some((c) => (c || "").trim() !== ""));
  // 헤더 자동 제외
  const first = rows[0] || [];
  const head = ((first[0] || "") + " " + (first[1] || "") + " " + (first[2] || "")).toLowerCase();
  if (/아이디|id|카페|블로그|url|주소|링크/.test(head)) rows = rows.slice(1);
  return rows;
}
