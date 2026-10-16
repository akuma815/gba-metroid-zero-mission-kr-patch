# Metroid: Zero Mission GBA 한국어화

일본판 Game Boy Advance ROM을 기준으로 시작한 한국어화 프로젝트다. 현재는 원본 식별과 작업 폴더 구성만 완료됐으며, 텍스트·폰트·압축·렌더러 구조는 아직 조사하지 않았다.

## 기준 입력

- ROM: `original/Metroid - Zero Mission (Japan).gba`
- 플랫폼/리전: Game Boy Advance / Japan
- 게임 코드: `BMXJ`
- 상세 식별 정보: [`workspace/config/source_rom.json`](workspace/config/source_rom.json)

원본 ROM은 수정하지 않는다. 모든 추출·분석·빌드는 원본을 읽기 전용 기준 입력으로 사용하고 새 경로에 결과를 만든다.

## 폴더 역할

```text
Metroid - Zero Mission/
├─ original/                 사용자 제공 원본 ROM
├─ extracted/                원본에서 재생성 가능한 추출 데이터
├─ workspace/
│  ├─ analysis/              ROM·텍스트·렌더러 조사 결과
│  ├─ config/                원본 식별자와 추후 빌드 설정
│  ├─ font/                  한글 폰트 소스·변환 사양·생성 글리프
│  ├─ text/
│  │  ├─ source/             가역 추출 원문
│  │  └─ translation/        한국어 번역 원장
│  ├─ asm/                   ARM/Thumb 훅·패치 소스
│  ├─ graphics/              번역용 그래픽 소스
│  ├─ scripts/               추출·삽입·빌드 도구
│  └─ tests/                 라운드트립·회귀 테스트
├─ work/                     일회성 조사·실험 공간
├─ build/                    재현 가능한 개발 빌드 산출물
├─ dist/                     배포용 패치·설명서·해시
├─ backups/                  로컬 백업
├─ qa/                       스크린샷·세이브·실행 로그
├─ tools/                    로컬 외부 도구
└─ docs/                     조사 기록과 인수인계 문서
```

## 작업 규칙

1. 원본 ROM과 이전 검증 산출물을 덮어쓰지 않는다.
2. 반복 작업은 `workspace/scripts`의 단일 빌드 경로로 승격한다.
3. ROM 변경은 대상 리비전 확인과 Expected Write 검증을 거친다.
4. 정적·빌드 검증과 에뮬레이터 실행 검증을 구분해 기록한다.
5. 작업 종료 시 최신 `docs/HANDOFF_*.md`에 변경 파일, 검증 결과, 미해결 항목, 재현 명령과 다음 단계를 반영한다.

현재 상태는 [`docs/HANDOFF_2026-08-17.md`](docs/HANDOFF_2026-08-17.md)를 기준으로 한다.
