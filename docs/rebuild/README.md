# 최종판 복원과 소스 재빌드

Git 소스와 아래 별도 입력으로 2026-08-24 최종판을 재현합니다. 과거 게임 폴더·추출물·배포 ZIP·개인 백업은 빌드에 필요하지 않습니다.

- 지원 일본판 원본 ROM: 8,388,608바이트. SHA-256은 `INPUTS.json` 참조.
- 공용 Font 폴더의 `Galmuri11-Condensed_9x12.png`, `Galmuri11-Condensed_8x12.png`, `Galmuri7_8x8.png`. 원본 TTF만으로 동일 시트를 재생성하는 절차는 이번에 검증하지 않았으므로 이 시트 3개를 별도 보존하세요. 게임 폴더 삭제에 포함되지 않습니다.
- Python 3.11 이상과 `requirements-rebuild.txt`의 Pillow.
- 승인된 타이틀 입력 `workspace/assets/title_ko.png`는 저장소에 포함됩니다.

```powershell
python -m pip install -r requirements-rebuild.txt
python -X utf8 -B workspace/scripts/rebuild_final.py --source-rom "D:/ROM/Metroid - Zero Mission (Japan).gba" --font-dir "D:/Font" --out "build/restored_final.gba"
```

원본 SHA-256·글꼴 시트 3개·타이틀 입력 해시를 확인하고, 원본에서 381개 메시지를 추출한 뒤 승인된 127개 번역·글리프·메뉴·OBJ/BG·타이틀·지도·통신 화면을 다시 빌드합니다. 결과는 최종 릴리즈 해시와 대조합니다. 기존 출력 파일은 거부합니다.

기존 하위 스크립트를 직접 사용할 때는 `MZM_SOURCE_ROM`, `MZM_FONT_DIR` 환경 변수로 입력 위치를 지정할 수 있습니다. 새 번역 작업은 하위 `build.py`로 별도 후보를 만들고 검증하세요. `rebuild_final.py`는 고정 최종판의 동일성 검사이므로 변경된 결과를 거부합니다.

실제 소스 재빌드와 다운로드한 릴리즈의 `apply.ps1` 적용 결과가 동일했습니다. 원문 왕복·토큰·배치·번역·승인·OBJ·지도·통신 데이터 검사 8종도 통과했습니다. 새 게임 실행·화면·전체 플레이·링크 케이블 검증은 수행하지 않았습니다.
