# Questions by Teams or email: the bot recipe

**Date:** 2026-10-05 · **For:** whoever runs the Agent One Finance webhook and the Teams/Power Automate flows.

A reviewer asks a desk, a trader or Operations for evidence (`requests.targets` on the
capability or group). Most people asked never open Agent One Finance, so the question reaches them in Teams
or by email, and their reply comes back into Agent One Finance as the answer. This works for every capability
that has request targets: FOBO Prime, FOBO Rates, or any other team that adds them.

## What Agent One Finance sends

With `AOF_NOTIFY_WEBHOOK_URL` set, every notification is POSTed there as JSON. A question also
carries what a flow needs to collect the reply:

```json
{
  "kind": "question",                       // or "question_reminder"
  "title": "Question from frank: PRIME-MB-04 · COB 2026-09-24 · Aged break · side not proven",
  "text": "…", "link": "https://aof.internal.example/cases/…",
  "case_id": "…", "capability_id": "break.investigation",
  "audience_roles": ["PRIME_DESK"], "audience_users": [],
  "request_id": "9f2c…",
  "question": "Was the IRS swap rebooked on Friday?",
  "target": "desk",
  "answer_url": "https://aof.internal.example/api/requests/9f2c…/answer",
  "answer_with_file_url": "https://aof.internal.example/api/requests/9f2c…/answer-with-file",
  "answer_in_console": "https://aof.internal.example/inbox"
}
```

Other kinds are notifications for people in Agent One Finance:
- `question_unanswered`: the reviewers are told after `escalate_after_hours`.
- `answered`: tells the person who asked.

## How the answer comes back

The bot answers **for** the person, with the event secret:

```bash
curl -X POST "$ANSWER_URL" \
  -H "X-AOF-Event-Secret: $AOF_EVENT_SECRET" -H 'Content-Type: application/json' \
  -d '{"answer": "Yes — cancelled and rebooked at the new rate on Friday", "answered_by": "tom"}'
```

With a file (PDF or Excel, at most 10 MB), the bot posts multipart to `answer_with_file_url`. The
form fields are `answer`, `answered_by` and `file`. Agent One Finance keeps the file as the case's evidence,
recording who sent it and which question it answered, and lists it on the question.

Then Agent One Finance:
- records the answer under the person's name (`answered_by`);
- releases the group if it was waiting (`hold_decision`);
- during review, sends the group back to the model with the answer
  (`reinvestigate_on_answer`), as the person who asked.

## Power Automate flow (Teams)

1. **Trigger:** *When an HTTP request is received* (this URL is `AOF_NOTIFY_WEBHOOK_URL`).
   Add a condition: `kind` is `question` or `question_reminder`.
2. **Post an adaptive card and wait for a response** to the channel or chat for the target, for
   example the Prime desk channel for `target = desk`. Show `title` and `question`, a text input
   *Your answer*, and a link to `answer_in_console`.
3. **HTTP:** POST `answer_url` with the headers above and the body
   `{"answer": <response text>, "answered_by": <responder's UPN mapped to an Agent One Finance user id>}`.
4. **On failure** (409 means already answered or cancelled), reply in the thread with Agent One Finance's
   `detail`.

For email, use *Send an email with options* or a shared mailbox. Parse the reply's first block
as `answer`, and send an attachment to `answer_with_file_url`.

## Chasing

Each capability or group sets these, under *Configure → Human review*:

| Setting | FOBO Prime and Rates | Effect |
|---|---|---|
| `requests.remind_after_hours` | 2 | the people asked get a `question_reminder` (and the bot re-posts) |
| `requests.escalate_after_hours` | 4 | the reviewers and whoever asked get `question_unanswered` |
| `requests.allow_attachments` | true | answers may carry a file |

Each happens once per question. The scheduler checks every minute.

## Security

- The event secret lets a bot answer **only** questions. It cannot read cases.
- `answered_by` is recorded as given. Map identities in the flow; do not let responders type it.
- In Agent One Finance, people asked see only the question and the rows it is about (*Inbox → Questions for
  you*). They do not see the whole case.
