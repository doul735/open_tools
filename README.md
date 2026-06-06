# open-gil

`open-gil`은 TMAP 대중교통 API를 근거로 출발 시각과 경로 후보를 계산하는 Python CLI입니다. Codex, Claude Code 같은 LLM은 자연어를 구조화하고 확인 질문을 하는 역할만 맡고, 경로/환승/소요시간/출발시각은 CLI가 API 응답으로 계산합니다.

MVP 범위는 서울, 경기, 인천입니다.

## 설치

배포 후 일반 사용자는 `pipx` 설치를 권장합니다.

```bash
pipx install open-gil
```

개발 중인 로컬 체크아웃에서는 다음처럼 설치합니다.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## TMAP API 키

1. SK Open API에서 앱을 만들고 TMAP API appKey를 발급합니다.
2. TMAP 대중교통 API와 POI 검색 API 사용 권한을 확인합니다.
3. 환경변수나 로컬 설정 파일 중 하나로 키를 설정합니다.

환경변수가 우선입니다.

```bash
export TMAP_API_KEY="발급받은_appKey"
```

설정 파일에 저장할 수도 있습니다. 파일은 `~/.config/open-gil/config.json`에 평문으로 저장되고 POSIX 환경에서는 `0600` 권한으로 맞춥니다.

```bash
open-gil config set-key
```

공식 문서:

- TMAP 대중교통 API: https://transit.tmapmobility.com/docs/routes
- TMAP POI 검색 API: https://tmap-skopenapi.readme.io/reference/%EC%9E%A5%EC%86%8C%ED%86%B5%ED%95%A9%EA%B2%80%EC%83%89
- NAVER Maps URL Scheme: https://guide.ncloud-docs.com/docs/en/maps-url-scheme
- KakaoMap URL Scheme: https://apis.map.kakao.com/ios_v2/docs/getting-started/urlscheme/

## 사용 예시

일정 시작 시각 기준입니다. `--event-at`은 15분 전 도착을 목표로 합니다.

```bash
open-gil plan \
  --origin "송도달빛축제공원역" \
  --destination "올림픽공원 올림픽홀" \
  --event-at "2026-06-06 13:00"
```

정확히 특정 시각까지 도착해야 하면 `--arrive-by`를 씁니다. 이 경우 추가 15분 버퍼는 적용하지 않습니다.

```bash
open-gil plan --origin "강남역" --destination "서울역" --arrive-by "18:30"
```

고정 출발 시각 조회는 `--depart-at`입니다.

```bash
open-gil plan --origin "강남역" --destination "서울역" --depart-at "09:00"
```

좌표를 직접 넣을 수도 있습니다. 좌표가 있으면 장소명 검색보다 우선합니다.

```bash
open-gil plan \
  --origin-lat 37.407722 --origin-lon 126.625572 --origin-label "송도달빛축제공원역" \
  --destination-lat 37.516289 --destination-lon 127.117314 --destination-label "올림픽홀" \
  --event-at "2026-06-06 13:00"
```

## JSON 입력과 출력

파일 입력:

```bash
open-gil plan --input plan.json --json
```

stdin 입력:

```bash
cat plan.json | open-gil plan --json
```

예시 JSON:

```json
{
  "origin": {"name": "송도달빛축제공원역"},
  "destination": {"name": "올림픽공원 올림픽홀"},
  "event_at": "2026-06-06 13:00"
}
```

성공 응답은 항상 다음 envelope입니다.

```json
{
  "status": "ok",
  "data": {}
}
```

실패 응답도 안정된 envelope와 `OPEN_GIL_*` 코드를 사용합니다.

```json
{
  "status": "error",
  "error": {
    "code": "OPEN_GIL_AUTH_INVALID",
    "message": "TMAP API 키가 유효하지 않습니다.",
    "remediation": "TMAP_API_KEY 값 또는 open-gil config set-key로 저장한 키를 확인하세요."
  }
}
```

## 동작 원칙

- 계산 근거는 TMAP 대중교통 API입니다.
- 네이버지도와 카카오맵 링크는 사용자가 직접 확인하기 위한 링크이며 계산 근거가 아닙니다.
- 장소 후보가 여러 개면 자동 선택하지 않습니다. 일반 터미널에서는 번호 선택을 요청하고, `--json`에서는 `OPEN_GIL_PLACE_AMBIGUOUS`와 후보 목록을 반환합니다.
- `--event-at`은 일정 시작 15분 전 도착을 목표로 합니다. 도착은 목적지까지의 도보 이동을 포함한 TMAP 경로 결과 기준입니다.
- 목표 도착 모드는 목표 시각 3시간 전부터 5분 간격으로 조회하고, 이전 후보/추천 후보/다음 후보를 반환합니다.
- TMAP 응답 이외의 별도 실시간 지연, 운행 중단, 행사 혼잡 정보는 보장하지 않습니다.
- 원문 자연어 프롬프트는 외부 API로 보내거나 캐시하지 않습니다.

## 테스트

기본 테스트는 fixture/mock 기반이라 API 키가 없어도 실행됩니다.

```bash
pytest
```

실제 TMAP API 테스트는 `TMAP_API_KEY`가 있을 때만 실행됩니다.

