"use client";

import { useState, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
async function extractTextFromPdf(file: File, maxPages: number = 10): Promise<string> {
  // Dynamic import — pdf.js needs DOM APIs, can't run during SSR
  const pdfjsLib = await import("pdfjs-dist");
  pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;

  const buffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
  const pages = Math.min(pdf.numPages, maxPages);

  let text = "";
  for (let i = 1; i <= pages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const pageText = content.items
      .map((item) => ("str" in item ? item.str : ""))
      .join(" ");
    text += `\n--- PAGE ${i} ---\n${pageText}\n`;
  }

  return text;
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fgNumber, setFgNumber] = useState("");
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setResult(null);

    try {
      // Step 1: Extract text client-side (first 10 pages only)
      setStatus("Reading PDF...");
      const text = await extractTextFromPdf(file, 10);

      if (text.length < 100) {
        setResult({ success: false, message: "Could not extract text from PDF. It may be scanned or a photo sheet." });
        setUploading(false);
        return;
      }

      // Step 2: Send just the text to the API (small payload)
      setStatus("Extracting claim data...");
      const res = await fetch("/api/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          fg_number: fgNumber,
          filename: file.name,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setResult({
          success: true,
          message: `${data.insured_name || "Claim"} (${data.fg_number}) extracted and added to review queue.`,
        });
        setFile(null);
        setFgNumber("");
        if (fileRef.current) fileRef.current.value = "";
      } else {
        setResult({ success: false, message: data.error || "Extraction failed" });
      }
    } catch (err) {
      setResult({ success: false, message: `Error: ${err}` });
    }

    setUploading(false);
    setStatus("");
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-xl font-semibold">Upload Final Report PDF</h2>
      <p className="text-sm text-zinc-500">
        Upload an Xactimate Final Report PDF. FloodStream reads the first few pages,
        extracts the data, generates the XML, and adds it to the review queue.
      </p>

      <form onSubmit={handleUpload}>
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="py-6 space-y-4">
            <div className="space-y-1.5">
              <Label className="text-sm text-zinc-400">FG File # (optional)</Label>
              <Input
                value={fgNumber}
                onChange={(e) => setFgNumber(e.target.value)}
                placeholder="FG151429 — will auto-detect from PDF if blank"
                className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-700"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-sm text-zinc-400">
                Final Report PDF <span className="text-red-500">*</span>
              </Label>
              <Input
                ref={fileRef}
                type="file"
                accept=".pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
                className="bg-zinc-950 border-zinc-800 text-zinc-100 file:bg-zinc-800 file:text-zinc-300 file:border-0 file:rounded file:px-3 file:py-1 file:mr-3"
              />
              <p className="text-xs text-zinc-600">
                Any size — only the first pages are read (narrative + proof of loss)
              </p>
            </div>

            <Button
              type="submit"
              disabled={!file || uploading}
              className="w-full h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
            >
              {uploading ? status || "Processing..." : "Upload & Extract"}
            </Button>
          </CardContent>
        </Card>
      </form>

      {result && (
        <Card className={result.success ? "bg-emerald-950/30 border-emerald-800/50" : "bg-red-950/30 border-red-800/50"}>
          <CardContent className="py-4 px-5">
            <p className={`text-sm ${result.success ? "text-emerald-400" : "text-red-400"}`}>
              {result.message}
            </p>
            {result.success && (
              <a href="/" className="text-sm text-zinc-400 hover:text-zinc-200 mt-2 inline-block">
                View queue
              </a>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
