import { useEffect, useState } from "react";
import axios from "axios";
import Link from "next/link";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function VerdictBadge({ verdict }) {
  const styles = {
    PASSED: "bg-green-100 text-green-700 border-green-300",
    FAILED: "bg-red-100 text-red-700 border-red-300",
    ERROR: "bg-orange-100 text-orange-700 border-orange-300",
    STOPPED: "bg-amber-100 text-amber-700 border-amber-300",
  };
  return (
    <span className={`px-2 py-0.5 text-xs font-bold uppercase rounded border ${styles[verdict] || "bg-gray-100 text-gray-500 border-gray-200"}`}>
      {verdict || "—"}
    </span>
  );
}

function StepRow({ step }) {
  const isPass = step.status === "passed";
  return (
    <tr className={`border-t border-gray-100 ${isPass ? "" : "bg-red-50"}`}>
      <td className="px-3 py-2 text-xs text-gray-500 font-mono">{step.step_number}</td>
      <td className="px-3 py-2">
        <span className="text-xs font-mono font-bold uppercase bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
          {step.action}
        </span>
      </td>
      <td className="px-3 py-2 text-xs text-gray-600 max-w-xs truncate" title={step.target}>{step.target}</td>
      <td className="px-3 py-2 text-xs text-gray-500 max-w-xs truncate" title={step.value}>{step.value || "—"}</td>
      <td className="px-3 py-2">
        <span className={`text-xs font-semibold ${isPass ? "text-green-600" : "text-red-600"}`}>
          {step.status}
        </span>
      </td>
      <td className="px-3 py-2 text-xs text-gray-500 max-w-sm" title={step.reasoning}>
        {step.reasoning?.slice(0, 100)}{step.reasoning?.length > 100 ? "…" : ""}
      </td>
      <td className="px-3 py-2 text-xs text-red-400 max-w-xs truncate" title={step.error_message}>
        {step.error_message || ""}
      </td>
    </tr>
  );
}

export default function Reports() {
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    axios.get(`${BACKEND}/tests?limit=50`)
      .then(r => setRuns(r.data))
      .catch(() => setError("Cannot connect to backend. Make sure it is running on port 8000."))
      .finally(() => setLoading(false));
  }, []);

  const loadDetail = async (run) => {
    setSelected(run);
    setDetail(null);
    setDetailLoading(true);
    try {
      const { data } = await axios.get(`${BACKEND}/tests/${run.id}`);
      setDetail(data);
    } catch {
      setDetail({ error: "Failed to load steps." });
    } finally {
      setDetailLoading(false);
    }
  };

  const deleteRun = async (e, id) => {
    e.stopPropagation();
    if (!confirm("Delete this test run?")) return;
    await axios.delete(`${BACKEND}/tests/${id}`).catch(() => {});
    setRuns(prev => prev.filter(r => r.id !== id));
    if (selected?.id === id) { setSelected(null); setDetail(null); }
  };

  const stats = {
    total: runs.length,
    passed: runs.filter(r => r.final_verdict === "PASSED").length,
    failed: runs.filter(r => r.final_verdict === "FAILED").length,
    errors: runs.filter(r => r.final_verdict === "ERROR").length,
    stopped: runs.filter(r => r.final_verdict === "STOPPED").length,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-blue-600 hover:text-blue-800 text-sm font-medium">← Back</Link>
          <h1 className="text-xl font-bold text-gray-800">Test Reports</h1>
        </div>
        <p className="text-xs text-gray-400">All data from web_tester.db</p>
      </header>

      {/* Stats bar */}
      <div className="bg-white border-b border-gray-100 px-6 py-3 flex gap-8">
        {[
          { label: "Total Runs", value: stats.total, color: "text-gray-700" },
          { label: "Passed", value: stats.passed, color: "text-green-600" },
          { label: "Failed", value: stats.failed, color: "text-red-600" },
          { label: "Errors", value: stats.errors, color: "text-orange-500" },
          { label: "Stopped", value: stats.stopped, color: "text-amber-500" },
        ].map(s => (
          <div key={s.label}>
            <p className="text-xs text-gray-400">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {error && (
        <div className="m-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">{error}</div>
      )}

      <div className="flex h-[calc(100vh-140px)]">
        {/* Left: Run list */}
        <div className="w-96 border-r border-gray-200 bg-white overflow-y-auto">
          {loading ? (
            <div className="p-6 text-center text-gray-400 animate-pulse">Loading...</div>
          ) : runs.length === 0 ? (
            <div className="p-6 text-center text-gray-400 text-sm">No test runs yet.<br/>Run a test from the home page.</div>
          ) : (
            runs.map(run => (
              <div
                key={run.id}
                onClick={() => loadDetail(run)}
                className={`px-4 py-4 border-b border-gray-100 cursor-pointer hover:bg-blue-50 transition-colors group ${selected?.id === run.id ? "bg-blue-50 border-l-4 border-l-blue-500" : ""}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-mono text-blue-600 truncate">{run.url}</p>
                    <p className="text-sm text-gray-700 mt-1 truncate font-medium">{run.goal}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <VerdictBadge verdict={run.final_verdict} />
                      <span className="text-xs text-gray-400">{run.total_steps} steps</span>
                      {run.duration && <span className="text-xs text-gray-400">{Math.round(run.duration)}s</span>}
                    </div>
                    <p className="text-xs text-gray-300 mt-1">
                      {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={e => deleteRun(e, run.id)}
                    className="text-gray-300 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-1"
                    title="Delete"
                  >✕</button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right: Detail panel */}
        <div className="flex-1 overflow-y-auto p-6">
          {!selected && (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center">
                <p className="text-4xl mb-3">📋</p>
                <p className="text-sm">Select a test run on the left to view its full report</p>
              </div>
            </div>
          )}

          {selected && detailLoading && (
            <div className="text-center text-gray-400 animate-pulse mt-20">Loading steps...</div>
          )}

          {selected && detail && !detailLoading && (
            <div>
              {/* Run summary */}
              <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <VerdictBadge verdict={detail.final_verdict} />
                      <span className="text-sm text-gray-500">{Math.round(detail.duration || 0)}s · {detail.total_steps} steps</span>
                    </div>
                    <p className="text-xs text-blue-600 font-mono mb-1">{detail.url}</p>
                    <p className="text-base font-semibold text-gray-800">{detail.goal}</p>
                  </div>
                  <p className="text-xs text-gray-300">{new Date(detail.created_at).toLocaleString()}</p>
                </div>

                <div className="flex gap-6 mt-4 pt-4 border-t border-gray-100">
                  <div><p className="text-xs text-gray-400">Passed</p><p className="text-lg font-bold text-green-600">{detail.passed_steps}</p></div>
                  <div><p className="text-xs text-gray-400">Failed</p><p className="text-lg font-bold text-red-500">{detail.failed_steps}</p></div>
                  <div><p className="text-xs text-gray-400">Total</p><p className="text-lg font-bold text-gray-700">{detail.total_steps}</p></div>
                </div>

                {detail.error && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg">
                    <p className="text-xs text-red-500 font-mono">{detail.error}</p>
                  </div>
                )}
              </div>

              {/* Steps table */}
              {detail.steps?.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                  <div className="px-5 py-3 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-700 text-sm">Steps Breakdown</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead className="bg-gray-50 text-xs text-gray-400 uppercase">
                        <tr>
                          <th className="px-3 py-2">#</th>
                          <th className="px-3 py-2">Action</th>
                          <th className="px-3 py-2">Target</th>
                          <th className="px-3 py-2">Value</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2">Reasoning</th>
                          <th className="px-3 py-2">Error</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.steps.map(s => <StepRow key={s.id} step={s} />)}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Screenshots */}
              {detail.steps?.some(s => s.screenshot_path) && (
                <div className="mt-6 bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                  <h3 className="font-semibold text-gray-700 text-sm mb-4">Screenshots</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {detail.steps.filter(s => s.screenshot_path).map(s => (
                      <div key={s.id}>
                        <p className="text-xs text-gray-400 mb-1">Step {s.step_number} — {s.action}</p>
                        <img
                          src={`${BACKEND}/screenshots/${s.screenshot_path.split(/[\\/]/).pop()}`}
                          alt={`Step ${s.step_number}`}
                          className="rounded-lg border border-gray-200 w-full shadow-sm"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
