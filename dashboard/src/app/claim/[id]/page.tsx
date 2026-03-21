"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import type { ClaimStatus } from "@/lib/types";

interface ClaimDetail {
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
  xml_data: Record<string, string>;
  xml_output: string;
}

export default function ClaimDetailPage() {
  const params = useParams();
  const [claim, setClaim] = useState<ClaimDetail | null>(null);
  const [status, setStatus] = useState<ClaimStatus>("pending_review");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`/api/claims/${params.id}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          setClaim(data);
          setStatus(data.status);
        }
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [params.id]);

  async function handleApprove() {
    const res = await fetch(`/api/claims/${params.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "approved", reviewed_by: "Betsy" }),
    });
    if (res.ok) setStatus("approved");
  }

  async function handleReject() {
    const res = await fetch(`/api/claims/${params.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "rejected", reviewed_by: "Betsy" }),
    });
    if (res.ok) setStatus("rejected");
  }

  if (loading) {
    return <div className="max-w-5xl mx-auto py-12 text-center text-zinc-500">Loading claim...</div>;
  }

  if (error || !claim) {
    return (
      <div className="max-w-5xl mx-auto py-12 text-center">
        <p className="text-red-400">{error || "Claim not found"}</p>
      </div>
    );
  }

  const xmlFields = (claim.xml_data || {}) as Record<string, string>;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold">{claim.insured_name}</h2>
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
            <Badge
              variant="outline"
              className={
                status === "pending_review"
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  : status === "approved"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : status === "rejected"
                      ? "bg-red-500/10 text-red-400 border-red-500/20"
                      : "bg-blue-500/10 text-blue-400 border-blue-500/20"
              }
            >
              {status === "pending_review" ? "Needs Review" : status}
            </Badge>
          </div>
          <div className="flex items-center gap-3 mt-1 text-sm text-zinc-500">
            <span className="font-mono">{claim.fg_number}</span>
            {claim.carrier && <span>{claim.carrier}</span>}
            <span>DOL: {claim.date_of_loss}</span>
            <span>Confidence: {Math.round(claim.confidence * 100)}%</span>
          </div>
        </div>

        {status === "pending_review" && (
          <div className="flex gap-3">
            <Button variant="outline" className="border-red-800 text-red-400 hover:bg-red-950" onClick={handleReject}>
              Reject
            </Button>
            <Button className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold" onClick={handleApprove}>
              Approve & Upload
            </Button>
          </div>
        )}

        {status === "approved" && (
          <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-base py-2 px-4">
            Approved
          </Badge>
        )}
      </div>

      {/* Warnings */}
      {claim.warnings && claim.warnings.length > 0 && (
        <Card className="bg-amber-950/30 border-amber-800/50">
          <CardContent className="py-3 px-5">
            <p className="text-sm font-medium text-amber-400 mb-1">Warnings</p>
            {claim.warnings.map((w, i) => (
              <p key={i} className="text-sm text-amber-300/70">{w}</p>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="summary">
        <TabsList className="bg-zinc-900 border border-zinc-800">
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="xml">XML Preview</TabsTrigger>
          <TabsTrigger value="details">All Fields</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="mt-4">
          {claim.report_type === "final" ? (
            <FinalSummary fields={xmlFields} />
          ) : (
            <PrelimSummary fields={xmlFields} />
          )}
        </TabsContent>

        <TabsContent value="xml" className="mt-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="py-4">
              <pre className="text-xs font-mono text-zinc-400 overflow-x-auto whitespace-pre leading-relaxed max-h-[600px] overflow-y-auto">
                {claim.xml_output || "No XML generated yet"}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="details" className="mt-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="py-4">
              <div className="space-y-1">
                {Object.entries(xmlFields).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between py-1.5 text-sm border-b border-zinc-800/50 last:border-0">
                    <span className="text-zinc-500 font-mono text-xs">{key}</span>
                    <span className="text-zinc-200 font-mono text-xs">{String(value)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FinalSummary({ fields }: { fields: Record<string, string> }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">Building (Coverage A)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Row label="Property RCV" value={dollar(fields.prop_val_bldg_rcv)} />
          <Row label="RCV Loss" value={dollar(fields.bldg_rcv_loss)} />
          <Row label="Depreciation" value={dollar(fields.bldg_depreciation)} muted />
          <Row label="ACV Loss" value={dollar(fields.bldg_acv_loss)} />
          <Separator className="bg-zinc-800" />
          <Row label="Claim Payable" value={dollar(fields.bldg_claim_payable)} highlight />
        </CardContent>
      </Card>
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">Contents (Coverage B)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Row label="Property RCV" value={dollar(fields.prop_val_cont_rcv)} />
          <Row label="RCV Loss" value={dollar(fields.cont_rcv_loss)} />
          <Row label="Depreciation" value={dollar(fields.cont_non_recoverable_depreciation)} muted />
          <Row label="ACV Loss" value={dollar(fields.cont_acv_loss)} />
          <Separator className="bg-zinc-800" />
          <Row label="Claim Payable" value={dollar(fields.cont_claim_payable)} highlight />
        </CardContent>
      </Card>
    </div>
  );
}

function PrelimSummary({ fields }: { fields: Record<string, string> }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">Inspection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Row label="Contact Date" value={fields.contact_date} />
          <Row label="Inspection Date" value={fields.inspection_date} />
          <Row label="Ext Water Height" value={`${fields.water_height_external}"`} />
          <Row label="Int Water Height" value={`${fields.water_height_internal}"`} />
          <Row label="Water Entered" value={fields.water_entered_date} />
          <Row label="Water Receded" value={fields.water_receded_date} />
          <Row label="Cause" value={fields.cause} />
        </CardContent>
      </Card>
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">Coverage & Reserves</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Row label="Building Type" value={fields.building_type} />
          <Row label="Occupancy" value={fields.occupancy} />
          <Row label="Floors" value={fields.number_of_floors} />
          <Row label="Foundation" value={fields.foundation_type} />
          <Separator className="bg-zinc-800" />
          <Row label="Bldg Coverage" value={dollar(fields.coverage_building)} />
          <Row label="Cont Coverage" value={dollar(fields.coverage_contents)} />
          <Row label="Bldg Reserves" value={dollar(fields.reserves_building)} highlight />
          <Row label="Cont Reserves" value={dollar(fields.reserves_content)} highlight />
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value, highlight = false, muted = false }: {
  label: string; value: string; highlight?: boolean; muted?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className={muted ? "text-zinc-600" : "text-zinc-400"}>{label}</span>
      <span className={`font-mono ${highlight ? "text-emerald-400 font-semibold" : muted ? "text-zinc-600" : "text-zinc-200"}`}>
        {value || "—"}
      </span>
    </div>
  );
}

function dollar(val: string | undefined): string {
  if (!val) return "—";
  try {
    return `$${parseFloat(val).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  } catch {
    return val;
  }
}
