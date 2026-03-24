const fs = require("fs");
const path = require("path");

const sharedEnvPath = path.join(__dirname, "..", "config", "app.env");
const sharedLocalEnvPath = path.join(__dirname, "..", "config", "app.local.env");

function loadEnvFile(filePath, { overwrite = false } = {}) {
  if (!fs.existsSync(filePath)) return;
  const content = fs.readFileSync(filePath, "utf8");
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separatorIndex = line.indexOf("=");
    if (separatorIndex <= 0) continue;
    const key = line.slice(0, separatorIndex).trim();
    let value = line.slice(separatorIndex + 1).trim();
    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (overwrite || !(key in process.env)) {
      process.env[key] = value;
    }
  }
}

// Precedence: shell env > app.local.env > app.env
loadEnvFile(sharedEnvPath, { overwrite: false });
loadEnvFile(sharedLocalEnvPath, { overwrite: true });

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: process.env.DOCKER_BUILD === "1" ? "standalone" : undefined,
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8009";
    return [
      { source: "/api/v1/:path*", destination: `${apiBase}/api/v1/:path*` },
    ];
  },
};

module.exports = nextConfig;
