# Semgrep precision / recall — measured results

Run on 2026-11-18T04:03:23+00:00 with Semgrep 1.186.0 on Windows-10-10.0.26300-SP0.
Suite: `dev`. Config set: `extended`.
Rule sources: `p/python`, `p/javascript`, `p/owasp-top-ten`, `p/secrets`, `p/security-audit`, `p/expressjs`, `p/gitleaks`, `r/javascript.browser.security.eval-detected.eval-detected`, `r/javascript.lang.security.audit.sqli.node-mysql-sqli.node-mysql-sqli`, `r/python.lang.security.audit.exec-detected.exec-detected`, `r/python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query`, `r/python.lang.security.audit.formatted-sql-query.formatted-sql-query`, `r/python.flask.security.xss.audit.explicit-unescape-with-markup.explicit-unescape-with-markup`, `backend/app/security/rules/`.
Current `labels.json` sha256 `f2e4d3818a22d8f9…`.

## Headline

| Metric | Target | Measured | Result |
|---|---|---|---|
| Precision | > 90% | 87.8% (36/41; 95% CI 74–95%) | **not met** |
| Recall | > 85% | 97.3% (36/37; 95% CI 86–100%) | met |

* Precision counting only findings in the five target classes: 87.8% (36/41; 95% CI 74–95%).
* Recall requiring the *right* class (CWE) as well: 97.3% (36/37; 95% CI 86–100%).
* Safe (fixed) cases that still got a finding: 17.4% (4/23; 95% CI 7–37%).

Raw counts: 37 vulnerable cases (36 detected, 1 missed), 23 safe cases, 5 false-positive findings (5 in the target classes), 24 duplicate findings on already-detected sinks.

## Label amendments

Labels were frozen before the first scored run. They were amended once afterwards; everything is disclosed here.

**A1** (labels before: sha256 `347abb99db678107…`) — After the first scored run, one finding (express-path-join-resolve-traversal) landed on the path.join line of js-path-express-readfile instead of the fs.readFile line. It is the same vulnerability reported at a different, equally valid line, but it was scored as a false positive plus a miss because only the file-access line was labeled. The path-construction line was added as a sink to all three path-traversal cases that build the path on a separate line from the file access (js-path-express-readfile, py-path-flask-open, py-path-bare-open) so the cases are treated consistently. This amendment can only help Semgrep's numbers; the initial numbers are kept in results_initial.json.

## Recall by vulnerability class

| Class | Recall | False-positive findings |
|---|---|---|
| sqli | 100.0% (8/8; 95% CI 68–100%) | 0 |
| xss | 100.0% (8/8; 95% CI 68–100%) | 2 |
| secret | 88.9% (8/9; 95% CI 56–98%) | 0 |
| path_traversal | 100.0% (6/6; 95% CI 61–100%) | 3 |
| eval | 100.0% (6/6; 95% CI 61–100%) | 0 |

## Recall by how the untrusted value arrives

Most Semgrep security rules are taint rules that need a recognisable source (e.g. `request.args`). `bare_param` cases pass the value as a plain function argument, which is common in real code but gives such rules nothing to start from.

| Source | Recall |
|---|---|
| bare_param | 100.0% (11/11; 95% CI 74–100%) |
| browser_source | 100.0% (2/2; 95% CI 34–100%) |
| framework | 100.0% (15/15; 95% CI 80–100%) |
| literal | 88.9% (8/9; 95% CI 56–98%) |

## Recall by language

| Language | Recall |
|---|---|
| javascript | 100.0% (18/18; 95% CI 82–100%) |
| python | 94.7% (18/19; 95% CI 75–99%) |

## Missed vulnerabilities (false negatives)

| Case | Class | Source | What it is |
|---|---|---|---|
| `py-secret-db-password` | secret | literal | database password assigned as a string literal |

## Detected

| Case | Rule(s) | Right class? |
|---|---|---|
| `js-eval-express` | `eval-detected`, `code-string-concat` | yes |
| `js-eval-bare` | `eval-detected` | yes |
| `js-eval-new-function` | `function-constructor-from-parameter` | yes |
| `js-path-express-readfile` | `path-from-parameter-reaches-file-read`, `express-path-join-resolve-traversal` | yes |
| `js-path-express-sendfile` | `express-res-sendfile` | yes |
| `js-path-bare-readfile` | `path-from-parameter-reaches-file-read` | yes |
| `js-secret-aws-keys` | `aws-access-token`, `detected-aws-access-key-id-value`, `detected-aws-secret-access-key` | yes |
| `js-secret-github-token` | `generic-api-key`, `github-pat` | yes |
| `js-secret-stripe-live` | `stripe-access-token`, `detected-stripe-api-key` | yes |
| `js-secret-jwt-secret` | `hardcoded-jwt-secret` | yes |
| `js-sqli-express-concat` | `tainted-sql-string` | yes |
| `js-sqli-express-template` | `tainted-sql-string` | yes |
| `js-sqli-bare-concat` | `node-mysql-sqli` | yes |
| `js-xss-innerhtml-bare` | `dom-xss-from-param-or-url` | yes |
| `js-xss-innerhtml-location` | `dom-xss-from-param-or-url` | yes |
| `js-xss-document-write` | `dom-xss-from-param-or-url` | yes |
| `js-xss-express-send` | `direct-response-write`, `raw-html-format` | yes |
| `jsx-xss-dangerously-set` | `react-dangerouslysetinnerhtml` | yes |
| `py-eval-flask` | `user-eval`, `eval-injection`, `eval-detected` | yes |
| `py-eval-bare` | `eval-detected` | yes |
| `py-exec-bare` | `exec-detected` | yes |
| `py-path-flask-open` | `path-from-input-reaches-file-access` | yes |
| `py-path-flask-send-file` | `path-from-input-reaches-file-access` | yes |
| `py-path-bare-open` | `path-from-input-reaches-file-access` | yes |
| `py-secret-aws-keys` | `aws-access-token`, `detected-aws-access-key-id-value`, `detected-aws-secret-access-key` | yes |
| `py-secret-github-token` | `generic-api-key`, `github-pat` | yes |
| `py-secret-stripe-live` | `stripe-access-token`, `detected-stripe-api-key` | yes |
| `py-secret-slack-token` | `generic-api-key`, `slack-bot-token` | yes |
| `py-sqli-flask-concat` | `tainted-sql-string`, `sqlalchemy-execute-raw-query` | yes |
| `py-sqli-flask-fstring` | `sql-injection-db-cursor-execute`, `tainted-sql-string`, `formatted-sql-query`, `sqlalchemy-execute-raw-query` | yes |
| `py-sqli-bare-concat` | `sqlalchemy-execute-raw-query` | yes |
| `py-sqli-bare-format` | `formatted-sql-query`, `sqlalchemy-execute-raw-query` | yes |
| `py-sqli-django-raw` | `avoid-raw-sql`, `sql-injection-using-raw` | yes |
| `py-xss-flask-returned-fstring` | `raw-html-format`, `directly-returned-format-string`, `raw-html-format` | yes |
| `py-xss-flask-template-string` | `raw-html-format`, `render-template-string`, `raw-html-format` | yes |
| `py-xss-flask-markup` | `explicit-unescape-with-markup` | yes |

## False-positive findings

| Where | Case | Line | Rule | Class |
|---|---|---|---|---|
| safe_case | `js-path-basename` | javascript/path_traversal.js:31 | `express-path-join-resolve-traversal` | path_traversal |
| safe_case | `js-path-resolved-check` | javascript/path_traversal.js:44 | `path-from-parameter-reaches-file-read` | path_traversal |
| safe_case | `py-path-resolved-check` | python/path_traversal.py:46 | `path-from-input-reaches-file-access` | path_traversal |
| safe_case | `py-xss-flask-escape` | python/xss.py:42 | `directly-returned-format-string` | xss |
| safe_case | `py-xss-flask-escape` | python/xss.py:42 | `raw-html-format` | xss |

## How to read this

* The suite is small, so each number comes with a 95% Wilson interval; one case moves a percentage by several points.
* Cases were written and labeled **before** the first scored run and were not adjusted to the output. See `backend/app/security/evaluation.py` for the exact scoring rules.
* This measures the rule set named at the top. A config that was tuned while looking at this same suite gives an optimistic result; only a suite the config was never tuned against is a fair estimate.
* Semgrep registry packs change over time; `semgrep_raw.json` is the exact output these numbers come from.
