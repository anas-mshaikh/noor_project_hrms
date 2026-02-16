"use client";

import { useTranslation } from "@/lib/i18n";

import { useLocale } from "@/lib/useLocale";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  const { t } = useTranslation();
  const { locale, setLocale } = useLocale();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("page.settings.title", { defaultValue: "Settings" })}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("page.settings.subtitle", {
            defaultValue: "Organization preferences. (UI scaffold)",
          })}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {t("page.settings.language_title", { defaultValue: "Language" })}
          </CardTitle>
          <CardDescription>
            {t("page.settings.language_body", {
              defaultValue: "Select application language for this device.",
            })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={locale === "en" ? "default" : "outline"}
              onClick={() => void setLocale("en")}
            >
              {t("language.en", { defaultValue: "English" })}
            </Button>
            <Button
              type="button"
              variant={locale === "ar" ? "default" : "outline"}
              onClick={() => void setLocale("ar")}
            >
              {t("language.ar", { defaultValue: "Arabic" })}
            </Button>
            <Button
              type="button"
              variant={locale === "de" ? "default" : "outline"}
              onClick={() => void setLocale("de")}
            >
              {t("language.de", { defaultValue: "German" })}
            </Button>
            <Button
              type="button"
              variant={locale === "fr" ? "default" : "outline"}
              onClick={() => void setLocale("fr")}
            >
              {t("language.fr", { defaultValue: "French" })}
            </Button>
            <Button
              type="button"
              variant={locale === "es" ? "default" : "outline"}
              onClick={() => void setLocale("es")}
            >
              {t("language.es", { defaultValue: "Español" })}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
