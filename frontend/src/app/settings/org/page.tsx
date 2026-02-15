import { PlaceholderPage } from "@/components/shell/PlaceholderPage";

export default function SettingsOrgPage() {
  return (
    <PlaceholderPage
      title="Organization"
      subtitle="Company profile. (UI scaffold)"
      primaryTitle="Profile"
      primaryBody="Edit tenant/company profile details and branch metadata."
      secondaryTitle="Coming soon"
      secondaryBody="This will be wired to /api/v1/tenancy/companies and /api/v1/tenancy/branches once final fields are set."
    />
  );
}
