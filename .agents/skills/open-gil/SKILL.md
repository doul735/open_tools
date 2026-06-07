---
name: open-gil
description: Use the local open-gil CLI to answer Korean public-transit departure planning questions without hallucinating routes. Trigger when a user asks when to leave, how to route by public transit, or wants a Codex/Claude agent to plan a Seoul/Gyeonggi/Incheon trip using TMAP-backed data.
---

# open-gil

Use `open-gil` for Seoul, Gyeonggi, and Incheon public-transit planning. TMAP Transit API is the source of truth for route calculation; do not invent departure times, transfer stations, durations, fares, or route details.

Natural-language status:

- It works when origin/destination coordinates can be confirmed and TMAP Transit route lookup succeeds.
- It may not work as a pure place-name lookup when the TMAP POI API is forbidden or unavailable.
- If TMAP POI fails but `KAKAO_REST_API_KEY` is configured, the CLI uses Kakao Local as coordinate fallback.
- If API coordinate fallback fails but coordinates can be confirmed from the user or public sources, rerun with coordinates and explain that only coordinate resolution used the fallback.
- It does not work when TMAP Transit itself is forbidden, quota-exceeded, or cannot find a route.

## Workflow

1. Parse the user's request into structured fields:
   - origin
   - destination
   - one time intent: `depart_at`, `event_at`, or `arrive_by`
2. Confirm the interpretation before lookup.
   - If the user says a relative date like "today" or "tomorrow", resolve it using the current local date and state the exact date in the answer.
   - If the user gives only a time with no date or relative-date word, ask for the exact date.
   - If the intent is inferred, ask whether it means fixed departure, event/start time, or arrival deadline.
3. Call the CLI with JSON and `--json`.
4. Read only the JSON envelope. Do not scrape human text.
5. If the CLI returns `OPEN_GIL_PLACE_AMBIGUOUS`, show the candidates and ask the user to choose. Re-run with coordinates and labels from the chosen candidate.
6. If the CLI returns `OPEN_GIL_AUTH_FORBIDDEN` during place-name lookup, do not say the whole route planner failed. First ensure `KAKAO_REST_API_KEY` is configured. If Kakao fallback is unavailable or ambiguous, follow the coordinate fallback workflow below, then rerun with `{lat, lon, label}`.
7. Summarize the selected result in Korean. Always include boarding and alighting points from `candidates[].legs[]` for every bus/subway/train leg.
8. If `planning_note` is present, mention it. Do not claim that previous/next departures were exhaustively searched.
9. End every user-facing route answer with NAVER Maps and KakaoMap route links from `verification_links`.

## Coordinate Fallback

Use this only when place-name lookup fails or when the user already supplied coordinates. The fallback is for resolving input coordinates, not for calculating the route.

Automatic provider order:

1. TMAP POI
2. Kakao Local keyword/address search, only when `KAKAO_REST_API_KEY` is configured
3. User-supplied coordinates or public/authoritative coordinate confirmation

If `origin.source` or `destination.source` starts with `kakao_local`, disclose that Kakao Local was used only for coordinate resolution.

1. Use public/authoritative sources only to confirm place identity and coordinates:
   - official venue/building pages, road-address pages, public map/geocoder results, or user-supplied coordinates
2. If the place is ambiguous, residential/private, or has multiple plausible candidates, ask the user to choose or provide coordinates before calling TMAP Transit.
3. If there is exactly one high-confidence public candidate and the user has asked you to proceed, you may run the coordinate-based CLI call and clearly disclose the coordinate fallback in the final answer.
4. Never use public web results for departure time, route, fare, transfer, stop, or delay data.
5. Rerun the CLI with coordinates:

```bash
cat <<'JSON' | open-gil plan --json
{
  "origin": {"lat": 37.4105748, "lon": 126.6266089, "label": "힐스테이트 송도 더테라스"},
  "destination": {"lat": 37.5727687, "lon": 126.9707238, "label": "내수동교회"},
  "event_at": "2026-06-07 11:00"
}
JSON
```

Required disclosure when fallback was used:

```text
장소 좌표는 Kakao Local 또는 공개/사용자 제공 자료로 확인했고, 출발시각/경로/요금/환승 계산은 확정 좌표로 호출한 TMAP Transit API 결과만 사용했습니다.
```

## Commands

Prefer stdin JSON to avoid shell quoting issues:

```bash
cat <<'JSON' | open-gil plan --json
{
  "origin": {"name": "송도달빛축제공원역"},
  "destination": {"name": "올림픽공원 올림픽홀"},
  "event_at": "2026-06-06 13:00"
}
JSON
```

For already confirmed coordinates:

```bash
cat <<'JSON' | open-gil plan --json
{
  "origin": {"lat": 37.407722, "lon": 126.625572, "label": "송도달빛축제공원역"},
  "destination": {"lat": 37.516289, "lon": 127.117314, "label": "올림픽홀"},
  "event_at": "2026-06-06 13:00"
}
JSON
```

## Time Intent Rules

- `event_at`: the user is going to a concert, meeting, class, reservation, or event that starts at that time. open-gil targets arrival 15 minutes before that time.
- `arrive_by`: the user explicitly says they must arrive by that time. No extra 15-minute buffer.
- `depart_at`: the user explicitly says they will leave at that time or asks for a route from that departure time.

Natural-language flows must confirm the inferred intent before running the CLI.

For `event_at` and `arrive_by`, the MVP uses a quota-safe single TMAP route lookup and calculates the recommended departure from the returned total duration. Do not describe it as an exhaustive latest-departure search.

## Route Call Budget

- For one natural-language user request, call TMAP Transit route calculation at most once.
- Resolve place candidates first using TMAP POI, Kakao Local, user choice, or user-provided coordinates. Do not call TMAP Transit until both origin and destination are resolved.
- If place resolution is ambiguous, ask the user to choose instead of spending a route call.
- If the one TMAP Transit call fails, report the exact error. Do not retry unless the user explicitly asks.
- Place lookup calls are separate from the TMAP Transit route-call budget, but keep them minimal.

## Error Handling

- `OPEN_GIL_AUTH_MISSING`: explain that `TMAP_API_KEY` or `open-gil config set-key` is needed.
- `OPEN_GIL_AUTH_INVALID`: tell the user the TMAP key is invalid or the authentication format is wrong; do not say only "400" or "401".
- `OPEN_GIL_AUTH_FORBIDDEN`: if this happens during place-name lookup and Kakao fallback is not configured, ask for `KAKAO_REST_API_KEY` or coordinates. If it happens during coordinate-based Transit lookup, tell the user route calculation is blocked and ask them to check API product permission, paid plan status, and domain/IP restrictions.
- `OPEN_GIL_PLACE_AMBIGUOUS`: ask the user to pick one candidate; do not choose automatically.
- `OPEN_GIL_PLACE_NOT_FOUND`: ask for a more specific place or coordinates.
- `OPEN_GIL_ROUTE_NOT_FOUND`: explain that TMAP did not return a qualifying route for the inputs.
- `OPEN_GIL_QUOTA_EXCEEDED`: explain that the TMAP daily/request quota is exhausted; do not keep retrying.
- `OPEN_GIL_API_ERROR`: report the API cause and retry only if the user wants another attempt.
- `OPEN_GIL_TIME_INVALID`: ask for an exact date/time.

## Output Guardrails

- Say the result is based on TMAP API data.
- If Kakao Local was used, say it was used only for coordinate lookup and that route calculation remained TMAP Transit.
- Do not stop at a route summary such as "BUS M6450 -> BUS 360"; include where to board and where to get off.
- If a WALK leg has the same start/end name with 0m or 0 seconds between two transit legs, summarize it as a same-stop transfer using the previous alighting route and next boarding route.
- Mention that field delays, disruptions, and event congestion can differ.
- NAVER Maps and KakaoMap links are verification/open links only, not calculation sources.
- Do not describe NAVER/Kakao links as exact links to the TMAP-selected route. They open route search with the same origin/destination coordinates, and each map app may recalculate a different route.
- Always include a final Korean section named `확인 링크` with both `네이버지도` and `카카오맵`. Do not omit it from concise answers.
- In the `확인 링크` section, include this warning: `지도앱은 같은 출발/도착 좌표로 다시 길찾기하므로 위 TMAP 경로와 다를 수 있습니다.`
- Never send or store the user's raw natural-language prompt through open-gil.
- Never log, quote, or expose the TMAP API key.
- Do not say simply "it works" or "it does not work." Distinguish: place-name lookup, coordinate resolution, and TMAP Transit route calculation.
