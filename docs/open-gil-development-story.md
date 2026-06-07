# open-gil Development Story

`open-gil` started from a simple requirement:

> When a user asks "I need to be at this place by this time. When should I leave, and what should I take?", an agent should answer without inventing public-transit facts.

The first MVP target is Seoul, Gyeonggi, and Incheon. The tool is intentionally narrow: an LLM can parse Korean natural language and ask clarification questions, but route time, fare, transfers, and arrival time must come from route APIs.

## Current Status

`open-gil` is ready as a public alpha MVP.

- It is a Python CLI and agent skill.
- It uses TMAP Transit as the route-calculation source of truth.
- It can use Kakao Local as an optional coordinate fallback.
- It returns a stable JSON envelope for agents and Korean text output for humans.
- It is designed to avoid hallucinated routes, not to beat every map app at routing quality.

The key product decision is honesty: when providers cannot guarantee the same route, the output says so instead of pretending they match.

## Where We Started

The first plan was more ambitious:

1. Parse the user's route request into structured input.
2. Use TMAP POI to turn place names into coordinates.
3. Use TMAP Transit to calculate routes.
4. For target-arrival questions, search every 5 minutes over a 3-hour window.
5. Return three candidates: previous, recommended, and next.
6. Add Naver Map and KakaoMap links for final user verification.

That design was correct from a planning perspective, but too expensive for realistic API limits. A single user question could become 37 route calls before retries or place lookup. For a low daily quota, that is not a usable default.

## What Changed

### 1. Candidate Search Became Quota-Safe

The MVP now uses one TMAP Transit route calculation per natural-language request.

For `event_at`, the target arrival time is 15 minutes before the event. For `arrive_by`, the target is exactly the requested arrival deadline. The CLI gets one route duration from TMAP and reverse-calculates the practical departure time from the target arrival time.

This means the MVP does not exhaustively prove "the latest possible train or bus." It gives a quota-safe recommendation based on the current top-ranked TMAP route. That tradeoff is explicit in the README and output.

### 2. TMAP POI Was Not Reliable for Every Key

During live testing, the TMAP app key worked for Transit route calculation but returned a forbidden response for POI search. In other words, the route API was usable, but place-name search was not available with that key.

The project added clearer auth errors:

- `OPEN_GIL_AUTH_INVALID` for invalid keys
- `OPEN_GIL_AUTH_FORBIDDEN` for valid-looking keys without permission for that API
- `OPEN_GIL_QUOTA_EXCEEDED` for quota exhaustion

Then we added Kakao Local as a coordinate fallback.

### 3. Kakao Local Is a Fallback, Not a Routing Source

Kakao Local helps with place-name to coordinate conversion. It does not calculate the route, departure time, fare, or transfers.

The provider boundary is fixed:

- TMAP Transit: route, time, fare, transfers
- TMAP POI: preferred place search when available
- Kakao Local: optional coordinate fallback
- Naver Map and KakaoMap links: verification links only

This keeps the result explainable. If a route says "TMAP API response basis," it should actually come from TMAP Transit.

### 4. Place Ambiguity Needed Agent Discipline

Live place searches can return multiple similar candidates. Churches, apartment complexes, stations, and venues often have several nearby results.

The rule is now:

- If the top candidate is clearly the intended place, the agent can proceed.
- If candidates are ambiguous, the agent must ask the user to choose before spending the one route calculation.
- The agent should not burn the route-call budget on a guessed coordinate.

This is one of the main reasons `open-gil` is both a CLI and a skill. The CLI gives deterministic behavior; the skill tells the agent when to stop and clarify.

### 5. Map Links Were Reworded

At first, the output treated Naver Map and KakaoMap links like links to "the route." In practice, those URL schemes reopen each app's own route search using the same origin and destination coordinates.

That means the app may show a different route than TMAP.

The output now calls them verification links and includes the warning:

```text
지도앱은 같은 출발/도착 좌표로 다시 길찾기하므로 위 TMAP 경로와 다를 수 있습니다.
```

This is not a small UX detail. It prevents a user from thinking open-gil broke when a map app recalculates differently.

### 6. Route Details Became More Useful

Early output was too thin. It could say that the user should take a subway or bus, but not always where to get on and off.

The formatter now tries to include:

- walking segments
- subway line names
- bus route names
- boarding and alighting stops
- same-stop transfers when the API describes them that way
- fare, transfers, duration, and arrival time

Exit numbers are not promised. The current TMAP Transit response does not provide a reliable exit-name field for every step. For on-the-ground details, the user still needs to open a map app near departure time.

## Final MVP Flow

```text
Korean natural-language question
  -> agent extracts structured intent
  -> open-gil CLI receives JSON or CLI options
  -> place names are resolved to coordinates
       -> TMAP POI if available
       -> Kakao Local fallback if configured
  -> TMAP Transit is called once for route calculation
  -> open-gil formats route, departure time, arrival time, fare, transfers
  -> Naver Map and KakaoMap verification links are included with a mismatch warning
```

The one-call route budget is intentional. It makes the tool practical for users with small API quotas and keeps the agent from silently spending a whole day's allowance on one question.

## Why This Is a Monorepo

We considered separate repositories for future `open_*` tools such as `open-review`.

The final decision was to keep one public repository for the series:

- GitHub stars, issues, and discussions do not fragment across many small repos.
- Each tool can still be packaged and released independently.
- Users can install only the CLI they need, such as `pipx install open-gil`.
- Shared contribution, security, and release documentation can stay at the root.

The current layout reflects that:

```text
packages/open-gil/
  pyproject.toml
  src/open_gil/
  tests/
  skills/open-gil/
.agents/skills/open-gil/
docs/
```

## Privacy and Key Handling

The project is designed for local use first.

- Users bring their own TMAP key.
- Kakao Local is optional and uses the user's own key.
- API keys are never printed.
- Local config is opt-in plaintext under `~/.config/open-gil/config.json`.
- On POSIX systems, the config file is written with `0600` permissions.
- Raw natural-language prompts are not sent to Kakao or TMAP.
- Kakao receives only place-search strings when fallback lookup is used.
- TMAP Transit receives coordinates and requested time fields needed for routing.

We discussed a hosted coordinate fallback using a privately held Kakao key, potentially on a Mac mini server, but that is not part of the MVP. If added later, it should proxy only coordinate lookup, not TMAP route calculation.

## Current Limitations

- The user still needs a TMAP API key for route calculation.
- TMAP POI permission may not be enabled for every TMAP app key.
- Kakao Local improves place lookup but cannot remove every ambiguity.
- The default target-arrival mode reverse-calculates from one top-ranked route instead of exhaustively searching all departure candidates.
- Naver Map and KakaoMap links may show different routes because those apps recalculate.
- Exit numbers and platform details are not guaranteed.
- Service disruptions, event crowding, and real-time delays are outside the current MVP guarantee.

## Future Improvements

The most useful next steps are:

1. Add an optional exact-result page, for example `/r/{id}`, that displays the TMAP route open-gil actually used.
2. Improve place candidate confidence scoring for Kakao Local results.
3. Add an optional hosted coordinate proxy for users who want easier setup, without proxying TMAP route calculation.
4. Support a provider chain such as TMAP POI -> Kakao Local -> Naver address search -> optional Google fallback for coordinates.
5. Add more fixture tests from real anonymized response shapes.
6. Add structured warnings for low-confidence place matches before route calls.
7. Revisit multi-candidate route search only when users have enough quota or a provider supports arrival-time search directly.

## Release Positioning

`open-gil` should be presented as a practical public alpha:

- It is useful now for TMAP-backed Korean public-transit planning.
- It is honest about provider boundaries.
- It avoids hallucinated answers.
- It is not a replacement for opening a map app at the final moment.

That is the main promise of the project: let the LLM help with the conversation, but keep operational facts tied to a real data source.
