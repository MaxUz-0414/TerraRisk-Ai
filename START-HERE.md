# Sayem Md Sajjudul Islam: your TerraRisk AI package

You are **Sayem Md Sajjudul Islam** (student ID 2401249), **Docker engineer**. This package holds exactly the files that you push to GitHub:
**31 files**, already in the folders where they belong in the repository. You only add files; you never edit, move or delete anything.

| In this folder | What it is |
|---|---|
| `START-HERE.md` | this page |
| `PUSH-PROMPT.txt` | a prompt for an AI assistant that does the whole push for you (the fastest way, "Way A") |
| `PR-BODY.md` | the text of your pull request, already filled in |
| `MY-TASKS.md` | your RACI rows, requirements, files and what to do after the push |
| `MANIFEST.csv` | every file with its size and SHA-256, to prove the copy is exact |
| `check_package.py` | optional checker: compares a clone with `MANIFEST.csv` (needs Python 3) |
| `repo/` | **your files**, laid out like the repository. Only the content of this folder goes to GitHub |

## Before you start (once, about 10 minutes)

1. **Wait for Abduraimboy's message** that the repository is ready (the Leader pushes the skeleton to `main` first). He also sends you the repository link and
   invites you on GitHub: **accept the invitation** (e-mail or https://github.com/notifications). Without it every push fails with *403* or *Permission denied*.
2. **Install Git** (https://git-scm.com/download/win on Windows, keep the default answers; on macOS run `git --version` and accept the installer that appears).
   Check in a terminal: `git --version`.
3. **Tell Git who you are** (once, use the e-mail of your GitHub account):
   `git config --global user.name "Sayem Md Sajjudul Islam"` and `git config --global user.email "you@example.com"`
4. Optional but helpful: the GitHub command line `gh` (https://cli.github.com), then `gh auth login`. With it the pull request opens by itself; without it you click one button.
5. **Unzip this package to a short folder**, for example `C:\work\` (Windows: right-click the zip, *Extract All*). A short path avoids the 260-character path limit of Windows.
   After unzipping you must see `START-HERE.md` and the folder `repo` side by side.

## Way A: with an AI assistant (fastest)

1. Open an AI assistant that can run terminal commands (Claude Code, or any other coding assistant) **in the unzipped folder `05_Sayem_Docker`**.
2. Open `PUSH-PROMPT.txt`, replace `<REPO_URL>` with the repository link Abduraimboy sent you, paste the whole text into the assistant and send it.
3. The assistant clones the repository, makes your branch, copies your files, checks them against `MANIFEST.csv`, commits, pushes and opens the pull request.
   It stops before merging. Read its summary: it must say **31 files** and give the pull-request link.

## Way B: by hand

Open a terminal **inside the unzipped folder `05_Sayem_Docker`** and replace `<REPO_URL>`.

**Windows (PowerShell):**
```powershell
cd ..
git clone <REPO_URL> terrarisk-ai
cd terrarisk-ai
git switch -c feature/docker-satellite-common
robocopy ..\05_Sayem_Docker\repo . /E
# robocopy prints a summary. Exit codes 0 to 7 mean "copied fine"; 8 or more means an error.
git status --porcelain -uall
# every line must start with ?? and be a path from MANIFEST.csv. If anything else appears, stop.
python ..\05_Sayem_Docker\check_package.py . ..\05_Sayem_Docker\MANIFEST.csv
git add -A
git commit -m "Add shared library, satellite service, Docker files, developer scripts and architecture documents"
git push -u origin feature/docker-satellite-common
gh pr create --base main --title "Docker: shared library, satellite service, Docker files, scripts and architecture documents" --body-file ..\05_Sayem_Docker\PR-BODY.md
```

**macOS / Linux (Terminal):**
```bash
cd ..
git clone <REPO_URL> terrarisk-ai
cd terrarisk-ai
git switch -c feature/docker-satellite-common
cp -R ../05_Sayem_Docker/repo/. .
git status --porcelain -uall
# every line must start with ?? and be a path from MANIFEST.csv. If anything else appears, stop.
python3 ../05_Sayem_Docker/check_package.py . ../05_Sayem_Docker/MANIFEST.csv
git add -A
git commit -m "Add shared library, satellite service, Docker files, developer scripts and architecture documents"
git push -u origin feature/docker-satellite-common
gh pr create --base main --title "Docker: shared library, satellite service, Docker files, scripts and architecture documents" --body-file ../05_Sayem_Docker/PR-BODY.md
```

No `gh`? Skip the last line. After `git push` GitHub prints a link, or open the repository in the browser and click **Compare & pull request**;
paste the content of `PR-BODY.md` as the description. Python missing? Skip the `check_package.py` line (the `git status` check above it is the important one).

## Way C: GitHub Desktop (no commands)

1. *File > Clone repository* > the URL tab > paste the link > Clone. Put it **next to** this folder, not inside it.
2. *Branch > New branch* > name `feature/docker-satellite-common` > Create branch.
3. In File Explorer / Finder open `repo` of this package, select **everything inside it** (also the folders that start with a dot, such as `.github`; on a Mac press Cmd+Shift+. to show them),
   and copy it into the root of the cloned folder. When asked about existing folders choose *Merge*.
4. GitHub Desktop now lists exactly your files as *added* (31 files). Anything else in the list is wrong: stop and ask the Leader.
5. Summary: `Add shared library, satellite service, Docker files, developer scripts and architecture documents` > *Commit to feature/docker-satellite-common* > *Publish branch* > *Create Pull Request*; paste the content of `PR-BODY.md`.

## After the pull request is open

- The Leader (and the co-owner of a shared file, if any) reviews it. Answer every comment. To fix something, change the file in your clone, commit and `git push` again on the same branch.
  **Never** force-push (`--force`) and never push to `main`.
- The Leader merges. Pull requests are merged in the order written in the *Push Plan* sheet of `TerraRisk_RACI.xlsx`.
- Then read `MY-TASKS.md`: it says what is left for you.

## If something goes wrong

| Message or problem | What it means | What to do |
|---|---|---|
| `Permission denied`, `403`, `Repository not found` | You were not invited yet, or you are logged in with another GitHub account | Accept the invitation; check `gh auth status` or the account in GitHub Desktop |
| `You appear to have cloned an empty repository` | The Leader has not pushed the skeleton yet | Wait for his message, delete the clone folder and clone again |
| `git status` shows files that are not in `MANIFEST.csv`, or shows `M` / `D` | Something other than your files changed | Stop. Do not commit. Delete the clone folder and start again from `git clone` |
| `check_package.py` says MISSING or DIFFERENT | The copy is incomplete (often hidden dot-folders were skipped) | Copy again (robocopy / cp command above), then check again |
| `robocopy` exit code 8 or higher | Real copy error (path too long, disk full) | Move the package to a shorter folder such as `C:\work\` and run it again |
| `Filename too long` | Windows path limit | Run `git config --global core.longpaths true`, or use a shorter folder |
| `warning: LF will be replaced by CRLF` | Windows line-ending note | Harmless: the repository keeps LF through its `.gitattributes` |
| `src refspec ... does not match any` | Nothing was committed | Run `git status`; copy the files in; commit; push again |
| `failed to push some refs ... (fetch first)` | The branch exists already with other content | Ask the Leader; never use `--force` |
| The assistant wants to change a file or use `--force` | Not allowed | Tell it to stop; follow Way B |

Questions: ask in the team chat and tag Abduraimboy (the Leader) for repository and Git problems and for anything about content or scope.
