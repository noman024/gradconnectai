"use client";

import { useState, useEffect, useCallback, use } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/config";

export default function EmailDraftPage({ params }: { params: Promise<{ professorId: string }> }) {
  const { professorId } = use(params);
  const [studentId, setStudentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ subject: string; body: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const sid = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("student_id") ?? sessionStorage.getItem("student_id") : null;
    setStudentId(sid);
    if (!sid) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/v1/email-drafts/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: sid, professor_id: professorId }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((d) => setDraft({ subject: d.subject || "", body: d.body || "" }))
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to generate draft");
        setDraft({ subject: "", body: "" });
      })
      .finally(() => setLoading(false));
  }, [professorId]);

  const copyToClipboard = useCallback(() => {
    if (!draft) return;
    const text = `Subject: ${draft.subject}\n\n${draft.body}`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [draft]);

  if (loading) {
    return (
      <div className="gc-card">
        <div className="gc-loading">
          <div className="gc-spinner" aria-hidden />
          <p>Generating your email draft…</p>
        </div>
      </div>
    );
  }
  if (!studentId) {
    return (
      <div className="gc-card">
        <p>Missing student. <Link href="/profile" className="gc-btn-primary">Create profile</Link></p>
      </div>
    );
  }

  return (
    <section className="gc-card">
      <div className="gc-page-header">
        <div>
          <h1 className="gc-title">Email draft</h1>
          <p className="gc-subtitle">
            Review, personalize if needed, then copy into your email client. We never send emails for you.
          </p>
        </div>
        <Link href="/matches" className="gc-btn-secondary">
          ← Back to matches
        </Link>
      </div>
      {error && <p className="gc-error">{error}</p>}
      {draft && (
        <div className="gc-email-draft">
          <div className="gc-email-subject">
            <span className="gc-email-label">Subject</span>
            <span>{draft.subject}</span>
          </div>
          <div className="gc-email-body-wrap">
            <span className="gc-email-label">Body</span>
            <div className="gc-email-body">
              {draft.body}
            </div>
          </div>
          <button
            type="button"
            className={`gc-copy-btn ${copied ? "copied" : ""}`}
            onClick={copyToClipboard}
          >
            {copied ? "✓ Copied to clipboard" : "Copy to clipboard"}
          </button>
        </div>
      )}
    </section>
  );
}
