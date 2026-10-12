#!/usr/bin/env bash
set -euo pipefail
task_repository="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mapfile -t task_settings < <(python - "$task_repository/openmontage.json" <<'PY'
import json,sys
c=json.load(open(sys.argv[1]))
for k in ['directory','repository','revision','python','browser']: print(c['engine'][k])
PY
)
task_engine="${task_settings[0]}"
task_engine_url="${task_settings[1]}"
task_revision="${task_settings[2]}"
task_python="${task_settings[3]}"
task_browser="${task_settings[4]}"
python - "$task_repository" <<'PY'
from pathlib import Path
import sys
router=Path('/workspace/AGENTS.md')
if not router.exists():
 router.write_text(f"# OpenMontage environment router\n\nWhen a user invokes `/openmontage [PROMPT]`, read `{sys.argv[1]}/AGENTS.md` and `{sys.argv[1]}/.agents/skills/openmontage/SKILL.md`. This is the owner's automatic production and verified GitHub-download workflow. Use the standing configuration in `{sys.argv[1]}/openmontage.json`. For other tasks, follow the selected repository's instructions.\n")
PY
for task_binary in git python node npm ffmpeg ffprobe; do
  command -v "$task_binary" >/dev/null || { echo "Missing required executable: $task_binary" >&2; exit 1; }
done
test -x "$task_browser" || { echo "Missing system Chromium: $task_browser" >&2; exit 1; }
if [ ! -d "$task_engine" ]; then
  git clone --no-checkout "$task_engine_url" "$task_engine"
  git -C "$task_engine" checkout --detach "$task_revision"
fi
test "$(git -C "$task_engine" rev-parse HEAD)" = "$task_revision" || {
  echo "Existing engine revision differs from configuration; preserve it and resolve explicitly." >&2; exit 1;
}
if [ ! -x "$task_python" ]; then
  python -m venv "$(dirname -- "$(dirname -- "$task_python")")"
fi
"$task_python" -m pip install --disable-pip-version-check -r "$task_engine/requirements.txt" playwright
task_lock_hash="$(sha256sum "$task_engine/remotion-composer/package-lock.json" | cut -d ' ' -f 1)"
mkdir -p "$task_repository/.openmontage-setup"
task_stamp="$task_repository/.openmontage-setup/node-lock.sha256"
if [ ! -d "$task_engine/remotion-composer/node_modules" ] || [ ! -f "$task_stamp" ] || [ "$(cat "$task_stamp")" != "$task_lock_hash" ]; then
  (cd "$task_engine/remotion-composer" && npm ci --cache /workspace/npm-cache --no-audit --no-fund)
  printf '%s\n' "$task_lock_hash" > "$task_stamp"
fi
python - "$task_engine/remotion-composer/remotion.config.ts" "$task_browser" <<'PY'
from pathlib import Path
import json,sys
p=Path(sys.argv[1]);browser=sys.argv[2]
if not p.exists():
 p.write_text("// Local cloud renderer configuration.\nimport {Config} from '@remotion/cli/config';\n"+f"Config.setBrowserExecutable({json.dumps(browser)});\nConfig.setPixelFormat('yuv420p');\nConfig.setVideoImageFormat('jpeg');\n")
elif 'setBrowserExecutable' not in p.read_text():
 raise SystemExit('Existing renderer configuration is preserved; specify the system browser before rendering.')
PY
python "$task_repository/scripts/openmontage.py" doctor --render
