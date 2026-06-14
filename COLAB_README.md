# Google Colab + GitHub Workflow

Use this repo from Google Colab: clone -> edit -> test -> commit -> push -> open PR.

Configured repo:

```text
GitHub repo: donnywpolson-sudo/US_stocks_swing_model
Colab path:  /content/US_stocks_swing_model
Branch:      colab-work
```

Colab is temporary. Changes disappear unless you commit and push.

Do not paste or commit secrets, tokens, API keys, patient/work data, or generated artifacts.

Blocked artifact folders in this workflow:

```text
data/
reports/
logs/
models/
```

---

## 1. Create GitHub token once

Create a fine-grained GitHub Personal Access Token:

```text
GitHub -> Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens -> Generate new token
```

Recommended token settings:

```text
Token name: Colab US stocks push
Expiration: 30 or 90 days
Resource owner: donnywpolson-sudo
Repository access: Only selected repositories
Repository: US_stocks_swing_model
Permissions:
  Contents: Read and write
  Metadata: Read-only
Optional only if editing .github/workflows/:
  Workflows: Read and write
```

Copy the token immediately. It usually starts with `github_pat_...`.

---

## 2. Add token to Colab Secrets

In Colab:

```text
Left sidebar -> Secrets/key icon -> Add new secret
Name: GITHUB_TOKEN
Value: paste github_pat_... token
Notebook access: ON
```

Test without printing the token:

```python
from google.colab import userdata

token = userdata.get("GITHUB_TOKEN")
print("Token loaded:", bool(token))
print("Prefix OK:", token.startswith(("github_pat_", "ghp_")) if token else False)
```

---

## 3. One-cell setup

Run this in a new Colab code cell.

```python
import os
import sys
import subprocess
from pathlib import Path

REPO_SLUG = "donnywpolson-sudo/US_stocks_swing_model"
BRANCH = "colab-work"
GIT_NAME = "Donny Polson"
GIT_EMAIL = "donnywpolson@gmail.com"
RUN_INSTALL = True
RUN_TESTS = True

REPO_NAME = REPO_SLUG.split("/")[-1]
REPO_DIR = Path("/content") / REPO_NAME
CLEAN_REMOTE = f"https://github.com/{REPO_SLUG}.git"


def run(cmd, cwd=None, check=True, display=None):
    shown = display or " ".join(map(str, cmd))
    print(f"\n$ {shown}")
    p = subprocess.run(
        list(map(str, cmd)),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
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
    token = get_token(False)

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
        print(f"Repo already exists: {REPO_DIR}")

    if not (REPO_DIR / ".git").exists():
        raise SystemExit(f"Not a Git repo: {REPO_DIR}")

    os.chdir(REPO_DIR)
    run(["git", "remote", "set-url", "origin", CLEAN_REMOTE], cwd=REPO_DIR, check=False)
    print(f"\nUsing repo: {REPO_DIR}")


def setup_branch():
    run(["git", "config", "user.name", GIT_NAME], cwd=REPO_DIR)
    run(["git", "config", "user.email", GIT_EMAIL], cwd=REPO_DIR)
    run(["git", "fetch", "origin"], cwd=REPO_DIR, check=False)

    existing = run(["git", "branch", "--list", BRANCH], cwd=REPO_DIR, check=False).stdout.strip()
    if existing:
        run(["git", "checkout", BRANCH], cwd=REPO_DIR)
    else:
        run(["git", "checkout", "-b", BRANCH], cwd=REPO_DIR)


def install_dependencies():
    run([sys.executable, "-m", "pip", "install", "-U", "pip", "pytest"], cwd=REPO_DIR)
    req = REPO_DIR / "requirements.txt"
    if req.exists():
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=REPO_DIR)
    else:
        run([
            sys.executable, "-m", "pip", "install",
            "pandas", "numpy", "pyarrow", "pyyaml", "scikit-learn", "matplotlib",
        ], cwd=REPO_DIR)


def run_checks():
    scripts = sorted((REPO_DIR / "scripts").rglob("*.py")) if (REPO_DIR / "scripts").exists() else []
    for py in scripts:
        run([sys.executable, "-m", "py_compile", str(py.relative_to(REPO_DIR))], cwd=REPO_DIR, check=False)

    if (REPO_DIR / "tests").exists():
        run([sys.executable, "-m", "pytest", "-q"], cwd=REPO_DIR, check=False)
    else:
        print("No tests/ folder found. Skipping pytest.")


clone_or_enter_repo()
setup_branch()

if RUN_INSTALL:
    install_dependencies()

if RUN_TESTS:
    run_checks()

run(["git", "status", "--short"], cwd=REPO_DIR, check=False)
print(f"\nReady. Edit files from: Left sidebar -> Files -> {REPO_NAME}")
```

---

## 4. Colab agentic prompt

Paste this into the Colab AI/Gemini prompt box, not a code cell.

```text
You are a careful coding agent inside Google Colab.

Repo:
/content/US_stocks_swing_model

Task:
[PASTE EXACT CODING TASK HERE]

Hard rules:
1. Work only inside /content/US_stocks_swing_model.
2. Do not edit .git/, data/, reports/, logs/, models/, .env, secrets, tokens, credentials, or large generated files.
3. Do not commit or push. I will do that manually after review.
4. Before editing, inspect:
   - git status --short
   - repo tree
   - relevant scripts/tests/configs
5. Make the smallest correct change.
6. Preserve existing public function names and test intent unless the task explicitly requires otherwise.
7. Run checks after editing:
   - python -m py_compile on changed Python files
   - python -m pytest -q
8. If tests fail, fix only the related issue. Do not hide failures.
9. End with:
   - files changed
   - git diff --stat
   - tests run
   - pass/fail result
   - any manual review needed
10. If you cannot edit files directly, return one valid unified diff only, starting with diff --git.

Start by running:
cd /content/US_stocks_swing_model
git status --short
find . -maxdepth 2 -type f | sort | head -200
python -m pytest -q
```

Example task:

```text
Task:
Fix the failing stage23 frozen feature set workflow with the smallest safe patch. Do not change model intent unless tests prove it is necessary.
```

---

## 5. Apply an AI-generated patch

Use only when the agent returns a real unified diff beginning with `diff --git`.

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

If `git apply --check` fails, do not force it. Regenerate the patch against current files.

---

## 6. Re-run checks after editing

```python
%cd /content/US_stocks_swing_model
!python -m py_compile $(find scripts -name "*.py" 2>/dev/null) || true
!python -m pytest -q
!git status --short
!git diff --stat
```

---

## 7. Commit and push

Run only after reviewing the diff.

```python
import os
import subprocess
from pathlib import Path

REPO_SLUG = "donnywpolson-sudo/US_stocks_swing_model"
BRANCH = "colab-work"
COMMIT_MESSAGE = "Colab update"
REPO_DIR = Path("/content") / REPO_SLUG.split("/")[-1]
BLOCKED_DIRS = {"data", "reports", "logs", "models"}
MAX_FILE_MB = 25


def run(cmd, check=True, display=None):
    shown = display or " ".join(map(str, cmd))
    print(f"\n$ {shown}")
    p = subprocess.run(
        list(map(str, cmd)),
        cwd=str(REPO_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(p.stdout)
    if check and p.returncode != 0:
        raise SystemExit(f"Command failed: {shown}")
    return p


def get_token():
    from google.colab import userdata
    token = userdata.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Missing Colab Secret: GITHUB_TOKEN")
    return token


def changed_files():
    lines = run(["git", "status", "--porcelain"], check=False).stdout.splitlines()
    return [line[3:].strip() for line in lines if line.strip() and line[3:].strip()]


def safety_check(files):
    problems = []
    for f in files:
        if f.split("/", 1)[0] in BLOCKED_DIRS:
            problems.append(f"blocked artifact folder: {f}")
        p = REPO_DIR / f
        if p.exists() and p.is_file() and p.stat().st_size > MAX_FILE_MB * 1024 * 1024:
            problems.append(f"file too large: {f}")
    if problems:
        print("\nSAFETY BLOCKED COMMIT")
        for item in problems:
            print(" -", item)
        raise SystemExit("Refusing to commit.")


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

## 8. Open PR

After push:

```text
https://github.com/donnywpolson-sudo/US_stocks_swing_model/compare/main...colab-work
```

Use:

```text
base: main
compare: colab-work
```

---

## 9. Quick troubleshooting

### Colab GitHub browser says no results

That usually means the repo has no `.ipynb` notebook files. Use `git clone` in a code cell instead.

### `git status` says not a Git repo

Run:

```python
%cd /content/US_stocks_swing_model
!git status
```

Use `%cd`, not `!cd`.

### Push authentication failed

Check:

```python
from google.colab import userdata
print(bool(userdata.get("GITHUB_TOKEN")))
```

Then confirm token permissions:

```text
Repository: US_stocks_swing_model
Contents: Read and write
```

### Push rejected

Use a new branch:

```python
%cd /content/US_stocks_swing_model
!git checkout -b colab-work-2
!git push -u origin colab-work-2
```

### Accidentally edited generated files

```python
%cd /content/US_stocks_swing_model
!git restore data reports logs models 2>/dev/null || true
!git status --short
```


