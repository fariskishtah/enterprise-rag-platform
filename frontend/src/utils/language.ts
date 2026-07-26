export type OutputLanguage = "auto" | "ar" | "en";

const arabicPattern = /[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/g;

export function isPrimarilyRtl(value: string | null | undefined): boolean {
  if (!value?.trim()) return false;
  const arabicCharacters = value.match(arabicPattern)?.length ?? 0;
  const letters = value.match(/[^\W\d_]/gu)?.length ?? 0;
  return arabicCharacters > 0 && arabicCharacters / Math.max(1, letters) >= 0.3;
}

export function contentDirection(value: string | null | undefined): "rtl" | "ltr" {
  return isPrimarilyRtl(value) ? "rtl" : "ltr";
}
