# Submitted Canopy demo walkthrough

The Night Shift submission is a 1:43 MP4 with male narration. It uses edited captures from a real run of [Canopy on Render](https://canopy-sbs0.onrender.com/) and point-in-time Mubit console screenshots. It is not an uninterrupted screen recording. The case, policy, and customer details are fictional.

| Time | What the video shows | What it establishes |
| --- | --- | --- |
| 0:00 to 0:09 | Canopy introduction and verification workspace | Canopy checks a claim against supplied policy and evidence. |
| 0:09 to 0:24 | The fictional refund case | The normal return window is 14 days; damaged items qualify within 30 days, even after use. The item was returned on day 21 with photos. |
| 0:24 to 0:36 | Training retention selected and the check run | Canopy requests recording for the fictional verification call and sends extraction and verification through Mubit. Recording requested does not mean an example was kept. |
| 0:36 to 0:51 | `VIOLATES` verdict, policy quote, and evidence | The claim that this refund must be refused contradicts the damaged-item exception. |
| 0:51 to 1:01 | Execution trace | The app shows fresh `mreq_` IDs and response details for the two Mubit calls. |
| 1:01 to 1:15 | Human review saved and reopened | A reviewer confirms the verdict with a written reason. The review is linked to its request and stored in Canopy. Reopening in the same session does not prove survival across a deployment restart. |
| 1:15 to 1:35 | Mubit Overview, matching Request, and current Task | The console shows 35 requests in the prior 24 hours, zero errors, the same refund case and `VIOLATES` reply, three calls in the newer task, zero of 25 kept examples, and no adapter serving. |
| 1:35 to 1:43 | Closing card | Canopy makes recurring decisions inspectable and gives reviewers a place to record their judgment. |

## What the evidence does and does not show

- The filmed verification ID is `mreq_01a170e534047400a5508a27e96bab37`. The Mubit console's own Request ID has a different format, so the match is based on the policy, evidence, claim, reply, and time.
- The console counts are a snapshot from the recording, not current dashboard totals. Its 0% routed metric is adapter or base routing under task rules. The matching call is listed in Mubit Requests as a Middleware request served by the configured provider.
- The newer task's zero of 25 kept examples must not be combined with an older task's count. No adapter version is shown in the video.
- The human action shown is a **confirmation** saved in Canopy. Mubit feedback submission is not connected. The video does not show a correction entering training or a model update.
- Chat with Canopy, the access example, the other verdict types, a restart test, and a provider-versus-adapter comparison are product or future evaluation topics, not scenes in this submission.
