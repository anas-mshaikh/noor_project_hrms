# HR Suite (UI-only, demo-first)

This folder contains the **HR Suite** frontend (Openings → Screening Runs → Pipeline → Onboarding).

**Phase status**
- UI-only: uses mock data and simulated loading.
- No backend wiring yet (intentionally).

**Structure**
- `mock/` — typed mock models + demo data
- `hooks/` — reduced motion + mock loading
- `lib/` — theme tokens + motion variants
- `components/` — reusable HR-specific UI components

**Design goals**
- Dark-only “purple glass” aesthetic
- Minimal duplication via shared primitives (GlassCard, Header, TagChip, etc.)
- Accessible + keyboard-friendly components
- Reduced-motion support (prefers-reduced-motion)

