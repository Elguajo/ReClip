# Claude Code Workflow Guide for ReClip

Pragmatic guide to installing Claude Code and using it to drive the work in `docs/ROADMAP.md`. This file is for **you, the human** — not for Claude. Once Claude Code is running in the repo, it should read `AGENTS.md` and `docs/ROADMAP.md`.

---

## 1. Install Claude Code

You have two options. Pick one.

### Option A — Native installer (recommended, no Node.js required)

**macOS / Linux:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (PowerShell, run as your user, not Administrator):**
```powershell
irm https://claude.ai/install.ps1 | iex
```

Or via WinGet:
```powershell
winget install Anthropic.ClaudeCode
```

### Option B — npm (requires Node.js 18+)

```bash
npm install -g @anthropic-ai/claude-code
```

If you hit `EACCES` on macOS/Linux, **don't use sudo**. Configure a user-local npm directory:
```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
npm install -g @anthropic-ai/claude-code
```

### Verify

```bash
claude --version
```

---

## 2. Authenticate

On first run, Claude Code opens your browser for OAuth. If you have a Claude Pro or Max subscription, log in there — usage counts against your subscription. If you don't, you'll need an API key from [console.anthropic.com](https://console.anthropic.com) (pay-as-you-go).

```bash
cd /path/to/ReClip
claude
# Browser opens → log in → approve → return to terminal
```

For ReClip-sized work, **Pro is enough** to start; if you'll be running long autonomous sessions daily, consider Max5.

---

## 3. Drop the context files into ReClip

In the root of your local ReClip clone, make sure these tracked files exist:

- `AGENTS.md` (provided)
- `docs/ROADMAP.md` (provided)

Both are picked up automatically by Claude Code. Commit them:

```bash
cd /path/to/ReClip
cp /path/to/downloaded/AGENTS.md .
mkdir -p docs
cp /path/to/downloaded/ROADMAP.md docs/ROADMAP.md
git add AGENTS.md docs/ROADMAP.md
git commit -m "docs: add AGENTS.md and ROADMAP.md for AI-assisted development"
```

---

## 4. Recommended working pattern

**Branch per phase.** Don't work on `main`.

```bash
git checkout -b phase-a1-quality-detection
```

When the phase is done and tests pass, commit, push, optionally PR, then start the next branch.

**One Claude Code session per phase.** Don't try to run multiple phases in one session — context gets muddled, and rate limits are per session window. Start fresh for each new phase.

**Read every diff before accepting.** Claude Code asks before modifying files. Use the prompt to review, especially in the first few sessions before you've calibrated trust.

---

## 5. Sequence of prompts

Below is the actual text to paste into Claude Code, in order. **Don't skip ahead** — Phase A0 ensures the AI has read the codebase before touching it, which dramatically improves Phase A1's quality.

### Phase A0 — Familiarization (20–30 minutes)

```
You are working on the ReClip repository. Read AGENTS.md and docs/ROADMAP.md
end to end before doing anything else. Then complete Phase A0:

1. Read app.py, job_manager.py, native.py end to end
2. Read templates/index.html and the contents of static/
3. Read existing tests under tests/

Don't run anything yet — just read and understand.

When done, write a summary covering:
- The overall request flow from "user pastes URL" to "file appears in
  save folder"
- The JobManager state machine: states, transitions, where progress is
  reported, how the UI gets updates
- The current quality picker behavior (is there one, where is it, what
  options does it offer today?)
- Anything in the code that already partially supports dynamic quality
  detection vs. what's hardcoded

Keep the summary concise but specific — file names and line numbers
where relevant. Don't propose changes yet.
```

After this, Claude Code returns a summary. **Read it carefully.** This is your chance to catch misunderstandings cheaply. If something looks wrong, say so:

```
On point 3 you said the quality dropdown is hardcoded in static/script.js,
but I see the options come from app.py. Re-read static/script.js around
line X and correct your understanding.
```

When the summary looks right:

```
Good. Now run `./reclip.sh` and confirm the app launches and the
existing flow works. Run `python -m pytest -q` and confirm all tests
pass. Report back with the results — don't make code changes.
```

When that's confirmed: **Phase A0 done.** Tick the checkboxes in `docs/ROADMAP.md`.

### Phase A1 — Dynamic Quality Detection

```
Phase A0 is complete. Now implement Phase A1 from docs/ROADMAP.md exactly
as specified. The acceptance criteria there are the contract.

Start by writing the tests (TDD), then make them pass:

1. tests/test_format_builder.py — for build_format_string()
2. tests/test_format_labels.py — for the friendly-label utility
3. Extend tests/test_app.py for the fetch-info endpoint and the
   download endpoint

After the tests are written and failing, show them to me before
implementing. I want to review the test fixtures and assertions before
you write production code.

Then implement the backend changes, then the frontend. Run the tests
after each step. Don't move on if tests fail.

When done, walk me through how to manually verify each acceptance
criterion in docs/ROADMAP.md Phase A1.
```

When Claude reports tests are written: **review them**. Test quality drives implementation quality. Push back on weak tests:

```
The fetch-info test mocks extract_info but doesn't include any audio-only
formats in the fixture. Real yt-dlp responses always include those. Add
two audio-only formats to the fixture and assert they're filtered out
of the height list.
```

When implementation is done, run through the acceptance criteria yourself with three real videos (one ≤1080p, one 4K, one 8K). When all pass:

```
Phase A1 acceptance criteria all pass on real videos. Commit the work
in clean, atomic commits — one for tests, one for backend, one for
frontend. Show me the commits before pushing.
```

Then mark Phase A1 done in `docs/ROADMAP.md` (or have Claude do it).

### Phase A2 — Conversion Presets

Start a fresh Claude Code session (`/clear` or quit and restart) for a clean context.

```
Phases A0 and A1 are complete and merged. Implement Phase A2 from
docs/ROADMAP.md.

The four presets are specified verbatim in docs/ROADMAP.md — copy them
exactly into a new presets.py module. Don't tweak the ffmpeg args.

Order of work:
1. Create presets.py with the constants and get_preset() helper
2. Write tests/test_presets.py
3. Extend job_manager.py with the 'converting' state and the ffmpeg
   subprocess management
4. Write tests/test_job_manager.py covering the new state machine
   (mock the ffmpeg subprocess, do not run real ffmpeg)
5. Add the convert_preset field to the download endpoint in app.py
   and extend tests/test_app.py
6. Add the Convert dropdown to templates/index.html and wire it up
   in static/script.js
7. Manually test all four presets on a real video and verify outputs
   with ffprobe

Show me the test files before writing the production code. Show me
the diff of job_manager.py before committing — that's the trickiest
file and I want to review the state machine changes carefully.
```

### Phase A3 — pywebview Migration

```
Phase A2 is complete and merged. Implement Phase A3 from docs/ROADMAP.md.

This phase changes the native wrapper but should NOT change any
frontend or backend behavior. The acceptance test is "the macOS app
looks and behaves identically to before; the Windows version works."

Order of work:
1. Add pywebview to requirements.txt with the right extras for Windows
2. Rewrite native.py to launch Flask in a thread and open a pywebview
   window pointing at it. Keep the same public functions/imports that
   other modules rely on.
3. Update build-macos-app.sh if needed for PyInstaller hidden imports
4. Test on macOS — must look and feel identical to current behavior

Don't attempt the Windows build yet — that's Phase A4. Just confirm
that pywebview works on macOS as a drop-in for the PyObjC wrapper.

I will manually test on Windows after you finish the macOS verification.
```

### Phase A4 — Windows Build & Release Pipeline

```
Phases A0-A3 are complete. Implement Phase A4 from docs/ROADMAP.md.

Order of work:
1. Write build-windows.ps1 mirroring build-macos-app.sh
2. Write the PyInstaller spec for Windows (single-folder is fine to
   start; we can move to .msi later)
3. Write .github/workflows/release.yml with the matrix build
4. Update README.md with the Windows installation section

The release workflow should NOT trigger on every push — only on tag
push (`v*`).

Show me the workflow YAML before committing. CI workflows are
security-sensitive (they have repo secrets), I want to review.
```

### Phase A5 — Polish

```
All previous phases are complete. Time for Phase A5.

1. Update README.md with screenshots of the new conversion picker
   and quality picker. Update the existing "Features" list.
2. Update the demo .mp4 if needed (I'll record a new one — don't
   try to generate video).
3. Walk through the issue tracker with me: list open issues, suggest
   labels and priorities for each.

When ready, we'll tag v1.1.0 and let CI cut the release.
```

---

## 6. Patterns that work well

**"Show me before you commit."** Always ask Claude to show diffs before staging. Default mode is incremental approval, but it's worth being explicit on risky files.

**"Write the test first."** TDD pairs unusually well with Claude Code. Tests force a clear spec before implementation, and Claude is good at making the tests pass without over-engineering.

**"Smallest change first."** If Claude proposes a 200-line refactor where a 20-line patch would do, push back: "Do the minimal change. We can refactor later if needed."

**Use `/clear` between phases.** Long sessions accumulate stale context. Fresh session = better focus.

**Use Plan Mode for unfamiliar work.** Type `/plan` (or use the keyboard shortcut shown by `/help`) before kicking off a phase. Claude will propose a plan without making changes; you approve or revise it before execution.

**Run tests in the same session.** Have Claude run `pytest -q` after edits. If it fails, Claude usually fixes it without you intervening — but only if it can see the failure in the same session.

---

## 7. Patterns that don't work

**Don't ask Claude to "do everything."** "Implement Phase A1 and A2 and A3" is too much for one session — context gets blown, quality drops, you lose ability to review intermediate steps.

**Don't approve all file writes blindly.** "Yes to all" mode is fine after the first few sessions when you've calibrated trust, but until then read every change.

**Don't skip Phase A0.** It feels redundant ("Claude can read the code on the fly"), but front-loading the read pays off in Phase A1 quality. Skipping it in tests we ran ourselves resulted in code that didn't match existing patterns.

**Don't run Claude on `main`.** Always a feature branch. Mistakes happen; branches are cheap.

---

## 8. When something goes wrong

**Claude makes a wrong change** → tell it specifically what's wrong and ask for a fix. If multiple things are wrong, revert with `git checkout -- <file>` and start the prompt again with more constraints.

**Tests fail and Claude can't fix them** → ask Claude to print the failing test output verbatim and explain the failure in its own words. Often this reveals a misunderstanding you can correct in one sentence.

**Session is lost / you ran out of context** → `/clear`, paste a fresh prompt with "Phase Ax is partially complete: <describe state>. Continue from <specific point>."

**A phase keeps drifting** → the spec in `docs/ROADMAP.md` may be ambiguous. Tighten it (commit the change), then continue.

---

## 9. After v1.1.0

The roadmap stops at A5. After release:

1. Collect feedback (you, your colleagues at RedMouse, anyone else who installs it)
2. Triage into Phase A6 candidates
3. Decide what's actually worth doing — most "wouldn't it be nice if" ideas don't survive a week of reflection
4. Update `docs/ROADMAP.md` with selected items, then start Phase B1 / A6.1 / whatever the numbering becomes

The roadmap is a living document. Keep it accurate.
