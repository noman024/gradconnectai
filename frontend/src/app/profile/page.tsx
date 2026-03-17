"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ProfilePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [cvText, setCvText] = useState("");
  const [fields, setFields] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/students", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          cv_text: cvText,
          preferences: { countries: [], universities: [], fields: fields.split(",").map((s) => s.trim()).filter(Boolean) },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const sid = data.student_id;
      if (sid) {
        sessionStorage.setItem("student_id", sid);
        router.push("/matches");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create profile");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ padding: "2rem", maxWidth: "40rem", margin: "0 auto" }}>
      <h1>Create your profile</h1>
      <p>We’ll analyze your CV and preferences to match you with potential supervisors.</p>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1.5rem" }}>
        <label>
          Full name
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} required style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.5rem" }} />
        </label>
        <label>
          CV or research summary (paste text)
          <textarea value={cvText} onChange={(e) => setCvText(e.target.value)} rows={6} style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.5rem" }} />
        </label>
        <label>
          Research fields (comma-separated)
          <input type="text" value={fields} onChange={(e) => setFields(e.target.value)} placeholder="e.g. ML, NLP, HCI" style={{ display: "block", width: "100%", marginTop: "0.25rem", padding: "0.5rem" }} />
        </label>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
        <button type="submit" disabled={loading} style={{ padding: "0.5rem 1rem" }}>
          {loading ? "Analyzing…" : "Save and get matches"}
        </button>
      </form>
    </main>
  );
}
