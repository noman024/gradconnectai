export default function EmailLoading() {
  return (
    <div className="gc-card">
      <div className="gc-loading">
        <div className="gc-spinner" aria-hidden />
        <p>Generating your email draft…</p>
      </div>
    </div>
  );
}
