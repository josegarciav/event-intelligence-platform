import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/event-intelligence-platform",
  assetPrefix: "/event-intelligence-platform/",
  reactStrictMode: true,
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
