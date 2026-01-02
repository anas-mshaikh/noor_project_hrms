import { redirect } from "next/navigation";

/**
 * Default landing:
 * - For a fresh install, /setup is always the first step (create org/store/camera).
 */
export default function Home() {
  redirect("/setup");
}
