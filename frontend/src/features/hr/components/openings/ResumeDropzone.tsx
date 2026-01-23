"use client";

import * as React from "react";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";

type ResumeDropzoneProps = {
  className?: string;
};

export function ResumeDropzone({ className }: ResumeDropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold tracking-tight">Upload resumes</div>
          <div className="mt-1 text-sm text-muted-foreground">
            Drag & drop or select files. Parsing/embedding will appear here once wired.
          </div>
        </div>
        <Button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
        >
          <UploadCloud className="h-4 w-4" />
          Select files
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={() =>
            toast("Mock upload", { description: "Backend wiring in Phase 2" })
          }
        />
      </div>

      <div className="mt-4 rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/5 ring-1 ring-white/10">
          <UploadCloud className="h-5 w-5 text-foreground/80" />
        </div>
        <div className="mt-3 text-sm font-medium">Drop files here</div>
        <div className="mt-1 text-xs text-muted-foreground">
          Supported: PDF, DOCX, images (later).
        </div>
      </div>
    </GlassCard>
  );
}

