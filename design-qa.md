# Terminal workspace QA

Scope: desktop event demo. This is an intentional terminal-style redesign, not a pixel-identical Claude Code clone.

Source visual truth: `docs/demo/before.jpg`, the previously deployed Canopy interface, plus the requested terminal workflow: readable monospace output, restrained surfaces, a prompt and real tool activity.

Implementation: `http://127.0.0.1:8190/`, captured at the default Chrome viewport. `docs/demo/terminal.jpg` shows a real completed Mubit verification. Source and implementation captures are both 1536 x 639 pixels at the same browser density; no image scaling was applied. The before capture is an empty conversation and the implementation capture contains a result, so this is a structural comparison, not a claim of matching message geometry.

## Comparison and fixes

The before and after captures were emitted together and visually inspected. The redesign removes the large dashboard counters, green message bubbles and fake training chart. Case navigation, a readable result, and actual gateway request events replace them. These are intentional changes requested by the user.

1. Initial preview: sample cases fell too far below the fold. Reduced welcome spacing, made the workflow steps wrap horizontally, and shortened the composer. The revised desktop preview shows the sample actions and persistent Run check button.
2. Initial preview: old started events retained a running visual state after completion. The trace now renders those historical events as started once their completed or failed event exists. Live running state remains driven by server events.
3. Initial missing-evidence flow scrolled to the bottom of the form. Completion now aligns the result turn with the top of the transcript so its request for missing facts is readable.
4. Added a top-level New case button so the primary action remains available when the sidebar is hidden.

## Required visual surfaces

- Typography: system monospace stack, readable result hierarchy and wrapping request IDs. No external font request is needed.
- Layout: independent transcript and inspector scrolling; the prompt remains visible at the tested laptop viewport.
- Colour: near-black neutral surfaces with a restrained warm accent. Verdicts include text labels as well as colour. Secondary text was brightened after the first inspection.
- Assets: no decorative artwork or approximated product icons. The wordmark is text; execution output and forms use native controls.
- Copy: no claimed trained adapters, invented confidence, fabricated accuracy or simulated reasoning steps. The inspector labels itself a read-only tool trace. Reviews explicitly report local storage.

## Browser checks

- Loaded a built-in fictional case and ran extraction and verification through Mubit.
- Observed real request IDs and server-measured response times.
- Opened the review form, saved a justified review, restarted the preview server and reopened the persisted case.
- Ran an incomplete case; the workflow requested missing policy and evidence.
- Supplied the missing inputs and received a fresh successful verification.
- Inspected Evidence and Execution tabs and checked captured browser console errors (none).
- No horizontal overflow was observed at the tested desktop viewport.

Mobile limitation: the browser viewport override did not change the controlled tab's width, so mobile rendering is not claimed as verified. The override was reset. Mobile CSS and primary controls exist, but an actual device check remains follow-up work.

## Functional evidence

11 focused runtime tests pass on Windows. All 32 repository tests pass in the Linux image with `CANOPY_BIND_HOST=127.0.0.1` for the unit-test environment. The production Docker image builds. Unit tests mock provider responses; browser Mubit checks used actual calls.

No actionable P0/P1/P2 desktop UI findings remain in the inspected states. Real correction-to-adapter integration is an application readiness blocker documented separately; this visual QA result does not assert it works.

final result: passed
