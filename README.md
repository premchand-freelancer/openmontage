# OpenMontage for Codex

Start a new Codex chat with **this repository and its prepared OpenMontage cloud environment selected**, then send:

```text
/openmontage Make a 15-second professional, animation-rich ad for Premchand V using the four demo websites. Exclude my personal portfolio.
```

Codex follows the repository instructions, produces a new video through OpenMontage, checks the rendered export, uploads the MP4 to this repository, and ends with a verified download link. This is a repository-scoped agent workflow; it does not register a global native slash command in unrelated Codex chats. `$openmontage` can also invoke the repository skill in clients that support skill invocation.

Defaults: 15 seconds, 4K vertical 2160×3840, 30 FPS, silent, local rendering without paid generation. Your prompt can override them. The personal portfolio website is excluded unless expressly requested. The Premchand brand/demo-site preferences apply only to relevant website advertisements.

## One-time cloud setup

This chat prepares the environment configuration. Use **Save and publish** in the environment editor to publish the updated snapshot/configuration, then select that environment for new chats. Runtime authentication and optional cloud providers are checked again in each chat; live servers do not carry over. New websites and providers can require network allowlist additions or provider credentials. Never paste credentials into chat.

The reusable install command is:

```bash
bash /workspace/openmontage/scripts/setup.sh
python /workspace/openmontage/scripts/openmontage.py doctor
```

The engine is pinned to a reviewed upstream revision in `openmontage.json`. Setup uses the existing engine checkout when present and does not rewrite upstream tracked source, dependency declarations, or lockfiles. The local renderer configuration selects system Chromium and H.264-compatible pixel output.

## Delivery

Videos are stored under `videos/<project>/`. The uploader publishes only the reviewed MP4, avoids overwriting earlier outputs, never force-pushes, and verifies the complete HTTPS download. URLs use an immutable Git commit, so subsequent videos cannot change old download links. Public repository files are publicly downloadable.

Native Git uses Codex's GitHub authentication. A failing `gh auth status` alone does not mean Git access is missing. Repository write permission must be available in the new environment. The uploader uses Git rather than release APIs so it does not require a separate API token. GitHub's single-file limit is handled conservatively at 95 MB; very large videos need reviewed encoding optimization or a separately authorized hosting destination. Keeping many videos in Git increases repository size.

## Workflow checks

Publication requires a passed final review with four inspected exported frames and `metadata.export_sha256` matching the final MP4. This prevents a review of an earlier render from authorizing a changed file.

```bash
python -m unittest discover -s tests -v
python scripts/openmontage.py verify VIDEO.mp4 --duration 15 --width 2160 --height 3840 --fps 30 --audio none
python scripts/openmontage.py publish VIDEO.mp4 --review FINAL_REVIEW.json --project PROJECT --duration 15 --width 2160 --height 3840 --fps 30 --audio none
```

The instructions are an agent workflow, not a standalone natural-language video-generation server. A new-chat production run still depends on the prompt, available assets, render capacity, GitHub write access, and any explicitly requested providers. On a real blocker Codex reports what is missing rather than inventing a successful video or download.
