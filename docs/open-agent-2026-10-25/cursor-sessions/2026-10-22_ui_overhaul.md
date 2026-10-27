`app/index.html`만 수정했습니다. Python은 건드리지 않았습니다.

적용된 내용:
- **EN/한국어** 토글(기본 EN, `localStorage` try/catch) — UI 문구만 번역, 데이터·모델 텍스트는 그대로
- 부제·스폰서 분리, **Try an example message** + 고객 말투 버튼(케이스 6은 이메일만 전송)
- 결과 순서: 답장/고칠 것 → Investigation(있으면) → 체인 → Why → Verified → Evidence/Trace(`<details>`, 기본 닫힘)
- `pre` 줄바꿈, 390px에서 가로 스크롤 방지, 인용/체인 클릭 시 slug id + flash 1.5s
- fetch try/catch, 빈 입력 힌트, Enter 조사, 체인 `tabindex=0`, 상태줄 평문

검증: `innerHTML` 템플릿의 동적 값은 모두 `esc()`(또는 esc로 만든 조각) 경유. `CSS.escape` 제거됨.
