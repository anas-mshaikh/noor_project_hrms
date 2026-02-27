"use client";

/**
 * 404 boundary.
 */

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-2xl">
      <Card className="border-white/10 bg-white/[0.03] backdrop-blur-xl">
        <CardHeader>
          <CardTitle className="tracking-tight">Page not found</CardTitle>
          <CardDescription className="text-muted-foreground">
            The page you are looking for does not exist.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/dashboard">Go to dashboard</Link>
          </Button>
          <Button asChild variant="secondary">
            <Link href="/scope">Scope</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
