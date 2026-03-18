const config = [
  ...((await import("eslint-config-next/core-web-vitals")).default ?? []),
  ...((await import("eslint-config-next/typescript")).default ?? []),
  {
    files: ["next.config.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
];

export default config;
