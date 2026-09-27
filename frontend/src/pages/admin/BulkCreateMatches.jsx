import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../api/client";

function todayNairobi() {
  const now = new Date();

  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);

  const get = (name) =>
    parts.find((part) => part.type === name)?.value;

  return `${get("year")}-${get("month")}-${get("day")}`;
}

export default function BulkCreateMatches() {
  const navigate = useNavigate();

  const today = todayNairobi();

  const [form, setForm] = useState({
    start_date: today,
    start_time: "00:00",
    end_date: today,
    end_time: "23:59",
    count: 20,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  function update(field, value) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function generateMatches(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await api.post(
        "/api/admin/matches/bulk-create",
        {
          start_date: form.start_date,
          start_time: form.start_time,
          end_date: form.end_date,
          end_time: form.end_time,
          count: Number(form.count),
        }
      );

      setResult(response.data);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
        "Failed to generate matches."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        maxWidth: "850px",
        margin: "0 auto",
        padding: "24px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "12px",
          marginBottom: "24px",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: "28px",
              fontWeight: 900,
            }}
          >
            ⚡ Create Bulk Matches
          </h1>

          <p
            style={{
              marginTop: "8px",
              color: "#6b7280",
            }}
          >
            Fetch upcoming football fixtures directly from Betika.
          </p>
        </div>

        <button
          type="button"
          onClick={() => navigate("/admin/matches")}
          style={{
            padding: "10px 16px",
            border: "1px solid #d1d5db",
            borderRadius: "8px",
            background: "#fff",
            cursor: "pointer",
            fontWeight: 700,
          }}
        >
          ← Back to Matches
        </button>
      </div>

      <form
        onSubmit={generateMatches}
        style={{
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: "14px",
          padding: "24px",
          boxShadow: "0 4px 18px rgba(0,0,0,0.05)",
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "20px",
          }}
        >
          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              fontWeight: 700,
            }}
          >
            Start Date
            <input
              type="date"
              value={form.start_date}
              onChange={(e) =>
                update("start_date", e.target.value)
              }
              required
              style={inputStyle}
            />
          </label>

          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              fontWeight: 700,
            }}
          >
            Start Time
            <input
              type="time"
              value={form.start_time}
              onChange={(e) =>
                update("start_time", e.target.value)
              }
              required
              style={inputStyle}
            />
          </label>

          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              fontWeight: 700,
            }}
          >
            End Date
            <input
              type="date"
              value={form.end_date}
              onChange={(e) =>
                update("end_date", e.target.value)
              }
              required
              style={inputStyle}
            />
          </label>

          <label
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              fontWeight: 700,
            }}
          >
            End Time
            <input
              type="time"
              value={form.end_time}
              onChange={(e) =>
                update("end_time", e.target.value)
              }
              required
              style={inputStyle}
            />
          </label>
        </div>

        <div style={{ marginTop: "28px" }}>
          <div
            style={{
              fontWeight: 800,
              marginBottom: "12px",
            }}
          >
            Matches to Generate
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            {[10, 20, 30, 50, 100].map((amount) => (
              <button
                key={amount}
                type="button"
                onClick={() => update("count", amount)}
                style={{
                  padding: "11px 20px",
                  borderRadius: "9px",
                  border:
                    Number(form.count) === amount
                      ? "2px solid #111827"
                      : "1px solid #d1d5db",
                  background:
                    Number(form.count) === amount
                      ? "#111827"
                      : "#fff",
                  color:
                    Number(form.count) === amount
                      ? "#fff"
                      : "#111827",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                {amount}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            marginTop: "28px",
            padding: "14px",
            border: "none",
            borderRadius: "10px",
            background: loading ? "#9ca3af" : "#111827",
            color: "#fff",
            fontSize: "16px",
            fontWeight: 900,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading
            ? "⏳ Fetching Betika Fixtures..."
            : `⚡ Generate ${form.count} Matches`}
        </button>
      </form>

      {error && (
        <div
          style={{
            marginTop: "20px",
            padding: "16px",
            borderRadius: "10px",
            background: "#fee2e2",
            color: "#991b1b",
            fontWeight: 700,
          }}
        >
          {error}
        </div>
      )}

      {result && (
        <div
          style={{
            marginTop: "20px",
            padding: "22px",
            borderRadius: "14px",
            background: "#f0fdf4",
            border: "1px solid #bbf7d0",
          }}
        >
          <h2
            style={{
              marginTop: 0,
              marginBottom: "18px",
            }}
          >
            ✅ Import Complete
          </h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(150px, 1fr))",
              gap: "12px",
            }}
          >
            <ResultCard
              label="Requested"
              value={result.requested}
            />
            <ResultCard
              label="Betika Found"
              value={result.betika_found}
            />
            <ResultCard
              label="Created"
              value={result.created_matches}
            />
            <ResultCard
              label="Already Existing"
              value={result.existing_matches}
            />
            <ResultCard
              label="Leagues"
              value={result.created_leagues}
            />
            <ResultCard
              label="Teams"
              value={result.created_teams}
            />
            <ResultCard
              label="Markets"
              value={result.created_markets}
            />
            <ResultCard
              label="Odds"
              value={result.created_odds}
            />
          </div>

          <p
            style={{
              marginBottom: 0,
              marginTop: "18px",
              color: "#166534",
            }}
          >
            Window: {result.start} → {result.end}
          </p>

          <button
            type="button"
            onClick={() => navigate("/admin/matches")}
            style={{
              marginTop: "18px",
              padding: "11px 18px",
              border: "none",
              borderRadius: "8px",
              background: "#166534",
              color: "#fff",
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            View Matches
          </button>
        </div>
      )}
    </div>
  );
}

function ResultCard({ label, value }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: "10px",
        padding: "14px",
        border: "1px solid #dcfce7",
      }}
    >
      <div
        style={{
          fontSize: "12px",
          color: "#6b7280",
          marginBottom: "5px",
        }}
      >
        {label}
      </div>

      <div
        style={{
          fontSize: "22px",
          fontWeight: 900,
        }}
      >
        {value}
      </div>
    </div>
  );
}

const inputStyle = {
  width: "100%",
  boxSizing: "border-box",
  padding: "11px 12px",
  border: "1px solid #d1d5db",
  borderRadius: "8px",
  fontSize: "15px",
  background: "#fff",
};
