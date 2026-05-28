/** Normaliza texto para busqueda case-insensitive sin acentos. */

export function normalizeSearchText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .trim();
}

export function matchesSearch(haystack: string, needle: string): boolean {
  const n = normalizeSearchText(needle);
  if (!n) return true;
  return normalizeSearchText(haystack).includes(n);
}
