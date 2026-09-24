/** @type {import('next').NextConfig} */
const nextConfig = {
  // The e2e console runs beside the dev one; its own directory keeps the two
  // dev servers from sharing (and locking) .next.
  distDir: process.env.NEXT_DIST_DIR || '.next',
};

export default nextConfig;
