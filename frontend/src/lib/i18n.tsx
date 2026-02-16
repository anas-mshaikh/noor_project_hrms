"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import ar from "@/i18n/ar.json";
import de from "@/i18n/de.json";
import en from "@/i18n/en.json";
import fr from "@/i18n/fr.json";
import {
  type AppLocale,
  applyDocumentLocale,
  getInitialLocaleClient,
  getLocaleFromDocumentCookie,
  normalizeLocale,
  setLocaleCookie
} from "@/lib/locale";

type TranslationOptions = {
  defaultValue?: string;
};

type I18nLike = {
  language: AppLocale;
  resolvedLanguage: AppLocale;
  changeLanguage: (nextLocale: string) => Promise<void>;
};

type TranslationApi = {
  t: (key: string, options?: TranslationOptions) => string;
  i18n: I18nLike;
};

type ContextValue = {
  locale: AppLocale;
  changeLanguage: (nextLocale: string) => Promise<void>;
};

const resources = {
  en,
  ar,
  de,
  fr
} as const;

const I18nContext = createContext<ContextValue | null>(null);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getNestedTranslation(
  locale: AppLocale,
  key: string
): string | null {
  const parts = key.split(".");

  let cursor: unknown = resources[locale];
  for (const part of parts) {
    if (!isRecord(cursor) || !(part in cursor)) return null;
    cursor = cursor[part];
  }

  return typeof cursor === "string" ? cursor : null;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<AppLocale>(() => {
    const cookieLocale = getLocaleFromDocumentCookie();
    if (cookieLocale) return cookieLocale;
    return getInitialLocaleClient();
  });

  useEffect(() => {
    applyDocumentLocale(locale);
    setLocaleCookie(locale);
  }, [locale]);

  const changeLanguage = useCallback(async (nextLocale: string): Promise<void> => {
    setLocale(normalizeLocale(nextLocale));
  }, []);

  const value = useMemo<ContextValue>(
    () => ({
      locale,
      changeLanguage
    }),
    [locale, changeLanguage]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation(): TranslationApi {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useTranslation must be used inside I18nProvider.");
  }

  const { locale, changeLanguage } = context;

  const t = useCallback(
    (key: string, options?: TranslationOptions): string => {
      const localized = getNestedTranslation(locale, key);
      if (localized) return localized;

      const english = getNestedTranslation("en", key);
      if (english) return english;

      return options?.defaultValue ?? key;
    },
    [locale]
  );

  return {
    t,
    i18n: {
      language: locale,
      resolvedLanguage: locale,
      changeLanguage
    }
  };
}
