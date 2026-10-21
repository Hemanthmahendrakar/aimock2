/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Browser requests stay same-origin; Next proxies API calls over the
  // Docker network, avoiding localhost:8000 on each student's computer.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL || "http://api:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
