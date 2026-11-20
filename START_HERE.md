# Start here

This project is a **robot reviewer for pull requests**. When someone opens a pull
request, the robot reads the changed Python and JavaScript code and leaves comments
right on the lines that look risky, for example "this builds a database query from
user input, which allows SQL injection".

You do **not** need to install anything to see it work. You need:

- a free **GitHub account**
- a web browser

Follow the three parts in order. Each takes about 10 minutes.

---

## Part 1: Put your own copy on GitHub

1. Unzip the folder you were given.
2. On GitHub, click **+** (top right) → **New repository**. Give it a name such as
   `code-review-ai`. Choose **Public** (this makes Part 3 much simpler). Click **Create repository**.
3. On the new empty repo page, click **uploading an existing file**.
4. GitHub's website accepts **at most 100 files per upload**, and this project has about
   115, so you upload it in **two rounds**. Open the unzipped folder.
   - **Round 1:** select these and drag them into the browser window: the folders
     `.github`, `backend`, `scripts`, and every loose file (`README.md`, `START_HERE.md`,
     `HANDOFF.md`, `action.yml`, ...). Wait until the upload finishes, then click
     **Commit changes**.
   - **Round 2:** on your repo page click **Add file** → **Upload files**. Drag in the
     folders `docs`, `frontend` and `ml`. Wait, then click **Commit changes**.
   - The folder `.github` must be included. On a Mac it is hidden: press
     **Cmd + Shift + .** in the folder window to show hidden files.

**Check:** your repo should show folders named `backend`, `frontend`, `scripts`,
`docs`, `ml`, and a folder named `.github`. If something is missing, upload it again.

> Comfortable with the command line? It avoids the 100-file limit: in the unzipped folder run
> `git init`, `git add -A`, `git commit -m "initial"`, `git branch -M main`,
> `git remote add origin https://github.com/YOU/code-review-ai.git`, `git push -u origin main`.

---

## Part 2: See the robot review a pull request

You will add a file with deliberate mistakes and open a pull request.

1. In your repo, click **Add file** → **Create new file**.
2. Name it `demo/bad_code.py` (typing the `/` makes the folder).
3. Paste this. It is **intentionally unsafe**, so never use it for real:

   ```python
   import sqlite3

   from flask import Flask, request

   app = Flask(__name__)


   @app.route("/user")
   def user():
       name = request.args.get("name")
       cur = sqlite3.connect("app.db").cursor()
       cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
       return str(cur.fetchone())


   @app.route("/calc")
   def calc():
       return str(eval(request.args["expr"]))


   @app.route("/hello")
   def hello():
       return f"<h1>Hello {request.args.get('name', '')}</h1>"
   ```

4. At the bottom choose **Create a new branch for this commit and start a pull
   request**, then **Propose changes**, then **Create pull request**.
5. Open the **Actions** tab. A run named **AI Code Review** starts. Wait about a minute
   until it shows a green tick.
6. Go back to the pull request. You should see:
   - a **summary comment** with a table of how many issues of each severity were found, and
   - **inline comments** on the risky lines (the SQL query, the `eval`, the HTML).

If you see those, the whole system works. 🎉

> You may also see a comment on a workflow (`.yml`) file saying to "pin" a version to a long
> code. That is good practice for production, but you can ignore it while learning.

---

## Part 3: Use it on another repository

Your uploaded copy is the "reviewer". Any other repo can borrow it with one small file.

1. Open the repo you want reviewed. Click **Add file** → **Create new file**.
2. Name it exactly `.github/workflows/ai-code-review.yml`.
3. Open `docs/examples/consumer-workflow.yml` from this project, copy **everything**, and
   paste it in.
4. Edit **one line**, the one marked `<-- EDIT THIS`. Replace
   `YOUR-GITHUB-USERNAME/YOUR-COPY-REPO-NAME` with your username and the name of the repo from Part 1.
   For example `sam/code-review-ai`. Keep `@main` at the end.
5. Click **Commit changes**.
6. Open a pull request in that repo that changes some Python or JavaScript. The review
   appears within a minute or two.

---

## If something goes wrong

| What you see | What it means and what to do |
|---|---|
| Run fails instantly (0 seconds) with "workflow file issue" | The `.yml` file is broken, nearly always from wrong indentation. Delete the file and paste `consumer-workflow.yml` again without changing spaces. |
| "Unable to resolve action … repository not found" | The reviewer repo is **private**. Either make it public, or in the reviewer repo go to **Settings → Actions → General → Access** and choose **Accessible from repositories owned by the user**. |
| No **Actions** tab, or no run starts | In the repo go to **Settings → Actions → General** and allow actions. A brand-new fork or copy sometimes has them off. |
| Green tick but no comments | Either the pull request changed no Python or JavaScript, or nothing risky was found. Try Part 2's file. |
| GitHub says "try to upload less than 100 files" | Upload in two rounds as described in Part 1 step 4, or use the command-line route. |
| "Push cannot contain secrets" / "GH013" when pushing | GitHub found fake test keys in an old copy of this project. Delete the folder `backend/eval` (if present), then run `git add -A`, `git commit --amend -m "initial"`, `git push -u origin main`. If it still complains, delete the hidden `.git` folder and start Part 1 again with `git init`. |
| "Resource not accessible by integration" | The pull request came from a **fork**. GitHub does not let forks post comments. Open the pull request from a branch inside the same repo. |

---

## What it can and cannot do

- It reviews **Python and JavaScript** only.
- It comments only on lines **the pull request changed**, not on old code.
- The security checks are Semgrep rules. In our own test of 67 cases they caught about
  **58%** of real vulnerabilities, so a clean review does **not** mean the code is safe.
  Details: `docs/evaluation/semgrep/SUMMARY.md`.
- The AI layer (style comments) is optional and off by default.
- Some test files in this project are deliberately vulnerable (for example `backend/examples/`).
  Never copy them into real projects.

---

## Going further (optional)

- **See your reviews on a dashboard:** the setup is in `HANDOFF.md` section 2. It needs Python and Node.js installed.
- **How the pieces work:** `docs/MODULES_EXPLAINED.md` explains each module in plain English.
- **All setup options** (PostgreSQL, publishing the model): `HANDOFF.md`.
