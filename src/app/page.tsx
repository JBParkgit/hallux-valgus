export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 space-y-4">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto">
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">달려라병원</h1>
            <p className="text-blue-600 font-semibold mt-1">
              무지외반증 수술 안내 시스템
            </p>
          </div>
          <p className="text-gray-500 text-sm leading-relaxed">
            이 시스템은 환자별 수술 안내서를 제공하는 웹 리포트 엔드포인트입니다.
            <br />
            담당 의사로부터 전달받은 링크를 통해 안내서를 확인하세요.
          </p>
          <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">
            <p className="text-sm text-blue-700 font-medium">
              안내서 URL 형식
            </p>
            <p className="text-xs text-blue-500 mt-1 font-mono">
              /report/[고유코드]
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-400">
          Hallux Valgus Report System &copy; 달려라병원
        </p>
      </div>
    </div>
  );
}
