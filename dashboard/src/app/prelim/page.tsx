"use client";

import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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

type Step = "input" | "review" | "submitted";

export default function PrelimPage() {
  const [step, setStep] = useState<Step>("input");
  const [notes, setNotes] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [form, setForm] = useState<PrelimFormData>(EMPTY_FORM);
  const [extracting, setExtracting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [extractionNote, setExtractionNote] = useState("");
  const [nolQuery, setNolQuery] = useState("");
  const [nolSearching, setNolSearching] = useState(false);
  const [nolResult, setNolResult] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function set(field: keyof PrelimFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleNolSearch() {
    if (!nolQuery.trim()) return;
    setNolSearching(true);
    setNolResult("");

    try {
      const res = await fetch("/api/prelim/nol-search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: nolQuery.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        setNolResult(data.error || "Search failed");
        setNolSearching(false);
        return;
      }

      if (!data.found) {
        setNolResult(data.message || "No NOL found");
        setNolSearching(false);
        return;
      }

      // Pre-fill form from NOL fields
      const merged = { ...EMPTY_FORM };
      for (const [key, value] of Object.entries(data.fields)) {
        if (key in merged && value) {
          (merged as Record<string, string>)[key] = String(value);
        }
      }
      setForm(merged);

      // Build result message
      let msg = `${data.nol_name} (${data.confidence}%)`;
      if (data.missing?.length) {
        msg += ` — Missing: ${data.missing.join(", ")}`;
      }
      setNolResult(msg);

      // Go straight to review with pre-filled data
      setExtractionNote(`NOL pre-filled ${Object.keys(data.fields).length} fields. Fill in inspection data below.`);
      setStep("review");
    } catch (err) {
      setNolResult("Network error");
    }
    setNolSearching(false);
  }

  function handlePhotoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      const newPhotos = Array.from(e.target.files);
      setPhotos((prev) => [...prev, ...newPhotos].slice(0, 10));
    }
  }

  function removePhoto(index: number) {
    setPhotos((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleExtract() {
    if (!notes.trim()) return;
    setExtracting(true);
    setExtractionNote("");

    try {
      const res = await fetch("/api/prelim/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: notes.trim() }),
      });

      if (!res.ok) {
        const err = await res.json();
        setExtractionNote(`Extraction failed: ${err.error}. You can fill in the fields manually.`);
        setStep("review");
        setExtracting(false);
        return;
      }

      const { extracted } = await res.json();

      // Merge extracted fields into form, keeping defaults for missing fields
      const merged = { ...EMPTY_FORM };
      for (const [key, value] of Object.entries(extracted)) {
        if (key in merged && value !== null && value !== undefined && value !== "") {
          (merged as Record<string, string>)[key] = String(value);
        }
      }
      setForm(merged);

      // Count how many fields were extracted vs total needed
      const filledCount = Object.entries(merged).filter(
        ([k, v]) => v && v !== "0" && v !== "NO" && k !== "building_elevated" && k !== "split_level"
      ).length;
      setExtractionNote(
        `Extracted ${filledCount} of 24 fields. Review and fill in anything missing.`
      );
      setStep("review");
    } catch (err) {
      setExtractionNote(`Network error. You can fill in the fields manually.`);
      setStep("review");
    }
    setExtracting(false);
  }

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
      setStep("submitted");
    } catch (err) {
      alert(`Network error: ${err}`);
    }
    setSubmitting(false);
  }

  // --- STEP 3: Success ---
  if (step === "submitted") {
    return (
      <div className="max-w-2xl mx-auto px-4">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="py-12 text-center space-y-4">
            <div className="text-4xl">✓</div>
            <h2 className="text-xl font-semibold text-emerald-400">
              Prelim Submitted for Review
            </h2>
            <p className="text-zinc-500">
              {form.insured_name || "Claim"} ({form.fg_number || "—"}) is now in
              the review queue.
            </p>
            <div className="flex gap-3 justify-center pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setForm(EMPTY_FORM);
                  setNotes("");
                  setPhotos([]);
                  setExtractionNote("");
                  setStep("input");
                }}
              >
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

  // --- STEP 1: Smart Paste Input ---
  if (step === "input") {
    return (
      <div className="max-w-2xl mx-auto px-4">
        <h2 className="text-xl font-semibold mb-2">New Preliminary Report</h2>
        <p className="text-sm text-zinc-500 mb-6">
          Search for the NOL by FG number or insured name, or paste field notes below.
        </p>

        <div className="space-y-6">
          {/* NOL Search */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
                Search NOL
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Input
                  value={nolQuery}
                  onChange={(e) => setNolQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleNolSearch()}
                  placeholder="FG151849 or HURLEY"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-700 flex-1"
                />
                <Button
                  onClick={handleNolSearch}
                  disabled={nolSearching || !nolQuery.trim()}
                  className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
                >
                  {nolSearching ? "Searching..." : "Search"}
                </Button>
              </div>
              {nolResult && (
                <p className="text-sm text-amber-400/80 mt-2">{nolResult}</p>
              )}
            </CardContent>
          </Card>

          {/* Notes input */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
                Or Paste Field Notes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={`Paste your notes here. Example:\n\nFG151849 HURLEY\nPolicy 37115256152001, Wright Flood\nDOL 3/15/2026\nInspected today 3/20, contacted 3/18\nWater 2 inches outside, -6 inside (basement)\nWater came in 3/15 around noon, went down by 3/16 6am\nMain dwelling, owner occupied, 2 floors, slab\nRainfall\nReserves 15000 bldg, 3000 contents\nNo advance`}
                className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-700 min-h-[200px] text-base"
                autoFocus
              />
            </CardContent>
          </Card>

          {/* Photos */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
                Photos ({photos.length}/10)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={handlePhotoSelect}
                className="hidden"
              />

              {photos.length > 0 && (
                <div className="grid grid-cols-3 gap-2 mb-4">
                  {photos.map((photo, i) => (
                    <div key={i} className="relative group">
                      <img
                        src={URL.createObjectURL(photo)}
                        alt={`Photo ${i + 1}`}
                        className="w-full h-24 object-cover rounded border border-zinc-800"
                      />
                      <button
                        type="button"
                        onClick={() => removePhoto(i)}
                        className="absolute top-1 right-1 bg-black/70 text-zinc-300 rounded-full w-6 h-6 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        ×
                      </button>
                      <p className="text-xs text-zinc-600 mt-1 truncate">
                        {photo.name}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={photos.length >= 10}
                className="w-full border-dashed border-zinc-700 text-zinc-400 hover:text-zinc-200 h-12"
              >
                {photos.length === 0
                  ? "Add Photos (from camera roll or files)"
                  : `Add More Photos (${10 - photos.length} remaining)`}
              </Button>
              <p className="text-xs text-zinc-600 mt-2">
                Front, address plate, sides, rear, water marks, interior damage.
                Photos are included in the prelim PDF package.
              </p>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              onClick={handleExtract}
              disabled={extracting || !notes.trim()}
              className="flex-1 h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
            >
              {extracting ? "Reading notes..." : "Extract & Review"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setStep("review")}
              className="h-12 text-zinc-400"
            >
              Skip — Manual Entry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // --- STEP 2: Review & Edit Extracted Fields ---
  return (
    <div className="max-w-2xl mx-auto px-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold">Review Prelim Data</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setStep("input")}
          className="text-zinc-500 hover:text-zinc-300"
        >
          ← Back to notes
        </Button>
      </div>

      {extractionNote && (
        <p className="text-sm text-amber-400/80 mb-4">{extractionNote}</p>
      )}

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
              <Field
                label="FG File #"
                value={form.fg_number}
                onChange={(v) => set("fg_number", v)}
                placeholder="FG151849"
                required
              />
              <Field
                label="Policy Number"
                value={form.policy_number}
                onChange={(v) => set("policy_number", v)}
                placeholder="37115256152001"
                required
              />
            </div>
            <Field
              label="Insured Name"
              value={form.insured_name}
              onChange={(v) => set("insured_name", v)}
              placeholder="BRYAN HURLEY"
              required
            />
            <div className="grid grid-cols-2 gap-4">
              <Field
                label="Date of Loss"
                value={form.date_of_loss}
                onChange={(v) => set("date_of_loss", v)}
                placeholder="MM/DD/YYYY"
                required
                type="date"
              />
              <Field
                label="Carrier"
                value={form.carrier}
                onChange={(v) => set("carrier", v)}
                placeholder="Wright Flood"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field
                label="Building Coverage ($)"
                value={form.coverage_building}
                onChange={(v) => set("coverage_building", v)}
                placeholder="200000"
                type="number"
              />
              <Field
                label="Contents Coverage ($)"
                value={form.coverage_contents}
                onChange={(v) => set("coverage_contents", v)}
                placeholder="80000"
                type="number"
              />
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
              <Field
                label="Contact Date"
                value={form.contact_date}
                onChange={(v) => set("contact_date", v)}
                type="date"
                required
              />
              <Field
                label="Inspection Date"
                value={form.inspection_date}
                onChange={(v) => set("inspection_date", v)}
                type="date"
                required
              />
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
              <Field
                label="Ext. Water Height (in)"
                value={form.water_height_external}
                onChange={(v) => set("water_height_external", v)}
                placeholder="1"
                type="number"
                required
              />
              <div>
                <Field
                  label="Int. Water Height (in)"
                  value={form.water_height_internal}
                  onChange={(v) => set("water_height_internal", v)}
                  placeholder="-84"
                  type="number"
                  required
                />
                <p className="text-xs text-zinc-600 mt-1">
                  Negative = below grade
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field
                label="Water Entered"
                value={form.water_entered_date}
                onChange={(v) => set("water_entered_date", v)}
                type="datetime-local"
                required
              />
              <Field
                label="Water Receded"
                value={form.water_receded_date}
                onChange={(v) => set("water_receded_date", v)}
                type="datetime-local"
                required
              />
            </div>
            <SelectField
              label="Cause of Flooding"
              value={form.cause}
              onChange={(v) => set("cause", v)}
              options={CAUSE_OPTIONS.map((o) => ({
                value: o.value,
                label: o.label,
              }))}
              required
            />
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
              <SelectField
                label="Building Type"
                value={form.building_type}
                onChange={(v) => set("building_type", v)}
                options={BUILDING_TYPES.map((t) => ({ value: t, label: t }))}
                required
              />
              <SelectField
                label="Occupancy"
                value={form.occupancy}
                onChange={(v) => set("occupancy", v)}
                options={OCCUPANCY_TYPES.map((t) => ({ value: t, label: t }))}
                required
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field
                label="Floors"
                value={form.number_of_floors}
                onChange={(v) => set("number_of_floors", v)}
                placeholder="2"
                type="number"
                required
              />
              <SelectField
                label="Elevated?"
                value={form.building_elevated}
                onChange={(v) => set("building_elevated", v)}
                options={[
                  { value: "NO", label: "No" },
                  { value: "YES", label: "Yes" },
                ]}
              />
              <SelectField
                label="Split Level?"
                value={form.split_level}
                onChange={(v) => set("split_level", v)}
                options={[
                  { value: "NO", label: "No" },
                  { value: "YES", label: "Yes" },
                ]}
              />
            </div>
            <SelectField
              label="Foundation"
              value={form.foundation_type}
              onChange={(v) => set("foundation_type", v)}
              options={FOUNDATION_TYPES.map((t) => ({ value: t, label: t }))}
              required
            />
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
              <Field
                label="Building Reserves ($)"
                value={form.reserves_building}
                onChange={(v) => set("reserves_building", v)}
                placeholder="10000"
                type="number"
                required
              />
              <Field
                label="Contents Reserves ($)"
                value={form.reserves_content}
                onChange={(v) => set("reserves_content", v)}
                placeholder="1000"
                type="number"
                required
              />
            </div>
            <Separator className="bg-zinc-800" />
            <div className="grid grid-cols-2 gap-4">
              <Field
                label="Advance Building ($)"
                value={form.advance_building}
                onChange={(v) => set("advance_building", v)}
                placeholder="0"
                type="number"
              />
              <Field
                label="Advance Contents ($)"
                value={form.advance_contents}
                onChange={(v) => set("advance_contents", v)}
                placeholder="0"
                type="number"
              />
            </div>
          </CardContent>
        </Card>

        {/* Photos summary */}
        {photos.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
                Photos ({photos.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-2">
                {photos.map((photo, i) => (
                  <img
                    key={i}
                    src={URL.createObjectURL(photo)}
                    alt={`Photo ${i + 1}`}
                    className="w-full h-20 object-cover rounded border border-zinc-800"
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <Button
          type="submit"
          disabled={submitting}
          className="w-full h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
        >
          {submitting ? "Submitting..." : "Submit for Review"}
        </Button>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-zinc-400">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </Label>
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
  label,
  value,
  onChange,
  options,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm text-zinc-400">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </Label>
      <Select
        value={value}
        onValueChange={(v) => onChange(v ?? "")}
        required={required}
      >
        <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100">
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent className="bg-zinc-900 border-zinc-800">
          {options.map((opt) => (
            <SelectItem
              key={opt.value}
              value={opt.value}
              className="text-zinc-100"
            >
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
