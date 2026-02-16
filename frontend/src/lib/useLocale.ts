"use client";

import { useMemo } from "react";
import { useTranslation } from "@/lib/i18n";

import {
  type AppLocale,
  SUPPORTED_LOCALES,
  isRtlLocale,
  normalizeLocale
} from "@/lib/locale";

export function useLocale() {
  const { i18n } = useTranslation();

  const locale = useMemo(
    () => normalizeLocale(i18n.resolvedLanguage ?? i18n.language),
    [i18n.language, i18n.resolvedLanguage]
  );

  async function setLocale(nextLocale: AppLocale): Promise<void> {
    await i18n.changeLanguage(nextLocale);
  }

  return {
    locale,
    isRtl: isRtlLocale(locale),
    setLocale,
    supportedLocales: SUPPORTED_LOCALES
  };
}
