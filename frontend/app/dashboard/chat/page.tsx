"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { listDataSources, getQueryHistory, getSuggestedPrompts, type DataSource, type QueryHistoryItem, type SuggestedPrompt } from "@/lib/api";
import { ChatInterface } from "@/components/ChatInterface";

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function ChatPage() {
  const router = useRouter();
  const [sources, setSources] = useState<DataSource[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [externalQuestion, setExternalQuestion] = useState<string>("");
  const [chatKey, setChatKey] = useState(0);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [suggestedPrompts, setSuggestedPrompts] = useState<SuggestedPrompt[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(false);

  const RECENT_LIMIT = 15;
  const THREE_MONTHS_AGO = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);

  const recentHistory = history.slice(0, RECENT_LIMIT);
  const extendedHistory = history.filter(
    (item) => new Date(item.created_at) >= THREE_MONTHS_AGO
  );
  const visibleHistory = showAllHistory ? extendedHistory : recentHistory;
  const hasMore = !showAllHistory && history.length > RECENT_LIMIT;

  const refreshHistory = useCallback(async (ids: string[]) => {
    try {
      const dsId = ids.length === 1 ? ids[0] : undefined;
      const items = await getQueryHistory(dsId);
      setHistory(items);
    } catch {
      // non-critical
    }
  }, []);

  const refreshPrompts = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return;
    setPromptsLoading(true);
    try {
      const prompts = await getSuggestedPrompts(ids);
      setSuggestedPrompts(prompts);
    } catch {
      // non-critical
    } finally {
      setPromptsLoading(false);
    }
  }, []);

  useEffect(() => {
    listDataSources()
      .then((data) => {
        setSources(data);
        const ids = data.map((s) => s.id);
        setSelectedIds(ids);
        refreshHistory(ids);
        refreshPrompts(ids);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [router, refreshHistory]);

  function toggleSource(id: string) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) {
        if (prev.length === 1) return prev;
        const next = prev.filter((i) => i !== id);
        refreshHistory(next);
        refreshPrompts(next);
        return next;
      }
      const next = [...prev, id];
      refreshHistory(next);
      refreshPrompts(next);
      return next;
    });
  }

  const selectedSources = sources.filter((s) => selectedIds.includes(s.id));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
          <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    );
  }

  if (sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="w-12 h-12 bg-gray-100 rounded-2xl flex items-center justify-center text-2xl">🗄️</div>
        <div className="text-center">
          <p className="font-medium text-gray-800 mb-1">No data sources yet</p>
          <p className="text-sm text-gray-400">Connect a CSV or database to start asking questions.</p>
        </div>
        <button
          onClick={() => router.push("/dashboard/sources")}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
        >
          Connect a data source
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100 bg-white flex-shrink-0 gap-4">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <h1 className="text-sm font-semibold text-gray-800 flex-shrink-0">AI Chat</h1>
          <span className="text-gray-300 flex-shrink-0">·</span>
          {sources.map((s) => {
            const active = selectedIds.includes(s.id);
            return (
              <button
                key={s.id}
                onClick={() => toggleSource(s.id)}
                className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors flex-shrink-0 ${
                  active
                    ? "bg-indigo-50 border-indigo-200 text-indigo-700 font-medium"
                    : "border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-500"
                }`}
              >
                {active && <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full" />}
                {s.name}
              </button>
            );
          })}
        </div>
        <button
          onClick={() => setChatKey((k) => k + 1)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-colors flex-shrink-0"
        >
          <span className="text-sm leading-none">✦</span>
          New Chat
        </button>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat */}
        <div className="flex-1 overflow-hidden min-w-0">
          <ChatInterface
            key={chatKey}
            dataSources={selectedSources}
            suggestedPrompts={suggestedPrompts}
            promptsLoading={promptsLoading}
            externalQuestion={externalQuestion}
            onExternalConsumed={() => setExternalQuestion("")}
            onQueryComplete={() => refreshHistory(selectedIds)}
          />
        </div>

        {/* History sidebar */}
        <aside className={`flex-shrink-0 border-l border-gray-100 flex flex-col bg-white transition-all duration-200 ${historyCollapsed ? "w-8" : "w-60"}`}>
          <div className="px-2 py-3 border-b border-gray-100 flex items-center justify-between">
            {!historyCollapsed && <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-2">History</span>}
            <button
              onClick={() => setHistoryCollapsed((c) => !c)}
              className="ml-auto p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
              title={historyCollapsed ? "Show history" : "Hide history"}
            >
              <svg className={`w-3.5 h-3.5 transition-transform duration-200 ${historyCollapsed ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
          <div className={`flex-1 overflow-y-auto ${historyCollapsed ? "hidden" : ""}`}>
            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full px-4 text-center">
                <span className="text-2xl mb-2">💬</span>
                <p className="text-xs text-gray-400">Your past questions will appear here</p>
              </div>
            ) : (
              <>
                <ul className="py-2">
                  {visibleHistory.map((item) => (
                    <li key={item.id}>
                      <button
                        onClick={() => setExternalQuestion(item.question)}
                        className="w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors group"
                      >
                        <p className="text-xs text-gray-700 leading-snug line-clamp-2 group-hover:text-indigo-700 transition-colors">
                          {item.question}
                        </p>
                        <p className="text-[10px] text-gray-400 mt-1">{timeAgo(item.created_at)}</p>
                      </button>
                    </li>
                  ))}
                </ul>
                {hasMore && (
                  <button
                    onClick={() => setShowAllHistory(true)}
                    className="w-full px-4 py-2.5 text-xs text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50 transition-colors text-left border-t border-gray-100"
                  >
                    Show past 3 months ({extendedHistory.length - RECENT_LIMIT} more) →
                  </button>
                )}
                {showAllHistory && (
                  <button
                    onClick={() => setShowAllHistory(false)}
                    className="w-full px-4 py-2.5 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors text-left border-t border-gray-100"
                  >
                    ← Show recent only
                  </button>
                )}
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
