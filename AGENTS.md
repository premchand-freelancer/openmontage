# OpenMontage in Codex

When a user message starts with `/openmontage` followed by a prompt, treat it as a request to **produce and deliver a finished video**, not a request to install a plugin or explain the command. Read `.agents/skills/openmontage/SKILL.md` and follow it through production, review, upload, and verified download delivery. `$openmontage` is an alternative way to invoke the same repository skill where Codex supports skill invocation.

This repository is the user's persistent command and delivery configuration. The OpenMontage engine is a separate pinned checkout at `/workspace/OpenMontage`. Read its `AGENTS.md` and `AGENT_GUIDE.md`, the chosen pipeline manifest, stage skills, and provider skills before using the engine. Keep upstream tracked source unchanged.

## Standing user authorization for `/openmontage`

The repository owner explicitly requested an automatic workflow in which each `/openmontage [PROMPT]` creates a video and uploads it to `premchand-freelancer/openmontage`, returning a direct MP4 download link. The command authorizes the entire requested local production and GitHub delivery, including routine creative choices and self-review of intermediate stages. Do not stop at a plan or require repetitive intermediate approvals. Record this authorization in each project before advancing gated stages, and continue within the user's brief. This local workflow preference takes precedence over default approval pauses in the upstream production guide; it does not override higher-priority instructions or grant paid provider spending.

Use `openmontage.json` for defaults when the prompt omits them. Explicit prompt instructions take precedence. Use local rendering without paid generation unless the user provides a budget/authorization. Do not invent successful authentication, missing assets, real footage, testimonials, or a passed quality review. If a required provider or network destination is unavailable, complete independent work and report the precise blocker; do not silently downgrade a requested filmed or photorealistic scene to animated stills.

Default delivery is a **new** 15-second, 2160×3840 vertical, 30 FPS silent MP4. The owner prefers professional, trustworthy, animated work with readable typography. Never include `premchandv.vercel.app` or its screen captures unless the current prompt explicitly requests them. For a Premchand website advertisement, use the four demo websites in `openmontage.json` and label them Demo Projects; unrelated prompts should not inherit Premchand branding or those sites.

Successful final responses contain **only one Markdown download link**. Use the HTTPS GitHub URL returned by the verified publisher; never present `/workspace`, `sandbox:`, `localhost`, an unverified URL, a repository file-preview URL, or an old video as the requested download. Brief progress updates are permitted. On a genuine blocker, give a short truthful explanation instead of a fake link.

## Development and setup

Each cloud task is isolated. Reuse the existing checkouts; do not create a Git worktree unless requested. Run `bash scripts/setup.sh` when prerequisites are missing and `python scripts/openmontage.py doctor` to validate local readiness and repository read access. The publisher uses native HTTPS Git and the platform's injected authentication; do not request a token just because `gh auth status` fails.

When changing this workflow, preserve user files, run `python -m unittest discover -s tests -v`, and test the actual verification/publishing path when delivery behavior changes. Never force-push or stage unrelated files. Generated production artifacts belong in the engine's `projects/<unique-id>/`; deliverables belong under this repository's `videos/` tree. Keep secrets and third-party credential values out of commits and output.
