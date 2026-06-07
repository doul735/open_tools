# open-gil

TMAP API로 계산하고, LLM이 지어내지 못하게 막는 대중교통 출발시간 CLI.

`open-gil`은 “몇 시에 출발해야 하지?”라는 질문에 대해 출발지, 목적지, 일정 시각을 받아 대중교통 경로와 추천 출발 시간을 계산합니다. Codex, Claude Code 같은 LLM은 자연어를 구조화하고 확인 질문을 하는 데만 쓰고, 출발시각, 환승, 소요시간, 도착시각은 TMAP 대중교통 API 응답으로만 만듭니다.

초기 MVP 범위는 서울, 경기, 인천입니다.

## Why

LLM은 길찾기 질문에 그럴듯한 답을 만들 수 있지만, 실제 대중교통 시간표와 환승 경로를 보장하지 못합니다. `open-gil`은 이 부분을 분리합니다.

- LLM: “사용자가 말한 시간이 일정 시작인지, 도착 마감인지, 출발 시간인지” 확인
- CLI: 장소 검색, 좌표 확정, TMAP 경로 조회, 출발시각 계산
- 사용자: 네이버지도와 카카오맵 링크로 최종 확인

핵심 원칙은 단순합니다. 모르면 추측하지 않고, API가 준 것만 말합니다.

개발 과정, 시행착오, 현재 한계, 다음 개선 방향은 [open-gil Development Story](https://github.com/doul735/open_tools/blob/main/docs/open-gil-development-story.md)에 정리되어 있습니다.

## Quick Start

Install from PyPI:

```bash
pipx install open-gil
open-gil --version
```

If `pipx` is not installed and you do not want to change your system setup, use a persistent venv under your home directory:

```bash
python3 -m venv "$HOME/.local/share/open-gil/venv"
"$HOME/.local/share/open-gil/venv/bin/python" -m pip install --upgrade pip
"$HOME/.local/share/open-gil/venv/bin/python" -m pip install --upgrade "open-gil>=0.1.4"
"$HOME/.local/share/open-gil/venv/bin/open-gil" --version
```

Avoid using `/tmp` for recurring use because macOS and other systems may clean it.

Or install directly from the repository:

```bash
pipx install "git+https://github.com/doul735/open_tools.git#subdirectory=packages/open-gil"
```

Configure your TMAP key:

```bash
open-gil config show
```

```bash
open-gil setup
```

그 다음 바로 물어볼 수 있습니다.

```bash
open-gil plan \
  --origin "송도달빛축제공원역" \
  --destination "올림픽공원 올림픽홀" \
  --event-at "2026-06-06 13:00"
```

`--event-at`은 일정 시작 시각입니다. open-gil은 기본적으로 15분 전 도착을 목표로 출발시각을 추천합니다.

## What You Get

하루 10회 수준의 낮은 API 호출 제한을 고려해, 기본 모드는 TMAP 경로 조회 1회로 총 소요시간을 받아 목표 도착시각에서 출발시각을 역산합니다.

이 방식은 API 호출을 아끼지만, “가장 늦은 출발”과 “이전/다음 수단”을 전수 검증하지는 않습니다. TMAP에 도착시각 기준 검색이 별도로 제공되지 않는 한, 그 기능은 여러 출발시각을 반복 조회해야 하므로 기본 MVP에서는 실행하지 않습니다.

예시 출력은 이런 형태입니다.

```text
송도달빛축제공원역 -> 올림픽공원 올림픽홀
기준: 2026-06-06 13:00 일정 시작, 목표 도착 2026-06-06 12:45

추천: 2026-06-06 11:29 출발 -> 2026-06-06 12:45 도착 / 소요 1시간 16분 / 목표 도착 가능
  경로: 도보 -> 지하철 인천1호선 -> 지하철 7호선 -> 도보

추천 경로 상세
- 도보: 출발지 -> 송도달빛축제공원역
- 버스 광역:M6450: 송도달빛축제공원역 승차 -> 선릉역 하차
- 같은 정류장 환승: 선릉역에서 버스 광역:M6450 하차 후 버스 간선:360 탑승
- 버스 간선:360: 선릉역 승차 -> 잠실트리지움아파트앞 하차
- 같은 정류장 환승: 잠실트리지움아파트앞에서 버스 간선:360 하차 후 버스 지선:3323 탑승
- 버스 지선:3323: 잠실트리지움아파트앞 승차 -> 올림픽베어스타운아파트앞 하차
- 도보: 올림픽베어스타운아파트앞 -> 올림픽홀

탐색 방식: 하루 호출 제한을 고려해 TMAP 경로 조회 1회로 총 소요시간을 받아 목표 도착시각에서 역산했습니다. 이전/다음 수단 전수 탐색은 실행하지 않았습니다.

확인 링크
지도앱은 같은 출발/도착 좌표로 다시 길찾기하므로 위 TMAP 경로와 다를 수 있습니다.
- 네이버지도: nmap://route/public?...
- 카카오맵: http://m.map.kakao.com/scheme/route?...

TMAP API 응답 기준입니다. 현장 지연, 운행 중단, 행사장 혼잡은 실제와 다를 수 있습니다.
```

위 출력은 형식 예시입니다. 실제 시간과 경로는 실행 시점의 TMAP API 응답에 따라 달라집니다.

## Time Modes

세 가지 시간 의도를 명확히 나눕니다.

```bash
# 일정 시작 시각. 15분 전 도착 목표.
open-gil plan --origin "강남역" --destination "서울역" --event-at "2026-06-06 19:00"

# 특정 시각까지 도착. 추가 버퍼 없음.
open-gil plan --origin "강남역" --destination "서울역" --arrive-by "2026-06-06 18:30"

# 특정 시각에 출발.
open-gil plan --origin "강남역" --destination "서울역" --depart-at "2026-06-06 09:00"
```

날짜 없이 `09:00`처럼 입력하면 직접 CLI 사용에서는 오늘 날짜로 해석합니다. LLM 스킬 흐름에서는 날짜를 사용자에게 확인해야 합니다.

## JSON for Agents

Codex나 Claude Code 같은 에이전트는 JSON을 쓰는 편이 안전합니다.

```bash
cat <<'JSON' | open-gil plan --json
{
  "origin": {"name": "송도달빛축제공원역"},
  "destination": {"name": "올림픽공원 올림픽홀"},
  "event_at": "2026-06-06 13:00"
}
JSON
```

성공 응답은 항상 envelope 형태입니다.

```json
{
  "status": "ok",
  "data": {
    "time_mode": "event_at",
    "arrival_buffer_minutes": 15,
    "search_strategy": "quota_safe_target_arrival_single_lookup",
    "route_api_calls_used": 1,
    "candidates": []
  }
}
```

오류도 구조화됩니다.

```json
{
  "status": "error",
  "error": {
    "code": "OPEN_GIL_AUTH_INVALID",
    "message": "TMAP API 키가 유효하지 않습니다.",
    "remediation": "키를 채팅창에 붙여넣지 마세요. TMAP_API_KEY 환경변수를 쓰고 있다면 새 값으로 바꾸거나 unset TMAP_API_KEY 후 open-gil setup을 실행하세요."
  }
}
```

장소 후보가 애매하면 `OPEN_GIL_PLACE_AMBIGUOUS`와 후보 목록을 반환합니다. 에이전트는 이때 임의로 고르지 말고 사용자에게 선택을 물어야 합니다.

403 Forbidden처럼 키는 전달됐지만 호출 권한이 거절되면 `OPEN_GIL_AUTH_FORBIDDEN`으로 반환합니다. 이 경우 TMAP 앱키에 해당 API 상품/권한이 활성화되어 있는지, 요금제/도메인/IP 제한이 있는지 확인해야 합니다.

호출 한도 초과는 `OPEN_GIL_QUOTA_EXCEEDED`로 반환합니다. 이 경우 자동 재시도하지 말고 TMAP 한도 초기화나 요금제/쿼터를 확인해야 합니다.

## Natural-Language Agent Flow

`$open-gil` 같은 에이전트 스킬은 자연어를 구조화한 뒤 CLI를 호출합니다.

정확한 상태는 다음과 같습니다.

- 장소명 검색과 경로 계산이 모두 성공하면 그대로 답변합니다.
- TMAP POI 장소명 검색이 `OPEN_GIL_AUTH_FORBIDDEN`, `OPEN_GIL_PLACE_NOT_FOUND`, `OPEN_GIL_QUOTA_EXCEEDED`로 실패하고 `KAKAO_REST_API_KEY`가 있으면 Kakao Local 주소/키워드 검색으로 좌표를 보조 확인합니다.
- 좌표가 확정되면 `open-gil plan --json`을 좌표 입력으로 다시 실행합니다. 이때 경로, 출발시각, 요금, 환승 정보는 TMAP Transit API 결과만 사용합니다.
- Kakao Local 후보가 애매하거나 민감한 장소면 에이전트가 임의로 고르지 않고 사용자에게 선택 또는 좌표 제공을 요청해야 합니다.
- TMAP Transit API 자체가 권한 오류, 한도 초과, 경로 없음으로 실패하면 경로 계산은 불가능합니다.

즉 “자연어 스킬”은 좌표가 확정되고 Transit API가 성공하면 동작합니다. Kakao Local은 좌표화 fallback일 뿐이며, 경로 계산 source of truth는 항상 TMAP Transit API입니다.

## Coordinates

이미 장소를 확정했다면 좌표를 직접 넣을 수 있습니다. 좌표가 있으면 장소명 검색보다 우선합니다.

```bash
open-gil plan \
  --origin-lat 37.407722 --origin-lon 126.625572 --origin-label "송도달빛축제공원역" \
  --destination-lat 37.516289 --destination-lon 127.117314 --destination-label "올림픽홀" \
  --event-at "2026-06-06 13:00"
```

## API Keys

TMAP API 키는 필수입니다.

1. SK Open API에서 앱을 만들고 appKey를 발급합니다.
2. TMAP 대중교통 API와 POI 검색 API 사용 권한을 확인합니다.
3. 키를 채팅창에 붙여넣지 말고, 터미널에서 직접 입력해 설정합니다.

일반 사용자는 `setup` 명령을 쓰는 것을 권장합니다.

```bash
open-gil setup
```

이 명령을 실행하면 API 키를 입력하라는 화면이 나옵니다.
입력하는 동안 글자가 화면에 보이지 않는 것이 정상입니다.
키를 입력한 뒤 Enter를 누르면 로컬 설정 파일에 저장됩니다.

고급 사용자는 환경변수를 쓸 수 있습니다. 환경변수가 로컬 설정 파일보다 우선합니다.

```bash
export TMAP_API_KEY="발급받은_appKey"
```

키 설정 상태는 값 노출 없이 확인할 수 있습니다.

```bash
open-gil config show
```

API 키를 Claude, Codex, ChatGPT 같은 채팅창에 붙여넣지 마세요. 이미 실제 키를 채팅창에 붙여넣었다면 해당 키는 폐기하고 새 키를 발급하는 편이 안전합니다.

Kakao Local fallback은 선택이지만 자연어 장소명 품질을 크게 올립니다. Kakao Developers에서 REST API 키를 발급하고 Local API 사용을 확인한 뒤 설정합니다.

```bash
export KAKAO_REST_API_KEY="발급받은_REST_API_key"
```

또는 로컬 파일에 저장합니다.

```bash
open-gil config set-kakao-key
```

설정 파일은 `~/.config/open-gil/config.json`에 평문으로 저장됩니다. POSIX 환경에서는 `0600` 권한으로 맞춥니다.

공식 문서:

- TMAP 대중교통 API: https://transit.tmapmobility.com/docs/routes
- TMAP POI 검색 API: https://tmap-skopenapi.readme.io/reference/%EC%9E%A5%EC%86%8C%ED%86%B5%ED%95%A9%EA%B2%80%EC%83%89
- Kakao Local API: https://developers.kakao.com/docs/latest/ko/local/dev-guide
- NAVER Maps URL Scheme: https://guide.ncloud-docs.com/docs/en/maps-url-scheme
- KakaoMap URL Scheme: https://apis.map.kakao.com/ios_v2/docs/getting-started/urlscheme/

## Install from Source

```bash
git clone https://github.com/doul735/open_tools.git
cd open_tools
python -m venv .venv
. .venv/bin/activate
python -m pip install -e "./packages/open-gil[dev]"
```

## Tests

기본 테스트는 fixture/mock 기반이라 API 키가 없어도 실행됩니다.

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests -p no:cacheprovider
```

실제 TMAP API 테스트는 `TMAP_API_KEY`가 있을 때만 실행됩니다.

```bash
export TMAP_API_KEY="발급받은_appKey"
PYTHONDONTWRITEBYTECODE=1 python -m pytest packages/open-gil/tests/test_live_tmap.py -p no:cacheprovider
```

## Release Prep

이 저장소는 GitHub Actions CI와 PyPI Trusted Publishing용 워크플로를 포함합니다.

- CI: `.github/workflows/ci.yml`
- PyPI publish: `.github/workflows/publish.yml`
- Dependabot: `.github/dependabot.yml`

로컬 배포 산출물 검증:

```bash
python -m pip install -e "./packages/open-gil[dev]"
python -m build packages/open-gil
```

새 버전을 PyPI에 배포하려면 GitHub Release 태그를 만들고 `publish.yml` 워크플로가 실행되는지 확인하세요.

PyPI Trusted Publisher 설정:

Publisher 값:

```text
Project name: open-gil
Owner: doul735
Repository name: open_tools
Workflow name: publish.yml
Environment name: pypi
```

## Limits

- 현재 MVP 범위는 서울, 경기, 인천입니다.
- 계산 근거는 TMAP 대중교통 API입니다.
- 목표 도착 모드는 기본적으로 경로 조회 1회로 출발시각을 역산합니다. 낮은 호출 제한 때문에 이전/추천/다음 수단 전수 탐색은 기본 제공하지 않습니다.
- 네이버지도와 카카오맵 링크는 확인용이며 계산 근거가 아닙니다.
- 네이버지도와 카카오맵 링크는 같은 출발/도착 좌표로 앱 자체 길찾기를 다시 실행하므로 TMAP 추천 경로와 다를 수 있습니다.
- 별도 실시간 지연, 운행 중단, 행사장 혼잡 정보를 보장하지 않습니다.
- 원문 자연어 프롬프트는 외부 API로 보내거나 캐시하지 않습니다.
