import { describe, expect, it } from "vitest";
import { CsvError, MAX_ROWS, detectDelimiter, parseCsv } from "../src/lib/csv";

describe("parseCsv", () => {
  it("parses a simple file and strips a BOM", () => {
    const p = parseCsv("﻿a,b\n1,2\n3,4\n");
    expect(p.headers).toEqual(["a", "b"]);
    expect(p.rows).toEqual([["1", "2"], ["3", "4"]]);
  });
  it("handles quotes, commas, escaped quotes and embedded newlines", () => {
    const p = parseCsv('name,note\n"Smith, J","said ""hi"""\n"multi\nline",x\n');
    expect(p.rows[0]).toEqual(["Smith, J", 'said "hi"']);
    expect(p.rows[1]).toEqual(["multi\nline", "x"]);
  });
  it("handles CRLF and skips blank lines, counting them", () => {
    const p = parseCsv("a,b\r\n1,2\r\n\r\n3,4\r\n");
    expect(p.rows.length).toBe(2);
    expect(p.issues.blankLinesSkipped).toBe(1);
  });
  it("detects semicolon and tab delimiters", () => {
    expect(detectDelimiter("a;b;c\n1;2;3\n")).toBe(";");
    expect(detectDelimiter("a\tb\n1\t2\n")).toBe("\t");
    expect(parseCsv("a;b\n1,5;2\n").rows[0]).toEqual(["1,5", "2"]);
  });
  it("keeps ragged rows (padded) and reports them instead of dropping", () => {
    const p = parseCsv("a,b,c\n1,2\n1,2,3,4\n");
    expect(p.rows).toEqual([["1", "2", ""], ["1", "2", "3"]]);
    expect(p.issues.raggedRows).toBe(2);
  });
  it("renames duplicate and blank headers", () => {
    const p = parseCsv("a,a,\n1,2,3\n");
    expect(p.headers).toEqual(["a", "a_2", "column_3"]);
    expect(p.issues.duplicateHeaders).toEqual(["a"]);
  });
  it("rejects empty files, header-only files and unterminated quotes", () => {
    expect(() => parseCsv("")).toThrow(CsvError);
    expect(() => parseCsv("   \n")).toThrow(/empty/);
    expect(() => parseCsv("a,b\n")).toThrow(/no data rows/);
    expect(() => parseCsv('a,b\n"oops,1\n')).toThrow(/never closed/);
  });
  it("rejects files above the row limit", () => {
    const big = "a\n" + "1\n".repeat(MAX_ROWS + 5);
    expect(() => parseCsv(big)).toThrow(/more than/);
  });
});
