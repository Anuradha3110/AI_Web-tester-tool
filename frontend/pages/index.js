import { useState, useRef, useEffect } from "react";
import axios from "axios";
import Link from "next/link";
import TestResult from "../components/TestResult";
import HistoryPanel from "../components/HistoryPanel";

const BACKEND = "http://localhost:8000";

const EXAMPLE_GOALS = [
  "Check if the homepage loads correctly",
  "Test the login flow",
  "Verify the contact form works",
  "Check if search functionality works",
  "Test navigation menu links",
];

const ACTION_ICON = {
  go_to: "→", click: "⊙", type: "✏", check: "✓",
  scroll: "↕", wait: "⏳", hover: "◎", select: "▼", done: "■",
};

function formatConsoleLog(log) {
  switch (log.type) {
    case "start":
      return { color: "text-blue-400", icon: "▶", text: `Testing: ${log.url}`, sub: null };
    case "step":
      return {
        color: "text-yellow-300",
        icon: `[${log.step}]`,
        text: `${log.action}  ${ACTION_ICON[log.action] || "·"}  ${log.target || ""}${log.value ? `  ←  "${log.value}"` : ""}`,
        sub: log.reasoning || null,
      };
    case "step_done":
      return log.status === "passed"
        ? { color: "text-green-400", icon: "    ✓", text: `passed${log.url ? `  ·  ${log.url}` : ""}`, sub: null }
        : { color: "text-red-400",   icon: "    ✗", text: `failed${log.error ? `  ·  ${log.error}` : ""}`, sub: null };
    case "done":
      return {
        color: log.verdict === "PASSED" ? "text-green-300" : "text-red-300",
        icon: "■",
        text: `${log.verdict}  ·  ${log.total_steps} steps  ·  ${log.duration?.toFixed(1)}s`,
        sub: null,
      };
    case "stopped":
      return {
        color: "text-amber-400",
        icon: "⏹",
        text: `Stopped · ${log.total_steps ?? 0} steps · ${log.duration?.toFixed(1) ?? "0"}s`,
        sub: null,
      };
    case "error":
      return { color: "text-red-400", icon: "⚠", text: `Error: ${log.message}`, sub: null };
    default:
      return { color: "text-gray-500", icon: "·", text: JSON.stringify(log), sub: null };
  }
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [goal, setGoal] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showCreds, setShowCreds] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [headedMode, setHeadedMode] = useState(false);
  const [slowMo, setSlowMo] = useState(500);
  const [execLogs, setExecLogs] = useState([]);
  const [runId, setRunId] = useState("");
  const [stopping, setStopping] = useState(false);
  const resultRef = useRef(null);
  const fileInputRef = useRef(null);
  const consoleRef = useRef(null);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [execLogs]);

  const handleFileSelect = (e) => {
    const incoming = Array.from(e.target.files || []);
    if (!incoming.length) return;
    setAttachedFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      return [...prev, ...incoming.filter((f) => !existingNames.has(f.name))];
    });
    e.target.value = "";
  };

  const removeFile = (idx) =>
    setAttachedFiles((prev) => prev.filter((_, i) => i !== idx));

  const stopTest = async () => {
    if (!runId || stopping) return;
    setStopping(true);
    try {
      await fetch(`${BACKEND}/stop/${runId}`, { method: "POST" });
    } catch {}
  };

  const handleStreamEvent = (event) => {
    if (event.type === "result") {
      setResult(event.data);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } else if (event.type === "init") {
      setRunId(event.run_id);
    } else if (event.type === "error") {
      setError(event.message || "An error occurred");
    } else {
      setExecLogs((prev) => [...prev, event]);
    }
  };

  const runTestStreaming = async (formData) => {
    try {
      const response = await fetch(`${BACKEND}/test-stream`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          if (chunk.startsWith("data: ")) {
            const raw = chunk.slice(6).trim();
            if (!raw) continue;
            try { handleStreamEvent(JSON.parse(raw)); } catch {}
          }
        }
      }
    } catch (err) {
      const msg =
        err.message?.includes("Failed to fetch") || err.message?.includes("NetworkError")
          ? "Cannot connect to backend. Make sure you ran: cd backend && python main.py"
          : err.message === "Not Found"
          ? "Headed mode endpoint not found — please restart the backend: cd backend && python main.py"
          : err.message || "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
      setRunId("");
      setStopping(false);
    }
  };

  const runTest = async (e) => {
    e.preventDefault();
    if (!url.trim() || !goal.trim()) {
      setError("Please enter both a URL and a test goal.");
      return;
    }

    const activeRunId = crypto.randomUUID();
    setRunId(activeRunId);
    setStopping(false);
    setLoading(true);
    setResult(null);
    setError("");
    setExecLogs([]);

    const formData = new FormData();
    formData.append("url", url.trim());
    formData.append("goal", goal.trim());
    formData.append("run_id", activeRunId);
    if (showCreds && (username || password)) {
      formData.append("credentials", JSON.stringify({ username, password }));
    }
    attachedFiles.forEach((f) => formData.append("files", f));

    if (headedMode) {
      formData.append("headed", "true");
      formData.append("slow_mo", String(slowMo));
      await runTestStreaming(formData);
    } else {
      try {
        const { data } = await axios.post(`${BACKEND}/test`, formData, {
          timeout: 300000,
        });
        setResult(data);
        setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
      } catch (err) {
        const serverDetail = err.response?.data?.detail;
        const msg = serverDetail
          ? `Server error: ${serverDetail}`
          : err.code === "ECONNREFUSED" || err.message?.includes("Network Error")
          ? "Cannot connect to backend. Make sure you ran: cd backend && python main.py"
          : err.code === "ECONNABORTED"
          ? "Request timed out. The test took too long."
          : err.message || "Unknown error";
        setError(msg);
      } finally {
        setLoading(false);
        setRunId("");
        setStopping(false);
      }
    }
  };

  const loadHistoryItem = async (test) => {
    try {
      const { data } = await axios.get(`${BACKEND}/tests/${test.id}`);
      const steps = (data.steps || []).map((s) => ({
        ...s,
        step: s.step_number,
        error: s.error_message,
        screenshot_url: s.screenshot_path
          ? `/screenshots/${s.screenshot_path.split(/[\\/]/).pop()}`
          : null,
      }));
      setResult({
        ...data,
        steps,
        final_verdict: data.final_verdict,
        report: {
          total_steps: data.total_steps,
          passed_steps: data.passed_steps,
          failed_steps: data.failed_steps,
          duration_seconds: data.duration ? Math.round(data.duration) : 0,
        },
      });
      setUrl(data.url);
      setGoal(data.goal);
      setShowHistory(false);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch {
      setError("Could not load test details.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900">
      {/* Header */}
      <header className="border-b border-white/10 bg-white/5 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
              <span className="text-white font-bold text-sm">AI</span>
            </div>
            <div>
              <h1 className="text-white font-bold text-lg leading-tight">AI Web Tester</h1>
              <p className="text-blue-300 text-xs">Powered by Claude + Playwright</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/reports"
              className="text-blue-300 hover:text-white text-sm font-medium border border-white/20 hover:border-white/40 px-4 py-1.5 rounded-lg transition-all"
            >
              View Reports
            </Link>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="text-blue-300 hover:text-white text-sm font-medium border border-white/20 hover:border-white/40 px-4 py-1.5 rounded-lg transition-all"
            >
              {showHistory ? "Close History" : "History"}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Form */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl shadow-2xl p-8">
            <h2 className="text-xl font-bold text-gray-800 mb-1">Run a Website Test</h2>
            <p className="text-gray-500 text-sm mb-6">
              Describe your test goal in plain English. The AI will control a real browser to verify it.
            </p>

            <form onSubmit={runTest} className="space-y-5">
              {/* URL */}
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Website URL
                </label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all"
                />
              </div>

              {/* Goal */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-semibold text-gray-700">
                    Test Goal
                  </label>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach a file (PDF, DOCX, Excel, TXT…)"
                    className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium border border-blue-200 hover:border-blue-400 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-lg transition-all"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8 4a3 3 0 00-3 3v4.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V7a6 6 0 10-12 0v1a1 1 0 102 0V7a4 4 0 018 0v4.586l.707.707H5.293L6 11.586V7a3 3 0 00-3-3z" clipRule="evenodd" />
                    </svg>
                    Attach file
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.md"
                    className="hidden"
                    onChange={handleFileSelect}
                  />
                </div>
                <textarea
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder="e.g. Test the login flow and verify the dashboard loads"
                  rows={3}
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all resize-none"
                />

                {/* Attached files */}
                {attachedFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {attachedFiles.map((f, idx) => (
                      <span
                        key={idx}
                        className="flex items-center gap-1.5 text-xs px-3 py-1 bg-green-50 border border-green-200 text-green-700 rounded-full"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                        </svg>
                        <span className="max-w-[140px] truncate">{f.name}</span>
                        <button
                          type="button"
                          onClick={() => removeFile(idx)}
                          className="hover:text-red-500 transition-colors leading-none"
                          title="Remove"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Example chips */}
                <div className="flex flex-wrap gap-2 mt-2">
                  {EXAMPLE_GOALS.map((eg) => (
                    <button
                      key={eg}
                      type="button"
                      onClick={() => setGoal(eg)}
                      className="text-xs px-3 py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-full border border-blue-100 transition-colors"
                    >
                      {eg}
                    </button>
                  ))}
                </div>
              </div>

              {/* Credentials toggle */}
              <div>
                <button
                  type="button"
                  onClick={() => setShowCreds(!showCreds)}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                >
                  <span>{showCreds ? "▼" : "▶"}</span>
                  Add login credentials (optional)
                </button>
                {showCreds && (
                  <div className="mt-3 grid grid-cols-2 gap-3 p-4 bg-gray-50 rounded-xl border border-gray-100">
                    <div>
                      <label className="block text-xs font-semibold text-gray-600 mb-1">
                        Username / Email
                      </label>
                      <input
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="user@example.com"
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-600 mb-1">
                        Password
                      </label>
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Headed / Headless Mode */}
              <div className="border border-gray-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-700">Browser Mode</p>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          headedMode
                            ? "bg-green-100 text-green-700 border border-green-200"
                            : "bg-gray-100 text-gray-500 border border-gray-200"
                        }`}
                      >
                        {headedMode ? "● HEADED" : "○ HEADLESS"}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {headedMode ? "Browser window visible — live execution console enabled" : "Background mode (faster, default)"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setHeadedMode((v) => !v)}
                    className={`relative inline-flex w-11 h-6 rounded-full transition-colors focus:outline-none ${
                      headedMode ? "bg-blue-600" : "bg-gray-300"
                    }`}
                    title="Toggle headed/headless mode"
                  >
                    <span
                      className={`inline-block w-5 h-5 bg-white rounded-full shadow transform transition-transform mt-0.5 ml-0.5 ${
                        headedMode ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>

                {headedMode && (
                  <div className="pt-1 border-t border-gray-100">
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-semibold text-gray-600">
                        Slow Motion
                      </label>
                      <span className="text-xs text-blue-600 font-mono">
                        {slowMo === 0 ? "Off (instant)" : `${slowMo} ms / action`}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="2000"
                      step="100"
                      value={slowMo}
                      onChange={(e) => setSlowMo(Number(e.target.value))}
                      className="w-full accent-blue-600"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                      <span>Instant</span>
                      <span>1s</span>
                      <span>2s / step</span>
                    </div>
                  </div>
                )}
              </div>

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl">
                  <p className="text-red-600 text-sm">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-3 px-6 rounded-xl transition-all flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    Running Test...
                  </>
                ) : (
                  "Run Test"
                )}
              </button>

              {loading && runId && (
                <button
                  type="button"
                  onClick={stopTest}
                  disabled={stopping}
                  className="w-full mt-2 bg-red-500 hover:bg-red-600 disabled:bg-red-300 text-white font-semibold py-3 px-6 rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  {stopping ? (
                    <>
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      Stopping...
                    </>
                  ) : (
                    <>
                      <span className="w-3 h-3 bg-white rounded-sm inline-block shrink-0" />
                      Stop Test
                    </>
                  )}
                </button>
              )}
            </form>

            {loading && (
              <div className="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <p className="text-blue-600 text-sm font-medium">
                    AI is controlling the browser and running your test...
                  </p>
                </div>
              </div>
            )}

            {/* Execution Console — visible in headed mode */}
            {headedMode && (execLogs.length > 0 || loading) && (
              <div className="mt-6 rounded-xl border border-gray-700 bg-gray-950 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                    <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
                    <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
                    <span className="text-gray-400 text-xs font-mono ml-1">Execution Console</span>
                  </div>
                  {loading ? (
                    <span className="flex items-center gap-1.5 text-xs text-green-400 font-mono">
                      <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                      LIVE
                    </span>
                  ) : (
                    <span className="text-xs text-gray-600 font-mono">DONE</span>
                  )}
                </div>
                <div
                  ref={consoleRef}
                  className="h-64 overflow-y-auto p-3 space-y-0.5 font-mono text-xs"
                >
                  {execLogs.map((log, i) => {
                    const entry = formatConsoleLog(log);
                    return (
                      <div key={i}>
                        <span className={entry.color}>
                          <span className="opacity-60 mr-2 select-none">{entry.icon}</span>
                          {entry.text}
                        </span>
                        {entry.sub && (
                          <div className="text-gray-500 pl-6 mt-0.5">{entry.sub}</div>
                        )}
                      </div>
                    );
                  })}
                  {execLogs.length === 0 && loading && (
                    <span className="text-gray-600">Waiting for browser to start...</span>
                  )}
                </div>
              </div>
            )}

            <div ref={resultRef}>
              <TestResult result={result} />
            </div>
          </div>
        </div>

        {/* Right: Info + History */}
        <div className="space-y-6">
          {/* How it works */}
          <div className="bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-6 text-white">
            <h3 className="font-bold text-sm uppercase tracking-wide text-blue-300 mb-4">
              How It Works
            </h3>
            <div className="space-y-3">
              {[
                ["1", "You give a URL and test goal"],
                ["2", "Claude AI plans the steps"],
                ["3", "Playwright controls the browser"],
                ["4", "Results + screenshots captured"],
                ["5", "Report saved to database"],
              ].map(([num, text]) => (
                <div key={num} className="flex items-start gap-3">
                  <span className="w-5 h-5 rounded-full bg-blue-500 text-white text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {num}
                  </span>
                  <p className="text-sm text-blue-100">{text}</p>
                </div>
              ))}
            </div>
          </div>

          {/* History */}
          <div className="bg-white rounded-2xl shadow-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-sm text-gray-700 uppercase tracking-wide">
                Recent Tests
              </h3>
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="text-xs text-blue-500 hover:text-blue-700"
              >
                {showHistory ? "Hide" : "Show"}
              </button>
            </div>
            {showHistory && <HistoryPanel onSelect={loadHistoryItem} />}
            {!showHistory && (
              <p className="text-xs text-gray-400">Click "Show" to view past test runs.</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
