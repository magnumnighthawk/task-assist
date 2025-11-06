Calendar Watch (in-app) — configuration and usage

Overview
--------
This document explains how the in-app Google Calendar watch management works and how to configure it for your deployment.

Why use in-app watches?
- The app can directly call the Google Calendar API `events.watch` to receive push notifications (webhooks) when calendar events are created/updated/deleted.
- The app stores watch channel metadata in the DB so it can renew or stop channels as needed.

Requirements
------------
- A GCP project with the Google Calendar API enabled.
- OAuth credentials (client ID/secret) in `credentials.json` in the repo root (existing project setup already uses this file).
- `token.pickle` or an OAuth flow to authorize the application so it can call Calendar API.
- A publicly reachable HTTPS endpoint for webhooks (e.g., https://your-domain/api/calendar/push). If you are deploying on Azure as a single container, ensure the container is reachable via HTTPS.

Configuration steps
-------------------
1. Ensure `credentials.json` exists and the Calendar API is enabled for your project.
2. Make sure the app can authenticate (the existing `reminder.get_calendar_service()` code will prompt or use `token.pickle`).
3. Choose a webhook address (the `address` param). For a single-container Azure deployment this will be something like `https://<your-app-host>/api/calendar/push`.
4. Create a channel from the app (example code):

   from reminder import ReminderAgent
   agent = ReminderAgent()
   resp = agent.create_calendar_watch(channel_id='channel-unique-1', address='https://<your-app>/api/calendar/push', ttl_seconds=3600)
   print(resp)

5. The app writes the channel entry to DB (table `watch_channel`). The `expiration` field is recorded from the API response.
6. The scheduler (if running `schedule.py`) includes a `renew_all_watches` job that runs every 30 minutes and attempts to recreate/re-register watches that are expiring soon.

Notes and operational guidance
-----------------------------
- Watches expire and must be renewed. The code in this repo attempts auto-renewal for channels expiring within 5 minutes.
- Google expects webhooks to be HTTPS; use a valid TLS certificate.
- The `/api/calendar/push` handler expects a JSON payload containing at least an `event_id` or `resourceId`. In practice, Calendar push notifications have headers like `X-Goog-Resource-Id` and may not include the full event data; the handler uses the `event_id` (or resourceId) to fetch the full event from the Calendar API and reconcile it using `ReminderAgent.process_event_by_id`.

Security
--------
- Validate requests where possible. For higher security, consider:
  - Using a secret token in the webhook URL (e.g., https://example.com/api/calendar/push?token=<secret>) and verifying it.
  - Or use a GCP-based bridge with Pub/Sub push that can supply authentication tokens.
- Keep `credentials.json` and `token.pickle` secure. Prefer service accounts for server-to-server usage where possible.

Limitations
-----------
- This in-app approach works for smaller deployments. For production or higher reliability, consider using Pub/Sub + Cloud Function bridge to handle notifications, then forward to your app.

Troubleshooting
---------------
- If watches are not received, check the public reachability of your webhook (firewalls, TLS, domain routing).
- Check logs for errors in creating watches, and ensure the watch `address` is reachable by Google.

