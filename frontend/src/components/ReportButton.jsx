import React, { useState } from "react";

export default function ReportButton() {
  const [dateFrom, setDateFrom] = useState("2026-02-01");
  const [dateTo, setDateTo] = useState("2026-02-15");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const apiBase = process.env.REACT_APP_API_URL || "http://localhost:8001";

  const downloadCsv = async () => {
    setLoading(true);
    setError("");

    try {
      const url = new URL(`${apiBase}/reports`);
      url.searchParams.set("date_from", dateFrom);
      url.searchParams.set("date_to", dateTo);
      url.searchParams.set("format", "csv");

      const res = await fetch(url.toString(), {
        method: "GET",
        credentials: "include", // важно: cookie-сессия
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const a = document.createElement("a");
      const href = URL.createObjectURL(blob);
      a.href = href;
      a.download = `report_${dateFrom}_${dateTo}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (e) {
      setError(e.message || "Failed to download report");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
      <div>
        <div style={{ fontSize: 12, opacity: 0.8 }}>Date from</div>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
      </div>

      <div>
        <div style={{ fontSize: 12, opacity: 0.8 }}>Date to</div>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </div>

      <button onClick={downloadCsv} disabled={loading}>
        {loading ? "Generating..." : "Get report (CSV)"}
      </button>

      {error && <div style={{ color: "crimson", maxWidth: 520 }}>{error}</div>}
    </div>
  );
}
