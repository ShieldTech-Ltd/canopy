# Canopy recording script

Use the **Recurring tasks** track. The video must stay under the organiser's current limit (the team handoff reports under three minutes). Record a fresh browser session after the reviewed PR is merged and the Render build matches that commit. Use only fictional or approved non-sensitive cases. Keep the Mubit API key and operator password out of the frame.

## Before capture

1. Open Render and warm `/livez`; confirm `/api/status` reports the deployed build. A key-present status is not a live model check.
2. Open Canopy as an authorised operator. Switch from Chat with Canopy to **Verify a case**. Keep the browser zoom high enough for the trace to read.
3. Check the Mubit console's current task, kept-example count, and Adapters page. Decide which of the two endings below is factually available. Do not call 25 successful requests 25 kept examples.
4. Rehearse the fictional refund case once. If it returns the correct `VIOLATES` verdict, the human review is a **confirmation**, not a correction. If it fails or times out, recover and record a clean run; disclose a material persistent failure.

## Three-minute sequence

| Time | Screen | Say |
|---|---|---|
| 0:00-0:20 | Canopy and the case prompt | “Canopy checks a claim against only the policy and evidence supplied. This is a repeatable support review task.” |
| 0:20-0:55 | Load and run **Refund exception** | “The normal refund window is 14 days. Damaged items have a 30-day exception, even after use. The customer has photos and is at day 21. The claim says we must refuse.” |
| 0:55-1:25 | Verdict and Evidence tab | “Canopy says `VIOLATES`, cites the damaged-item exception, and explains why. Missing facts would produce `INSUFFICIENT`.” |
| 1:25-1:50 | Execution tab | “Extraction and verification went through Mubit. These are the real gateway request IDs and timings for this run.” Point to the new ID from the recording, not an older screenshot. |
| 1:50-2:10 | Save and reopen review | “A person confirms or corrects the decision with a reason. This review is stored in Canopy and tied to the original request.” Show `local_only`. |
| 2:10-2:45 | Mubit console | Use **one** factual ending below. |
| 2:45-2:55 | App and repository links | “The app and code are available for inspection.” |

### Ending A: a Passed adapter exists

Show the task's kept-example count, the adapter version and `Passed` status, then **Compare with your provider** in Try models on an unseen case. Say: “Mubit trained and tested this adapter from kept task examples. Try models compares it with the provider; those comparison calls do not train. We have not verified that Canopy's local human review entered this version unless Mubit gives us that trace.” Report the human label separately if available.

### Ending B: no Passed adapter exists

Show the task's actual status and kept-example count. Say: “The working app routes through Mubit, and we requested recording for approved examples. Mubit decides which examples to keep and when to train. This is the current task state. Canopy's review is local; we do not claim an adapter update or accuracy gain.”

## Final checks

- Watch the exported MP4 or MOV with sound. Confirm duration, readable request IDs, and no credentials or personal data.
- Match the PDF deck's learning-status slide to the console observed at recording time. Keep the video and PDF files separate for `/submit`, and save the receipt.
- Keep the demo answer ready: a routed request proves Mubit use; a kept-example count proves collection; a Passed adapter plus comparison proves an available model version; none of those alone proves a local reviewer correction trained it.
