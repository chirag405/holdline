# Holdline — extension backlog

Things that make the project stand out past the core "cancel a subscription"
demo. None are on the critical path; pull them in once Days 1–8 are solid.

## AWS services — planned vs. optional

| Service | Role | When | Status |
|---|---|---|---|
| **Amazon Bedrock — Nova 2 Sonic** | Speech-to-speech voice core | Day 1 | in use |
| **Amazon DynamoDB** | State: tasks / calls / decisions | Day 4 | code written, not connected |
| **Amazon Bedrock AgentCore Runtime** | Host the bidi WebSocket agent in the cloud | Day 7 | planned |
| **Amazon Bedrock AgentCore Memory** | Long-term: provider IVR paths, user account profiles | Day 7 | planned |
| **Amazon S3** | Store call recordings + full transcripts (Twilio records, we archive) | Day 6 | optional |
| **Amazon SNS** | Push/SMS the escalation Decision to the user when the dashboard isn't open | Day 5–6 | optional, high value for the "surfaces only when needed" story |
| **AWS Secrets Manager** | Twilio + provider creds instead of `.env` | polish | optional |
| **Amazon CloudWatch** | Dashboards from Strands OpenTelemetry export (hold time, escalation rate, success rate) | Day 8 | optional, good README screenshot |
| **Amazon Connect** | Pure-AWS telephony alternative to Twilio (one config swap) | if time | documented, not built |
| **Amazon Comprehend** | Sentiment on the rep's turns → escalate earlier when a call turns hostile | stretch | idea |

## Product extensions (pick to broaden appeal)

1. **Multi-vertical task library.** Beyond cancellations: dispute a charge, chase
   an insurance claim status, reschedule an appointment, request a refund, ask for
   a hardship extension. Each is a `CallBrief` template + a practice-IVR branch.
2. **"Call me when a human picks up."** Option to have Holdline navigate the IVR
   and wait on hold, then conference the user in the moment a person answers —
   the agent did the boring 20 minutes, the human takes the conversation.
3. **Provider address book (DynamoDB).** Save each provider's number, account
   number, and learned IVR path so a repeat task is one tap.
4. **Scheduled + retry.** "Try again tomorrow at 9am" when a call hits a closed
   office or an all-circuits-busy. EventBridge Scheduler.
5. **Batch mode for a household.** One person runs the same cancellation call for
   three family members' accounts back to back.
6. **Polyglot.** Nova Sonic speaks multiple languages natively — let the user set
   the call language (e.g. call a Spanish-language support line).
7. **Evidence pack.** After the call: transcript + recording + confirmation number
   + a drafted follow-up email, bundled as a PDF the user can forward if the
   provider later disputes the cancellation.
8. **Accessibility framing.** Explicit mode for users for whom phone calls are a
   barrier (anxiety, speech, hearing, language) — the differentiator for the
   "who is it for / why it matters" pitch.
