import { describe, expect, it } from "vitest";

import { contentDirection, isPrimarilyRtl } from "./language";

describe("Arabic direction detection", () => {
  it("marks primarily Arabic content as RTL while preserving English and mixed names", () => {
    expect(isPrimarilyRtl("ما موعد إطلاق Atlas في 15 مايو؟")).toBe(true);
    expect(contentDirection("The Atlas launch is on 15 May.")).toBe("ltr");
    expect(contentDirection("الإجابة هي Qwen 2.5 بتاريخ 2026-05-15.")).toBe("rtl");
  });
});
