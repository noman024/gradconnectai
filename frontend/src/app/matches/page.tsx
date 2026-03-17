"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface Match {
  professor_id: string;
  score: number;
  opportunity_score: number;
  final_rank: number;
}

export default function MatchesPage() {
  const [studentId, setStudentId] = useState<string | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const sid = typeof window !== "undefined" ? sessionStorage.getItem("student_id") : null;
    setStudentId(sid);
    if (!sid) {
      setLoading(false);
      return;
    }
    fetch(`/api/v1/matches?student_id=${encodeURIComponent(sid)}`)
      .then((r) => r.json())
      .then((d) => setMatches(d.matches || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (!studentId) {
    return (
      <main style={{ padding: "2rem", maxWidth: "48rem", margin: "0 auto" }}>
        <p>No profile found. <Link href="/profile">Create your profile</Link> first.</p>
      </main>
    );
  }

  return (
    <main style={{ padding: "2rem", maxWidth: "56rem", margin: "0 auto" }}>
      <h1>Your matches</h1>
      <p>Ranked by fit and opportunity. Click a professor to generate an outreach email draft.</p>
      <nav style={{ marginBottom: "1rem" }}><Link href="/">Home</Link></nav>
      {matches.length === 0 ? (
        <p>No matches yet. Add professors via the discovery pipeline or seed data.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {matches.map((m) => (
            <li key={m.professor_id} style={{ marginBottom: "1rem", padding: "1rem", border: "1px solid #eee", borderRadius: "8px" }}>
              <Link href={`/email/${m.professor_id}?student_id=${studentId}`}>
                Professor {m.professor_id.slice(0, 8)}… — rank {m.final_rank.toFixed(2)} (fit: {m.score.toFixed(2)}, opportunity: {m.opportunity_score.toFixed(2)})
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
