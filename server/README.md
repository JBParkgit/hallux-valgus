# 무지외반증 측정기 서버 (Vultr)

측정기(데스크톱)는 DB에 직접 붙지 않고 이 서버 API(`/api/hv/*`)만 사용한다.

- 모든 의료진: 모든 케이스 **조회** 가능
- 작성자 본인만: **수정·삭제·X-ray 저장·알림톡 발송** (서버에서 강제)
- X-ray 원본: 서버 `/var/lib/hv-server/xray`
- 알림톡: 서버 → 기존 중계 서버(203.245.41.19:5003) → 비즈톡 (비즈톡 형식 payload)
- 의사별 알고리즘 설정: 서버 DB (어느 PC에서든 동일)

## 1. 서버 만들기 (최초 1회)

1. Vultr에서 **Seoul / Ubuntu 24.04 / vc2-1c-1gb** 서버 생성 + 자동 백업 (월 약 $6). 사용량이 늘면 Vultr에서 사양만 올리면 된다
2. 도메인 A 레코드를 서버 IP로 연결 (예: `hv.hospitalrun.co.kr`)
3. PC에서:
   ```
   ssh root@<서버IP> "mkdir -p /root/hv-src"
   scp -r server/hv_server server/deploy server/manage.py server/requirements.txt server/.env.example root@<서버IP>:/root/hv-src/
   ssh root@<서버IP> "bash /root/hv-src/deploy/setup.sh hv.hospitalrun.co.kr"   # 이메일은 선택 (인증서 만료 알림용)
   ```
   PostgreSQL·nginx·https(무료 인증서)·방화벽·매일 백업까지 설정된다.
4. 서버의 `/opt/hv-server/.env` 에 알림톡 값 입력 후 `systemctl restart hv-server`
   - `ALIMTALK_SENDER_KEY` : 비즈톡 발신 프로필 키 (이미지 캡처 프로그램과 동일)
   - `ALIMTALK_TEMPLATE_CODE` : **카카오 승인받은** 수술 안내서 템플릿 코드
   - 템플릿 본문은 `hv_server/alimtalk.py` 의 `build_message()` 와 **글자 하나까지 같아야** 한다

## 2. 의사 계정

```
cd /opt/hv-server
sudo -u hv .venv/bin/python manage.py add-doctor kim 김철수       # 비밀번호 입력
sudo -u hv .venv/bin/python manage.py reset-password kim
sudo -u hv .venv/bin/python manage.py set-active kim off          # 퇴사 등 (즉시 로그아웃)
sudo -u hv .venv/bin/python manage.py list-doctors
```

## 3. 측정기 PC 설정

실행 파일 옆 `.env` 에 **서버 주소만** 둔다 (DB 비밀번호 불필요):

```
HV_API_URL=https://hv.hospitalrun.co.kr
```

## 4. 업데이트 배포

```
scp -r server/hv_server root@<서버IP>:/opt/hv-server/
ssh root@<서버IP> "systemctl restart hv-server"
```

## 4-1. 환자 리포트 사이트 (`/report/{hash}`)

알림톡 '수술 안내서 보기' 버튼이 여는 페이지. 저장소 루트의 Next.js 앱을 **정적 파일**로 빌드해
이 서버의 nginx가 내보낸다 (Node 실행 불필요). 페이지는 같은 도메인의 `/api/hv/report/{hash}` 를 읽는다.

```
# PC (저장소 루트)
npm run build                                   # → out/
ssh root@<서버IP> "rm -rf /root/hv-src/report-site"
scp -r out root@<서버IP>:/root/hv-src/report-site
scp server/deploy/nginx-hv-report.conf server/deploy/enable-report.sh root@<서버IP>:/root/hv-src/deploy/

# 서버 — 최초 1회는 nginx 설정·REPORT_BASE_URL 까지 바꾸고, 이후에는 파일만 교체된다
ssh root@<서버IP> "bash /root/hv-src/deploy/enable-report.sh /root/hv-src/report-site"
```

- 리포트 주소: `https://hv.hospitalrun.co.kr/report/{hash}` (서버 `.env` 의 `REPORT_BASE_URL`)
- 측정 각도 안내 문서: `https://hv.hospitalrun.co.kr/guide/` — 리포트의 '각도는 어떻게 재나요?' 링크 (`src/app/guide/page.tsx`)
- 화면만 고친 경우에도 위 순서 그대로 (빌드 → 올리기 → `enable-report.sh`)
- 개발: `npm run dev` 후 `http://localhost:3000/report/{hash}` — `/api/hv/*` 는 `.env` 의 `HV_API_URL` 서버로 전달된다

## 5. 백업/복구

- 매일 03:30 `/var/backups/hv` 에 DB 덤프 (14일 보관). X-ray는 Vultr 자동 백업(디스크 전체)으로 보호
- 복구: `sudo -u postgres pg_restore -d hv --clean <파일>.dump`

## 로컬 테스트

```
docker run -d --name hv-pg -e POSTGRES_USER=hv -e POSTGRES_PASSWORD=test -e POSTGRES_DB=hv -p 127.0.0.1:55432:5432 postgres:16-alpine
cd server && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
set DATABASE_URL=postgresql://hv:test@127.0.0.1:55432/hv
.venv\Scripts\python manage.py init-db
.venv\Scripts\python manage.py add-doctor kim 김의사
.venv\Scripts\uvicorn hv_server.main:app --port 8765
```
측정기 `.env`: `HV_API_URL=http://127.0.0.1:8765`
