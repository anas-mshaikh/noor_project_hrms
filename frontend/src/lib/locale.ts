export const LOCALE_COOKIE = "attendance-admin-locale";
export const SUPPORTED_LOCALES = ["en", "ar", "de", "fr"] as const;

export type AppLocale = (typeof SUPPORTED_LOCALES)[number];
export type LocaleDir = "ltr" | "rtl";

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

function splitLocale(input: string): string {
  return input.trim().toLowerCase().split("-")[0] ?? "";
}

export function normalizeLocale(input: string | null | undefined): AppLocale {
  if (!input) return "en";
  const base = splitLocale(input);
  return (SUPPORTED_LOCALES as readonly string[]).includes(base)
    ? (base as AppLocale)
    : "en";
}

function getDefaultLocaleFromEnv(): AppLocale | null {
  // Optional demo override. When unset, fall back to browser / accept-language / "en".
  // Only NEXT_PUBLIC_* is available client-side.
  const envLocale =
    typeof process === "undefined" ? null : process.env.NEXT_PUBLIC_DEFAULT_LOCALE;
  const normalized = normalizeLocale(envLocale);
  return normalized === "en" ? null : normalized;
}

export function localeToDir(locale: AppLocale): LocaleDir {
  return locale === "ar" ? "rtl" : "ltr";
}

export function isRtlLocale(locale: AppLocale): boolean {
  return localeToDir(locale) === "rtl";
}

export function pickLocaleFromAcceptLanguage(
  acceptLanguage: string | null | undefined
): AppLocale | null {
  if (!acceptLanguage) return null;
  const parts = acceptLanguage
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);

  for (const part of parts) {
    // Example: "ar-SA;q=0.9" -> "ar-SA"
    const langTag = part.split(";")[0]?.trim() ?? "";
    const locale = normalizeLocale(langTag);
    if (locale !== "en") return locale;
  }

  return null;
}

export function getLocaleFromCookieString(cookieString: string): AppLocale | null {
  const match = cookieString.match(new RegExp(`(?:^|; )${LOCALE_COOKIE}=([^;]+)`));
  if (!match?.[1]) return null;
  return normalizeLocale(decodeURIComponent(match[1]));
}

export function getLocaleFromDocumentCookie(): AppLocale | null {
  if (typeof document === "undefined") return null;
  return getLocaleFromCookieString(document.cookie);
}

export function getInitialLocaleClient(): AppLocale {
  const cookieLocale = getLocaleFromDocumentCookie();
  if (cookieLocale) return cookieLocale;

  const envDefault = getDefaultLocaleFromEnv();
  if (envDefault) return envDefault;

  const browserLocales =
    typeof navigator === "undefined"
      ? []
      : [...(navigator.languages ?? []), navigator.language].filter(Boolean);

  for (const raw of browserLocales) {
    const locale = normalizeLocale(raw);
    if (locale !== "en") return locale;
  }

  return "en";
}

export function setLocaleCookie(locale: AppLocale): void {
  if (typeof document === "undefined") return;
  document.cookie = `${LOCALE_COOKIE}=${encodeURIComponent(
    locale
  )}; Path=/; Max-Age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
}

export function applyDocumentLocale(locale: AppLocale): void {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale;
  document.documentElement.dir = localeToDir(locale);
}
