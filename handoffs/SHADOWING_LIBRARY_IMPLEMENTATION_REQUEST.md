# Shadowing Library 구현 시작 작업지시

## 선택 템플릿
**구현시작 역할분담**

## 0. 현재 전제
- `youtube-knowledge-agent`의 전체 V2 마이그레이션은 112/115편 완료, 3편은 기존 자산을 보존한 채 안전 종료되었다.
- 이제 다음 프로젝트인 **영어 Shadowing Library** 구현을 시작한다.
- 이 문서는 `handoffs/SHADOWING_LIBRARY_NEXT_PROJECT_DIRECTION.md`의 확정 방향을 실행 단계로 옮긴다.

## 1. 목적
기존 `english-study-site`의 Listening 콘텐츠를 그대로 보존하면서,
**토니의 지식 도서관과 거의 동일한 탐색 경험을 갖는 독립 Shadowing Library**를 만든다.

핵심 사용 장면은 다음과 같다.
1. Owner가 공개 Library에서 전체 Shadowing 콘텐츠를 한 화면에서 본다.
2. 제목/채널/화자 등으로 검색한다.
3. 채널별로 탐색한다.
4. 화자/강사 정보가 의미 있는 콘텐츠는 화자별로 탐색한다.
5. 카드를 누르면 기존의 개별 Shadowing 학습 페이지를 그대로 연다.
6. Local Admin에서 YouTube URL을 넣으면 **현재 기존 영상과 동일한 형식**의 새 Shadowing 콘텐츠를 생성한다.

## 2. 절대 보존 조건
다음은 이번 구현에서 **수정 금지**다.
- 기존 개별 영상 HTML 페이지
- 각 영상 폴더의 기존 학습 자산
  - `00_meta.txt`
  - `01_intro.txt`
  - `02_core.txt`
  - `03_summary.txt`
  - `04_full_script.txt`
  - `05_wordcard.txt`
  - `06_hangman.json`
- 기존 콘텐츠의 학습 페이지 구조와 동작

새 Library는 위 자산을 **읽고 연결하는 상위 관리/탐색 레이어**로 만든다.

## 3. UI/UX 기준
`tonykks/youtube-knowledge-agent`의 **토니의 지식 도서관**을 UX 기준으로 삼는다.

필수:
- 전체 콘텐츠
- 검색
- 채널별 보기
- 화자/강사별 보기
- 카드형 목록
- 전체 콘텐츠 수 표시
- 반응형 화면
- Local Admin / Public Read-only 분리

단, 다음은 다르게 한다.
- Shadowing 전용 색상 톤 적용
- Level별 페이지 분리 없음
- Level은 기존 메타데이터/카드 표시 정보로만 사용
- Grammar 메뉴/콘텐츠는 이번 범위에서 제외

## 4. 채널 / 화자 메타데이터 원칙
- **채널은 기본 필수값**
- **화자/강사는 선택값**

일반 영어학습 영상:
- 채널 중심으로 관리
- 화자/강사는 비워도 됨

화자가 콘텐츠 선택의 핵심인 경우:
- Steve Jobs 연설
- Barack Obama 연설
- 유명 설교자/연설자
- 기타 명확한 단독 강연자/화자

이때만 화자/강사를 저장하고 화자별 탐색에 노출한다.

기존 콘텐츠에 화자 정보가 거의 없으므로,
기존 개별 파일을 수정해서 억지로 채우지 말고 **새 Library용 index/catalog에서 필요한 범위만 파생/보완**한다.

## 5. 신규 콘텐츠 생성
Local Admin에서 YouTube URL을 입력하면,
기존 Listening 콘텐츠와 **동일한 결과 형식**으로 새 콘텐츠를 만든다.

신규 생성 결과는 기존과 동일하게:
- 영상별 폴더
- 기존 00~06 학습 자산
- 기존 형식의 개별 HTML 학습 페이지
- Library catalog/index 반영

을 수행한다.

기존 콘텐츠 생성 방식이 현재 저장소에 자동화 코드로 존재하지 않는다면,
기존 결과물 형식을 분석하여 **동일 산출물을 만드는 생성 Pipeline**을 새로 구현한다.

초기 V1은 단일 URL 입력부터 완성하고,
구조적으로 어렵지 않으면 다중 URL Batch 확장도 허용한다.

## 6. 저장소 구조
원본 `tonykks/english-study-site`는 기존 자산의 Source로 보존한다.

독립 서비스용 개발 저장소의 기본 제안:
- Private 개발 저장소: `tonykks/english-shadowing-agent`
- Public 정적 사이트 저장소: `tonykks/tony-english-shadowing`

서비스 임시명:
- **Tony's English Shadowing**

구현 중 더 적절한 이름이 필요해도 목적을 바꾸지 말고 우선 위 이름으로 진행한다.

## 7. 역할
### Geni
- 전체 현황 파악
- 구조 설계
- 구현 orchestration
- 결과 통합

### Hank / Tody
- 구조 분석 또는 코드 구현이 필요할 때 실제 Subagent로 분리 실행
- 역할이 필요하지 않으면 억지로 호출하지 않는다.

### Any
- 독립 검증
- 기존 개별 학습 페이지 무변형 확인
- 신규 1편 End-to-End 생성 확인
- Library 검색/채널/화자 탐색 확인

## 8. 구현 순서
1. 기존 Listening 자산 inventory
2. 기존 catalog와 개별 페이지 연결 구조 파악
3. Knowledge Library 구조 중 재사용 가능한 패턴 분석
4. 독립 Shadowing Library shell 구현
5. 기존 전체 콘텐츠 catalog 연결
6. 검색 / 채널별 / 화자별 탐색 구현
7. Local Admin 구현
8. 신규 YouTube URL 1편 실제 생성
9. 생성 결과가 기존 개별 콘텐츠 형식과 동일한지 검증
10. 기존 콘텐츠가 1바이트도 불필요하게 변경되지 않았는지 검증
11. 공개 배포 직전 Public checklist 작성

## 9. Public 배포 경계
외부 공개 저장소 push / GitHub Pages 배포 전에는 반드시 다음 checklist를 RESULT에 먼저 제시하고 Owner 승인 대기:
1. 공개 파일 목록
2. 제외/ignore 목록
3. credential / 개인정보 / 내부 Agent 협업자료 노출 여부
4. 공개 repo root가 실제 App 폴더인지
5. README에 제품 기능만 있고 내부 협업 구조가 없는지

Private 개발 저장소 commit/push는 승인 범위 안에서 계속 진행한다.

## 10. 성공 조건
최소 TRIAL-USABLE 기준:
- 기존 개별 학습 페이지 무변형
- 기존 전체 Listening 콘텐츠가 새 Library에서 조회 가능
- 검색 동작
- 채널별 보기 동작
- 화자 정보가 있는 경우 화자별 보기 동작
- Local Admin에서 신규 URL 1편 실제 생성 성공
- 신규 생성 페이지가 기존 형식과 동일하게 학습 가능
- 공개 배포 체크리스트 준비 완료

## 11. 결과 기록
완료 시:
- `handoffs/RESULT_20261003_SHADOWING_LIBRARY_V1.md`
- `STATE.md` 업데이트
- 관련 commit SHA
- Local 실행 방법
- 실제 신규 생성 영상 1편 Evidence
- 알려진 제한사항

을 남긴다.

중간의 사소한 기술 선택은 Owner에게 묻지 말고 승인 범위 안에서 자율 진행한다.
