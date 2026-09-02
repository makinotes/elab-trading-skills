# Privacy, publishing, and compliance

## Allowed input

- public Futu profile pages and posts;
- a logged-in page the user is authorized to view, without exporting session secrets;
- user-provided symbol mappings and annotations;
- public market data.

## Never collect or publish

- cookies, authorization headers, CSRF tokens, passwords, browser profiles, or API secrets;
- private messages, contacts, follower-only content, or unrelated account metadata;
- the researcher's own holdings or trading records unless they deliberately add them to a private run;
- inferred identity, health status, private emotion, or non-public financial information.

## Repository sanitation

Public code, documentation, and fixtures must contain:

- placeholder UIDs and invented names only;
- synthetic post text and price series;
- no cached API responses from real users;
- no screenshots, avatars, or downloaded media;
- no local absolute paths or machine usernames;
- no output directories from live runs.

Before publication, scan tracked files for:

- profile URLs with numeric IDs;
- names from the source study;
- emails, tokens, cookies, and authorization strings;
- home-directory paths;
- raw JSON, CSV, images, and report artifacts.

## Report publication

Public posts can still contain personal data and copyrighted expression. Before republishing a report:

- quote minimally and link to the original when possible;
- distinguish quotation from paraphrase;
- redact account IDs or images when they are unnecessary;
- state capture date and missing-content boundary;
- provide corrections when attribution is wrong;
- comply with platform terms and applicable law.

## Financial-research boundary

Reports are educational research, not investment advice. Do not:

- promise returns;
- recommend automatic copying;
- equate visible public posts with a complete portfolio;
- claim account performance without verified account-level records;
- present statistical noise as stable alpha.

## Access-control failures

When blocked by login, CAPTCHA, rate limits, or interface changes:

1. stop automated requests;
2. preserve the failure response metadata without secrets;
3. tell the user what is missing;
4. suggest a legitimate login or manual export path;
5. never offer anti-bot bypass instructions.
