"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";

export default function EmailDraftPage({ params }: { params: Promise<{ professorId: string }> }) {
  const { professorId } = use(params);
  const [studentId, setStudentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ subject: string; body: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const sid = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("student_id") ?? sessionStorage.getItem("student_id") : null;
    setStudentId(sid);
    if (!sid) {
      setLoading(false);
      return;
    }
    fetch("/api/v1/email-drafts/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: sid, professor_id: professorId }),
    })
      .then((r) => r.json())
      .then((d) => setDraft({ subject: d.subject || "", body: d.body || "" }))
      .catch(() => setDraft({ subject: "", body: "Failed to generate draft." }))
      .finally(() => setLoading(false));
  }, [professorId]);

  if (loading) return <p>Generating draft…</p>;
  if (!studentId) return <p>Missing student. <Link href="/profile">Create profile</Link>.</p>;

  return (
    <main style={{ padding: "2rem", maxWidth: "48rem", margin: "0 auto" }}>
      <h1>Email draft</h1>
      <p>Review and copy this draft to send manually. We don’t send emails for you.</p>
      <nav style={{ marginBottom: "1rem" }}><Link href="/matches">Back to matches</Link></nav>
      {draft && (
        <div style={{ border: "1px solid #eee", borderRadius: "8px", padding: "1rem" }}>
          <p><strong>Subject:</strong> {draft.subject}</p>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{draft.body}</pre>
        </div>
      )}
    </main>
  );
}
