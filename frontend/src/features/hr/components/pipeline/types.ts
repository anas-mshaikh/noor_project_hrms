"use client";

import type { ApplicationOut } from "@/lib/types";

export type PipelineStageUi = {
  id: string;
  name: string;
  sort_order: number;
  is_terminal: boolean;
};

export type PipelineCardUi = {
  id: string; // application_id
  stageId: string;
  title: string;
  tags: string[];
  score?: number;
  application: ApplicationOut;
};

