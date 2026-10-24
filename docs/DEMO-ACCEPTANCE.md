# Canopy demo acceptance

Record the date, deployed build, tester, and links to evidence when running this checklist. Mark each item **passed**, **failed**, or **not verified**. Do not turn a prior report or mocked test into a current live result.

## Source and deployment

- [ ] The full unit suite and `node --check canopy_ui/app.js` pass. Required CI passes for the exact PR head.
- [ ] Render `/livez` and authenticated `/readyz` respond; `/api/status` reports the expected build. `configured=true` means only that a key is present.
- [ ] The public app requires the operator password; a wrong password fails. The authenticated browser can load chat and Verify a case. No secret appears in the UI or recording.
- [ ] `CANOPY_PUBLIC_ORIGIN` is the exact HTTPS Render origin. A foreign-origin POST is rejected.
- [ ] `CANOPY_AGENT_DB` points to a mounted persistent disk, and a reviewed case reopens after restart. If no disk is available, mark this **failed** and disclose that cases may be lost.

## Live verification walkthrough

- [ ] In a fresh authenticated browser, switch from Chat with Canopy to Verify a case. Load the fictional refund example and run it.
- [ ] Check the verdict, reason, policy excerpt, evidence, execution trace, and the extraction and verification `mreq_` IDs. Match the verification ID to the correct Mubit Requests entry.
- [ ] Save a justified human verdict and reason. Reopen the case in the same browser session and verify `local_only` and the original request ID remain visible. If the model was correct, call the review a confirmation.
- [ ] Run the fictional access example and confirm missing approval evidence leads to `INSUFFICIENT` or an explicit request for missing facts. Try contradictory evidence and check that the verdict is explained by supplied material.
- [ ] Confirm a provider error produces a visible failed state and that a later valid case works. Use an authorised test method; do not expose the API key.
- [ ] Test the recording in a fresh browser viewport. Text, request IDs, and audio are legible; no credentials or private records are shown.

## Learning evidence and submission

- [ ] Read the current Mubit task, Requests, kept-example count, and Adapters state. Record exact observations; successful recorded calls are not necessarily kept examples.
- [ ] If a Mubit adapter version has **Passed**, compare it with the provider in Try models and label the comparison. Mubit support confirmed Try models interactions do not train; only the recorded app calls can contribute examples. If no version has passed, show the actual task status instead.
- [ ] If Mubit documents a correction workflow, submit one approved synthetic correction and capture its accepted status and correlation to the original request. Trace any model update to a specific adapter version. Otherwise say reviews remain `local_only` and do not claim they caused training.
- [ ] Claim an accuracy change only after comparing provider and a confirmed passing adapter on the same independently labelled held-out cases.
- [ ] Verify the video meets the live `/submit` format and time limit. Confirm the form's actual required fields, submit before 07:00 Sunday 25 October London time, save the receipt, and confirm demo attendance. The PDF deck is optional unless the form requests it.

## Evidence log

| Date / build | Gate | Result | Evidence or limitation |
|---|---|---|---|
| Pending live run | Render, browser, Mubit, and submission | Not verified | Fill after executing the checklist. |
