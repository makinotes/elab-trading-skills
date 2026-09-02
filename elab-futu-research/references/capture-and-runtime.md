# Capture and runtime

## Source boundary

This workflow archives content that the user may legitimately access. It does not bypass authentication, CAPTCHA, paywalls, regional restrictions, or private-account controls.

The currently observed public endpoints are implementation details and may change:

```text
GET https://q.futunn.com/nnq/personal-list
  ?type=301|302
  &num=10
  &load_list_type=2|1
  &target_uid=<uid>
  [&more_mark=<cursor>]
  [&sequence=<sequence>]

GET https://q.futunn.com/v2/api/feed/detail
  ?feedId=<feed_id>
  &targetLang=0
  &translateType=1
  &lang=zh-cn
```

`301` is the dynamics/all stream. `302` is the columns stream. A first page uses `load_list_type=2`; subsequent pages use `1` and carry the returned `more_mark` and `sequence`.

Treat the endpoints as unstable. Validate JSON shape before trusting it. An HTML login page, redirect, status 401/403/429, missing list data, or a repeated cursor is a recorded failure—not an empty archive.

## Completeness protocol

For each UID and stream:

1. Save every raw page before transformation.
2. Record request parameters, retrieval time, status, response hash, returned IDs, cursor, and `has_more`.
3. Deduplicate by `feed_id`, but preserve stream membership. A column may also appear in the all stream.
4. Continue until:
   - `has_more=0`; or
   - a requested `--since` boundary has been crossed by two consecutive pages whose parseable records are all older.
5. Fetch every retained detail record. Retry transient failures with exponential backoff and jitter.
6. Save every successful detail response before normalization.
7. Download only URLs present in public post data. Preserve SHA-256, byte size, content type, and source URL in the media manifest.
8. Write failures explicitly. Never silently omit them.

All-history status is `complete_visible_history` only when both streams reach `has_more=0`. Date-window status can be `complete_requested_window` when the verified cutoff rule is satisfied.

## Resumption

- Reuse a valid cached page or detail record.
- Re-download a media object only when the file is missing, zero bytes, or its manifest hash does not match.
- `--refresh` may re-request list pages, but must not delete older evidence.
- Write temporary downloads with `.part`, then atomically rename.
- Keep run metadata in `manifest.json`.

## Time and date handling

Save:

- source timestamp as returned;
- parsed ISO timestamp when possible;
- source timezone assumption;
- retrieval timestamp in UTC.

Do not silently coerce an unparseable timestamp. Keep the raw value and flag `timestamp_parse_error`.

## Browser fallback

Prefer the public JSON endpoints because they are reproducible. If they legitimately require a logged-in browser:

1. ask the user to sign in through their own browser session;
2. use visible browser interactions or developer-visible responses within that session;
3. never export cookies or credentials;
4. preserve the same raw-page and audit contract;
5. stop at CAPTCHA or anti-bot challenges.

## Politeness defaults

- list requests: sequential;
- detail workers: at most 4;
- media workers: at most 6;
- retries: 4 with exponential backoff and jitter;
- identify the tool with a stable, non-deceptive User-Agent;
- honor `Retry-After`.

The user may reduce concurrency. Do not raise it merely to finish faster.
