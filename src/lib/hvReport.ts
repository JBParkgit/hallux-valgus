/**
 * 환자 리포트 데이터 — 측정기 서버(Vultr)의 공개 리포트 API에서 읽는다.
 *
 * 리포트 사이트는 정적 파일로 빌드되어 측정기 서버(nginx)가 같은 도메인에서 내보낸다:
 *   https://hv.hospitalrun.co.kr/report/{hash}      ← 환자가 여는 주소 (알림톡 버튼)
 *   https://hv.hospitalrun.co.kr/api/hv/report/{hash} ← 이 파일이 읽는 데이터
 * 같은 도메인이므로 API 주소는 상대 경로로 부른다. (개발 중에는 next.config 의 rewrite)
 *
 * 서버는 공개 리포트에서 전화번호·등록번호·의사 ID·이미지 경로를 숨긴다.
 */

export interface ReportCase {
  id: string;
  reportHash: string;
  patientName: string;
  patientBirth: string;
  patientAge: number;
  hvaAngle: number | null;
  imaAngle: number | null;
  dmaaAngle: number | null;
  painDuration: string | null;
  hypermobility: boolean;
  jointCongruency: string;
  osteoarthritis: string;
  previousSurgery: boolean;
  previousSurgeryNote: string | null;
  clinicalNotes: string | null;
  severity: string | null;
  algorithmResult: string | null;
  algorithmReason: string | null;
  finalDecision: string | null;
  overrideReason: string | null;
  angleData: string | null;
  createdAt: Date;
  doctor: { name: string; hospital: string | null };
  /** 서버에 X-ray가 있으면 공개 이미지 주소, 없으면 null */
  xrayUrl: string | null;
}

const HASH_RE = /^[A-Za-z0-9_-]{1,64}$/;

export class ReportError extends Error {}

/** '/report/{hash}' (또는 '?h={hash}') 에서 해시를 꺼낸다. */
export function hashFromLocation(loc: Location): string | null {
  const m = loc.pathname.match(/\/report\/([^/?#]+)\/?$/);
  const raw = m ? decodeURIComponent(m[1]) : new URLSearchParams(loc.search).get("h");
  return raw && HASH_RE.test(raw) ? raw : null;
}

/** 리포트 해시로 케이스를 읽는다. 없으면 null. */
export async function loadReportCase(hash: string): Promise<ReportCase | null> {
  if (!HASH_RE.test(hash)) return null;
  const url = `/api/hv/report/${encodeURIComponent(hash)}`;
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch {
    throw new ReportError("네트워크에 연결할 수 없습니다. 잠시 후 다시 열어 주세요.");
  }
  if (res.status === 404) return null;
  if (!res.ok) throw new ReportError(`안내서를 불러오지 못했습니다. (오류 ${res.status})`);
  const c = await res.json();
  return {
    id: c.id,
    reportHash: c.reportHash,
    patientName: c.patientName ?? "",
    patientBirth: c.patientBirth ?? "",
    patientAge: c.patientAge ?? 0,
    hvaAngle: c.hvaAngle ?? null,
    imaAngle: c.imaAngle ?? null,
    dmaaAngle: c.dmaaAngle ?? null,
    painDuration: c.painDuration ?? null,
    hypermobility: !!c.hypermobility,
    jointCongruency: c.jointCongruency ?? "congruent",
    osteoarthritis: c.osteoarthritis ?? "none",
    previousSurgery: !!c.previousSurgery,
    previousSurgeryNote: c.previousSurgeryNote ?? null,
    clinicalNotes: c.clinicalNotes ?? null,
    severity: c.severity ?? null,
    algorithmResult: c.algorithmResult ?? null,
    algorithmReason: c.algorithmReason ?? null,
    finalDecision: c.finalDecision ?? null,
    overrideReason: c.overrideReason ?? null,
    angleData: c.angleData ?? null,
    createdAt: new Date(c.createdAt),
    doctor: { name: c.doctorName ?? "", hospital: c.hospital ?? null },
    xrayUrl: c.hasXray ? `${url}/xray` : null,
  };
}

/** 이미지의 원본 픽셀 크기 (측정선 오버레이 좌표계 맞추기용). 실패하면 null. */
export function loadImageSize(url: string): Promise<{ w: number; h: number } | null> {
  return new Promise((resolve) => {
    const img = new window.Image();
    img.onload = () => resolve(img.naturalWidth ? { w: img.naturalWidth, h: img.naturalHeight } : null);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}
