import "@testing-library/jest-dom/vitest";

Object.assign(navigator, {
  clipboard: {
    writeText: async () => undefined,
  },
});

Object.defineProperty(Element.prototype, "scrollIntoView", {
  value: () => undefined,
  configurable: true,
});
