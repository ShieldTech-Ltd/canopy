# Two-minute Canopy demo

Submit an MP4 or MOV of at most **2:00** and **300 MB**. The submission has no deck. The team fills the private `/submit` form; judges inspect the default `main` branch and README at **08:00 Sunday 25 October, London time**. The earlier announcement also called **07:00** the code freeze, so finish the merge before 07:00 unless the organisers explicitly supersede that cutoff. The UK clock moves back at 02:00.

Use the **Recurring tasks** track and fictional or approved non-sensitive cases. Show a live request, not a prepared answer. Keep secrets and personal data out of the recording.

## Preflight on the deployed build

1. Confirm Render's deployed commit is the intended commit on `main`, then open `/livez`. Its build label is a release string, not a Git commit hash. `/api/status` showing `configured=true` proves key presence only.
2. Select training retention for the fictional case, then run it through the deployed app. Check the verdict, policy quote, and fresh `mreq_` IDs. Match the verification ID in Mubit Requests. If Mubit is unavailable, show the error honestly and wait for service recovery before recording a successful run.
3. Save a human review, reopen the case in the same browser session, and confirm the reason and original request ID remain. A review of a correct verdict is a **confirmation**. A different verdict is a **correction**. Both are currently `local_only`.
4. Have the teammate who owns the Mubit project read the **current verification task's** kept-example count, adapter version, and test result. The 25 October instruction change may have created a new Mubit task. Do not combine counts across task versions. A recorded call is not necessarily a kept example. Use the adapter ending below only if a version is `Passed` and available in Try models.
5. Check whether Render uses a persistent disk for `CANOPY_AGENT_DB` and whether the case survives a restart. Reopening within one deployment proves SQLite storage, not persistence across redeploys.

## Capture sequence (target 1:50)

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | Verify a case and the built-in refund case | “Canopy checks repeatable support decisions against the policy and evidence supplied for each case.” |
| 0:15–0:45 | Run the case and reveal the result | “This fictional policy has a 30-day damaged-item exception. The claim says the day-21 refund must be refused. The verdict is `VIOLATES`; here is the policy wording behind it.” |
| 0:45–1:05 | Evidence and Execution tabs | “These are the supplied facts, the actual Mubit request IDs, and this run's measured time.” Do not claim a speedup without a measured manual baseline. |
| 1:05–1:25 | Save the human verdict and reason; reopen it | “A reviewer can confirm or correct the result. Canopy stores that review with its originating request ID.” Show the `local_only` status. |
| 1:25–1:50 | Mubit console, then app | Use **one** factual ending below. Leave a few seconds for the app and repository URL. |

### If a passing adapter is available

Show the task's kept-example count, the adapter version and `Passed` result, then **Compare with your provider** in Try models using an unseen case with an independent human label. State the provider and adapter answers separately. Try models comparisons do not train. A passing version does **not** prove that Canopy's locally saved review entered training, so do not attribute a changed answer to that review without an accepted correction trace.

### If no passing adapter is available

Show the task's actual state. Say: “The app routes through Mubit and can request recording for approved cases. This is the current kept-example and adapter status. Reviewer decisions remain in Canopy, so we do not claim a model update or an accuracy gain.”

## Final recording check

- Watch the exported file with sound. Confirm duration, file size, legible request IDs, and no secrets.
- Match every learning claim to the console state observed in the recording. A new answer after editing the policy or evidence shows changed context, not learning.
- A live routed request, a stored human review, a kept example, and a passing adapter are distinct facts. Show each only when verified.
