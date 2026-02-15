import { redirect } from "next/navigation";

/**
 * Default landing:
 * - In most cases you should start at /login.
 * - For a fresh DB, use /setup to bootstrap tenancy + an admin user.
 */
export default function Home() {
  redirect("/login");
}
