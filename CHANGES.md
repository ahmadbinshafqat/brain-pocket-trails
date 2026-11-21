# Changes: Saved-route sharing links

Added public, read-only sharing links for saved walking-loop route plans.

## What changed

- Added `share_token` to `RoutePlan` and made it unique/indexed.
- Added route-plan lookup by share token.
- Added a public `/share/{share_token}` page that renders the existing plan view in read-only shared mode.
- Added share-link UI on the plan page with copy-to-clipboard support.
- Updated styles for share controls and shared-plan banner.
- Added a small database compatibility helper that creates/backfills the `share_token` column for existing SQLite databases on startup.

## Integration notes

No new environment variables are required.

Run the app as before:

```bash
uvicorn app.main:app --reload
```

Existing saved plans will receive share tokens automatically at startup when using SQLite.