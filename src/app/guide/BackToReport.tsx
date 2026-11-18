"use client";

import { useEffect, useState } from "react";

/** 리포트에서 왔으면(?r={hash}) 그 리포트로 돌아가는 링크. 아니면 표시하지 않는다. */
export function BackToReport({ className = "" }: { className?: string }) {
  const [href, setHref] = useState<string | null>(null);

  useEffect(() => {
    const r = new URLSearchParams(window.location.search).get("r");
    if (r && /^[A-Za-z0-9_-]{1,64}$/.test(r)) setHref(`/report/${r}`);
  }, []);

  if (!href) return null;
  return (
    <a href={href} className={className}>
      ← 내 수술 안내서로 돌아가기
    </a>
  );
}
