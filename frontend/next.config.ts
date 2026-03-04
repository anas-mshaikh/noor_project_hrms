import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next may infer an incorrect workspace root in monorepos (multiple lockfiles),
  // which breaks module resolution for Tailwind v4's `@import "tailwindcss"`.
  // Pin Turbopack's root to the frontend package directory.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
