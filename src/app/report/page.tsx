"use client";

/**
 * /report/{hash} — 환자가 알림톡 버튼으로 여는 수술 안내서.
 *
 * 정적 파일로 빌드되어 측정기 서버(nginx)가 /report/* 요청에 이 페이지를 내보낸다.
 * 페이지는 주소의 해시로 같은 서버의 /api/hv/report/{hash} 를 읽어 그린다.
 */
import { useEffect, useState } from "react";
import { ReportView } from "./ReportView";
import { hashFromLocation, loadImageSize, loadReportCase, ReportError, type ReportCase } from "@/lib/hvReport";

type State =
  | { kind: "loading" }
  | { kind: "notfound" }
  | { kind: "error"; message: string }
  | { kind: "ready"; caseData: ReportCase; imgDim: { w: number; h: number } | null };

export default function ReportPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const hash = hashFromLocation(window.location);
      if (!hash) return setState({ kind: "notfound" });
      try {
        const caseData = await loadReportCase(hash);
        if (!caseData) return !cancelled && setState({ kind: "notfound" });
        const imgDim = caseData.xrayUrl ? await loadImageSize(caseData.xrayUrl) : null;
        if (!cancelled) {
          document.title = `${caseData.patientName}님 무지외반증 수술 안내서 - 달려라병원`;
          setState({ kind: "ready", caseData, imgDim });
        }
      } catch (e) {
        if (!cancelled) {
          setState({
            kind: "error",
            message: e instanceof ReportError ? e.message : "안내서를 불러오지 못했습니다.",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "ready") return <ReportView caseData={state.caseData} imgDim={state.imgDim} />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-6">
      <div className="max-w-sm w-full text-center space-y-3">
        {state.kind === "loading" && (
          <>
            <div className="w-10 h-10 mx-auto rounded-full border-4 border-blue-100 border-t-blue-600 animate-spin" />
            <p className="text-sm text-gray-500">수술 안내서를 불러오는 중입니다…</p>
          </>
        )}
        {state.kind === "notfound" && (
          <>
            <h1 className="text-lg font-bold text-gray-800">안내서를 찾을 수 없습니다</h1>
            <p className="text-sm text-gray-500 leading-relaxed">
              링크가 올바른지 확인해 주세요.
              <br />
              문의: 달려라병원 1600-7511
            </p>
          </>
        )}
        {state.kind === "error" && (
          <>
            <h1 className="text-lg font-bold text-gray-800">잠시 후 다시 열어 주세요</h1>
            <p className="text-sm text-gray-500 leading-relaxed">{state.message}</p>
          </>
        )}
      </div>
    </div>
  );
}
