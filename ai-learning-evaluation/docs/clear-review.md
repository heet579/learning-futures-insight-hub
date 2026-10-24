# CLEAR: how a person reviews every report

Statement-by-statement checking (30+ clicks per report) has been replaced by **CLEAR**. The
application proves the facts, and the reviewer spends their time on judgement only a person can
make. Oversight is measured, not assumed.

| Step | Who | What happens |
|---|---|---|
| **C**heck | The app | Every number must match the survey, every quote must be a real learner comment, possible names must be confirmed or removed, groups under 5 responses are hidden, and cause-and-effect wording is flagged. A failed check blocks the report. |
| **L**evel | The app | **Standard** (internal report, 30+ responses, no critical finding): 3 questions, any administrator approves. **High risk** (client report, fewer than 30 responses, or overall satisfaction under 3.5): 5 questions, a Learning Futures lead approves. |
| **E**xamine | The reviewer | Answers 3 or 5 questions (below), about 3 minutes. |
| **A**pprove | The reviewer | A different signed-in account approves. "No" or "Partly" on *Faithful*, or "No" on *Fit*, sends the report back with the reviewer's note. |
| **R**ecord | The app | Answers, the reviewer's priority, caveats and review time go into the hash-chained audit log, the report's *Reviewer notes* and the review record. |

## The questions

1. **Faithful to learners**: five learner comments picked at random by the app (not the AI). Does the report reflect them? *Yes / Partly / No*
2. **Balanced**: the report's strongest claim next to the strongest evidence against it. *Keep it / Add a caveat* (the caveat goes into the report).
3. **Owned**: which recommendation would you act on first, in your own words? It appears in the report under the reviewer's name.
4. **Fair to people** (high risk): could the report unfairly affect anyone? *No / Yes, add a fairness note*
5. **Fit for the audience** (high risk): is the wording right for this audience, with nothing confidential? *Yes / No*

## Oversight panel (administrators)

**Oversight** in the browser app shows, per reviewer: reviews, approved, sent back, typical review
time (timed by the server from when the reviewer opens the questions), and how often they raised a
concern. A reviewer is flagged after 5 reviews with no concern raised, or when their typical review
takes under 2 minutes. Every figure comes from the audit chain.

## Where it lives

- Rules and questions: `src/review/clear.py` (shared by the browser app, desktop app and server)
- Automatic fact check: `src/review/claims.py`, `src/reporting/grounding.py`
- Approval and send-back: `src/storage/reports.py` (`transition`)
- Oversight: `server/oversight.py`, `GET /api/oversight`
- Desktop questions: `src/ui/clear_dialog.py`
