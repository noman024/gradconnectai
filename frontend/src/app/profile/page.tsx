"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ProfilePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [cvText, setCvText] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [usePdf, setUsePdf] = useState(true);
  const [fields, setFields] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      let res: Response;
      const preferences = {
        countries: [] as string[],
        universities: [] as string[],
        fields: fields.split(",").map((s) => s.trim()).filter(Boolean),
      };

      if (usePdf && cvFile) {
        const form = new FormData();
        form.append("name", name);
        form.append("preferences_json", JSON.stringify(preferences));
        form.append("file", cvFile);
        res = await fetch(`${API_BASE}/api/v1/students/upload`, {
          method: "POST",
          body: form,
        });
      } else {
        res = await fetch(`${API_BASE}/api/v1/students`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            cv_text: cvText,
            preferences,
          }),
        });
      }
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
    <div className="gc-grid">
      <section className="gc-card">
        <h1 className="gc-title">Create your GradConnectAI profile</h1>
        <p className="gc-subtitle">
          Upload your CV as a PDF or paste your research summary. We’ll extract topics and build an embedding for
          matching.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="gc-input-row">
            <label className="gc-label" htmlFor="name">
              Full name
            </label>
            <input
              id="name"
              className="gc-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Sara Ahmed"
            />
          </div>

          <div className="gc-toggle-row">
            <div>
              <div className="gc-label">CV input mode</div>
              <p className="gc-helper">You can switch between uploading a PDF or pasting text.</p>
            </div>
            <div className="gc-toggle-pill">
              <button
                type="button"
                className={usePdf ? "gc-toggle-active" : ""}
                onClick={() => setUsePdf(true)}
              >
                PDF upload
              </button>
              <button
                type="button"
                className={!usePdf ? "gc-toggle-active" : ""}
                onClick={() => setUsePdf(false)}
              >
                Paste text
              </button>
            </div>
          </div>

          {usePdf ? (
            <div className="gc-input-row">
              <label className="gc-label" htmlFor="cvFile">
                CV (PDF)
              </label>
              <input
                id="cvFile"
                className="gc-file"
                type="file"
                accept="application/pdf"
                onChange={(e) => setCvFile(e.target.files?.[0] || null)}
                required={!cvText}
              />
              <p className="gc-helper">Upload the same CV you would send to supervisors (PDF format).</p>
            </div>
          ) : (
            <div className="gc-input-row">
              <label className="gc-label" htmlFor="cvText">
                CV or research summary (paste text)
              </label>
              <textarea
                id="cvText"
                className="gc-textarea"
                value={cvText}
                onChange={(e) => setCvText(e.target.value)}
                placeholder="Paste your CV or a detailed research summary here..."
              />
              <p className="gc-helper">We recommend at least a few paragraphs so the model has enough signal.</p>
            </div>
          )}

          <div className="gc-input-row">
            <label className="gc-label" htmlFor="fields">
              Research fields (comma-separated)
            </label>
            <input
              id="fields"
              className="gc-input"
              type="text"
              value={fields}
              onChange={(e) => setFields(e.target.value)}
              placeholder="e.g. machine learning, NLP, causal inference"
            />
            <p className="gc-helper">Used as an additional signal for topic extraction and filtering.</p>
          </div>

          {error && <p className="gc-error">{error}</p>}

          <div className="gc-button-row">
            <button type="submit" disabled={loading} className="gc-btn-primary">
              {loading ? "Analyzing profile…" : "Save profile & see matches"}
            </button>
          </div>
          <p className="gc-footer-note">
            Your profile is used only to compute matches. You can request data export or deletion at any time.
          </p>
        </form>
      </section>
      <aside className="gc-card-secondary">
        <p className="gc-subtitle">Tips for better matches</p>
        <ul className="gc-list">
          <li className="gc-list-item">
            <strong>Highlight methods and domains</strong>
            <p className="gc-helper">
              Mention techniques (e.g. transformers, RL, econometrics) and domains (e.g. climate, healthcare).
            </p>
          </li>
          <li className="gc-list-item">
            <strong>Mention your target track</strong>
            <p className="gc-helper">
              Master&apos;s, PhD, or Postdoc — this helps you manually filter matches later.
            </p>
          </li>
          <li className="gc-list-item">
            <strong>Keep it honest</strong>
            <p className="gc-helper">
              The system works best when your profile reflects your real experience and interests.
            </p>
          </li>
        </ul>
      </aside>
    </div>
  );
}
