# Shadowing Library 다음 프로젝트 방향

## 상태
- 현재 `youtube-knowledge-agent` 전체 V2 마이그레이션이 진행 중이다.
- 이 작업이 끝난 뒤 새 Shadowing Library 작업을 시작한다.
- 지금은 구현하지 않고 방향만 확정해 둔다.

## 목적
기존 `english-study-site`의 Listening 콘텐츠를 버리거나 수정하지 않고 그대로 보존하면서,
지식 도서관과 거의 동일한 사용 방식의 **독립 Shadowing Library**를 만든다.

## 핵심 원칙
1. 현재 영상별 학습 HTML과 `00_meta.txt ~ 06_hangman.json` 등 기존 콘텐츠는 손대지 않는다.
2. 새 앱은 기존 콘텐츠를 목록/검색/탐색하고, 새 YouTube URL로 동일 형식의 콘텐츠를 생성하는 관리·도서관 레이어다.
3. UI/UX는 `토니의 지식 도서관` 구조를 최대한 재사용한다.
4. 컬러 톤만 별도로 가져가 Shadowing 앱임을 구분한다.
5. 레벨별 별도 페이지는 두지 않는다. 전체 콘텐츠를 한 화면에 순서대로 보여준다.
6. 카드 안의 기존 Level 표시는 그대로 활용한다.
7. 검색 기능을 제공한다.
8. 채널별 보기를 제공한다.
9. 화자/강사 정보는 선택값이다.
   - 일반 영어학습 영상: 채널 중심 관리
   - Steve Jobs, Barack Obama, 유명 설교자 등 실제 화자가 콘텐츠 선택의 핵심일 때만 화자/강사 필드를 채운다.
10. Local Admin에서 YouTube URL을 입력하면 기존 형식의 Shadowing 콘텐츠를 자동 생성하고 목록에 추가한다.
11. Local에서는 생성/관리, Public에서는 검색/탐색/학습만 가능하게 한다.
12. 완성 후 Skyview의 Family Sites에 독립 서비스로 추가한다.
13. Grammar는 이번 Shadowing 앱 범위에서 제외한다. 추후 별도 앱 또는 지식 도서관의 언어 영역으로 다룬다.

## 권장 서비스 개념명
- 임시명: `Tony's English Shadowing`
- 최종 이름은 구현 직전 Owner와 확인 가능

## 권장 새 작업 순서
1. 기존 Listening 자산 inventory
2. 지식 도서관 UI/UX와 publication 구조 재사용 범위 확인
3. 새 Shadowing Library PROJECT_INTENT 작성
4. Local Admin + Public Library 구조 구현
5. 기존 콘텐츠 무변형 연결
6. 신규 URL 1편 실증
7. Batch 및 공개 동기화 검증
8. Family Sites 연결

## 실행 시작 조건
Owner가 현재 진행 중인 지식 도서관 전체 마이그레이션 종료를 확인하고
“Shadowing Library 시작”이라고 지시하면 이 문서를 기준으로 새 작업을 시작한다.
