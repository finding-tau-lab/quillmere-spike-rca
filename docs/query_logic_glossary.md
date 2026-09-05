# Query logic glossary (quillmere-demo-v1)

SYNTHETIC DEMO DIALECT. This is not a vendor query language. It exists so a reviewer (or Copilot) can read `query_logic` strings in the RCA packet.

## Operators

| Operator | Meaning |
|---|---|
| `LIKE("phrase")` | Phrase or a close spoken variant is present in the transcript. |
| `NOTLIKE("phrase")` | Exclude the call if that phrase is present (false-positive cut). |
| `OR(...)` | Any child condition may match. |
| `AND(...)` | All child conditions must match. |
| `FIRST90(...)` | The inner condition must occur in the first 90 seconds of the call (opening problem, not wrap-up chatter). |
| `NEAR("a","b",n)` | Terms occur within `n` seconds of each other. Use sparingly. |

## How to evaluate

Read the tree inside-out.

1. Resolve `LIKE` / `NOTLIKE` / `NEAR` against the transcript text and timestamps.
2. Apply `AND` / `OR`.
3. Apply `FIRST90` as a window filter, not as a topic filter.

`NOTLIKE` is for cutting false positives. It is not how you find the problem.

## Example

```
FIRST90(
  AND(
    OR( LIKE("can't log in"), LIKE("login failed"), LIKE("app won't open"), LIKE("error code") ),
    NOTLIKE("password reset complete")
  )
)
```

A match requires an access-failure phrase in the opening 90 seconds, and drops calls that already finished a reset.

## What this is not

- Not a NICE product language.
- Not a production speech-query library.
- Not scored against a real contact-center corpus.
