# Open Gil Claude Code Onboarding Prompt

아래 프롬프트는 처음 쓰는 사용자가 Claude Code에 그대로 붙여넣는 용도입니다.
목표는 한 번에 `open_tools` 클론, `open-gil` CLI 설치, Claude Code `/open-gil` 스킬 등록, 설정 상태 확인까지 끝내는 것입니다.

```text
open-gil을 처음 설치하고 Claude Code에서 /open-gil로 쓸 수 있게 준비해 주세요.

규칙:
- API 키를 채팅창에 요구하지 마세요.
- TMAP API 키 입력은 사용자가 Claude Code 안이 아닌 일반 터미널에서 직접 하도록 안내하세요.
- sudo, 전역 pip install, /tmp venv, shell PATH/alias/symlink 수정은 하지 마세요.
- 길찾기 실행은 하지 마세요. 설치와 설정 상태 확인까지만 하세요.

작업:
1. 사용자가 Claude Code를 연 현재 작업 폴더를 기준으로 진행하세요.
2. 현재 작업 폴더 아래 `open_tools`가 없으면 `https://github.com/doul735/open_tools.git`을 클론하고, 있으면 `git pull --ff-only`로 최신화하세요. 로컬 변경이나 충돌 때문에 최신화할 수 없으면 임의로 지우거나 덮어쓰지 말고 멈춰서 이유를 설명하세요.
3. `packages/open-gil/skills/open-gil/SKILL.md`를 읽고 설치 규칙을 따르세요.
4. `pipx`가 있으면 `pipx install open-gil` 또는 `pipx upgrade open-gil`을 사용하세요.
5. `pipx`가 없으면 `$HOME/.local/share/open-gil/venv`에 영구 venv를 만들고 `open-gil>=0.1.6`을 설치하세요. `/tmp`는 쓰지 마세요.
6. Claude Code에서 `/open-gil`이 뜨도록 아래 파일을 설치하세요. 기존 파일이 있으면 새 파일과 같은지 비교하고, 다르면 open_tools의 최신 파일로 교체하세요.
   - 원본: `./open_tools/packages/open-gil/skills/open-gil/SKILL.md`
   - 대상: `~/.claude/skills/open-gil/SKILL.md`
7. `open-gil --version` 또는 영구 venv의 전체 실행 파일 경로로 버전을 확인하세요.
8. `open-gil config show` 또는 영구 venv의 전체 실행 파일 경로로 설정 상태를 확인하세요.

완료 보고에는 아래만 포함하세요:
- 설치된 open-gil 버전
- 실행 파일 경로
- Claude Code 스킬 파일 경로
- TMAP API 키 상태: 있음/없음만, 값은 절대 출력하지 않기
- Kakao REST API 키는 선택이라는 점
- TMAP 키가 없으면 사용자가 일반 터미널에서 실행할 setup 명령

TMAP 키가 없으면 이렇게 안내하세요:
`open-gil setup`은 TMAP 키만 설정합니다. 키를 채팅창에 붙여넣지 말고 일반 터미널에서 직접 실행하세요.
영구 venv로 설치했다면 `$HOME/.local/share/open-gil/venv/bin/open-gil setup`을 실행하세요.
입력 중 글자가 화면에 보이지 않는 것은 정상입니다.

TMAP API 키 발급 안내가 필요하면 아래 공식 링크를 알려주세요:
- SK Open API: https://openapi.sk.com/
- TMAP 대중교통 이용 절차: https://transit.tmapmobility.com/guide/procedure
- TMAP 대중교통 API 문서: https://transit.tmapmobility.com/docs/routes
```

## After Setup

설치가 끝나면 Claude Code를 재시작하거나 새 세션을 열어 `/open-gil`이 보이는지 확인합니다.
그 다음부터는 터미널 명령을 직접 치기보다 Claude Code에 자연어로 요청하는 흐름이 기본입니다.

```text
/open-gil 내일 오후 1시에 올림픽홀 공연이 있는데, 송도에서 몇 시에 출발하면 돼?
```
