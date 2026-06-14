# Google Colab + GitHub Workflow

This file is a copy/paste guide for using a normal GitHub Python repo inside Google Colab, editing files, running tests, committing changes, pushing a branch, and opening a pull request.

Configured repo:

```text
GitHub repo: donnywpolson-sudo/US_stocks_swing_model
Colab path:  /content/US_stocks_swing_model
```

To reuse this for another repo, change only:

```python
REPO_SLUG = "donnywpolson-sudo/US_stocks_swing_model"
```

---

## 0. Rules

Colab is temporary. Any file changes vanish unless you commit and push them to GitHub.

Do not paste or print secrets, GitHub tokens, API keys, passwords, patient/work data, or proprietary work files.

Use `%cd`, not `!cd`, when changing directories manually in Colab. `%cd` persists across cells. `!cd` does not.

Do not commit generated data/artifacts unless intentionally approved. This workflow blocks common artifact folders:

```text
data/
reports/
logs/
models/
```

---

## 1. Create a GitHub token

You need a GitHub Personal Access Token to push from Colab.

Use a **fine-grained token**.

GitHub path:

```text
GitHub â profile photo â Settings â Developer settings â Personal access tokens â Fine-grained tokens â Generate new token
```

Recommended settings:

```text
Token name: Colab US stocks push
Expiration: 30 or 90 days
Resource owner: donnywpolson-sudo
Repository access: Only selected repositories
Repository: US_stocks_swing_model
Permissions:
  Contents: Read and write
  Metadata: Read-only
```

Only add this extra permission if you need to edit GitHub Actions files under `.github/workflows/`:

```text
Workflows: Read and write
```

After generating the token, copy it immediately. It usually starts with:

```text
github_pat_...
```

---

## 2. Add token to Colab Secrets

In Google Colab:

```text
Left sidebar â key icon / Secrets â Add new secret
Name: GITHUB_TOKEN
Value: paste your github_pat_... token
Notebook access: ON
```

Never paste the token into a normal code cell, markdown cell, chat, screenshot, or committed file.

Test secret loading without printing the token:

```python
from google.colab import userdata

token = userdata.get("GITHUB_TOKEN")
print("Token loaded:", bool(token))
print("Token prefix OK:", token.startswith(("github_pat_", "ghp_")) if token else False)
```

---

## 3. One-cell setup script

Open a new Colab notebook and run this entire cell.

It will:

- load your GitHub token from Colab Secrets
- clone the repo if missing
- enter the repo folder
- create or switch to a working branch
- install dependencies
- run available tests
- show Git status

```python
# ==========================================
# GOOGLE COLAB â GITHUB SETUP WORKFLOW
# Repo: donnywpolson-sudo/US_stocks_swing_model
# ==========================================

import os
import sys
import subprocess
from pathlib import Path

# -------- USER SETTINGS --------
REPO_SLUG = "donnywpolson-sudo/US_stocks_swing_model"
BRANCH = "colab-work"
GIT_NAME = "Donny Polson"
GIT_EMAIL = "donnywpolson@gmail.com"

RUN_INSTALL = True
RUN_TESTS = True
# -------------------------------

REPO_NAME = REPO_SLUG.split("/")[-1]
REPO_DIR = Path("/content") / REPO_NAME
CLEAN_REMOTE = f"https://github.com/{REPO_SLUG}.git"


def run(cmd, cwd=None, check=True, display=None, env=None):
    """Run a shell command safely. Use display=... to avoid printing secrets."""
    shown = display if display is not None else " ".join(map(str, cmd))
    print(f"\n$ {shown}")
    p = subprocess.run(
        list(map(str, cmd)),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print(p.stdout)
    if check and p.returncode != 0:
        raise SystemExit(f"Command failed: {shown}")
    return p


def get_token(required=False):
    try:
        from google.colab import userdata
        token = userdata.get("GITHUB_TOKEN")
    except Exception:
        token = None
    if required and not token:
        raise SystemExit("Missing Colab Secret: GITHUB_TOKEN")
    return token


def clone_or_enter_repo():
    token = get_token(required=False)

    if not REPO_DIR.exists():
        if token:
            auth_remote = f"https://x-access-token:{token}@github.com/{REPO_SLUG}.git"
            run(
                ["git", "clone", auth_remote, str(REPO_DIR)],
                cwd="/content",
                display=f"git clone https://x-access-token:***@github.com/{REPO_SLUG}.git {REPO_DIR}",
            )
        else:
            run(["git", "clone", CLEAN_REMOTE, str(REPO_DIR)], cwd="/content")
    else:
        print(f"Repo folder already exists: {REPO_DIR}")

    if not (REPO_DIR / ".git").exists():
        raise SystemExit(f"Not a Git repo: {REPO_DIR}")

    os.chdir(REPO_DIR)
    run(["git", "remote", "set-url", "origin", CLEAN_REMOTE], cwd=REPO_DIR, check=False)
    print(f"\nUsing repo folder: {REPO_DIR}")


def setup_git_branch():
    run(["git", "config", "user.name", GIT_NAME], cwd=REPO_DIR)
    run(["git", "config", "user.email", GIT_EMAIL], cwd=REPO_DIR)

    # Fetch may fail for private repos if tokenless remote is used. Not fatal for setup.
    run(["git", "fetch", "origin"], cwd=REPO_DIR, check=False)

    existing = run(["git", "branch", "--list", BRANCH], cwd=REPO_DIR, check=False).stdout.strip()
    if existing:
        run(["git", "checkout", BRANCH], cwd=REPO_DIR)
    else:
        run(["git", "checkout", "-b", BRANCH], cwd=REPO_DIR)

    run(["git", "branch", "--show-current"], cwd=REPO_DIR, check=False)


def install_dependencies():
    run([sys.executable, "-m", "pip", "install", "-U", "pip", "pytest"], cwd=REPO_DIR)

    req = REPO_DIR / "requirements.txt"
    if req.exists():
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=REPO_DIR)
    else:
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "pandas",
                "numpy",
                "pyarrow",
                "pyyaml",
                "scikit-learn",
                "matplotlib",
            ],
            cwd=REPO_DIR,
        )


def run_checks():
    scripts_dir = REPO_DIR / "scripts"
    if scripts_dir.exists():
        py_files = sorted(scripts_dir.rglob("*.py"))
        if py_files:
            print(f"\nCompiling {len(py_files)} script files...")
            for py in py_files:
                rel = py.relative_to(REPO_DIR)
                run([sys.executable, "-m", "py_compile", str(rel)], cwd=REPO_DIR, check=False)

    tests_dir = REPO_DIR / "tests"
    if tests_dir.exists():
        run([sys.executable, "-m", "pytest", "-q"], cwd=REPO_DIR, check=False)
    else:
        print("\nNo tests/ folder found. Skipping pytest.")


def show_status():
    run(["git", "status", "--short"], cwd=REPO_DIR, check=False)
    print("\nReady. Edit files from Colab left sidebar:")
    print(f"Files â {REPO_NAME}")


clone_or_enter_repo()
setup_git_branch()

if RUN_INSTALL:
    install_dependencies()

if RUN_TESTS:
    run_checks()

show_status()
```

---

## 4. Edit files in Colab

Use the Colab file browser:

```text
Left sidebar â Files â US_stocks_swing_model
```

Open files under folders like:

```text
scripts/
tests/
configs/
docs/
```

Do not edit or commit generated artifacts unless you intentionally mean to:

```text
data/
reports/
logs/
models/
```

---

## 5. Optional: apply an AI-generated patch

Ask AI for a unified diff, then apply it like this:

```python
%%bash
cd /content/US_stocks_swing_model
cat > /tmp/patch.diff <<'PATCH'
PASTE_UNIFIED_DIFF_HERE
PATCH

git apply --check /tmp/patch.diff && git apply /tmp/patch.diff

git status --short
git diff --stat
```

If `git apply --check` fails, do not force it. Ask AI to regenerate the patch against the current file contents.

---

## 6. Re-run checks after editing

```python
%cd /content/US_stocks_swing_model
!python -m py_compile $(find scripts -name "*.py" 2>/dev/null) || true
!python -m pytest -q
!git status --short
!git diff --stat
```

For a targeted test:

```python
%cd /content/US_stocks_swing_model
!python -m pytest tests -q
```

---

## 7. Commit and push cell

Run this only after you edited files and reviewed the diff.

It will:

- block accidental commits from `data/`, `reports/`, `logs/`, and `models/`
- block files over 25 MB
- show status and diff stats
- commit
- push the branch to GitHub
- print the pull request link

```python
# ==========================================
# COMMIT + PUSH FROM COLAB TO GITHUB
# ==========================================

import os
import sys
import subprocess
from pathlib import Path

REPO_SLUG = "donnywpolson-sudo/US_stocks_swing_model"
REPO_NAME = REPO_SLUG.split("/")[-1]
REPO_DIR = Path("/content") / REPO_NAME
BRANCH = "colab-work"
COMMIT_MESSAGE = "Colab update"

BLOCKED_TOP_LEVEL_DIRS = {"data", "reports", "logs", "models"}
MAX_FILE_MB = 25


def run(cmd, cwd=REPO_DIR, check=True, display=None, env=None):
    shown = display if display is not None else " ".join(map(str, cmd))
    print(f"\n$ {shown}")
    p = subprocess.run(
        list(map(str, cmd)),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print(p.stdout)
    if check and p.returncode != 0:
        raise SystemExit(f"Command failed: {shown}")
    return p


def get_token():
    try:
        from google.colab import userdata
        token = userdata.get("GITHUB_TOKEN")
    except Exception:
        token = None
    if not token:
        raise SystemExit("Missing Colab Secret: GITHUB_TOKEN")
    return token


def changed_files():
    out = run(["git", "status", "--porcelain"], check=False).stdout.splitlines()
    files = []
    for line in out:
        if not line.strip():
            continue
        # Handles normal porcelain lines like: ' M path' or '?? path'
        path = line[3:].strip()
        if path:
            files.append(path)
    return files


def safety_check(files):
    problems = []
    for f in files:
        top = f.split("/", 1)[0]
        if top in BLOCKED_TOP_LEVEL_DIRS:
            problems.append(f"blocked artifact folder: {f}")

        p = REPO_DIR / f
        if p.exists() and p.is_file():
            size_mb = p.stat().st_size / (1024 * 1024)
            if size_mb > MAX_FILE_MB:
                problems.append(f"file too large ({size_mb:.1f} MB): {f}")

    if problems:
        print("\nSAFETY BLOCKED COMMIT")
        for item in problems:
            print(" -", item)
        raise SystemExit("Refusing to commit blocked or large files.")


if not (REPO_DIR / ".git").exists():
    raise SystemExit(f"Not a Git repo: {REPO_DIR}")

os.chdir(REPO_DIR)
run(["git", "checkout", BRANCH], check=False)

files = changed_files()
if not files:
    print("No changes to commit.")
else:
    safety_check(files)

    run(["git", "status", "--short"], check=False)
    run(["git", "diff", "--stat"], check=False)
    run(["git", "diff", "--", "."], check=False)

    run(["git", "add", "."])
    run(["git", "commit", "-m", COMMIT_MESSAGE])

    token = get_token()
    auth_remote = f"https://x-access-token:{token}@github.com/{REPO_SLUG}.git"
    run(
        ["git", "remote", "set-url", "origin", auth_remote],
        display=f"git remote set-url origin https://x-access-token:***@github.com/{REPO_SLUG}.git",
    )
    run(["git", "push", "-u", "origin", BRANCH])
    run(["git", "remote", "set-url", "origin", f"https://github.com/{REPO_SLUG}.git"], check=False)

    print("\nPushed successfully.")
    print(f"Open PR: https://github.com/{REPO_SLUG}/compare/main...{BRANCH}")
```

---

## 8. Open the pull request

After pushing, open:

```text
https://github.com/donnywpolson-sudo/US_stocks_swing_model/compare/main...colab-work
```

Use:

```text
base: main
compare: colab-work
```

---

## 9. Useful AI prompts

### Prompt A â safe code edit

```text
You are editing my GitHub repo in Google Colab.

Repo: donnywpolson-sudo/US_stocks_swing_model
Task: [describe the exact task]

Allowed files:
- [list exact files]

Hard constraints:
- Do not edit data/, reports/, logs/, models/, or generated artifacts.
- Do not add secrets, tokens, passwords, credentials, or API keys.
- Do not make broad refactors.
- Preserve existing public function names unless absolutely necessary.
- Prefer the smallest patch that fixes the issue.

Return:
1. Short plan
2. Exact files to change
3. Unified diff only
4. Tests to run in Colab
```

### Prompt B â test failure fix

```text
I am running this repo in Google Colab:

donnywpolson-sudo/US_stocks_swing_model

Here is the failing command:
[paste command]

Here is the full error output:
[paste traceback]

Fix request:
- Diagnose root cause.
- Provide the smallest safe patch.
- Do not edit generated artifacts.
- Do not change test intent just to make tests pass.
- Return a unified diff I can apply with git apply.
```

### Prompt C â code review before commit

```text
Review this git diff before I commit.

Goal:
[describe task]

Diff:
[paste git diff]

Check for:
- logic bugs
- data leakage
- brittle paths
- accidental generated artifact changes
- missing tests
- overbroad edits

Return:
1. Commit / do not commit recommendation
2. Any must-fix issues
3. Suggested commit message
```

### Prompt D â pull request description

```text
Write a concise GitHub pull request description.

Repo: donnywpolson-sudo/US_stocks_swing_model
Branch: colab-work

Goal:
[describe goal]

Changed files:
[paste git diff --stat]

Tests run:
[paste test commands and results]

Format:
- Summary
- Changes
- Tests
- Risk / notes
```

---

## 10. Common problems

### Problem: Colab says âNo resultsâ when opening GitHub repo

That usually means Colab is looking for `.ipynb` notebook files. A normal Python repo will not show there. Use `git clone` from a Colab code cell instead.

### Problem: `cd` did not persist

Use:

```python
%cd /content/US_stocks_swing_model
```

Do not use:

```python
!cd /content/US_stocks_swing_model
```

### Problem: authentication failed on push

Check:

```python
from google.colab import userdata
print(bool(userdata.get("GITHUB_TOKEN")))
```

Then verify the GitHub token has:

```text
Repository: US_stocks_swing_model
Contents: Read and write
```

### Problem: push rejected

Create a new branch name and push again:

```python
%cd /content/US_stocks_swing_model
!git checkout -b colab-work-2
!git push -u origin colab-work-2
```

### Problem: accidentally edited generated files

Reset unwanted files before commit:

```python
%cd /content/US_stocks_swing_model
!git restore data reports logs models 2>/dev/null || true
!git status --short
```

---

## 11. Minimal daily workflow

```python
# Setup
%cd /content
!git clone https://github.com/donnywpolson-sudo/US_stocks_swing_model.git
%cd /content/US_stocks_swing_model
!git checkout -b colab-work
!python -m pip install -r requirements.txt || python -m pip install pytest pandas numpy pyarrow pyyaml scikit-learn

# Edit files in left sidebar, then test
!python -m pytest -q
!git status --short
!git diff --stat

# Commit/push using the full commit cell above
```

