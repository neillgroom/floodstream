"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  BUILDING_TYPES,
  OCCUPANCY_TYPES,
  FOUNDATION_TYPES,
  CAUSE_OPTIONS,
} from "@/lib/types";
import type { PrelimFormData } from "@/lib/types";

const EMPTY_FORM: PrelimFormData = {
  fg_number: "",
  insured_name: "",
  policy_number: "",
  date_of_loss: "",
  coverage_building: "",
  coverage_contents: "",
  carrier: "",
  contact_date: "",
  inspection_date: "",
  water_height_external: "",
  water_height_internal: "",
  water_entered_date: "",
  water_receded_date: "",
  building_type: "",
  occupancy: "",
  number_of_floors: "",
  building_elevated: "NO",
  split_level: "NO",
  foundation_type: "",
  cause: "",
  reserves_building: "",
  reserves_content: "",
  advance_building: "0",
  advance_contents: "0",
};

export default function PrelimPage() {
  const [form, setForm] = useState<PrelimFormData>(EMPTY_FORM);
  const [submitted, setSubmitted] = useState(false);

  function set(field: keyof PrelimFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch("/api/prelim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Error: ${err.error}`);
        setSubmitting(false);
        return;
      }
      setSubmitted(true);
    } catch (err) {
      alert(`Network error: ${err}`);
    }
    setSubmitting(false);
  }

  if (submitted) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="py-12 text-center space-y-4">
            <div className="text-4xl">✓</div>
            <h2 className="text-xl font-semibold text-emerald-400">Prelim Submitted for Review</h2>
            <p className="text-zinc-500">
              {form.insured_name} ({form.fg_number}) is now in the review queue.
            </p>
            <div className="flex gap-3 justify-center pt-4">
              <Button variant="outline" onClick={() => { setForm(EMPTY_FORM); setSubmitted(false); }}>
                New Prelim
              </Button>
              <a href="/">
                <Button>View Queue</Button>
              </a>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-xl font-semibold mb-6">New Preliminary Report</h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Claim Info */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Claim Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="FG File #" value={form.fg_number} onChange={(v) => set("fg_number", v)} placeholder="FG151849" required />
              <Field label="Policy Number" value={form.policy_number} onChange={(v) => set("policy_number", v)} placeholder="37115256152001" required />
            </div>
            <Field label="Insured Name" value={form.insured_name} onChange={(v) => set("insured_name", v)} placeholder="BRYAN HURLEY" required />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Date of Loss" value={form.date_of_loss} onChange={(v) => set("date_of_loss", v)} placeholder="MM/DD/YYYY" required type="date" />
              <Field label="Carrier" value={form.carrier} onChange={(v) => set("carrier", v)} placeholder="Wright Flood" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Building Coverage ($)" value={form.coverage_building} onChange={(v) => set("coverage_building", v)} placeholder="200000" type="number" />
              <Field label="Contents Coverage ($)" value={form.coverage_contents} onChange={(v) => set("coverage_contents", v)} placeholder="80000" type="number" />
            </div>
          </CardContent>
        </Card>

        {/* Inspection Dates */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Inspection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Contact Date" value={form.contact_date} onChange={(v) => set("contact_date", v)} type="date" required />
              <Field label="Inspection Date" value={form.inspection_date} onChange={(v) => set("inspection_date", v)} type="date" required />
            </div>
          </CardContent>
        </Card>

        {/* Water Info */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Flood Water
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Ext. Water Height (inches)" value={form.water_height_external} onChange={(v) => set("water_height_external", v)} placeholder="1" type="number" required />
              <div>
                <Field label="Int. Water Height (inches)" value={form.water_height_internal} onChange={(v) => set("water_height_internal", v)} placeholder="-84" type="number" required />
                <p className="text-xs text-zinc-600 mt-1">Negative = below grade (basement)</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Water Entered" value={form.water_entered_date} onChange={(v) => set("water_entered_date", v)} type="datetime-local" required />
              <Field label="Water Receded" value={form.water_receded_date} onChange={(v) => set("water_receded_date", v)} type="datetime-local" required />
            </div>
            <SelectField label="Cause of Flooding" value={form.cause} onChange={(v) => set("cause", v)} options={CAUSE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))} required />
          </CardContent>
        </Card>

        {/* Building */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Building
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <SelectField label="Building Type" value={form.building_type} onChange={(v) => set("building_type", v)} options={BUILDING_TYPES.map((t) => ({ value: t, label: t }))} required />
              <SelectField label="Occupancy" value={form.occupancy} onChange={(v) => set("occupancy", v)} options={OCCUPANCY_TYPES.map((t) => ({ value: t, label: t }))} required />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Floors" value={form.number_of_floors} onChange={(v) => set("number_of_floors", v)} placeholder="2" type="number" required />
              <SelectField label="Elevated?" value={form.building_elevated} onChange={(v) => set("building_elevated", v)} options={[{ value: "NO", label: "No" }, { value: "YES", label: "Yes" }]} />
              <SelectField label="Split Level?" value={form.split_level} onChange={(v) => set("split_level", v)} options={[{ value: "NO", label: "No" }, { value: "YES", label: "Yes" }]} />
            </div>
            <SelectField label="Foundation" value={form.foundation_type} onChange={(v) => set("foundation_type", v)} options={FOUNDATION_TYPES.map((t) => ({ value: t, label: t }))} required />
          </CardContent>
        </Card>

        {/* Reserves */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Reserves & Advance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Building Reserves ($)" value={form.reserves_building} onChange={(v) => set("reserves_building", v)} placeholder="10000" type="number" required />
              <Field label="Contents Reserves ($)" value={form.reserves_content} onChange={(v) => set("reserves_content", v)} placeholder="1000" type="number" required />
            </div>
            <Separator className="bg-zinc-800" />
            <div className="grid grid-cols-2 gap-4">
              <Field label="Advance Building ($)" value={form.advance_building} onChange={(v) => set("advance_building", v)} placeholder="0" type="number" />
              <Field label="Advance Contents ($)" value={form.advance_contents} onChange={(v) => set("advance_contents", v)} placeholder="0" type="number" />
            </div>
          </CardContent>
        </Card>

        <Button type="submit" disabled={submitting} className="w-full h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50">
          {submitting ? "Submitting..." : "Submit for Review"}
        </Button>
      </form>
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, type = "text", required = false,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-zinc-400">{label}{required && <span className="text-red-500 ml-0.5">*</span>}</Label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        type={type}
        required={required}
        className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-700"
      />
    </div>
  );
}

function SelectField({
  label, value, onChange, options, required = false,
}: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-zinc-400">{label}{required && <span className="text-red-500 ml-0.5">*</span>}</Label>
      <Select value={value} onValueChange={(v) => onChange(v ?? "")} required={required}>
        <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100">
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent className="bg-zinc-900 border-zinc-800">
          {options.map((opt) => (
            <SelectItem key={opt.value} value={opt.value} className="text-zinc-100">
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
