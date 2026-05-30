import { useState } from "react";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function StepBadge({ status }) {
  const cls =
    status === "passed"
      ? "bg-green-100 text-green-700 border border-green-300"
      : "bg-red-100 text-red-700 border border-red-300";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${cls}`}>
      {status}
    </span>
  );
}

function ActionChip({ action }) {
  const colors = {
    go_to: "bg-blue-100 text-blue-700",
    click: "bg-purple-100 text-purple-700",
    type: "bg-yellow-100 text-yellow-700",
    check: "bg-teal-100 text-teal-700",
    scroll: "bg-gray-100 text-gray-700",
    wait: "bg-orange-100 text-orange-700",
    done: "bg-green-100 text-green-700",
  };
  const cls = colors[action] || "bg-gray-100 text-gray-600";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold uppercase ${cls}`}>
      {action}
    </span>
  );
}

export default function TestResult({ result }) {
  const [expandedStep, setExpandedStep] = useState(null);

  if (!result) return null;

  const { final_verdict, steps = [], report = {}, duration, goal, url, error } = result;

  const verdictColor =
    final_verdict === "PASSED"
      ? "bg-green-500"
      : final_verdict === "FAILED"
      ? "bg-red-500"
      : final_verdict === "STOPPED"
      ? "bg-amber-500"
      : "bg-orange-400";

  return (
    <div className="mt-6 rounded-2xl border border-gray-200 bg-white shadow-lg overflow-hidden">
      {/* Verdict Banner */}
      <div className={`${verdictColor} px-6 py-4 flex items-center justify-between`}>
        <div>
          <p className="text-white text-sm opacity-80 font-medium">Test Result</p>
          <p className="text-white text-2xl font-bold tracking-wide">{final_verdict}</p>
        </div>
        <div className="text-right text-white text-sm opacity-90">
          <p>{report.total_steps} steps</p>
          <p>{report.duration_seconds}s</p>
        </div>
      </div>

      {/* Summary */}
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50">
        <p className="text-xs text-gray-500 font-semibold uppercase mb-1">URL</p>
        <p className="text-sm text-blue-600 font-mono truncate">{url}</p>
        <p className="text-xs text-gray-500 font-semibold uppercase mt-3 mb-1">Goal</p>
        <p className="text-sm text-gray-800">{goal}</p>

        {final_verdict === "STOPPED" && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-xs text-amber-700 font-semibold">Test was stopped by user</p>
            <p className="text-xs text-amber-600 mt-1">The partial results below show what was completed before stopping.</p>
          </div>
        )}
        {final_verdict === "ERROR" && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-xs text-red-600 font-semibold">Error Details</p>
            <p className="text-xs text-red-500 mt-1 font-mono break-all">
              {error || "An unexpected error occurred. Check that the backend is running and ANTHROPIC_API_KEY is set in backend/.env"}
            </p>
          </div>
        )}

        <div className="flex gap-4 mt-3">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400 inline-block"></span>
            <span className="text-xs text-gray-600">{report.passed_steps} passed</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400 inline-block"></span>
            <span className="text-xs text-gray-600">{report.failed_steps} failed</span>
          </div>
        </div>
      </div>

      {/* Steps */}
      <div className="px-6 py-4">
        <p className="text-xs text-gray-500 font-semibold uppercase mb-3">Steps Taken</p>
        <div className="space-y-2">
          {steps.map((step) => (
            <div key={step.step} className="border border-gray-100 rounded-xl overflow-hidden">
              <button
                className="w-full flex items-start gap-3 px-4 py-3 hover:bg-gray-50 text-left transition-colors"
                onClick={() =>
                  setExpandedStep(expandedStep === step.step ? null : step.step)
                }
              >
                <span className="text-xs text-gray-400 font-mono w-5 mt-0.5 shrink-0">
                  {step.step}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <ActionChip action={step.action} />
                    <StepBadge status={step.status} />
                  </div>
                  <p className="text-xs text-gray-500 truncate">{step.reasoning}</p>
                </div>
                <span className="text-gray-300 text-xs shrink-0 mt-1">
                  {expandedStep === step.step ? "▲" : "▼"}
                </span>
              </button>

              {expandedStep === step.step && (
                <div className="px-4 pb-4 bg-gray-50 border-t border-gray-100">
                  <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                    {step.target && (
                      <div>
                        <p className="text-gray-400 font-semibold uppercase mb-1">Target</p>
                        <p className="font-mono text-gray-700 break-all">{step.target}</p>
                      </div>
                    )}
                    {step.value && (
                      <div>
                        <p className="text-gray-400 font-semibold uppercase mb-1">Value</p>
                        <p className="font-mono text-gray-700 break-all">{step.value}</p>
                      </div>
                    )}
                  </div>
                  {step.error && (
                    <div className="mt-2 p-2 bg-red-50 rounded border border-red-100">
                      <p className="text-xs text-red-500 font-mono">{step.error}</p>
                    </div>
                  )}
                  {step.screenshot_url && (
                    <div className="mt-3">
                      <p className="text-gray-400 font-semibold uppercase text-xs mb-2">Screenshot</p>
                      <img
                        src={`${BACKEND}${step.screenshot_url}`}
                        alt={`Step ${step.step}`}
                        className="rounded-lg border border-gray-200 w-full max-w-lg shadow-sm"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
