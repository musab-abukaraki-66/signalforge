/** Small RFC 4180 CSV parser: BOM, quotes, embedded newlines, delimiter detection, limits. */

export const MAX_BYTES = 10 * 1024 * 1024;
export const MAX_ROWS = 200_000;
export const MAX_COLUMNS = 200;

export class CsvError extends Error {}

export interface ParsedCsv {
  headers: string[];
  rows: string[][];
  delimiter: string;
  issues: {
    blankLinesSkipped: number;
    raggedRows: number; // rows whose field count differed from the header (padded/truncated, never dropped)
    duplicateHeaders: string[];
  };
}

const DELIMITERS = [",", ";", "\t", "|"];

/** Split one logical line into fields honouring quotes (used for detection only). */
function countFields(line: string, delim: string): number {
  let n = 1;
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') inQuotes = !inQuotes;
    else if (c === delim && !inQuotes) n++;
  }
  return n;
}

export function detectDelimiter(text: string): string {
  const lines = text.split(/\r\n|\n|\r/).filter((l) => l.trim() !== "").slice(0, 20);
  let best = ",";
  let bestScore = 0;
  for (const d of DELIMITERS) {
    const counts = lines.map((l) => countFields(l, d));
    if (counts.length === 0 || counts[0] < 2) continue;
    const consistent = counts.filter((c) => c === counts[0]).length / counts.length;
    const score = consistent * counts[0];
    if (score > bestScore) {
      bestScore = score;
      best = d;
    }
  }
  return best;
}

export function parseCsv(input: string, delimiter?: string): ParsedCsv {
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input;
  if (text.trim() === "") throw new CsvError("The file is empty.");
  const delim = delimiter ?? detectDelimiter(text);
  const records: string[][] = [];
  let blank = 0;
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  let fieldWasQuoted = false;
  let i = 0;
  const n = text.length;

  const endField = () => {
    row.push(field);
    field = "";
    fieldWasQuoted = false;
  };
  const endRow = () => {
    endField();
    if (row.length === 1 && row[0].trim() === "" && !fieldWasQuoted) blank++;
    else records.push(row);
    row = [];
    if (records.length > MAX_ROWS + 1) {
      throw new CsvError(`The file has more than ${MAX_ROWS.toLocaleString()} rows, the supported maximum.`);
    }
  };

  while (i < n) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i++;
        continue;
      }
      field += c;
      i++;
    } else if (c === '"' && field === "") {
      inQuotes = true;
      fieldWasQuoted = true;
      i++;
    } else if (c === delim) {
      endField();
      i++;
    } else if (c === "\r" || c === "\n") {
      endRow();
      i += c === "\r" && text[i + 1] === "\n" ? 2 : 1;
    } else {
      field += c;
      i++;
    }
  }
  if (inQuotes) throw new CsvError("A quoted field is never closed. Check for a stray double quote.");
  if (field !== "" || row.length > 0) endRow();

  if (records.length === 0) throw new CsvError("The file has no rows.");
  const headers = records[0].map((h, idx) => h.trim() || `column_${idx + 1}`);
  if (headers.length > MAX_COLUMNS) throw new CsvError(`The file has more than ${MAX_COLUMNS} columns.`);
  if (records.length < 2) throw new CsvError("The file has a header but no data rows.");

  const seen = new Map<string, number>();
  const duplicateHeaders: string[] = [];
  const uniqueHeaders = headers.map((h) => {
    const count = (seen.get(h) ?? 0) + 1;
    seen.set(h, count);
    if (count === 1) return h;
    duplicateHeaders.push(h);
    return `${h}_${count}`;
  });

  let ragged = 0;
  const rows = records.slice(1).map((r) => {
    if (r.length === uniqueHeaders.length) return r;
    ragged++;
    return uniqueHeaders.map((_, k) => r[k] ?? "");
  });
  return {
    headers: uniqueHeaders,
    rows,
    delimiter: delim,
    issues: { blankLinesSkipped: blank, raggedRows: ragged, duplicateHeaders },
  };
}
