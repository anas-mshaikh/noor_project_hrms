import React from "react";
import { View, Text, ActivityIndicator, ScrollView } from "react-native";
import { auth, db } from "../lib/firebase";
import { doc, getDoc } from "firebase/firestore";
import { paths } from "../data/paths";

type UserMapping = {
  tenant_id: string;
  branch_id: string;
  employee_id: string;
  employee_code: string;
  department?: string | null;
  role: string;
  active: boolean;
};

export function HomeScreen() {
  const [loading, setLoading] = React.useState(true);
  const [mapping, setMapping] = React.useState<UserMapping | null>(null);
  const [monthKey] = React.useState("2026-01"); // MVP: hardcode first; later we’ll list months
  const [myStats, setMyStats] = React.useState<any>(null);
  const [overall, setOverall] = React.useState<any>(null);

  React.useEffect(() => {
    async function run() {
      setLoading(true);
      const uid = auth.currentUser?.uid;
      if (!uid) return;

      // 1) users/{uid}
      const mappingSnap = await getDoc(doc(db, paths.userMapping(uid)));
      if (!mappingSnap.exists())
        throw new Error("Missing users/{uid} mapping doc.");
      const m = mappingSnap.data() as UserMapping;
      if (!m.active) throw new Error("Account is inactive.");
      setMapping(m);

      // 2) employee month doc
      const statsSnap = await getDoc(
        doc(
          db,
          paths.employeeMonth(m.tenant_id, m.branch_id, monthKey, m.employee_code),
        ),
      );
      setMyStats(statsSnap.exists() ? statsSnap.data() : null);

      // 3) overall leaderboard
      const lbSnap = await getDoc(
        doc(db, paths.leaderboardOverall(m.tenant_id, m.branch_id, monthKey)),
      );
      setOverall(lbSnap.exists() ? lbSnap.data() : null);

      setLoading(false);
    }

    run().catch((e) => {
      console.error(e);
      setLoading(false);
    });
  }, [monthKey]);

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!mapping) return <Text style={{ padding: 16 }}>No mapping found.</Text>;

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
      <Text style={{ fontSize: 18, fontWeight: "600" }}>
        Hi {myStats?.name ?? mapping.employee_code}
      </Text>

      <Text>Month: {monthKey}</Text>

      <View style={{ padding: 12, borderWidth: 1, borderRadius: 10 }}>
        <Text style={{ fontWeight: "600" }}>My Stats</Text>
        <Text>Net Sales: {myStats?.net_sales ?? "-"}</Text>
        <Text>Bills: {myStats?.bills ?? "-"}</Text>
        <Text>Customers: {myStats?.customers ?? "-"}</Text>
        <Text>Present: {myStats?.present ?? "-"}</Text>
        <Text>Absent: {myStats?.absent ?? "-"}</Text>
        <Text>Rank Overall: {myStats?.rank_overall ?? "-"}</Text>
        <Text>Rank Dept: {myStats?.rank_department ?? "-"}</Text>
      </View>

      <View style={{ padding: 12, borderWidth: 1, borderRadius: 10 }}>
        <Text style={{ fontWeight: "600" }}>Overall Leaderboard (Top)</Text>
        {overall?.top?.slice(0, 5)?.map((row: any) => (
          <Text key={row.employee_code}>
            #{row.rank} {row.name} — {row.metric_value}
          </Text>
        )) ?? <Text>-</Text>}
      </View>
    </ScrollView>
  );
}
