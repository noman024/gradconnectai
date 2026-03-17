import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ padding: "2rem", maxWidth: "56rem", margin: "0 auto" }}>
      <h1>GradConnectAI</h1>
      <p>AI-driven supervisor discovery and matching for graduate students.</p>
      <p style={{ marginTop: "1rem" }}>
        Start by creating your profile so we can analyze your CV and match you with potential supervisors.
      </p>
      <nav style={{ display: "flex", gap: "1rem", marginTop: "2rem" }}>
        <Link href="/profile">Create profile</Link>
        <Link href="/matches">View matches</Link>
      </nav>
    </main>
  );
}

