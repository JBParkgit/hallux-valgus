/**
 * /guide/ — 환자용 '측정 각도 안내' 문서.
 * 수술 안내서(리포트)의 X-ray 아래 링크로 연결된다 (/guide/?r={hash} 이면 돌아가기 링크 표시).
 * 그림은 실제 X-ray가 아닌 단순화한 모식도다.
 */
import type { Metadata } from "next";
import { BackToReport } from "./BackToReport";

export const metadata: Metadata = {
  title: "무지외반증 측정 각도 안내 - 달려라병원",
  description: "X-ray에서 HVA·IMA·DMAA 각도를 재는 방법과 각 각도의 의미",
  robots: { index: false, follow: false },
};

/* ─── 모식도 ─── */

type P = [number, number];
const AXIS = "#d4a90a"; // 기준선(제1중족골 축) — 밝은 배경용 노랑
const COLOR = { HVA: "#e5484d", IMA: "#2f6fe0", DMAA: "#13a37a" } as const;

// 오른발을 위(발가락 쪽)에서 본 정면 모식도 — 엄지는 왼쪽, 바깥쪽은 오른쪽
const M1: [P, P] = [[132, 256], [109, 154]]; // 제1중족골 (아래=몸쪽, 위=발가락쪽)
const P1: [P, P] = [[106, 143], [132, 86]];  // 엄지 첫마디뼈(근위지골)
const M2: [P, P] = [[168, 262], [166, 151]]; // 제2중족골

function ext([a, b]: [P, P], k: number): [P, P] {
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy);
  return [[a[0] - (dx / L) * k, a[1] - (dy / L) * k], [b[0] + (dx / L) * k, b[1] + (dy / L) * k]];
}

function Bone({ seg, w }: { seg: [P, P]; w: number }) {
  return <line x1={seg[0][0]} y1={seg[0][1]} x2={seg[1][0]} y2={seg[1][1]} stroke="#e5e7eb" strokeWidth={w} strokeLinecap="round" />;
}

function Axis({ seg, color, dashed = false }: { seg: [P, P]; color: string; dashed?: boolean }) {
  const [a, b] = ext(seg, 18);
  return (
    <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={color} strokeWidth={3} strokeLinecap="round"
      strokeDasharray={dashed ? "5 4" : undefined} />
  );
}

/** 원위 관절면 선: 제1중족골 머리 끝을 가로지르는 짧은 선 (축의 수직에서 tilt 도 기울어짐) */
function articularLine(tilt: number): [P, P] {
  const [a, b] = M1;
  const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy);
  const ux = dx / L, uy = dy / L;
  const th = ((90 - tilt) * Math.PI) / 180;
  const vx = ux * Math.cos(th) - uy * Math.sin(th), vy = ux * Math.sin(th) + uy * Math.cos(th);
  const c: P = [b[0] + ux * 8, b[1] + uy * 8];
  return [[c[0] - vx * 22, c[1] - vy * 22], [c[0] + vx * 22, c[1] + vy * 22]];
}

function perpendicularAtHead(): [P, P] {
  return articularLine(0);
}

function FootDiagram({ show }: { show: "axis" | "HVA" | "IMA" | "DMAA" }) {
  return (
    <svg viewBox="40 30 190 245" className="w-full max-w-[220px] mx-auto block" role="img"
      aria-label={`${show} 측정 모식도`}>
      {/* 뼈 (모식) */}
      <Bone seg={M1} w={20} />
      <Bone seg={P1} w={16} />
      <Bone seg={[[134, 80], [147, 48]]} w={14} />
      <Bone seg={M2} w={14} />
      <Bone seg={[[166, 140], [165, 92]]} w={11} />
      <Bone seg={[[198, 262], [204, 160]]} w={12} />

      {/* 기준선은 모든 그림에 */}
      <Axis seg={M1} color={AXIS} />
      {show === "HVA" && <Axis seg={P1} color={COLOR.HVA} />}
      {show === "IMA" && <Axis seg={M2} color={COLOR.IMA} />}
      {show === "DMAA" && (
        <>
          <Axis seg={perpendicularAtHead()} color="#9ca3af" dashed />
          <Axis seg={articularLine(14)} color={COLOR.DMAA} />
        </>
      )}
    </svg>
  );
}

/* ─── 문서 ─── */

function AngleSection({
  id, abbr, name, color, how, meaning, normal, show,
}: {
  id: string; abbr: string; name: string; color: string;
  how: React.ReactNode; meaning: React.ReactNode; normal: string;
  show: "HVA" | "IMA" | "DMAA";
}) {
  return (
    <section id={id} className="scroll-mt-4">
      <div className="flex items-baseline gap-2">
        <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
        <h2 className="text-lg font-extrabold text-gray-900">{abbr}</h2>
        <span className="text-sm font-semibold text-gray-500">{name}</span>
      </div>
      <div className="mt-3 grid grid-cols-[1fr] gap-3">
        <div className="bg-gray-50 border border-gray-100 rounded-2xl p-3">
          <FootDiagram show={show} />
        </div>
        <div>
          <h3 className="text-[13px] font-bold text-gray-800">어떻게 재나요?</h3>
          <div className="text-[13px] text-gray-600 leading-relaxed mt-1">{how}</div>
        </div>
        <div>
          <h3 className="text-[13px] font-bold text-gray-800">무엇을 뜻하나요?</h3>
          <div className="text-[13px] text-gray-600 leading-relaxed mt-1">{meaning}</div>
        </div>
        <p className="text-[12px] text-gray-500 bg-gray-50 rounded-xl px-3 py-2">
          일반적인 정상 범위: <b className="text-gray-700">{normal}</b>
        </p>
      </div>
    </section>
  );
}

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <article className="max-w-[480px] mx-auto bg-white min-h-screen shadow-xl">
        <header className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white px-5 pt-6 pb-5">
          <p className="text-white/70 text-[12px] font-medium">달려라병원 · 무지외반증 수술 안내서</p>
          <h1 className="text-xl font-extrabold mt-1">측정 각도 안내</h1>
          <p className="text-white/70 text-[12px] mt-1.5 leading-relaxed">
            수술 안내서에 나온 HVA·IMA·DMAA 각도를
            <br />
            어떻게 재고, 무엇을 뜻하는지 정리했습니다.
          </p>
          <BackToReport className="inline-block mt-3 text-[12px] font-semibold text-white bg-white/15 rounded-full px-3 py-1" />
        </header>

        <div className="px-5 py-6 space-y-9">
          <section>
            <h2 className="text-base font-extrabold text-gray-900">각도는 이렇게 잽니다</h2>
            <p className="text-[13px] text-gray-600 leading-relaxed mt-2">
              발 X-ray(정면 사진) 위에 뼈의 방향을 따라 <b>선</b>을 긋고, 두 선 사이의 <b>각도</b>를 잽니다.
              모든 각도는 <b style={{ color: AXIS }}>제1중족골 축</b>(엄지발가락 뒤쪽의 긴 뼈를 따라 그은 선)을
              기준선으로 삼습니다.
            </p>
            <div className="mt-3 bg-gray-50 border border-gray-100 rounded-2xl p-3">
              <FootDiagram show="axis" />
              <p className="text-[11px] text-gray-400 text-center mt-1">
                오른발 모식도 · 노란 선이 기준선(제1중족골 축) · 실제 X-ray가 아닌 그림입니다
              </p>
            </div>
            <nav className="mt-3 flex gap-2 text-[12px] font-semibold">
              {(["HVA", "IMA", "DMAA"] as const).map((k) => (
                <a key={k} href={`#${k.toLowerCase()}`} className="flex-1 text-center rounded-xl border border-gray-200 py-2 text-gray-700">
                  <span className="inline-block w-2 h-2 rounded-full mr-1 align-middle" style={{ backgroundColor: COLOR[k] }} />
                  {k}
                </a>
              ))}
            </nav>
          </section>

          <AngleSection
            id="hva" abbr="HVA" name="무지외반각 (Hallux Valgus Angle)" color={COLOR.HVA} show="HVA"
            how={<>기준선(제1중족골 축)과 <b>엄지발가락 첫마디뼈(근위지골)의 축</b> 사이의 각도입니다.</>}
            meaning={<>엄지발가락이 바깥쪽(둘째발가락 쪽)으로 <b>얼마나 휘었는지</b>를 나타냅니다.
              무지외반증의 정도를 볼 때 가장 기본이 되는 각도로, 클수록 엄지가 많이 휘어 있다는 뜻입니다.</>}
            normal="15° 미만"
          />

          <AngleSection
            id="ima" abbr="IMA" name="중족골간각 (Intermetatarsal Angle)" color={COLOR.IMA} show="IMA"
            how={<>기준선(제1중족골 축)과 <b>둘째 중족골의 축</b> 사이의 각도입니다.</>}
            meaning={<>엄지 쪽 중족골이 둘째 중족골에서 <b>얼마나 벌어졌는지</b>를 나타냅니다.
              이 각도가 크면 엄지 뿌리 쪽 뼈 자체가 안쪽으로 벌어져 있다는 뜻이어서,
              어느 부위의 뼈를 교정할지 정하는 데 중요한 기준이 됩니다.</>}
            normal="9° 미만"
          />

          <AngleSection
            id="dmaa" abbr="DMAA" name="원위 중족골 관절면각 (Distal Metatarsal Articular Angle)" color={COLOR.DMAA} show="DMAA"
            how={<>제1중족골 머리 끝의 <b>관절면 양 끝을 잇는 선</b>을 긋고, 이 선이 기준선에 수직인 선(회색 점선)에서
              얼마나 기울었는지를 잽니다. 관절면이 기준선과 정확히 직각이면 0°입니다.</>}
            meaning={<>엄지발가락과 맞닿는 <b>관절면이 얼마나 기울어 있는지</b>를 나타냅니다.
              관절면 자체가 기울어 있으면 뼈의 위치만 옮겨서는 교정이 부족할 수 있어,
              수술 방법을 고를 때 함께 살펴봅니다.</>}
            normal="10° 미만"
          />

          <section className="space-y-3">
            <h2 className="text-base font-extrabold text-gray-900">알아 두시면 좋은 점</h2>
            <ul className="text-[13px] text-gray-600 leading-relaxed space-y-2 list-disc pl-5">
              <li>
                중증도(경증·중등도·중증)는 주로 <b>HVA와 IMA</b>로 나눕니다. 나누는 기준은 의료기관과 문헌마다 조금씩 다를 수 있습니다.
              </li>
              <li>
                각도는 X-ray 위에 손으로 선을 그어 재기 때문에, 촬영 자세나 측정하는 사람에 따라 <b>몇 도 정도 차이</b>가 날 수 있습니다.
              </li>
              <li>
                수술 방법은 각도만으로 정하지 않습니다. 통증, 관절 상태(관절염 등), 발의 유연성, 생활 습관을 함께 보고
                담당 의사가 결정합니다.
              </li>
              <li>
                안내서의 그림과 설명은 이해를 돕기 위한 것입니다. 궁금한 점은 진료 때 담당 의사에게 물어봐 주세요.
              </li>
            </ul>
          </section>

          <footer className="text-center text-[12px] text-gray-400 pt-2 pb-4 space-y-2">
            <BackToReport className="inline-block text-[13px] font-semibold text-blue-600" />
            <p>달려라병원 · 문의 1600-7511</p>
          </footer>
        </div>
      </article>
    </div>
  );
}
