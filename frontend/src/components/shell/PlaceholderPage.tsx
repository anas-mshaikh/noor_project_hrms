/**
 * components/shell/PlaceholderPage.tsx
 *
 * Simple, demo-ready placeholder used for not-yet-implemented modules.
 * Keeps visual consistency with the dark "purple glass" shell.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type PlaceholderPageProps = {
  title: string;
  subtitle: string;
  primaryTitle?: string;
  primaryBody?: string;
  secondaryTitle?: string;
  secondaryBody?: string;
};

export function PlaceholderPage({
  title,
  subtitle,
  primaryTitle = "Overview",
  primaryBody = "This module is scaffolded for the demo. The real data and workflows will be wired next.",
  secondaryTitle = "Coming soon",
  secondaryBody = "This section is intentionally mocked. No backend APIs are called yet.",
}: PlaceholderPageProps) {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          className={cn(
            "rounded-2xl border-white/10 bg-white/[0.04] shadow-sm backdrop-blur-xl"
          )}
        >
          <CardHeader>
            <CardTitle className="text-base">{primaryTitle}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {primaryBody}
          </CardContent>
        </Card>

        <Card
          className={cn(
            "rounded-2xl border-white/10 bg-white/[0.04] shadow-sm backdrop-blur-xl"
          )}
        >
          <CardHeader>
            <CardTitle className="text-base">{secondaryTitle}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {secondaryBody}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

