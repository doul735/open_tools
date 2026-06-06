---
name: open-gil
description: Use the local open-gil CLI to answer Korean public-transit departure planning questions without hallucinating routes. Trigger when a user asks when to leave, how to route by public transit, or wants a Codex/Claude agent to plan a Seoul/Gyeonggi/Incheon trip using TMAP-backed data.
---

# open-gil

Use `open-gil` for Seoul, Gyeonggi, and Incheon public-transit planning. The CLI is the source of truth; do not invent departure times, transfer stations, durations, fares, or route details.

## Workflow

1. Parse the user's request into structured fields:
   - origin
   - destination
   - one time intent: `depart_at`, `event_at`, or `arrive_by`
2. Confirm the interpretation before lookup.
   - If the user gave a date-less natural-language time, ask for the exact date.
   - If the intent is inferred, ask whether it means fixed departure, event/start time, or arrival deadline.
3. Call the CLI with JSON and `--json`.
4. Read only the JSON envelope. Do not scrape human text.
5. If the CLI returns `OPEN_GIL_PLACE_AMBIGUOUS`, show the candidates and ask the user to choose. Re-run with coordinates and labels from the chosen candidate.
6. Summarize the selected result in Korean and include the NAVER/Kakao verification links.
7. If `planning_note` is present, mention it. Do not claim that previous/next departures were exhaustively searched.

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

## Error Handling

- `OPEN_GIL_AUTH_MISSING`: explain that `TMAP_API_KEY` or `open-gil config set-key` is needed.
- `OPEN_GIL_AUTH_INVALID`: tell the user the TMAP key is invalid; do not say only "400" or "401".
- `OPEN_GIL_PLACE_AMBIGUOUS`: ask the user to pick one candidate; do not choose automatically.
- `OPEN_GIL_PLACE_NOT_FOUND`: ask for a more specific place or coordinates.
- `OPEN_GIL_ROUTE_NOT_FOUND`: explain that TMAP did not return a qualifying route for the inputs.
- `OPEN_GIL_API_ERROR`: report the API cause and retry only if the user wants another attempt.
- `OPEN_GIL_TIME_INVALID`: ask for an exact date/time.

## Output Guardrails

- Say the result is based on TMAP API data.
- Mention that field delays, disruptions, and event congestion can differ.
- NAVER Maps and KakaoMap links are verification/open links only, not calculation sources.
- Never send or store the user's raw natural-language prompt through open-gil.
