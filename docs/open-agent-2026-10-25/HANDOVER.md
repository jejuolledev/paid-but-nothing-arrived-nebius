# 인수인계 — Open Agent Hackathon 「Paid, but nothing arrived」 (2026-10-22, Fable 세션 작성)

이 파일은 다음 세션(Opus/Fable 누구든)이 바로 이어 하기 위한 것. 영어 제출물(README·슬라이드·영상 자막)은 이 저장소 안에, 한국어 메모는 여기에만.

## 0. 지금 상태 (10/22 오전 갱신 — 아래 시각은 대략치)
- GitHub 비공개 저장소 생성·푸시됨: https://github.com/jejuolledev/paid-but-nothing-arrived (제출 전에 `gh repo edit --visibility public --accept-visibility-change-consequences`).
- 데모 **Zetaris 백엔드 판** 녹화 완료(10/22 오전): `docs/demo/walkthrough_zetaris.mp4`(2분 10초, 화면에 「backend zetaris-jdbc · model none」), 캡처 case-1~6, captions.srt. Nightshift/Nemotron 붙인 뒤 한 번 더 찍으면 model 칸이 채워짐(`rm -rf docs/demo && node scripts/record_demo.mjs && ffmpeg …`). 제출 폼 값은 `docs/submission_form.md`.
- (이전) 데모 초안: `scripts/record_demo.mjs`(Playwright headless, 1280×720, 자막 배너 주입) → `docs/demo/walkthrough_draft.mp4`(53초, DuckDB 백엔드·모델 없음 상태) + `case-1~6.png` + `captions.srt`. Zetaris·Nightshift 붙인 뒤 **같은 스크립트로 다시 찍으면** 화면 상단 「backend zetaris-jdbc · model …」이 찍힌 최종본이 됨. 규정 1~4분이라 앞뒤에 문제 설명 15초·구조 한 장 15초를 더해 2분 안팎으로(ffmpeg concat 또는 recorder에 단계 추가).
- Zetaris 로컬 스택 `docker compose up -d` 완료(가동 중)(에뮬레이션이라 느림) → 로그 scratchpad/zetaris_up.log, 확인 `docker compose ps`·`./verify.sh`. 그 뒤 순서: `zetaris/load_postgres.sh`(POSTGRES_PASSWORD는 번들 `.env`에서) → `.env.local`에 JDBC 값 → `.venv/bin/python zetaris/run_sql.py`(한 문장씩 실행, 오류는 출력만) → `ZETARIS_SCHEMA=lightning.metastore.demo.order_journey`로 `pytest`.
- Nemotron 로컬 시험: rapid-mlx 모델 다운로드 완료(16.6GB). 영상 세션(llm-de)이 `…/video-kit/output/logs/slot_open` 파일로 10분 창을 열어 주면 `scratchpad/nemotron_slot.sh`(백그라운드 감시 중)가 포트 8197에 띄워 `scripts/llm_smoke.py` 실행 → 결과 `docs/nemotron_slot_run.log`·`docs/measurements.md`. 이 수치가 「citation check 통과율·지연」 근거.
- **hackathon.genai.works 로그인은 안 했음**: 사이트는 「Sign in」 상태(쿠키 없음). Google 로그인 버튼을 누르면 계정 선택 창까지 감. 10/18 가입이 Google 로그인이었는지 이메일+비밀번호였는지 기록이 없어, 다른 방식으로 로그인하면 **계정이 둘이 되어 실격(규정 1절)** 위험 → 대표가 직접 로그인. 로그인 뒤 작업 공간의 제출 폼 칸(영상 링크·저장소·슬라이드·설명문·pre-existing·트랙 선택)을 확인해 `docs/submission_form.md`에 적을 것.

- 저장소 `/Users/ollekil/Desktop/Moahub-Labs/hackathons/paid-but-nothing-arrived` — 첫 커밋 10/22 10:04 KST(빌드 윈도 10/22 09:00 KST 이후 ✔). `.venv`(Python 3.12, uv).
- 돌아가는 것: `python data/gen_synthetic.py`(합성 데이터 4원천+5사례) → `pytest`(3 passed: 5사례 모두 정답 고리) → `uvicorn app.main:app --port 8765` → http://127.0.0.1:8765 (돈의 사슬 화면, 원본 행, 답장·조치·증거 묶음).
- 지금은 Zetaris 없이 DuckDB(`agent/sql_backend.py`)로, LLM 없이 verifier 문장으로 돈다. 화면·결과에 `backend`·`llm`이 그대로 찍힘(속이지 않음).

## 1. 후원사 필수 연동 — 진행 상황
### Zetaris (필수) — ✅ 10/22 오전 연동 완료
- 로컬 스택 가동 중(`docker compose ps` 전부 healthy, bootstrap만 one-shot), JDBC `SELECT 1` 4.8s. 합성 CSV 5개를 번들 Postgres `demo` DB에 적재(`zetaris/load_postgres.sh`), `zetaris/register.sql`로 데이터소스 `demo_pg` + 네임스페이스 `lightning.metastore.demo` + USL `order_journey` 등록·활성화 완료(`zetaris/run_sql.py`). 조인 스모크 쿼리 OK.
- 에이전트 5사례 pytest **zetaris-jdbc 백엔드로 5/5 통과**(1사례 약 9초 — 에뮬레이션 Spark). `.env.local` 작성됨(비밀번호는 번들 `.env`에서; 커밋 제외).
- Lightning DDL이 거부한 것: 설명문에 공백/콜론, 열 이름 `to`(백틱도 안 됨)·`tag` → `to_address`·`order_tag`로 전부 개명(생성기·CSV·Postgres·tools·DuckDB 뷰). `SHOW NAMESPACES`는 비활성(`SHOW NAMESPACES IN …` 아님, 그냥 못 씀).
- 맥 재부팅되면 `colima start`(설정 유지) → `cd hackathons/zetaris-platform && docker compose up -d && ./verify.sh` → USL·데이터는 볼륨에 남아 있음(사라지면 load_postgres.sh·run_sql.py 다시).
- (아래는 연동 전 메모)
- 공용 서버 없음 → **로컬 Docker판**. Zetaris Cloud 계정 로그인 완료(jejuolleapps, OTP는 Gmail /u/1). 대시보드 「Run locally」 안내 그대로 진행.
- 번들: `/Users/ollekil/Desktop/Moahub-Labs/hackathons/zetaris-platform/` (zip은 같은 폴더). `./preflight.sh` 전부 PASS(docker=colima vz+rosetta, compose 플러그인 설치함, 레지스트리 `zetarishackathon.azurecr.io` 로그인 완료 — 로그인 명령은 개인용, 저장소·문서에 적지 않음. 스크래치 `zetaris_login_cmd.txt`에만).
- `docker compose pull` 백그라운드 진행 중(약 4GB, 로그 scratchpad/zetaris_pull.log). 끝나면: `docker compose up -d` → `./verify.sh` → UI http://localhost:3000 (admin@zetaris.com / 초기 비밀번호는 대시보드 7단계에 표시, 첫 로그인 후 바꿀 것) → JDBC `jdbc:zetaris:lightning@localhost:10000`, 드라이버 `jdbc/ndp-jdbc-driver-2.4.3.1-7eff043-driver.jar`, 클래스 `com.zetaris.lightning.jdbc.LightningDriver`, Java는 `/opt/homebrew/opt/openjdk@21`.
- 다음 할 일(Z-1~Z-4):
  1. Python에서 JDBC: `uv pip install jaydebeapi jpype1` → `agent/sql_backend.py`에 `ZetarisJDBCBackend` 추가(`SELECT 1` 통과). REST 백엔드 뼈대는 이미 있으나 실제 API 경로는 미확인 — JDBC가 공식 안내라 JDBC 우선.
  2. 원천 등록: 로컬 Docker판은 파일을 S3 경로로만 읽음(문서 「Zetaris cannot read this local cache by a documented PATH」). 번들 안 Postgres(`zetaris-postgres-1`)에 합성 CSV 5개를 적재해 `CREATE DATASOURCE`(JDBC postgres)로 등록하는 게 가장 빠름. 안 되면 MinIO 컨테이너 하나 띄워 s3a 경로. SQL 파일은 `zetaris/register.sql`로 저장소에 둔다.
  3. USL `order_journey`(orders ↔ payments ↔ grants ↔ server_logs ↔ mail_events, 키 order_id/payment_id/email) — `COMPILE USL` / `ACTIVATE USL TABLE`.
  4. `.env.local`에 접속값 → 5사례 pytest가 Zetaris 백엔드로도 5/5 통과하면 끝. 화면 `backend: zetaris` 캡처를 영상에.
### Meterless Nightshift (필수)
- 앱 설치함: `/Applications/Nightshift M1-M4.app`(0.92.1, quarantine 해제). **아직 실행 안 함**(GUI 앱, 대표 규칙상 창 띄우지 않음 — 대표가 돌아오면 한 번 열어 「hotspot on」). Tauri 앱 안에 OpenAI 호환 런타임(`/v1/chat/completions`, `/v1/models`, `/v1/explain/`, 헤더 `meterless-mode`·`meterless-trace`·`meterless-deliberation`, 모델 별칭 `meterless/local`·`meterless/auto`·`meterless/fast`·`meterless/deep`, 포트 env `NS_MAC_RUNTIME_PORT`). 실행 후 `connect.html`/설정 화면에서 주소·키 확인 → `.env.local`의 `NIGHTSHIFT_BASE_URL`·`NIGHTSHIFT_API_KEY`.
- 로컬 Nemotron: Nightshift 모델 목록에 「Nemotron 3.5 Lightning · local or cloud」 있음. 별도로 rapid-mlx `nemotron-3.5-lightning-30b-4bit`(16.6GB) 다운로드 중(scratchpad/nemotron_pull.log) — Nightshift가 자체 다운로드하면 이건 예비(서버 둘 동시에 띄우지 말 것: 영상 세션 edit 서버가 99GB 씀).
- 설치 dmg: `/Users/ollekil/Desktop/Moahub-Labs/hackathons/Nightshift-M1-M4-0.92.1-macos-arm64.dmg`(마운트 /tmp/ns_inner, /tmp/ns_mount — 끝나면 `hdiutil detach`).
- 연동 뒤 할 일(M-1~M-3): `investigator.py`의 설명 단계를 Nightshift로 호출 → `meterless-trace` 응답을 받아 화면 「확인한 것/확인 못 한 것」 옆에 「Nightshift 검사 기록」으로 표시 → `/v1/explain/` 쓸 수 있으면 인용 검사에 활용.
### Cursor (필수)
- `cursor-agent` CLI 설치됨(`~/.local/bin/cursor-agent`, 2026.10.19). **로그인 안 됨** → 대표가 `cursor-agent login`(브라우저) 한 번. Cursor.app(3.25.9)도 미로그인.
- 로그인 뒤: 남은 작업(JDBC 백엔드·Nightshift 연동·README 다듬기)을 `cursor-agent -p "<지시>"`로 시켜 커밋 메시지 끝에 `[cursor-agent]` 표시, 대화 기록을 `docs/cursor-sessions/`에 저장. 설명문의 「How Cursor was used」 근거.
- 규칙 파일 `.cursor/rules/project.mdc` 있음.
### NVIDIA (특별상) — 로컬 Nemotron 1차 측정 완료(10:37)
- rapid-mlx `nemotron-3.5-lightning-30b-4bit`(포트 8197, 영상 세션 slot 안에서 2분): **판정 5/5(verifier), 모델 응답 평균 12.9초, 인용 검사 1/5 통과** — 모델이 `[ref: orders:…]`·맨몸 ref로 써서 파서가 못 잡은 것. 파서·프롬프트 고침(커밋 「Citation check accepts…」). **2차 측정 완료(10:48): 판정 5/5 · 인용 검사 5/5 · 평균 14.0초** → README 「Measured」·슬라이드 8장에 반영함. 고객 답장이 사례 3·5에서 고객 말투로 새는 문제 → 프롬프트 보강 + 답장 검사(어긋나면 템플릿으로 교체, `citation_check.reply_replaced`) 추가. 감시 스크립트는 종료됨(다시 쓰려면 scratchpad/nemotron_slot.sh).
- Nightshift가 켜지면 `.env.local`에 `NIGHTSHIFT_BASE_URL=http://127.0.0.1:8088/v1`, `NIGHTSHIFT_API_KEY=rt-local`, `LLM_MODEL=meterless/local`(또는 Nightshift 모델 목록의 Nemotron 이름)로 바꾸고 같은 smoke 스크립트 → 이게 제출 기준 수치(Meterless 필수 연동).
- 모델: Nemotron 3.5 Lightning(로컬) — Nightshift 또는 rapid-mlx. 클라우드 예비: OpenRouter `nvidia/nemotron-3.5-lightning:free`(키 없음, 대표 가입 필요 — 없어도 됨).

## 2. 남은 제출물 (규정 6절) — 10/22 오전 현재 초안 전부 있음
- ✅ 영상 `docs/demo/final.mp4` 2분 40초(제목 카드 14초 + Zetaris 백엔드 워크스루 2분 10초 + 구조 카드 16초, 무음·자막 배너). 만드는 법: `node scripts/record_demo.mjs && bash scripts/build_video.sh`. Nightshift 연동 후 한 번 더 돌리면 「model …」 칸이 채워진 최종본.
- ✅ 슬라이드 `docs/slides.pdf`(marp, 10장) ← `docs/slides.md`. 제품 화면 장에는 `docs/demo/case-*.png`를 넣으면 더 좋음(지금은 글만).
- ✅ 저장소(비공개) + README · ✅ `docs/sponsor-tech.md` · ✅ `docs/submission_form.md`(폼에 붙일 값).
- ⏳ 남은 것: Nightshift 연동(대표가 앱 켜면) → `.env.local` NIGHTSHIFT_* → `scripts/llm_smoke.py`로 수치 → 영상·README 「model」 반영 / Cursor 로그인 뒤 cursor-agent로 마무리 작업 1~2건 + `docs/cursor-sessions/` / 유튜브 업로드(대표) / 저장소 공개 전환 / 폼 제출.

1. 데모 영상 1~4분(영어 자막) — 대본 뼈대: `지원사업제출/0_해커톤_안낸것/01 Open Agent…/문서_md/11_착수계획_6일.md` 5절. 화면 녹화는 headless(playwright) 캡처 또는 QuickTime(대표).
2. 슬라이드 10장 — 같은 문서 6절 목차. `docs/slides.md` → PDF.
3. GitHub 공개 저장소 + README(설치·사용·의존성·합성 데이터 선언·후원사 기술·pre-existing 없음) — `gh repo create` 계정 jejuolledev.
4. 설명문(Zetaris·Meterless·Cursor·NVIDIA·독특한 점) — `docs/sponsor-tech.md`.
- 제출 폼은 hackathon.genai.works 작업 공간. 목표 제출 10/27 14:00 KST(동점 때 제출 시각). 대표 10/23~27 부재 → **10/22 밤 또는 10/28 아침(마감 08:45 KST) 둘 중 하나**. 현실적으로 10/22 밤 「동작하는 판」을 내고 10/28 아침 보완본 재제출 가능 여부는 작업 공간에서 확인.

## 3. 사실 규칙(서류에 쓸 때)
- 사례 5개 = 「우리 결제 점검에서 찾은 결함, 그중 2개는 실제 결제에서 발생」. 「real incidents」 금지. 매출·건수 숫자 금지. 동화모아 코드 0줄(pre-existing 없음).
- 대표가 정한 것 먼저, AI가 한 것 뒤에. 모든 데이터 합성(@example.com, 테스트 카드 끝자리).
