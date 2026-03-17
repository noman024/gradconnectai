import Link from "next/link";

export default function HomePage() {
  return (
    <div className="gc-grid gc-hero-grid">
      <section className="gc-card gc-hero-card">
        <h1 className="gc-hero-title">Find the right supervisor, faster.</h1>
        <p className="gc-subtitle gc-hero-subtitle">
          GradConnectAI scans labs and faculty pages, analyzes your research profile, and ranks potential supervisors by
          fit and opportunity.
        </p>
        <div className="gc-chip-row">
          <span className="gc-chip">Portfolio analysis</span>
          <span className="gc-chip">Semantic matching</span>
          <span className="gc-chip">Email drafts</span>
        </div>
        <div className="gc-button-row gc-hero-actions">
          <Link href="/profile" className="gc-btn-primary">
            Start with your profile
          </Link>
          <Link href="/matches" className="gc-btn-secondary">
            View matches
          </Link>
        </div>
        <p className="gc-footer-note">
          We never send emails on your behalf. You stay in control of every outreach.
        </p>
      </section>
      <aside className="gc-card-secondary gc-how-it-works">
        <h2 className="gc-how-title">How it works</h2>
        <ol className="gc-steps">
          <li className="gc-step">
            <span className="gc-step-num">1</span>
            <div>
              <strong>Upload or paste your CV</strong>
              <p className="gc-helper">We extract topics, methods, and fields from your research history.</p>
            </div>
          </li>
          <li className="gc-step">
            <span className="gc-step-num">2</span>
            <div>
              <strong>We scan labs and faculty pages</strong>
              <p className="gc-helper">Crawl4AI + our discovery engine track active and potential supervisors.</p>
            </div>
          </li>
          <li className="gc-step">
            <span className="gc-step-num">3</span>
            <div>
              <strong>You get ranked matches</strong>
              <p className="gc-helper">
                Matches are scored by semantic fit and likelihood of openings.
              </p>
            </div>
          </li>
        </ol>
      </aside>
    </div>
  );
}

