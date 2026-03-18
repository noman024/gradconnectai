"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/config";

interface Match {
  professor_id: string;
  professor_name?: string | null;
  university?: string | null;
  lab_focus?: string | null;
  opportunity_explanation?: string | null;
  score: number;
  opportunity_score: number;
  final_rank: number;
}

export default function MatchesPage() {
  const [studentId] = useState<string | null>(() => (
    typeof window !== "undefined" ? sessionStorage.getItem("student_id") : null
  ));
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState<boolean>(() => Boolean(studentId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!studentId) {
      return;
    }
    fetch(`${API_BASE}/api/v1/matches?student_id=${encodeURIComponent(studentId)}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((d) => {
        setError(null);
        setMatches(d.matches || []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load matches"))
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading) {
    return (
      <div className="gc-card">
        <div className="gc-loading">
          <div className="gc-spinner" aria-hidden />
          <p>Loading your matches…</p>
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="gc-card">
        <p className="gc-error">{error}</p>
        <Link href="/profile" className="gc-btn-primary">Create profile</Link>
      </div>
    );
  }

  if (!studentId) {
    return (
      <div className="gc-card gc-empty-state">
        <h1 className="gc-title">No profile yet</h1>
        <p className="gc-subtitle">
          Create a profile so we can analyze your research interests and find matching supervisors.
        </p>
        <Link href="/profile" className="gc-btn-primary">
          Create your profile
        </Link>
      </div>
    );
  }

  return (
    <section className="gc-card">
      <div className="gc-page-header">
        <div>
          <h1 className="gc-title">Your supervisor matches</h1>
          <p className="gc-subtitle">
            Ranked by research fit and opportunity score. Click a row to generate a tailored outreach email.
          </p>
        </div>
        <Link href="/profile" className="gc-btn-secondary">
          Edit profile
        </Link>
      </div>

      {matches.length === 0 ? (
        <div className="gc-empty-state gc-empty-inline">
          <p className="gc-helper">No matches yet. Run discovery to ingest professors, then refresh.</p>
          <Link href="/profile" className="gc-btn-secondary">Back to profile</Link>
        </div>
      ) : (
        <div className="gc-table-wrap">
          <table className="gc-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Professor</th>
                <th>University</th>
                <th>Lab focus</th>
                <th className="gc-th-num">Fit</th>
                <th className="gc-th-num">Opportunity</th>
                <th className="gc-th-action">Action</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m, index) => (
                <tr key={m.professor_id}>
                  <td className="gc-td-rank">{index + 1}</td>
                  <td>
                    <span className="gc-table-name">
                      {m.professor_name || `Professor ${m.professor_id.slice(0, 8)}…`}
                    </span>
                  </td>
                  <td className="gc-td-univ">{m.university || "—"}</td>
                  <td className="gc-td-focus">
                    {m.lab_focus ? (
                      <span className="gc-focus-preview" title={m.lab_focus}>
                        {m.lab_focus.length > 60 ? `${m.lab_focus.slice(0, 60)}…` : m.lab_focus}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="gc-td-num">
                    <span className="gc-score gc-score-fit">{(m.score * 100).toFixed(0)}%</span>
                  </td>
                  <td className="gc-td-num">
                    <span className="gc-score gc-score-opp">{(m.opportunity_score * 100).toFixed(0)}%</span>
                    {m.opportunity_explanation ? (
                      <div className="gc-helper" title={m.opportunity_explanation}>
                        {m.opportunity_explanation.length > 65
                          ? `${m.opportunity_explanation.slice(0, 65)}…`
                          : m.opportunity_explanation}
                      </div>
                    ) : null}
                  </td>
                  <td className="gc-td-action">
                    <Link
                      href={`/email/${m.professor_id}?student_id=${studentId}`}
                      className="gc-btn-table"
                    >
                      Draft email
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
