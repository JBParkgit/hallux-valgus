import type { NextConfig } from "next";

/**
 * 환자 리포트 사이트 — 정적 파일(out/)로 빌드해 측정기 서버(Vultr)의 nginx가 내보낸다.
 *   빌드:  npm run build   → out/
 *   배포:  server/README.md '리포트 사이트' 참고
 *
 * 개발(npm run dev)에서는 nginx 대신 아래 rewrite 가 같은 역할을 한다:
 *   /report/{hash}  → /report 페이지
 *   /api/hv/*       → 측정기 서버 (HV_API_URL, .env)
 */
const isDev = process.env.NODE_ENV === "development";
const apiUrl = (process.env.HV_API_URL ?? "https://hv.hospitalrun.co.kr").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  ...(isDev
    ? {
        async rewrites() {
          return [
            { source: "/report/:hash", destination: "/report" },
            { source: "/api/hv/:path*", destination: `${apiUrl}/api/hv/:path*` },
          ];
        },
      }
    : { output: "export" as const, trailingSlash: true }),
  images: { unoptimized: true },
};

export default nextConfig;
