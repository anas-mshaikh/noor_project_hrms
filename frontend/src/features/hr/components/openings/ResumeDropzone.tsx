"use client";

import * as React from "react";
import { Loader2, UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/features/hr/components/cards/GlassCard";

type ResumeDropzoneProps = {
  className?: string;
  disabled?: boolean;
  uploading?: boolean;
  onFilesSelected?: (files: File[]) => void;
  helperText?: string;
};

export function ResumeDropzone({
  className,
  disabled,
  uploading,
  onFilesSelected,
  helperText,
}: ResumeDropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement | null>(null);

  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold tracking-tight">Upload resumes</div>
          <div className="mt-1 text-sm text-muted-foreground">
            {helperText ??
              "Drag & drop or select files. Parsing will start automatically."}
          </div>
        </div>
        <Button
          type="button"
          disabled={Boolean(disabled) || Boolean(uploading)}
          onClick={() => inputRef.current?.click()}
          className="rounded-2xl bg-white/[0.06] hover:bg-white/[0.09]"
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <UploadCloud className="h-4 w-4" />
          )}
          {uploading ? "Uploading…" : "Select files"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            // Allow selecting the same file again by resetting the input.
            e.target.value = "";
            if (!files.length) return;
            onFilesSelected?.(files);
          }}
        />
      </div>

      <div
        className="mt-4 rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center"
        onDragOver={(e) => {
          if (disabled || uploading) return;
          e.preventDefault();
        }}
        onDrop={(e) => {
          if (disabled || uploading) return;
          e.preventDefault();
          const files = Array.from(e.dataTransfer.files ?? []);
          if (!files.length) return;
          onFilesSelected?.(files);
        }}
      >
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
