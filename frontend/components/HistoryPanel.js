import { useEffect, useState } from "react";
import axios from "axios";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function HistoryPanel({ onSelect }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      const { data } = await axios.get(`${BACKEND}/tests?limit=30`);
      setHistory(data);
    } catch {
      // backend may not be running yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    try {
      await axios.delete(`${BACKEND}/tests/${id}`);
      setHistory((prev) => prev.filter((t) => t.id !== id));
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-gray-400 text-sm animate-pulse">
        Loading history...
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="p-4 text-center text-gray-400 text-sm">No tests yet.</div>
    );
  }

  return (
    <div className="space-y-2 max-h-96 overflow-y-auto scrollbar-thin pr-1">
      {history.map((test) => {
        const verdictColor =
          test.final_verdict === "PASSED"
            ? "text-green-500"
            : test.final_verdict === "FAILED"
            ? "text-red-500"
            : "text-orange-400";

        return (
          <div
            key={test.id}
            className="flex items-start gap-3 p-3 rounded-xl bg-gray-50 hover:bg-blue-50 cursor-pointer border border-transparent hover:border-blue-200 transition-all group"
            onClick={() => onSelect(test)}
          >
            <div className="flex-1 min-w-0">
              <p className="text-xs font-mono text-blue-600 truncate">{test.url}</p>
              <p className="text-xs text-gray-600 truncate mt-0.5">{test.goal}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs font-bold ${verdictColor}`}>
                  {test.final_verdict || "—"}
                </span>
                <span className="text-xs text-gray-400">
                  {test.total_steps} steps · {test.duration ? `${Math.round(test.duration)}s` : ""}
                </span>
              </div>
            </div>
            <button
              className="text-gray-300 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              onClick={(e) => handleDelete(e, test.id)}
              title="Delete"
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
