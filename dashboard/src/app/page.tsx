import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import type { ClaimStatus } from "@/lib/types";

const statusColors: Record<ClaimStatus, string> = {
  pending_review: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  approved: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  uploaded: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  rejected: "bg-red-500/10 text-red-400 border-red-500/20",
};

const statusLabels: Record<ClaimStatus, string> = {
  pending_review: "Needs Review",
  approved: "Approved",
  uploaded: "Uploaded",
  rejected: "Rejected",
};

interface ClaimRow {
  id: string;
  fg_number: string;
  insured_name: string;
  policy_number: string;
  date_of_loss: string;
  carrier: string;
  report_type: "prelim" | "final";
  status: ClaimStatus;
  confidence: number;
  created_at: string;
  warnings: string[];
}

export const dynamic = "force-dynamic";

export default async function ClaimsPage() {
  const { data: claims, error } = await supabase
    .from("claims")
    .select("id, fg_number, insured_name, policy_number, date_of_loss, carrier, report_type, status, confidence, created_at, warnings")
    .order("created_at", { ascending: false });

  const allClaims: ClaimRow[] = claims ?? [];
  const pending = allClaims.filter((c) => c.status === "pending_review");
  const completed = allClaims.filter((c) => c.status !== "pending_review");

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {error && (
        <Card className="bg-red-950/30 border-red-800/50">
          <CardContent className="py-3 px-5">
            <p className="text-sm text-red-400">Database error: {error.message}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Pending Review" value={pending.length} accent="text-amber-400" />
        <StatCard label="Approved" value={completed.filter((c) => c.status === "approved").length} accent="text-emerald-400" />
        <StatCard label="Uploaded" value={completed.filter((c) => c.status === "uploaded").length} accent="text-blue-400" />
        <StatCard label="Total" value={allClaims.length} accent="text-zinc-300" />
      </div>

      {pending.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider">
            Needs Review ({pending.length})
          </h2>
          <div className="space-y-3">
            {pending.map((claim) => (
              <ClaimCard key={claim.id} claim={claim} />
            ))}
          </div>
        </section>
      )}

      {completed.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider">
            Completed
          </h2>
          <div className="space-y-3">
            {completed.map((claim) => (
              <ClaimCard key={claim.id} claim={claim} />
            ))}
          </div>
        </section>
      )}

      {allClaims.length === 0 && !error && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="py-12 text-center">
            <p className="text-zinc-500">No claims in queue</p>
            <p className="text-sm text-zinc-600 mt-1">
              Claims appear here when processed via Telegram or the New Prelim form
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ClaimCard({ claim }: { claim: ClaimRow }) {
  return (
    <Link href={`/claim/${claim.id}`}>
      <Card className="bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-colors cursor-pointer">
        <CardContent className="py-4 px-5">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-zinc-100 truncate">
                  {claim.insured_name}
                </span>
                <Badge variant="outline" className={statusColors[claim.status]}>
                  {statusLabels[claim.status]}
                </Badge>
                <Badge
                  variant="outline"
                  className={
                    claim.report_type === "final"
                      ? "bg-purple-500/10 text-purple-400 border-purple-500/20"
                      : "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                  }
                >
                  {claim.report_type}
                </Badge>
              </div>
              <div className="flex items-center gap-3 mt-1 text-sm text-zinc-500 flex-wrap">
                <span className="font-mono">{claim.fg_number}</span>
                {claim.carrier && <span>{claim.carrier}</span>}
                <span>DOL: {claim.date_of_loss}</span>
                {claim.confidence < 1 && (
                  <span className="text-amber-500">
                    {Math.round(claim.confidence * 100)}% confidence
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {claim.warnings && claim.warnings.length > 0 && (
                <span className="text-xs text-amber-500">
                  {claim.warnings.length} warning{claim.warnings.length > 1 ? "s" : ""}
                </span>
              )}
              <Button variant="ghost" size="sm" className="text-zinc-400">
                Review
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardContent className="py-4 px-5">
        <p className={`text-2xl font-bold font-mono ${accent}`}>{value}</p>
        <p className="text-xs text-zinc-500 mt-1">{label}</p>
      </CardContent>
    </Card>
  );
}
