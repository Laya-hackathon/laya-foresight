# Foresight
### Proactive Claim Escalation Prevention · Laya Healthcare

---

## Problem Statement

When a user submits a health insurance claim, they enter a period of uncertainty. They don't know whether their claim will be accepted, how long it will take, or whether anything is wrong with their submission. This uncertainty drives anxiety — and anxiety drives behaviour.

Users begin repeatedly logging into the app, refreshing their claim status page, and re-uploading documents they've already submitted. When none of that provides reassurance, they do the only thing left: they call support.

Support calls are expensive. They consume agent time, drive up operational cost, and — critically — they're often entirely avoidable. The user didn't need a human agent. They needed timely, clear information at the right moment. The problem isn't that users call. The problem is that the system waited for them to call rather than reaching out first.

---

## Solution

Foresight is a two-component system that identifies high-risk users before they escalate and intervenes proactively to resolve their concern.

---

### Component 1 — Risk Predictor Model

A binary classification model trained on behavioural, claim, and historical signals that predicts whether a given user is likely to call support within the next 48 hours. The model scores every active claim on a rolling basis and assigns each user to a risk band: High, Medium, or Low.

Features used include:

- *Behavioural signals* — number of app logins post-submission, status page views, time to first re-check, document uploads, claim edits
- *Claim signals* — claim type, estimated amount, missing documents, days since submission
- *Historical signals* — past claims by the same user, prior escalation history

---

### Component 2 — LayaAIAgent

LayaAIAgent is an intelligent agent that consumes the risk scores produced by Component 1 and takes autonomous action on two fronts.

**Internal — Alerting the Laya Team**

LayaAIAgent surfaces a prioritised view of at-risk users directly to the Laya support and operations team. It communicates who is showing urgency signals, how severe the risk is, and what the likely cause is — giving agents the context they need to act before a call comes in. Rather than agents reacting to an inbound queue, they are handed a ranked list of users who need attention, ordered by predicted urgency.

**External — Deciding Whether to Reach Out to the User**

LayaAIAgent also makes an independent decision on whether to proactively contact the user directly. Based on the risk score, the claim context, and the nature of the signals detected, it determines whether sending a message would be helpful — and if so, what that message should contain. This could be a status update, a note about a missing document, a processing time estimate, or a reassurance that the claim is progressing normally.

The agent does not message every flagged user. It exercises judgement — if the available information is unlikely to reduce the user's anxiety or if the claim situation is too ambiguous to communicate clearly, it holds back and routes the case to a human instead.

The outcome of every action — whether the user called anyway, whether the message resolved their concern — is captured and fed back into the training pipeline, continuously improving both the risk model and the agent's decision-making over time.

---

## Status

> Early-stage design and architecture phase. Data availability and app instrumentation requirements are being scoped with Laya. Model training cannot begin until behavioural event tracking is instrumented in the Laya app and a minimum dataset of labelled escalation events is established.

---

*Foresight — built for Laya Healthcare*
