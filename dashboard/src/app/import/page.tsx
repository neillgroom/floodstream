"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function ImportPage() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [createFolders, setCreateFolders] = useState(true);

  async function handleImport() {
    if (!text.trim()) return;
    setLoading(true);
    setResults(null);

    try {
      const res = await fetch("/api/claims/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), create_folders: createFolders }),
      });

      const data = await res.json();
      if (!res.ok) {
        setResults({ error: data.error });
      } else {
        setResults(data);
      }
    } catch (err) {
      setResults({ error: `Network error: ${err}` });
    }
    setLoading(false);
  }

  return (
    <div className="max-w-3xl mx-auto px-4">
      <h2 className="text-xl font-semibold mb-2">Import Claims</h2>
      <p className="text-sm text-zinc-500 mb-6">
        Paste the open claims list from Venue. Creates Supabase records and
        Dropbox folders for each claim. Skips duplicates.
      </p>

      <div className="space-y-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm text-zinc-400 uppercase tracking-wider">
              Venue Claims List
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste from Venue open claims page — tab-separated rows with Policy#, FG#, DOL, Claim#, Adjuster, Insured, Address..."
              className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-700 min-h-[200px] text-sm font-mono"
              autoFocus
            />
            <div className="flex items-center gap-3 mt-4">
              <label className="flex items-center gap-2 text-sm text-zinc-400">
                <input
                  type="checkbox"
                  checked={createFolders}
                  onChange={(e) => setCreateFolders(e.target.checked)}
                  className="rounded border-zinc-700"
                />
                Create Dropbox folders
              </label>
            </div>
          </CardContent>
        </Card>

        <Button
          onClick={handleImport}
          disabled={loading || !text.trim()}
          className="w-full h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Importing..." : "Import Claims"}
        </Button>

        {results?.folderError && (
          <Card className="bg-zinc-900 border-amber-800">
            <CardContent className="py-4 text-amber-400 text-sm">
              Dropbox folders: {results.folderError}
            </CardContent>
          </Card>
        )}

        {results && !results.error && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="py-6">
              <div className="flex gap-6 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-emerald-400">
                    {results.created}
                  </div>
                  <div className="text-xs text-zinc-500">Created</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-zinc-500">
                    {results.skipped}
                  </div>
                  <div className="text-xs text-zinc-500">Skipped</div>
                </div>
                {results.errors > 0 && (
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-400">
                      {results.errors}
                    </div>
                    <div className="text-xs text-zinc-500">Errors</div>
                  </div>
                )}
              </div>
              <div className="space-y-1 text-sm">
                {results.results?.map(
                  (r: any, i: number) => (
                    <div
                      key={i}
                      className={`flex justify-between py-1 px-2 rounded ${
                        r.status === "exists"
                          ? "text-zinc-600"
                          : r.status.startsWith("error")
                          ? "text-red-400 bg-red-500/5"
                          : "text-emerald-400 bg-emerald-500/5"
                      }`}
                    >
                      <span>
                        {r.fg} — {r.name}
                      </span>
                      <span className="text-xs">{r.status}</span>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {results?.error && (
          <Card className="bg-zinc-900 border-red-800">
            <CardContent className="py-4 text-red-400 text-sm">
              {results.error}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
