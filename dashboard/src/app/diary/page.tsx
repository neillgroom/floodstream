"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface ActivityEntry {
  activity_type: string;
  due_date: string;
  status: string;
  description: string;
}

interface PrelimDates {
  fg_number: string;
  date_assigned: string;
  date_contacted: string;
  date_inspected: string;
  date_prelim_due: string;
}

interface FinalData {
  fg_number: string;
  date_insured_contacted: string;
  date_loss_inspected: string;
  activities: ActivityEntry[];
  total_hours: string;
  total_expenses: string;
  total_travel: string;
}

type Mode = "prelim" | "final";

export default function DiaryPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Prelim mode state
  const [prelimDates, setPrelimDates] = useState<PrelimDates | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);

  // Final mode state
  const [finalData, setFinalData] = useState<FinalData | null>(null);

  async function handleExtract(mode: Mode) {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setPrelimDates(null);
    setFinalData(null);
    setSaved(null);

    try {
      const res = await fetch("/api/diary/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), mode }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error);
      } else if (mode === "prelim") {
        setPrelimDates(data.extracted);
      } else {
        setFinalData(data.extracted);
      }
    } catch (err) {
      setError(`Network error: ${err}`);
    }
    setLoading(false);
  }

  async function handleSavePrelim() {
    if (!prelimDates) return;
    setSaving(true);
    setSaved(null);

    try {
      const res = await fetch("/api/diary/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fg_number: prelimDates.fg_number,
          diary_data: {
            date_insured_contacted: prelimDates.date_contacted,
            date_loss_inspected: prelimDates.date_inspected,
            date_assigned: prelimDates.date_assigned,
            date_prelim_due: prelimDates.date_prelim_due,
          },
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error);
      } else {
        setSaved(data.fg_number);
      }
    } catch (err) {
      setError(`Save failed: ${err}`);
    }
    setSaving(false);
  }

  function handleActivityEdit(
    index: number,
    field: keyof ActivityEntry,
    value: string
  ) {
    if (!finalData) return;
    const updated = [...finalData.activities];
    updated[index] = { ...updated[index], [field]: value };
    setFinalData({ ...finalData, activities: updated });
  }

  function handleRemoveActivity(index: number) {
    if (!finalData) return;
    const updated = finalData.activities.filter((_, i) => i !== index);
    setFinalData({ ...finalData, activities: updated });
  }

  return (
    <div className="max-w-4xl mx-auto px-4">
      <h2 className="text-xl font-semibold mb-2">Diary Paste</h2>
      <p className="text-sm text-zinc-500 mb-6">
        Paste the raw diary log from Venue. Two uses: extract dates for the{" "}
        <span className="text-blue-400">prelim</span>, or filter to official
        actions for the{" "}
        <span className="text-emerald-400">final activity report PDF</span>.
      </p>

      <div className="space-y-6">
        {/* Paste area */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Raw Venue Diary Log
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={`Paste the diary tab from Venue — tab-separated rows:

FG151159    05/28/2025    05:44    05/28/2025    Note to File    ...
FG151159    05/28/2025    05:45    05/28/2025    Contacted Insured    ...
FG151159    10/04/2024    18:32    11/03/2024    Inspection Completed    ...`}
              className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-700 min-h-[200px] text-sm font-mono"
              autoFocus
            />
          </CardContent>
        </Card>

        {/* Two action buttons */}
        <div className="grid grid-cols-2 gap-4">
          <Button
            onClick={() => handleExtract("prelim")}
            disabled={loading || !text.trim()}
            className="h-12 text-base font-semibold bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "Extracting..." : "Extract for Prelim"}
          </Button>
          <Button
            onClick={() => handleExtract("final")}
            disabled={loading || !text.trim()}
            className="h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
          >
            {loading ? "Filtering..." : "Generate Activity Report"}
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-4 -mt-4">
          <p className="text-xs text-zinc-600 text-center">
            Haiku — grabs assigned, contacted, inspected dates
          </p>
          <p className="text-xs text-zinc-600 text-center">
            Sonnet — filters garbage, keeps only official actions
          </p>
        </div>

        {error && (
          <Card className="bg-zinc-900 border-red-800">
            <CardContent className="py-4 text-red-400 text-sm">
              {error}
            </CardContent>
          </Card>
        )}

        {/* === PRELIM MODE RESULTS === */}
        {prelimDates && (
          <>
            <Card className="bg-zinc-900 border-blue-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm text-blue-400 uppercase tracking-wider">
                  Prelim Dates — {prelimDates.fg_number}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {(
                    [
                      ["date_assigned", "Date Assigned"],
                      ["date_contacted", "Date Insured Contacted"],
                      ["date_inspected", "Date Loss Inspected"],
                      ["date_prelim_due", "Prelim Due Date"],
                    ] as const
                  ).map(([key, label]) => (
                    <div key={key} className="flex flex-col gap-1">
                      <label
                        className={`text-xs ${
                          key === "date_contacted"
                            ? "text-amber-400 font-medium"
                            : "text-zinc-500"
                        }`}
                      >
                        {label}
                      </label>
                      <input
                        type="text"
                        value={prelimDates[key]}
                        onChange={(e) =>
                          setPrelimDates({
                            ...prelimDates,
                            [key]: e.target.value,
                          })
                        }
                        className={`bg-zinc-950 border px-2 py-1 rounded text-sm font-mono ${
                          key === "date_contacted"
                            ? "border-amber-700 text-amber-300"
                            : "border-zinc-800 text-zinc-200"
                        }`}
                      />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Button
              onClick={handleSavePrelim}
              disabled={saving || !prelimDates.fg_number}
              className="w-full h-12 text-base font-semibold bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
            >
              {saving
                ? "Saving..."
                : `Save Dates to ${prelimDates.fg_number}`}
            </Button>

            {saved && (
              <Card className="bg-zinc-900 border-emerald-800">
                <CardContent className="py-4 text-emerald-400 text-sm">
                  Prelim dates saved to {saved}.
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* === FINAL MODE RESULTS === */}
        {finalData && (
          <>
            <Card className="bg-zinc-900 border-emerald-800">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm text-emerald-400 uppercase tracking-wider">
                    Activity Report — {finalData.fg_number}
                  </CardTitle>
                  <span className="text-xs text-zinc-500">
                    {finalData.activities?.length || 0} entries (filtered)
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                {/* Key dates */}
                <div className="flex gap-6 mb-4 pb-4 border-b border-zinc-800">
                  <div>
                    <label className="text-xs text-amber-400">
                      Date Insured Contacted
                    </label>
                    <input
                      type="text"
                      value={finalData.date_insured_contacted}
                      onChange={(e) =>
                        setFinalData({
                          ...finalData,
                          date_insured_contacted: e.target.value,
                        })
                      }
                      className="block bg-zinc-950 border border-amber-700 text-amber-300 px-2 py-1 rounded text-sm font-mono mt-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-500">
                      Date Loss Inspected
                    </label>
                    <input
                      type="text"
                      value={finalData.date_loss_inspected}
                      onChange={(e) =>
                        setFinalData({
                          ...finalData,
                          date_loss_inspected: e.target.value,
                        })
                      }
                      className="block bg-zinc-950 border border-zinc-800 text-zinc-200 px-2 py-1 rounded text-sm font-mono mt-1"
                    />
                  </div>
                </div>

                {/* Activity entries */}
                <div className="space-y-2">
                  {finalData.activities?.map((act, i) => (
                    <div
                      key={i}
                      className="grid grid-cols-[1fr_110px_130px_28px] gap-2 items-center py-2 border-b border-zinc-800/50 last:border-0"
                    >
                      <div className="space-y-1">
                        <input
                          type="text"
                          value={act.activity_type}
                          onChange={(e) =>
                            handleActivityEdit(
                              i,
                              "activity_type",
                              e.target.value
                            )
                          }
                          className="bg-zinc-950 border border-zinc-800 text-zinc-200 px-2 py-1 rounded text-sm font-medium w-full"
                        />
                        <input
                          type="text"
                          value={act.description}
                          onChange={(e) =>
                            handleActivityEdit(i, "description", e.target.value)
                          }
                          className="bg-zinc-950 border border-zinc-800 text-zinc-400 px-2 py-1 rounded text-xs w-full"
                        />
                      </div>
                      <input
                        type="text"
                        value={act.due_date}
                        onChange={(e) =>
                          handleActivityEdit(i, "due_date", e.target.value)
                        }
                        className="bg-zinc-950 border border-zinc-800 text-zinc-300 px-2 py-1 rounded text-sm font-mono text-center"
                      />
                      <span
                        className={`text-xs font-medium text-center px-2 py-1 rounded ${
                          act.status === "Completed"
                            ? "text-emerald-400 bg-emerald-500/10"
                            : "text-amber-400 bg-amber-500/10"
                        }`}
                      >
                        {act.status}
                      </span>
                      <button
                        onClick={() => handleRemoveActivity(i)}
                        className="text-zinc-600 hover:text-red-400 text-lg leading-none"
                        title="Remove entry"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>

                {/* Totals */}
                <div className="flex gap-6 mt-4 pt-4 border-t border-zinc-800 text-sm">
                  <div>
                    <span className="text-zinc-500">Hours:</span>{" "}
                    <span className="font-mono text-zinc-300">
                      {finalData.total_hours}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Expenses:</span>{" "}
                    <span className="font-mono text-zinc-300">
                      {finalData.total_expenses}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Travel:</span>{" "}
                    <span className="font-mono text-zinc-300">
                      {finalData.total_travel}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* JSON for pipeline */}
            <details className="text-sm">
              <summary className="text-zinc-500 cursor-pointer hover:text-zinc-300">
                Raw JSON (for pipeline)
              </summary>
              <pre className="mt-2 bg-zinc-950 border border-zinc-800 rounded p-4 text-xs text-zinc-400 overflow-x-auto">
                {JSON.stringify(finalData, null, 2)}
              </pre>
              <p className="mt-2 text-xs text-zinc-600">
                Output filename:{" "}
                <code className="text-zinc-400">
                  activity_{finalData.fg_number}_
                  {finalData.fg_number && "LASTNAME"}.pdf
                </code>
              </p>
            </details>
          </>
        )}
      </div>
    </div>
  );
}
