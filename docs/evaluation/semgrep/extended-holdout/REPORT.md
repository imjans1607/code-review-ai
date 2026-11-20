# Semgrep precision / recall — measured results

Run on 2026-11-18T04:03:42+00:00 with Semgrep 1.186.0 on Windows-10-10.0.26300-SP0.
Suite: `holdout`. Config set: `extended`.
Rule sources: `p/python`, `p/javascript`, `p/owasp-top-ten`, `p/secrets`, `p/security-audit`, `p/expressjs`, `p/gitleaks`, `r/javascript.browser.security.eval-detected.eval-detected`, `r/javascript.lang.security.audit.sqli.node-mysql-sqli.node-mysql-sqli`, `r/python.lang.security.audit.exec-detected.exec-detected`, `r/python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query`, `r/python.lang.security.audit.formatted-sql-query.formatted-sql-query`, `r/python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup`, `backend/app/security/rules/`.
Current `labels.json` sha256 `3ddaed4a7e0544fc…`.

## Headline

| Metric | Target | Measured | Result |
|---|---|---|---|
| Precision | > 90% | 84.6% (22/26; 95% CI 66–94%) | **not met** |
| Recall | > 85% | 57.9% (22/38; 95% CI 42–72%) | **not met** |

* Precision counting only findings in the five target classes: 84.6% (22/26; 95% CI 66–94%).
* Recall requiring the *right* class (CWE) as well: 55.3% (21/38; 95% CI 40–70%).
* Safe (fixed) cases that still got a finding: 13.8% (4/29; 95% CI 6–31%).

Raw counts: 38 vulnerable cases (22 detected, 16 missed), 29 safe cases, 4 false-positive findings (4 in the target classes), 12 duplicate findings on already-detected sinks.

## Recall by vulnerability class

| Class | Recall | False-positive findings |
|---|---|---|
| sqli | 87.5% (7/8; 95% CI 53–98%) | 1 |
| xss | 44.4% (4/9; 95% CI 19–73%) | 0 |
| secret | 62.5% (5/8; 95% CI 31–86%) | 0 |
| path_traversal | 14.3% (1/7; 95% CI 3–51%) | 2 |
| eval | 83.3% (5/6; 95% CI 44–97%) | 1 |

## Recall by how the untrusted value arrives

Most Semgrep security rules are taint rules that need a recognisable source (e.g. `request.args`). `bare_param` cases pass the value as a plain function argument, which is common in real code but gives such rules nothing to start from.

| Source | Recall |
|---|---|
| bare_param | 30.0% (3/10; 95% CI 11–60%) |
| browser_source | 50.0% (1/2; 95% CI 10–90%) |
| framework | 72.2% (13/18; 95% CI 49–88%) |
| literal | 62.5% (5/8; 95% CI 31–86%) |

## Recall by language

| Language | Recall |
|---|---|
| javascript | 42.1% (8/19; 95% CI 23–64%) |
| python | 73.7% (14/19; 95% CI 51–88%) |

## Missed vulnerabilities (false negatives)

| Case | Class | Source | What it is |
|---|---|---|---|
| `hj-eval-settimeout-string` | eval | bare_param | function argument passed to setTimeout as a string |
| `hj-path-createreadstream` | path_traversal | framework | query value streamed straight from disk |
| `hj-path-res-download` | path_traversal | framework | query value passed to res.download |
| `hj-path-writefile` | path_traversal | framework | request body decides where a file is written |
| `hj-secret-google-key` | secret | literal | Google API key in source |
| `hj-secret-db-url-password` | secret | literal | database password embedded in a connection URL |
| `hj-sqli-knex-raw` | sqli | bare_param | function argument concatenated into knex.raw |
| `hj-xss-jquery-html-hash` | xss | browser_source | location.hash passed to jQuery .html() |
| `hj-xss-insert-adjacent-html` | xss | bare_param | function argument passed to insertAdjacentHTML |
| `hj-xss-outerhtml` | xss | bare_param | function argument assigned to outerHTML |
| `hj-xss-react-state` | xss | bare_param | component state rendered with dangerouslySetInnerHTML |
| `hp-path-fastapi-fileresponse` | path_traversal | framework | FastAPI path parameter built into a path and served |
| `hp-path-tar-extractall` | path_traversal | bare_param | archive extracted without checking member paths |
| `hp-path-open-concat` | path_traversal | bare_param | function argument concatenated into a path and opened |
| `hp-secret-db-url-password` | secret | literal | database password embedded in a connection URL |
| `hp-xss-fastapi-htmlresponse` | xss | framework | FastAPI parameter in an HTML f-string response |

## Detected

| Case | Rule(s) | Right class? |
|---|---|---|
| `hj-eval-vm-run` | `express-vm-injection` | yes |
| `hj-eval-localstorage` | `eval-detected` | yes |
| `hj-secret-sendgrid` | `sendgrid-api-token` | yes |
| `hj-secret-npm-token` | `generic-api-key`, `npm-access-token` | yes |
| `hj-sqli-pg-template` | `tainted-sql-string` | yes |
| `hj-sqli-mysql2-concat` | `node-mysql-sqli` | yes |
| `hj-sqli-sequelize-query` | `tainted-sql-string`, `express-sequelize-injection` | yes |
| `hj-xss-express-write` | `direct-response-write`, `raw-html-format` | yes |
| `hp-eval-flask-exec` | `exec-injection`, `exec-detected` | yes |
| `hp-eval-django-eval-post` | `user-eval`, `eval-detected` | yes |
| `hp-eval-compile-exec` | `exec-detected` | yes |
| `hp-path-flask-open-form` | `path-from-input-reaches-file-access`, `path-traversal-open`, `path-traversal-open` | yes |
| `hp-secret-google-api-key` | `gcp-api-key` | yes |
| `hp-secret-sendgrid-key` | `sendgrid-api-token` | yes |
| `hp-secret-jwt-encode` | `jwt-python-hardcoded-secret` | no |
| `hp-sqli-fastapi-fstring` | `formatted-sql-query`, `sqlalchemy-execute-raw-query` | yes |
| `hp-sqli-sqlalchemy-text-fstring` | `tainted-sql-string`, `avoid-sqlalchemy-text` | yes |
| `hp-sqli-psycopg2-percent` | `formatted-sql-query`, `sqlalchemy-execute-raw-query` | yes |
| `hp-sqli-django-cursor-concat` | `sqlalchemy-execute-raw-query` | yes |
| `hp-xss-django-mark-safe` | `avoid-mark-safe` | yes |
| `hp-xss-django-httpresponse-fstring` | `raw-html-format`, `reflected-data-httpresponse` | yes |
| `hp-xss-flask-make-response` | `raw-html-format`, `raw-html-format` | yes |

## False-positive findings

| Where | Case | Line | Rule | Class |
|---|---|---|---|---|
| safe_case | `hp-path-secure-filename` | python/path_traversal.py:48 | `path-traversal-open` | path_traversal |
| safe_case | `hp-sqli-constant-concat` | python/sqli.py:57 | `sqlalchemy-execute-raw-query` | sqli |
| safe_case | `hj-path-basename-stream` | javascript/path_traversal.js:29 | `express-path-join-resolve-traversal` | path_traversal |
| safe_case | `hp-eval-compile-constant` | python/eval_exec.py:37 | `exec-detected` | eval |

## How to read this

* The suite is small, so each number comes with a 95% Wilson interval; one case moves a percentage by several points.
* Cases were written and labeled **before** the first scored run and were not adjusted to the output. See `backend/app/security/evaluation.py` for the exact scoring rules.
* This measures the rule set named at the top. A config that was tuned while looking at this same suite gives an optimistic result; only a suite the config was never tuned against is a fair estimate.
* Semgrep registry packs change over time; `semgrep_raw.json` is the exact output these numbers come from.
