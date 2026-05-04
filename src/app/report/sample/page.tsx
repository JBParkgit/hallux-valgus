export const dynamic = "force-dynamic";

import { prisma } from "@/lib/prisma";
import { redirect } from "next/navigation";

/**
 * /report/sample – redirects to the most recent real case's report page.
 * If no cases exist, renders a message.
 */
export default async function SampleRedirect() {
  const latest = await prisma.case.findFirst({
    orderBy: { createdAt: "desc" },
    select: { reportHash: true },
  });

  if (latest) {
    redirect(`/report/${latest.reportHash}`);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="text-center space-y-3">
        <p className="text-5xl">📋</p>
        <h1 className="text-xl font-bold text-gray-800">저장된 케이스가 없습니다</h1>
        <p className="text-sm text-gray-500">데스크톱 앱에서 케이스를 먼저 저장해 주세요.</p>
      </div>
    </div>
  );
}
