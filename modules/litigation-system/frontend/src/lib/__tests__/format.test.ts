/* plan 测试计划「前端 Vitest + RTL」：展示格式化纯函数（金额/百分比/日期/列表）。
   真值断言对齐后端 638/312/48.9%/¥1,284,600/¥870（docs/04 §4 关键事实基线）。 */
import { describe, expect, it } from "vitest";
import { fmtByType, fmtDate, fmtList, fmtMoney, fmtNum, fmtPct, fmtText } from "../format";

describe("fmtMoney 金额", () => {
  it("千分位 + ¥ 前缀", () => {
    expect(fmtMoney(1284600)).toBe("¥1,284,600");
    expect(fmtMoney(870)).toBe("¥870");
  });
  it("小数保留 2 位", () => {
    expect(fmtMoney(66.5)).toBe("¥66.50");
    expect(fmtMoney(0)).toBe("¥0");
  });
  it("空值 → —", () => {
    expect(fmtMoney(null)).toBe("—");
    expect(fmtMoney(undefined)).toBe("—");
    expect(fmtMoney("")).toBe("—");
  });
});

describe("fmtPct 百分比", () => {
  it("0~1 与 0~100 自动识别", () => {
    expect(fmtPct(0.782)).toBe("78.2%");
    expect(fmtPct(78.2)).toBe("78.2%");
    expect(fmtPct(0.489)).toBe("48.9%");
    expect(fmtPct(0.064)).toBe("6.4%");
  });
  it("空值 → —", () => {
    expect(fmtPct(null)).toBe("—");
  });
});

describe("fmtNum 原始数字", () => {
  it("千分位无小数", () => {
    expect(fmtNum(638)).toBe("638");
    expect(fmtNum(1284600)).toBe("1,284,600");
    expect(fmtNum(null)).toBe("—");
  });
});

describe("fmtDate / fmtList / fmtByType", () => {
  it("epoch_ms → YYYY-MM-DD（本地时区构造避免偏移）", () => {
    const d = new Date(2026, 0, 5); // 2026-01-05 本地
    expect(fmtDate(d.getTime())).toBe("2026-01-05");
    expect(fmtDate(null)).toBe("—");
  });
  it("数组 join 过滤空值", () => {
    expect(fmtList(["北京A", "", "北京B"])).toBe("北京A / 北京B");
    expect(fmtList([])).toBe("—");
  });
  it("按类型分发", () => {
    expect(fmtByType(1284600, "num")).toBe("¥1,284,600");
    expect(fmtByType("not-a-date", "date")).toBe("not-a-date"); // 非法日期串兜底原样
    expect(fmtText("x")).toBe("x");
  });
});