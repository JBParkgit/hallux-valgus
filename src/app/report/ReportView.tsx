/**
 * 환자용 무지외반증 리포트 화면 (디자인).
 * 데이터는 /report 페이지(page.tsx)가 측정기 서버 API에서 받아 넘겨준다.
 */
import Image from "next/image";
import type { ReportCase } from "@/lib/hvReport";

/* ─── types ─── */

interface SurgeryData {
  angles?: { hva?: number; ima?: number; dmaa?: number };
  severity?: string;
  algorithm_result?: string;
  addon_surgery?: string;
  reasons?: string[];
  final_decision?: string;
  override_reason?: string | null;
}

interface ClinicalData {
  hypermobility?: boolean;
  congruent?: boolean;
  oa_grade?: number;
}

interface MeasurementPoints {
  points: number[][]; // [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
  angle: number | null;
}

interface AngleData {
  foot_side?: string;
  left_surgery?: SurgeryData;
  right_surgery?: SurgeryData;
  clinical?: {
    left?: ClinicalData;
    right?: ClinicalData;
  };
  measurements?: Record<string, MeasurementPoints>;
}

/* ─── constants ─── */

const SEVERITY_CONFIG = {
  mild: {
    label: "경증",
    eng: "Mild",
    color: "from-emerald-500 to-green-600",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    text: "text-emerald-700",
    badgeBg: "bg-emerald-100",
    icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
    description: "무지외반증의 초기 단계로, 변형이 크지 않아 보존적 치료와 함께 경과 관찰이 가능한 상태입니다. 적절한 교정으로 양호한 예후가 기대됩니다.",
  },
  moderate: {
    label: "중등도",
    eng: "Moderate",
    color: "from-amber-500 to-orange-500",
    bg: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-700",
    badgeBg: "bg-amber-100",
    icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z",
    description: "적극적인 치료가 필요한 단계입니다. 변형이 진행되어 일상생활에 불편함을 초래하며, 수술적 교정을 통해 정상에 가까운 회복이 가능합니다.",
  },
  severe: {
    label: "중증",
    eng: "Severe",
    color: "from-red-500 to-rose-600",
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    badgeBg: "bg-red-100",
    icon: "M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    description: "심한 변형으로 수술적 치료가 반드시 필요한 단계입니다. 전문적인 수술을 통해 통증 완화와 기능 회복을 목표로 합니다.",
  },
} as const;

const SEVERITY_KO_MAP: Record<string, keyof typeof SEVERITY_CONFIG> = {
  mild: "mild",
  moderate: "moderate",
  severe: "severe",
  "경증": "mild",
  "중등도": "moderate",
  "중증": "severe",
};

/** 병원 무지외반증 클리닉 페이지 (리포트 하단 '병원 정보'에서 연결) */
const HOSPITAL_BUNION_URL = "https://www.hospitalrun.co.kr/bunion/";

/** 같은 수술의 다른 이름 → SURGERY_INFO 의 이름 */
const SURGERY_ALIASES: Record<string, string> = {
  "핀홀교정술": "핀홀 무지외반증 교정술",
};

const SURGERY_INFO: Record<string, { desc: string; detail: string }> = {
  "핀홀 무지외반증 교정술": {
    desc: "최소침습 교정술 · 핀홀교정술",
    detail: "피부를 크게 절개하지 않고 작은 구멍(핀홀)을 통해 특수 기구로 뼈를 교정하는 최소침습 수술입니다. 엄지발가락 뒤쪽의 제1중족골을 가로로 절골하여 바깥쪽으로 옮겨 각도를 바로잡고, 엄지발가락 첫마디뼈를 교정하는 Akin 절골술을 함께 시행합니다. 교정한 뼈는 고정 기구로 단단히 고정합니다.",
  },
  "Chevron 절골술": {
    desc: "원위 중족골 V자형 절골술",
    detail: "제1중족골 원위부를 V자(chevron) 모양으로 절골한 후 외측으로 이동시켜 고정합니다. 경증~중등도의 무지외반증에 가장 널리 사용되는 술식으로, 수술 시간이 짧고 회복이 비교적 빠릅니다. 절골 부위는 특수 나사(screw)로 고정하며, 뼈가 유합된 후에는 제거하지 않아도 됩니다.",
  },
  "Scarf 절골술": {
    desc: "중족골 Z자형 절골술",
    detail: "제1중족골을 Z자 모양으로 길게 절골하여 정밀하게 교정합니다. Chevron 절골술보다 큰 교정이 가능하며, 특히 중등도 변형에 효과적입니다. 넓은 절골면이 안정적인 고정을 제공하고, 3차원적 교정(회전, 단축, 이동)이 가능한 장점이 있습니다.",
  },
  "근위 절골술": {
    desc: "근위 중족골 절골술",
    detail: "제1중족골의 기저부(몸쪽)에서 절골하여 큰 각도의 교정을 수행합니다. 중족골간각(IMA)이 크게 증가된 경우에 효과적이며, 근본적인 교정이 가능합니다. 절골 후 금속판 또는 나사로 고정하며, 뼈 유합까지 체중 부하를 제한해야 합니다.",
  },
  "Lapidus 절골술": {
    desc: "제1중족-내측 설상골 관절 유합술",
    detail: "제1중족-내측 설상골(TMT) 관절을 유합하여 변형의 근본 원인인 관절 불안정성을 교정합니다. 중증 변형, 과운동성(hypermobility)이 있는 경우, 재발된 무지외반증에 특히 효과적입니다. 재발률이 가장 낮은 술식이지만, 회복 기간이 다소 깁니다.",
  },
  "제1MTP 관절유합술": {
    desc: "제1중족지절 관절 유합술",
    detail: "제1중족지절(MTP) 관절을 유합하여 통증을 제거하고 안정성을 확보합니다. 심한 관절염이 동반된 중증 무지외반증, 이전 수술 후 재발, 또는 관절 파괴가 진행된 경우에 시행합니다. 관절 운동은 제한되지만 통증 해소 효과가 확실합니다.",
  },
};

const OA_GRADES = ["없음", "경도", "중등도", "중증"] as const;

/* ─── helpers ─── */

function getAngleInfo(type: "hva" | "ima" | "dmaa", value: number) {
  const configs = {
    hva: {
      name: "HVA",
      fullName: "무지외반각 (Hallux Valgus Angle)",
      description: "엄지발가락이 바깥쪽으로 벌어진 각도입니다. 이 각도가 클수록 무지외반증의 정도가 심합니다.",
      normal: 15,
      ranges: [
        { max: 15, label: "정상", color: "text-emerald-600", bg: "bg-emerald-500", barColor: "bg-emerald-400" },
        { max: 30, label: "경증", color: "text-amber-600", bg: "bg-amber-500", barColor: "bg-amber-400" },
        { max: 40, label: "중등도", color: "text-orange-600", bg: "bg-orange-500", barColor: "bg-orange-400" },
        { max: Infinity, label: "중증", color: "text-red-600", bg: "bg-red-500", barColor: "bg-red-400" },
      ],
      maxDisplay: 60,
      normalLabel: "< 15°",
    },
    ima: {
      name: "IMA",
      fullName: "중족골간각 (Intermetatarsal Angle)",
      description: "첫 번째와 두 번째 중족골 사이의 각도입니다. 이 각도가 크면 엄지발가락이 바깥으로 밀려나는 원인이 됩니다.",
      normal: 9,
      ranges: [
        { max: 9, label: "정상", color: "text-emerald-600", bg: "bg-emerald-500", barColor: "bg-emerald-400" },
        { max: 14, label: "경증", color: "text-amber-600", bg: "bg-amber-500", barColor: "bg-amber-400" },
        { max: 16, label: "중등도", color: "text-orange-600", bg: "bg-orange-500", barColor: "bg-orange-400" },
        { max: Infinity, label: "중증", color: "text-red-600", bg: "bg-red-500", barColor: "bg-red-400" },
      ],
      maxDisplay: 25,
      normalLabel: "< 9°",
    },
    dmaa: {
      name: "DMAA",
      fullName: "원위중족골 관절면각 (Distal Metatarsal Articular Angle)",
      description: "원위 중족골의 관절면 기울기 각도입니다. 수술 방법 선택에 중요한 지표가 됩니다.",
      normal: 10,
      ranges: [
        { max: 10, label: "정상", color: "text-emerald-600", bg: "bg-emerald-500", barColor: "bg-emerald-400" },
        { max: Infinity, label: "비정상", color: "text-red-600", bg: "bg-red-500", barColor: "bg-red-400" },
      ],
      maxDisplay: 30,
      normalLabel: "< 10°",
    },
  };

  const config = configs[type];
  // 화면에 보이는 값(소수점 1자리)으로 판정 — 14.96° 가 '15.0°'로 보이면서 '정상'으로 나오지 않도록
  const shown = round1(value);
  const range = config.ranges.find((r) => shown < r.max) ?? config.ranges[config.ranges.length - 1];
  const percent = Math.min((shown / config.maxDisplay) * 100, 100);

  return { ...config, status: range, percent };
}

/** 각도는 소수점 1자리까지만 표시한다 */
function round1(v: number): number {
  return Math.round(v * 10) / 10;
}

/** 문장 속 각도(예: 'HVA: 35.41237°')를 소수점 1자리로 — 예전에 저장된 판단 근거용 */
function formatAnglesInText(text: string): string {
  return text.replace(/(\d+\.\d{2,})(?=\s*°)/g, (m) => round1(parseFloat(m)).toFixed(1));
}

function parseSeverityKey(raw: string | null | undefined): keyof typeof SEVERITY_CONFIG | null {
  if (!raw) return null;
  return SEVERITY_KO_MAP[raw] ?? null;
}

function formatDate(date: Date): string {
  return new Date(date).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/* ─── components ─── */

function AngleMeasurementCard({ type, value }: { type: "hva" | "ima" | "dmaa"; value: number }) {
  const info = getAngleInfo(type, value);
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <div>
          <span className="text-[13px] font-bold text-gray-900">{info.name}</span>
          <span className="text-[11px] text-gray-400 ml-1.5">{info.fullName.split("(")[0].trim()}</span>
        </div>
        <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${info.status.bg} text-white`}>
          {info.status.label}
        </span>
      </div>
      <p className="text-[11px] text-gray-400 mb-3 leading-relaxed">{info.description}</p>
      <div className="flex items-end gap-3">
        <span className={`text-2xl font-extrabold tabular-nums ${info.status.color}`}>{value.toFixed(1)}°</span>
        <span className="text-[11px] text-gray-400 mb-1">정상 {info.normalLabel}</span>
      </div>
      {/* bar */}
      <div className="mt-2 relative">
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${info.status.barColor} transition-all`}
            style={{ width: `${info.percent}%` }}
          />
        </div>
        {/* normal threshold marker */}
        <div
          className="absolute top-0 h-2 border-r-2 border-dashed border-gray-400"
          style={{ left: `${(info.normal / info.maxDisplay) * 100}%` }}
        />
      </div>
    </div>
  );
}

function FootReportSection({
  side,
  surgery,
  clinical,
}: {
  side: "left" | "right";
  surgery: SurgeryData;
  clinical?: ClinicalData;
}) {
  const sideLabel = side === "left" ? "왼발" : "오른발";
  const sideIcon = side === "left" ? "L" : "R";
  const sevKey = parseSeverityKey(surgery.severity);
  const sevConfig = sevKey ? SEVERITY_CONFIG[sevKey] : null;
  const decision = surgery.final_decision ?? surgery.algorithm_result ?? "";
  const baseSurgery = decision.replace(/\s*\+\s*Akin 절골술/g, "").trim();
  const hasAkin = decision.includes("Akin");
  const surgeryDetail = SURGERY_INFO[SURGERY_ALIASES[baseSurgery] ?? baseSurgery];

  return (
    <div className="space-y-4">
      {/* foot side header */}
      <div className="flex items-center gap-2">
        <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${sevConfig?.color ?? "from-gray-400 to-gray-500"} flex items-center justify-center`}>
          <span className="text-white text-xs font-extrabold">{sideIcon}</span>
        </div>
        <div>
          <h3 className="text-base font-bold text-gray-900">{sideLabel}</h3>
          {sevConfig && (
            <span className={`text-[11px] font-semibold ${sevConfig.text}`}>{sevConfig.label} ({sevConfig.eng})</span>
          )}
        </div>
      </div>

      {/* severity card */}
      {sevConfig && (
        <div className={`rounded-2xl ${sevConfig.bg} ${sevConfig.border} border p-4`}>
          <div className="flex items-start gap-2.5">
            <svg className={`w-5 h-5 mt-0.5 flex-shrink-0 ${sevConfig.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d={sevConfig.icon} />
            </svg>
            <div>
              <p className={`text-sm font-bold ${sevConfig.text}`}>진단: {sevConfig.label} 무지외반증</p>
              <p className="text-[12px] text-gray-600 mt-1 leading-relaxed">{sevConfig.description}</p>
            </div>
          </div>
        </div>
      )}

      {/* angle measurements */}
      {surgery.angles && (
        <div className="space-y-3">
          <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">각도 측정 결과</h4>
          <div className="space-y-2.5">
            {surgery.angles.hva != null && <AngleMeasurementCard type="hva" value={surgery.angles.hva} />}
            {surgery.angles.ima != null && <AngleMeasurementCard type="ima" value={surgery.angles.ima} />}
            {surgery.angles.dmaa != null && <AngleMeasurementCard type="dmaa" value={surgery.angles.dmaa} />}
          </div>
        </div>
      )}

      {/* clinical findings */}
      {clinical && (
        <div className="space-y-3">
          <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">임상 소견</h4>
          <div className="grid grid-cols-2 gap-2.5">
            <ClinicalItem
              label="관절 과운동성"
              value={clinical.hypermobility ? "있음" : "없음"}
              isWarning={!!clinical.hypermobility}
            />
            <ClinicalItem
              label="관절 적합성"
              value={clinical.congruent ? "적합 (Congruent)" : "부적합 (Incongruent)"}
              isWarning={!clinical.congruent}
            />
            <ClinicalItem
              label="골관절염"
              value={OA_GRADES[clinical.oa_grade ?? 0]}
              isWarning={(clinical.oa_grade ?? 0) >= 2}
              colSpan2
            />
          </div>
        </div>
      )}

      {/* surgery recommendation */}
      {decision && (
        <div className="space-y-3">
          <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">수술 권장 사항</h4>
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-4 space-y-3">
            <div>
              <p className="text-[11px] text-blue-500 font-bold uppercase tracking-wider">권장 수술법</p>
              <p className="text-lg font-extrabold text-blue-900 mt-0.5">{decision}</p>
            </div>

            {surgeryDetail && (
              <>
                <div>
                  <p className="text-[11px] text-blue-500 font-bold uppercase tracking-wider">{surgeryDetail.desc}</p>
                  <p className="text-[12px] text-gray-700 mt-1 leading-[1.7]">{surgeryDetail.detail}</p>
                </div>

                {hasAkin && (
                  <div className="bg-white/60 rounded-xl px-3.5 py-2.5 border border-blue-100">
                    <p className="text-[11px] text-blue-500 font-bold uppercase tracking-wider">+ Akin 절골술 (추가 시술)</p>
                    <p className="text-[12px] text-gray-600 mt-1 leading-relaxed">
                      근위지골 내측 쐐기 절골술을 추가하여 엄지발가락의 정렬을 더욱 개선합니다. 잔여 변형을 미세 교정하여 수술 결과를 최적화합니다.
                    </p>
                  </div>
                )}
              </>
            )}

            {/* algorithm reasons */}
            {surgery.reasons && surgery.reasons.length > 0 && (
              <div>
                <p className="text-[11px] text-blue-500 font-bold uppercase tracking-wider mb-1.5">판단 근거</p>
                <ul className="space-y-1">
                  {surgery.reasons.map((r, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] text-gray-600">
                      <span className="text-blue-400 mt-0.5 flex-shrink-0">&#8226;</span>
                      <span>{formatAnglesInText(r)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* override */}
            {surgery.override_reason && (
              <div className="bg-amber-50 rounded-xl px-3.5 py-2.5 border border-amber-200">
                <p className="text-[11px] text-amber-600 font-bold uppercase tracking-wider">담당의 소견</p>
                <p className="text-[12px] text-gray-700 mt-1 leading-relaxed">{surgery.override_reason}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ClinicalItem({
  label,
  value,
  isWarning,
  colSpan2,
}: {
  label: string;
  value: string;
  isWarning: boolean;
  colSpan2?: boolean;
}) {
  return (
    <div className={`bg-white rounded-xl border ${isWarning ? "border-amber-200 bg-amber-50/30" : "border-gray-100"} px-3 py-2.5 ${colSpan2 ? "col-span-2" : ""}`}>
      <p className="text-[10px] text-gray-400 font-medium">{label}</p>
      <p className={`text-[13px] font-bold mt-0.5 ${isWarning ? "text-amber-700" : "text-gray-800"}`}>{value}</p>
    </div>
  );
}

function SectionDivider() {
  return <div className="border-t border-dashed border-gray-200 my-2" />;
}

/* ─── X-ray with SVG measurement overlay ─── */

/** 측정 프로그램과 같은 색: 기준선(제1중족골 축)은 노랑, 각도별 두 번째 선은 각도 색 */
const AXIS_COLOR = "#facc15";
const ANGLE_COLORS: Record<string, string> = { HVA: "#f2555a", IMA: "#4c8dff", DMAA: "#22c38e" };
const ANGLE_NAMES: Record<string, string> = { HVA: "무지외반각", IMA: "중족골간각", DMAA: "원위관절면각" };
const ANGLE_ORDER = ["HVA", "IMA", "DMAA"];

interface SideLegend {
  key: string;            // "L-" | "R-" | ""
  label: string;          // 좌측 / 우측 / 측정값
  onLeft: boolean;        // 이미지에서 왼쪽에 있는 발이면 true → 왼쪽 아래에 표시
  rows: { base: string; angle: number }[];
}

/** 측정값을 발별로 묶고, 그 발의 선이 이미지 왼쪽/오른쪽 어디에 있는지 판단한다. */
function buildLegends(measurements: Record<string, MeasurementPoints>, imageWidth: number): SideLegend[] {
  const groups = new Map<string, { xs: number[]; rows: { base: string; angle: number }[] }>();
  for (const [name, m] of Object.entries(measurements)) {
    if (!m.points || m.points.length < 4 || m.angle == null) continue;
    const prefix = /^[LR]-/.test(name) ? name.slice(0, 2) : "";
    const base = name.replace(/^[LR]-/, "");
    if (!ANGLE_NAMES[base]) continue;
    const g = groups.get(prefix) ?? { xs: [], rows: [] };
    g.xs.push(...m.points.map((p) => p[0]));
    g.rows.push({ base, angle: m.angle });
    groups.set(prefix, g);
  }
  const legends: SideLegend[] = [...groups.entries()].map(([key, g]) => {
    const avgX = g.xs.reduce((a, b) => a + b, 0) / g.xs.length;
    return {
      key,
      label: key === "L-" ? "좌측 발" : key === "R-" ? "우측 발" : "측정값",
      onLeft: avgX < imageWidth / 2,
      rows: g.rows.sort((a, b) => ANGLE_ORDER.indexOf(a.base) - ANGLE_ORDER.indexOf(b.base)),
    };
  });
  // 두 발이 같은 쪽으로 판단되면(드문 경우) 좌측 발을 왼쪽에 둔다
  if (legends.length === 2 && legends[0].onLeft === legends[1].onLeft) {
    for (const l of legends) l.onLeft = l.key !== "R-";
  }
  return legends;
}

function LegendBox({ legend }: { legend: SideLegend }) {
  return (
    <div className="bg-black/70 backdrop-blur-[2px] rounded-lg px-2.5 py-2 min-w-[112px] shadow-lg">
      <p className="text-[11px] font-bold text-white mb-1">{legend.label}</p>
      <ul className="space-y-0.5">
        {legend.rows.map((r) => (
          <li key={r.base} className="flex items-center gap-1.5 text-[11px] leading-tight text-white/90">
            <span className="inline-block w-3 h-[3px] rounded-full shrink-0" style={{ backgroundColor: ANGLE_COLORS[r.base] }} />
            <span className="font-semibold">{r.base}</span>
            <span className="hidden min-[440px]:inline text-white/55 text-[10px] whitespace-nowrap">{ANGLE_NAMES[r.base]}</span>
            <span className="ml-auto pl-2 font-bold tabular-nums whitespace-nowrap">{r.angle.toFixed(1)}°</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function XrayWithOverlay({
  imageUrl,
  measurements,
  imageWidth = 550,
  imageHeight = 550,
}: {
  imageUrl: string;
  measurements?: Record<string, MeasurementPoints>;
  imageWidth?: number;
  imageHeight?: number;
}) {
  const entries = Object.entries(measurements ?? {}).filter(
    ([, m]) => m.points && m.points.length >= 4 && m.angle != null,
  );
  const legends = measurements ? buildLegends(measurements, imageWidth) : [];
  const leftLegends = legends.filter((l) => l.onLeft);
  const rightLegends = legends.filter((l) => !l.onLeft);

  // viewBox matches actual image pixel dimensions so SVG coordinates align
  const vbW = imageWidth;
  const vbH = imageHeight;
  const strokeW = vbW / 280;
  const dotR = vbW / 200;
  const ext = vbW * 0.04;

  return (
    <div>
      <div className="rounded-2xl overflow-hidden border border-gray-200 bg-black shadow-sm relative">
        <Image
          src={imageUrl}
          alt="X-ray 측정 영상"
          width={600}
          height={500}
          className="w-full object-contain block"
          unoptimized
          priority
        />
        {entries.length > 0 && (
          <svg
            className="absolute inset-0 w-full h-full"
            viewBox={`0 0 ${vbW} ${vbH}`}
            preserveAspectRatio="xMidYMid meet"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* 각도별 두 번째 선 (그 각도의 색) */}
            {entries.map(([name, m]) => {
              const color = ANGLE_COLORS[name.replace(/^[LR]-/, "")] ?? "#ffffff";
              const pts = m.points;
              return (
                <g key={name}>
                  <ExtendedLine p0={pts[2]} p1={pts[3]} color={color} strokeW={strokeW} ext={ext} />
                  <circle cx={pts[2][0]} cy={pts[2][1]} r={dotR} fill={color} />
                  <circle cx={pts[3][0]} cy={pts[3][1]} r={dotR} fill={color} />
                </g>
              );
            })}
            {/* 기준선(제1중족골 축) — 맨 위에 한 번만 보이도록 마지막에 그린다 */}
            {entries.map(([name, m]) => (
              <g key={`axis-${name}`}>
                <ExtendedLine p0={m.points[0]} p1={m.points[1]} color={AXIS_COLOR} strokeW={strokeW} ext={ext} />
                <circle cx={m.points[0][0]} cy={m.points[0][1]} r={dotR} fill={AXIS_COLOR} />
                <circle cx={m.points[1][0]} cy={m.points[1][1]} r={dotR} fill={AXIS_COLOR} />
              </g>
            ))}
          </svg>
        )}

        {/* 각도 값: 이미지 하단 양쪽에 발별로 정리 */}
        {legends.length > 0 && (
          <div className="absolute inset-x-0 bottom-0 p-2 flex justify-between items-end gap-2 pointer-events-none">
            <div className="space-y-1.5">{leftLegends.map((l) => <LegendBox key={l.key} legend={l} />)}</div>
            <div className="space-y-1.5">{rightLegends.map((l) => <LegendBox key={l.key} legend={l} />)}</div>
          </div>
        )}
      </div>
      {entries.length > 0 && (
        <p className="flex items-center justify-center gap-1.5 text-[10px] text-gray-400 mt-2">
          <span className="inline-block w-3 h-[3px] rounded-full" style={{ backgroundColor: AXIS_COLOR }} />
          노란 선: 기준선(제1중족골 축) · 색 선: 각 각도의 두 번째 선
        </p>
      )}
    </div>
  );
}

/** 측정 각도 안내 문서(/guide/) 링크 — 각도를 어떻게 재는지 궁금한 환자용 */
function GuideLink({ hash }: { hash: string }) {
  return (
    <a
      href={`/guide/?r=${encodeURIComponent(hash)}`}
      className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-blue-700"
    >
      <span>
        <span className="block text-[13px] font-bold">각도는 어떻게 재나요?</span>
        <span className="block text-[11px] text-blue-500 mt-0.5">HVA·IMA·DMAA 측정 방법과 의미 보기</span>
      </span>
      <span aria-hidden className="text-lg font-bold">→</span>
    </a>
  );
}

function ExtendedLine({
  p0,
  p1,
  color,
  strokeW,
  ext,
}: {
  p0: number[];
  p1: number[];
  color: string;
  strokeW: number;
  ext: number;
}) {
  const dx = p1[0] - p0[0];
  const dy = p1[1] - p0[1];
  const len = Math.hypot(dx, dy);
  if (len < 0.1) return null;
  const nx = dx / len;
  const ny = dy / len;
  return (
    <line
      x1={p0[0] - nx * ext}
      y1={p0[1] - ny * ext}
      x2={p1[0] + nx * ext}
      y2={p1[1] + ny * ext}
      stroke={color}
      strokeWidth={strokeW}
      strokeLinecap="round"
      opacity={0.9}
    />
  );
}

/* ─── page ─── */

export function ReportView({
  caseData,
  imgDim,
}: {
  caseData: ReportCase;
  /** X-ray 원본 크기 (측정선 좌표계). 모르면 null */
  imgDim: { w: number; h: number } | null;
}) {
  // parse bilateral data
  let angleData: AngleData = {};
  try {
    angleData = caseData.angleData ? JSON.parse(caseData.angleData) : {};
  } catch {
    angleData = {};
  }

  const isBilateral = !!(angleData.left_surgery && angleData.right_surgery);
  const footSide = angleData.foot_side ?? (isBilateral ? "bilateral" : "left");

  // For single-foot fallback: use top-level fields
  const hasBilateralData = !!(angleData.left_surgery || angleData.right_surgery);

  // Build single-foot fallback surgery data from top-level fields
  const fallbackSurgery: SurgeryData | null = !hasBilateralData
    ? {
        angles: {
          hva: caseData.hvaAngle ?? undefined,
          ima: caseData.imaAngle ?? undefined,
          dmaa: caseData.dmaaAngle ?? undefined,
        },
        severity: caseData.severity ?? undefined,
        algorithm_result: caseData.algorithmResult ?? undefined,
        final_decision: caseData.finalDecision ?? undefined,
        override_reason: caseData.overrideReason,
        reasons: caseData.algorithmReason ? (() => { try { return JSON.parse(caseData.algorithmReason); } catch { return [caseData.algorithmReason]; } })() : undefined,
      }
    : null;

  const fallbackClinical: ClinicalData | null = !hasBilateralData
    ? {
        hypermobility: caseData.hypermobility,
        congruent: caseData.jointCongruency === "congruent",
        oa_grade: caseData.osteoarthritis === "none" ? 0 : caseData.osteoarthritis === "mild" ? 1 : caseData.osteoarthritis === "moderate" ? 2 : 3,
      }
    : null;

  const imageUrl = caseData.xrayUrl;
  const createdDate = formatDate(caseData.createdAt);

  // 머리글은 병원 색으로 고정 (중증도 색은 본문의 발별 배지·진단 박스에서만 사용)
  const headerGradient = "from-blue-600 to-indigo-700";

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-[480px] mx-auto bg-white min-h-screen shadow-xl">

        {/* ━━━ Header ━━━ */}
        <header className={`bg-gradient-to-r ${headerGradient} text-white px-5 pt-6 pb-5`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 bg-white/20 rounded-lg flex items-center justify-center backdrop-blur-sm">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <div>
                <h1 className="text-lg font-extrabold tracking-tight">{caseData.doctor.hospital ?? "달려라병원"}</h1>
                <p className="text-white/60 text-[11px]">정형외과 전문</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-white/90 text-[12px] font-medium">{caseData.doctor.name} 원장</p>
              <p className="text-white/50 text-[11px]">{createdDate}</p>
            </div>
          </div>

          <div className="bg-white/10 backdrop-blur-sm rounded-2xl px-4 py-3">
            <p className="text-white/60 text-[11px] font-medium">환자 보고서</p>
            <p className="text-xl font-extrabold mt-0.5">
              {caseData.patientName}
              <span className="text-white/60 text-sm font-medium ml-1.5">님</span>
            </p>
            <p className="text-white/50 text-[11px] mt-1">
              무지외반증 정밀 분석 리포트 &middot; {createdDate}
            </p>
          </div>
        </header>

        {/* ━━━ Content ━━━ */}
        <div className="px-5 py-6 space-y-8">

          {/* ── Patient Info ── */}
          <section>
            <h2 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">환자 정보</h2>
            <div className="grid grid-cols-3 gap-2.5">
              <InfoCard label="생년월일" value={caseData.patientBirth} />
              <InfoCard label="나이" value={`${caseData.patientAge}세`} />
              <InfoCard label="측정일" value={createdDate} />
            </div>
            {caseData.painDuration && (
              <div className="mt-2.5 bg-gray-50 rounded-xl border border-gray-100 px-3 py-2.5">
                <p className="text-[10px] text-gray-400 font-medium">통증 지속 기간</p>
                <p className="text-[13px] font-bold text-gray-800 mt-0.5">{caseData.painDuration}</p>
              </div>
            )}
            {caseData.previousSurgery && (
              <div className="mt-2.5 bg-amber-50 rounded-xl border border-amber-200 px-3 py-2.5">
                <p className="text-[10px] text-amber-500 font-medium">이전 수술 이력</p>
                <p className="text-[13px] font-bold text-amber-800 mt-0.5">
                  {caseData.previousSurgeryNote || "수술 이력 있음"}
                </p>
              </div>
            )}
          </section>

          {/* ── X-ray Image with Measurement Overlay ── */}
          {imageUrl && (
            <section>
              <h2 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">
                X-ray 측정 영상
              </h2>
              <XrayWithOverlay
                imageUrl={imageUrl}
                measurements={angleData.measurements}
                imageWidth={imgDim?.w ?? 550}
                imageHeight={imgDim?.h ?? 550}
              />
              <p className="text-[10px] text-gray-400 mt-1 text-center leading-relaxed">
                HVA, IMA, DMAA 각도가 각각 측정되어 아래 분석에 사용됩니다.
              </p>
              <GuideLink hash={caseData.reportHash} />
            </section>
          )}
          {!imageUrl && <GuideLink hash={caseData.reportHash} />}

          <SectionDivider />

          {/* ── Bilateral / Single Foot Report ── */}
          {hasBilateralData ? (
            <>
              {/* bilateral header */}
              <section>
                <div className="flex items-center gap-2 mb-1">
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <h2 className="text-base font-extrabold text-gray-900">상세 분석 결과</h2>
                </div>
                <p className="text-[12px] text-gray-400">
                  {footSide === "bilateral" ? "양측(좌/우) 발 모두 측정되었습니다." : `${footSide === "left" ? "왼발" : "오른발"} 측정 결과입니다.`}
                </p>
              </section>

              {/* left foot */}
              {angleData.left_surgery && (
                <section>
                  <FootReportSection
                    side="left"
                    surgery={angleData.left_surgery}
                    clinical={angleData.clinical?.left}
                  />
                </section>
              )}

              {/* divider between feet */}
              {isBilateral && (
                <div className="flex items-center gap-3 py-1">
                  <div className="flex-1 border-t border-gray-200" />
                  <span className="text-[10px] text-gray-300 font-bold tracking-widest">LEFT / RIGHT</span>
                  <div className="flex-1 border-t border-gray-200" />
                </div>
              )}

              {/* right foot */}
              {angleData.right_surgery && (
                <section>
                  <FootReportSection
                    side="right"
                    surgery={angleData.right_surgery}
                    clinical={angleData.clinical?.right}
                  />
                </section>
              )}
            </>
          ) : fallbackSurgery ? (
            <section>
              <div className="flex items-center gap-2 mb-4">
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <h2 className="text-base font-extrabold text-gray-900">상세 분석 결과</h2>
              </div>
              <FootReportSection
                side="left"
                surgery={fallbackSurgery}
                clinical={fallbackClinical ?? undefined}
              />
            </section>
          ) : null}

          <SectionDivider />

          {/* ── Clinical Notes ── */}
          {caseData.clinicalNotes && (
            <section>
              <h2 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">담당의 임상 메모</h2>
              <div className="bg-slate-50 rounded-2xl border border-slate-200 px-4 py-3.5">
                <div className="flex items-start gap-2.5">
                  <svg className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  <p className="text-[13px] text-gray-700 leading-[1.8] whitespace-pre-wrap">{caseData.clinicalNotes}</p>
                </div>
              </div>
            </section>
          )}

          {/* ── Recovery Guide ── */}
          <section>
            <h2 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">수술 후 주의사항</h2>
            <div className="space-y-2.5">
              <RecoveryItem
                step="1"
                title="수술 직후 (1~2주)"
                desc="수술 부위의 붕대와 특수 신발을 착용합니다. 발을 심장보다 높이 올려 부기를 줄이고, 처방된 약을 정시에 복용하세요."
              />
              <RecoveryItem
                step="2"
                title="초기 회복기 (2~6주)"
                desc="특수 수술 신발을 착용하고 제한적 보행이 가능합니다. 물리치료를 시작하며, 발가락 운동을 점진적으로 진행합니다."
              />
              <RecoveryItem
                step="3"
                title="회복기 (6~12주)"
                desc="점차 일반 신발로 전환하며, 일상 활동을 서서히 재개합니다. 무리한 운동은 삼가고 정기 검진을 통해 회복 상태를 확인합니다."
              />
              <RecoveryItem
                step="4"
                title="완전 회복 (3~6개월)"
                desc="대부분의 일상 활동이 가능해지며, 스포츠 활동은 담당의와 상담 후 진행합니다. 편안한 신발을 선택하여 재발을 예방합니다."
              />
            </div>
          </section>

          <SectionDivider />

          {/* ── Hospital Info ── */}
          <section>
            <h2 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-3">병원 정보</h2>
            <div className="bg-gray-50 rounded-2xl border border-gray-100 p-4 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <div>
                  <p className="text-base font-extrabold text-gray-900">{caseData.doctor.hospital ?? "달려라병원"}</p>
                  <p className="text-[12px] text-gray-400">정형외과 전문</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div className="bg-white rounded-xl border border-gray-100 px-3 py-2.5">
                  <p className="text-[10px] text-gray-400">담당 원장</p>
                  <p className="text-[13px] font-bold text-gray-800 mt-0.5">{caseData.doctor.name}</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-100 px-3 py-2.5">
                  <p className="text-[10px] text-gray-400">진료일</p>
                  <p className="text-[13px] font-bold text-gray-800 mt-0.5">{createdDate}</p>
                </div>
              </div>
              <a
                href={HOSPITAL_BUNION_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between gap-3 rounded-xl bg-blue-600 px-4 py-3 text-white"
              >
                <span>
                  <span className="block text-[13px] font-bold">달려라병원 무지외반증 클리닉</span>
                  <span className="block text-[11px] text-white/75 mt-0.5">병원 홈페이지에서 자세히 보기</span>
                </span>
                <span aria-hidden className="text-lg font-bold">↗</span>
              </a>
            </div>
          </section>

          {/* ── Disclaimer ── */}
          <section className="pb-6">
            <div className="bg-gray-100 rounded-2xl px-4 py-3.5 space-y-1.5">
              <p className="text-[10px] text-gray-500 leading-relaxed text-center">
                본 보고서는 담당 의사의 전문적 판단에 기반한 수술 안내 자료입니다.
              </p>
              <p className="text-[10px] text-gray-500 leading-relaxed text-center">
                최종 수술 결정은 반드시 담당 의사와의 상담을 통해 이루어져야 하며,
                본 자료는 의료 행위를 대체하지 않습니다.
              </p>
              <p className="text-[10px] text-gray-400 text-center mt-2">
                &copy; {new Date().getFullYear()} {caseData.doctor.hospital ?? "달려라병원"} &middot; 무지외반증 수술 결정 지원 시스템
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

/* ─── small components ─── */

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded-xl border border-gray-100 px-3 py-2.5 text-center">
      <p className="text-[10px] text-gray-400 font-medium">{label}</p>
      <p className="text-[13px] font-bold text-gray-800 mt-0.5 truncate">{value}</p>
    </div>
  );
}

function RecoveryItem({ step, title, desc }: { step: string; title: string; desc: string }) {
  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span className="text-[11px] font-extrabold text-blue-600">{step}</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-bold text-gray-900">{title}</p>
        <p className="text-[12px] text-gray-500 leading-[1.7] mt-0.5">{desc}</p>
      </div>
    </div>
  );
}
