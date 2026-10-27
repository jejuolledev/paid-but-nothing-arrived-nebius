세 기능 모두 반영했고, `.venv/bin/python -m pytest -q` 기준 **10 passed**입니다.

1. **승인 후 실제 수정** (`agent/actions.py` + `POST /api/approve`)
   - DuckDB: CSV를 쓰기 가능한 TABLE로 로드, `execute()`, `actions` 감사 테이블
   - Zetaris 등 `execute` 없는 백엔드 → **409** + 지정 문구
   - `broken`별 수정 → 재조사 → `{applied, audit, after}` 반환
   - `revoked` 중복은 기존처럼 `granted`만 집계

2. **한국어 고객 답장**
   - Hangul → `lang=ko`, 프롬프트에 존댓말 지시, 한국어 템플릿 + `_reply_ok` 키워드 확장

3. **UI**
   - Approve fix 버튼, 감사 메모, Nightshift receipt 줄, 타임라인 모델 표시, EN/KO 문자열이전에 돌린 pytest는 한국어 답장 테스트가 로컬 LLM에 붙어 `llm == "none"` 단언이 깨진 것이었고, 그 부분은 이미 고쳤습니다. 지금은 **10 passed**입니다.
