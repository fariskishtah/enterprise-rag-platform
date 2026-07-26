import "@testing-library/jest-dom/vitest";

// Node can expose an incomplete localStorage object when its storage-file flag
// is unset. Keep browser-facing tests deterministic with a standards-shaped
// in-memory implementation.
const storedValues = new Map<string, string>();
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: {
    get length() {
      return storedValues.size;
    },
    clear: () => storedValues.clear(),
    getItem: (key: string) => storedValues.get(key) ?? null,
    key: (index: number) => Array.from(storedValues.keys())[index] ?? null,
    removeItem: (key: string) => storedValues.delete(key),
    setItem: (key: string, value: string) => storedValues.set(key, String(value)),
  } satisfies Storage,
});

Object.assign(navigator, {
  clipboard: {
    writeText: async () => undefined,
  },
});

Object.defineProperty(Element.prototype, "scrollIntoView", {
  value: () => undefined,
  configurable: true,
});
