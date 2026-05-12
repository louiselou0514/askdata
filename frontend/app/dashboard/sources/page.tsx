"use client";

import { useEffect, useRef, useState } from "react";
import { listDataSources, uploadCSV, deleteDataSource, type DataSource } from "@/lib/api";

type Mode = "none" | "csv";

export default function SourcesPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [mode, setMode] = useState<Mode>("none");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // CSV form
  const [csvName, setCsvName] = useState("");

  useEffect(() => {
    listDataSources().then(setSources);
  }, []);

  async function handleCSVUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !csvName) return;
    setLoading(true);
    setError("");
    try {
      const ds = await uploadCSV(csvName, file);
      setSources((prev) => [...prev, ds]);
      setMode("none");
      setCsvName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: string) {
    setDeleteLoading(true);
    setError("");
    try {
      await deleteDataSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      setConfirmDeleteId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove data source");
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-xl font-semibold text-gray-900 mb-1">Data Sources</h1>
      <p className="text-sm text-gray-500 mb-6">
        Connect your data so stakeholders can ask questions about it.
      </p>

      {/* Connected sources list */}
      {sources.length > 0 && (
        <div className="mb-8 space-y-2">
          {sources.map((s) => (
            <div key={s.id} className="flex items-center justify-between bg-white border border-gray-200 rounded-xl px-4 py-3">
              <div>
                <p className="font-medium text-sm text-gray-900">{s.name}</p>
                <p className="text-xs text-gray-400 capitalize">{s.source_type.replace("_", " ")}</p>
              </div>
              <div className="flex items-center gap-3">
                {confirmDeleteId === s.id ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">Remove?</span>
                    <button
                      onClick={() => handleDelete(s.id)}
                      disabled={deleteLoading}
                      className="text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
                    >
                      {deleteLoading ? "…" : "Yes"}
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteId(s.id)}
                    title="Remove"
                    className="text-gray-300 hover:text-red-400 transition-colors text-sm leading-none p-1 rounded"
                  >
                    ✕
                  </button>
                )}
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  s.status === "connected"
                    ? "bg-green-50 text-green-700"
                    : s.status === "error"
                    ? "bg-red-50 text-red-700"
                    : "bg-yellow-50 text-yellow-700"
                }`}>
                  {s.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add source buttons */}
      {mode === "none" && (
        <div className="flex gap-3">
          <button onClick={() => setMode("csv")}
            className="rounded-xl border-2 border-dashed border-gray-300 px-5 py-3 text-sm text-gray-600 hover:border-indigo-400 hover:text-indigo-600 transition-colors">
            + Upload CSV / Excel
          </button>
        </div>
      )}

      {/* CSV form */}
      {mode === "csv" && (
        <form onSubmit={handleCSVUpload} className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <h2 className="font-semibold text-gray-800">Upload CSV or Excel</h2>
          <div>
            <label className="block text-sm text-gray-600 mb-1">Name</label>
            <input type="text" value={csvName} onChange={(e) => setCsvName(e.target.value)} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">File</label>
            <input type="file" ref={fileRef} accept=".csv,.xlsx,.xls" required
              className="text-sm text-gray-600" />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex gap-3">
            <button type="submit" disabled={loading}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
              {loading ? "Uploading…" : "Upload & Connect"}
            </button>
            <button type="button" onClick={() => setMode("none")}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </form>
      )}

    </div>
  );
}
