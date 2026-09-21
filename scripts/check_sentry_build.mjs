// Fail before downloading runtimes or compiling Rust if a monitored build cannot upload maps.
if (process.env.VITE_PUBLIC_SENTRY_DSN?.trim() && !process.env.SENTRY_AUTH_TOKEN?.trim()) {
  console.error('SENTRY_AUTH_TOKEN is missing. Configure the repository Actions Secret before building with VITE_PUBLIC_SENTRY_DSN.');
  process.exit(1);
}
console.log(process.env.VITE_PUBLIC_SENTRY_DSN?.trim()
  ? 'Sentry build credentials are configured (values hidden).'
  : 'Sentry DSN is not configured; building without monitoring uploads.');
