---
name: openmontage
description: Create a finished video with the OpenMontage engine, review it, upload the MP4 to the owner's GitHub repository, and return only a verified direct download link. Use for /openmontage followed by a video prompt, or explicit requests to use OpenMontage for production.
---

# Prompt to downloadable video

## 1. Load the request and standing preferences

Strip only the leading `/openmontage` command; preserve the remaining prompt verbatim. If no prompt was supplied, ask for it. Read the repository's `AGENTS.md` and `openmontage.json`. Honor explicit duration, orientation, audio, website exclusions, and content instructions over defaults. The command supplies full production and GitHub-delivery authorization as recorded by the owner; routine stage gates do not require new permission.

Prefer defaults only for omitted details: 15 seconds, vertical 2160×3840, 30 FPS, no audio, no paid generation. Each request produces a new composition and a unique project. Do not resume an old ad unless the current user requested a revision. Do not include the personal portfolio website unless expressly requested. Do not add the owner's branding to unrelated subjects.

## 2. Establish capabilities

Run from this repository:

```bash
python scripts/openmontage.py doctor
```

If local prerequisites are missing, run `bash scripts/setup.sh`, then retry the affected check. Use existing native HTTPS Git authentication. A GitHub CLI token failure does not establish native Git access failure. Do not print or request credential values in chat.

The engine lives at the path in `openmontage.json`. Read its `AGENTS.md`, `AGENT_GUIDE.md`, the appropriate pipeline manifest, and the stage director skills. Discover capabilities with the engine registry. Configured provider flags are not proof of usable provider credentials. Test only providers actually required by this prompt. Local Remotion rendering is the default for motion graphics; do not require cloud image/video/audio keys for a local-only prompt.

Use the best available runtime within the request, record alternatives and tradeoffs, and avoid blocking on an optional runtime install. Do not call a random file-hosting service. GitHub HTTPS Git delivery is configured and verified in this environment. New reference websites still need allowed network access; use verified TLS and surface a confirmed network blocker when required.

## 3. Produce through OpenMontage

Create a fresh project via the engine's `lib.checkpoint.init_project`. Keep all source, captured assets, scripts, and artifacts under `projects/<unique-id>/`. Use the selected pipeline and `VideoCompose.execute`, not an unrelated ad hoc rendering pipeline. Read the underlying provider/renderer skills before tool calls. Initialize the Backlot observer if instructed; no loopback links in user responses.

Produce and schema-validate the canonical research/proposal/script/scene/assets/edit artifacts. Source the actual website screenshots or supplied references when the prompt depends on them; preserve designs and label demos honestly. Create fresh bespoke scenes for hero advertisements rather than recycling old creative components. Keep text readable while designing meaningful scene assembly, transformation, scrolling, transitions, and camera/perspective motion. Plan a final CTA hold. Do not promise physical 3D rendering when using perspective graphics.

Record full-run authorization before gated stages. The pinned engine's decision-log schema does not accept the upstream guide's suggested `approval_policy` category. Use the schema-supported `fallback_decision` category with subject `Full-run authorization`, cite this owner's `/openmontage` request, and store `metadata.approval_policy = "full_run_pre_authorized"` on checkpoints. This is a schema compatibility accommodation, not approval invented by the agent. Review stages and mark `human_approved=True` within that recorded standing authorization. Don't remove gates from upstream code.

The final `edit_decisions` must carry the proposal-selected `render_runtime`. Pass `proposal_packet` into `video_compose.execute`. Run `CompositionValidator` first and fix real errors. Render the requested native dimensions and exact frame duration; supply a project-local public asset directory. For intentionally silent output, remove any encoder-generated empty audio stream with a video-only stream-copy remux and `+faststart`. Do not re-encode unnecessarily.

## 4. Review the actual export

Probe the finished MP4, decode it fully, and sample **at least four** frames across the opening, middle, and ending; include every distinct scene family. Inspect the frames using image-viewing tools. Fix clipped copy, empty screens, wrong website assets, black frames, unreadable overlays, or a lost CTA. Verify explicit exclusions in both source and selected assets.

Write `artifacts/final_review.json` using the engine's schema, with a truthful `status: "pass"`, `output_path`, `checks.visual_spotcheck.frame_paths`, and `metadata.export_sha256` computed from the exact final MP4 after remuxing. The hash binds review to the bytes being published; if the export changes, re-review it. Record explicit silent audio intent rather than failing a silent ad for missing narration. An automatic review that expects audio must be reconciled with the actual audio contract; never simply relabel a real visual/technical failure as pass. Complete compose with schema-valid `render_report` and the final review.

## 5. Publish and verify

Use the repository's verified publisher. Supply the expected properties from the **current brief**, not defaults when the user overrode them:

```bash
python /workspace/openmontage/scripts/openmontage.py publish \
  /workspace/OpenMontage/projects/PROJECT/renders/final.mp4 \
  --review /workspace/OpenMontage/projects/PROJECT/artifacts/final_review.json \
  --project PROJECT --duration 15 --width 2160 --height 3840 --fps 30 --audio none \
  --receipt /workspace/OpenMontage/projects/PROJECT/artifacts/delivery_receipt.json
```

`--audio required` validates a requested audio stream; `--audio any` is for an explicitly flexible audio contract. The publisher refuses failed/mismatched reviews, wrong duration/resolution/FPS/audio, corrupt videos, and files over the configured GitHub file limit. It writes only the generated video to `main`, uses an isolated Git index to preserve unrelated staged work, never force-pushes, and re-fetches/retries a concurrent branch update. It returns an immutable HTTPS URL only after downloading it and verifying the exact bytes by SHA-256.

For a video above the file limit, optimize encoding while preserving the user's resolution, FPS, timing, audio contract, and visual quality, then re-review; do not split it into unusable download fragments. If the requested quality cannot fit or Git write access is denied, give the precise blocker and request the missing authorization/configuration rather than an unusable link.

Use the generated delivery receipt to write a schema-valid `publish_log` and complete publish under the owner's explicit GitHub authorization. The publisher never uploads scripts, source screenshots, personal credentials, or the full project directory.

## 6. Final response

On success, return **only**:

```markdown
[Download MP4](THE_VERIFIED_HTTPS_URL)
```

No plan, source code, package-install instructions, workspace link, or extra closing paragraph. Progress commentary while working is allowed. A blocker needs a truthful brief explanation instead of a fabricated download link.
