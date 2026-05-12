"use client";

import { useEffect, useRef, useState } from "react";
import { runQuery, type QueryResult, type SuggestedPrompt } from "@/lib/api";
import { generateDocHTML, generateSlidesHTML } from "@/lib/export";
import { ResultsTable } from "./ResultsTable";
import { ResultsChart } from "./ResultsChart";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  result?: QueryResult;
  error?: string;
}

interface ExportModal {
  html: string;
  title: string;
}

const PROMPT_COLORS = [
  "bg-indigo-50 text-indigo-600",
  "bg-amber-50 text-amber-600",
  "bg-emerald-50 text-emerald-600",
  "bg-rose-50 text-rose-600",
];

const FALLBACK_TEMPLATES: Array<{ label: string; icon: string; q: (name: string) => string }> = [
  { label: "Trend over time",      icon: "📈", q: (n) => `How has ${n} changed over time?` },
  { label: "Top performers",       icon: "🏆", q: (n) => `What are the top 10 ${n} by value?` },
  { label: "Breakdown by category",icon: "🗂️", q: (n) => `Show me a breakdown of ${n} by category` },
  { label: "Overall summary",      icon: "📊", q: (n) => `Give me an overall summary of ${n}` },
];

function buildFallbackPrompts(sources: Array<{ name: string }>): SuggestedPrompt[] {
  if (sources.length === 0) return [];
  return FALLBACK_TEMPLATES.map((t, i) => {
    const name = sources[i % sources.length].name;
    return { label: t.label, icon: t.icon, question: t.q(name) };
  });
}

interface ChatInterfaceProps {
  dataSources: Array<{ id: string; name: string }>;
  suggestedPrompts?: SuggestedPrompt[];
  promptsLoading?: boolean;
  externalQuestion?: string;
  onExternalConsumed?: () => void;
  onQueryComplete?: () => void;
}

export function ChatInterface({ dataSources, suggestedPrompts = [], promptsLoading = false, externalQuestion, onExternalConsumed, onQueryComplete }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [exportModal, setExportModal] = useState<ExportModal | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (externalQuestion) {
      submit(externalQuestion);
      onExternalConsumed?.();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalQuestion]);

  function handleExport(type: "doc" | "slides", question: string, result: QueryResult) {
    const html = type === "doc" ? generateDocHTML(question, result) : generateSlidesHTML(question, result);
    const title = type === "doc" ? "Business Document" : "Business Slides";
    setExportModal({ html, title });
  }

  function handlePrint() {
    iframeRef.current?.contentWindow?.print();
  }

  async function submit(question: string) {
    const q = question.trim();
    if (!q || loading || dataSources.length === 0) return;
    setMessages((p) => [...p, { id: crypto.randomUUID(), role: "user", text: q }]);
    setInput("");
    setLoading(true);
    try {
      const result = await runQuery(q, dataSources.map((ds) => ds.id));
      setMessages((p) => [
        ...p,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: `${result.row_count} row${result.row_count !== 1 ? "s" : ""} · ${result.execution_ms}ms`,
          result,
        },
      ]);
      onQueryComplete?.();
    } catch (err) {
      setMessages((p) => [
        ...p,
        { id: crypto.randomUUID(), role: "assistant", text: "", error: err instanceof Error ? err.message : "Something went wrong" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  }

  const hasMessages = messages.length > 0;
  const displayPrompts = suggestedPrompts.length > 0 ? suggestedPrompts : buildFallbackPrompts(dataSources);

  return (
    <div className="flex flex-col h-full bg-white">

      {/* Export overlay */}
      {exportModal && (
        <div className="fixed inset-0 z-50 flex flex-col bg-gray-900/80">
          {/* Toolbar */}
          <div className="flex-shrink-0 flex items-center justify-between bg-white px-6 py-3 shadow-md">
            <span className="text-sm font-semibold text-gray-800">{exportModal.title}</span>
            <div className="flex items-center gap-3">
              <p className="text-xs text-gray-400">Print → Save as PDF to download</p>
              <button
                onClick={handlePrint}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                🖨️ Print / Save as PDF
              </button>
              <button
                onClick={() => setExportModal(null)}
                className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                ✕ Close
              </button>
            </div>
          </div>
          {/* Preview */}
          <iframe
            ref={iframeRef}
            srcDoc={exportModal.html}
            className="flex-1 w-full border-0"
            title={exportModal.title}
          />
        </div>
      )}

      {/* Thread */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full px-8 pb-32">
            <div className="w-14 h-14 bg-indigo-600 rounded-2xl flex items-center justify-center mb-5 shadow-lg shadow-indigo-200">
              <span className="text-white text-2xl font-bold">A</span>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Welcome to AskData</h1>
            <p className="text-sm text-gray-400 mb-10 text-center max-w-sm">
              Get started by asking a question and AskData can do the rest. Not sure where to start?
            </p>
            <div className="grid grid-cols-2 gap-3 w-full max-w-xl">
              {promptsLoading
                ? Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="flex items-start gap-3 p-4 bg-white border border-gray-200 rounded-2xl animate-pulse">
                      <div className="w-9 h-9 rounded-xl bg-gray-100 flex-shrink-0" />
                      <div className="flex-1 space-y-2 pt-0.5">
                        <div className="h-3 bg-gray-100 rounded w-3/4" />
                        <div className="h-2.5 bg-gray-100 rounded w-full" />
                      </div>
                    </div>
                  ))
                : displayPrompts.map((p, i) => (
                    <button
                      key={p.question}
                      onClick={() => submit(p.question)}
                      className="group flex items-start gap-3 p-4 bg-white border border-gray-200 rounded-2xl text-left hover:border-indigo-200 hover:shadow-md transition-all"
                    >
                      <span className={`w-9 h-9 rounded-xl flex items-center justify-center text-lg flex-shrink-0 ${PROMPT_COLORS[i % PROMPT_COLORS.length]}`}>
                        {p.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 leading-snug">{p.label}</p>
                        <p className="text-xs text-gray-400 mt-0.5 leading-snug truncate">{p.question}</p>
                      </div>
                      <span className="text-gray-300 group-hover:text-indigo-400 transition-colors mt-0.5 flex-shrink-0">→</span>
                    </button>
                  ))
              }
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto w-full px-6 py-8 space-y-8">
            {messages.map((msg) =>
              msg.role === "user" ? (
                <div key={msg.id} className="flex justify-end">
                  <div className="bg-indigo-600 text-white px-4 py-3 rounded-2xl rounded-tr-sm max-w-lg text-sm leading-relaxed shadow-sm">
                    {msg.text}
                  </div>
                </div>
              ) : (
                <div key={msg.id} className="flex gap-3">
                  <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                    <span className="text-white text-xs font-bold">A</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    {msg.error ? (
                      <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 px-4 py-3 rounded-2xl rounded-tl-sm text-sm text-red-600">
                        <span className="flex-shrink-0 mt-0.5">⚠️</span>
                        <span>{msg.error}</span>
                      </div>
                    ) : (
                      <div className="bg-gray-50 border border-gray-100 rounded-2xl rounded-tl-sm overflow-hidden">
                        {msg.result?.row_count === 0 && (
                          <div className="px-4 py-4 flex items-start gap-2.5">
                            <span className="text-lg flex-shrink-0">🔍</span>
                            <div>
                              <p className="text-sm font-medium text-gray-700">No results found</p>
                              <p className="text-xs text-gray-400 mt-0.5">Your data may not have records matching this filter. Try removing a time range or broadening the question.</p>
                            </div>
                          </div>
                        )}
                        {msg.result?.narrative && (
                          <div className="px-4 pt-4 pb-3">
                            <p className="text-sm text-gray-800 leading-relaxed">{msg.result.narrative}</p>
                          </div>
                        )}
                        {msg.result && (
                          <>
                            {msg.result.chart_suggestion.type !== "table" && (
                              <div className={`px-4 pb-3 ${msg.result.narrative ? "border-t border-gray-200 pt-3" : "pt-2"}`}>
                                <ResultsChart result={msg.result} />
                              </div>
                            )}
                            <div className="border-t border-gray-200">
                              <ResultsTable result={msg.result} />
                            </div>
                            <div className="border-t border-gray-200 px-4 py-2.5 flex items-center justify-between gap-3">
                              <span className="text-xs text-gray-400 flex-shrink-0">{msg.text}</span>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleExport("doc", msg.result!.question, msg.result!)}
                                  className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
                                >
                                  <span>📄</span> Doc
                                </button>
                                <button
                                  onClick={() => handleExport("slides", msg.result!.question, msg.result!)}
                                  className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors"
                                >
                                  <span>📊</span> Slides
                                </button>
                                <details className="text-right">
                                  <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 select-none font-medium">
                                    SQL ↓
                                  </summary>
                                  <pre className="mt-2 text-xs bg-white border border-gray-200 rounded-xl p-3 overflow-x-auto text-gray-600 font-mono leading-relaxed text-left">
                                    {msg.result.sql}
                                  </pre>
                                </details>
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )
            )}

            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 bg-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm">
                  <span className="text-white text-xs font-bold">A</span>
                </div>
                <div className="bg-gray-50 border border-gray-100 rounded-2xl rounded-tl-sm px-4 py-4">
                  <div className="flex gap-1.5 items-center">
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className={`flex-shrink-0 px-6 ${hasMessages ? "py-4 border-t border-gray-100" : "pb-10"}`}>
        <div className="max-w-xl mx-auto">
          <div className="bg-white border border-gray-200 rounded-2xl shadow-md overflow-hidden focus-within:border-indigo-300 focus-within:shadow-indigo-100 transition-all">
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
              }}
              onKeyDown={handleKey}
              placeholder="Ask anything about your data…"
              disabled={loading}
              className="w-full px-4 pt-4 pb-2 text-sm text-gray-800 placeholder-gray-400 resize-none focus:outline-none bg-transparent leading-relaxed disabled:opacity-50"
              style={{ height: "52px" }}
            />
            <div className="flex items-center justify-between px-3 pb-3 pt-1">
              <div />
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-300">{input.length}/2,000</span>
                <button
                  onClick={() => submit(input)}
                  disabled={loading || !input.trim()}
                  className="w-7 h-7 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-30 rounded-lg flex items-center justify-center transition-colors text-white text-sm font-bold"
                >
                  ↑
                </button>
              </div>
            </div>
          </div>
          <p className="text-center text-xs text-gray-300 mt-2">
            AskData generates queries from your schema — always review before acting on results.
          </p>
        </div>
      </div>
    </div>
  );
}
