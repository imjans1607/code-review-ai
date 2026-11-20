# Semgrep precision / recall — measured results

Run on 2026-11-18T03:37:47+00:00 with Semgrep 1.186.0 on Windows-10-10.0.26300-SP0.
Suite: `dev`. Config set: `baseline` (the product's shipped config as of 2026-11-18).
Rule sources: `p/python`, `p/javascript`, `p/owasp-top-ten`, `p/secrets`.
Current `labels.json` sha256 `f2e4d3818a22d8f9…`.

## Headline

| Metric | Target | Measured | Result |
|---|---|---|---|
| Precision | > 90% | 84.2% (16/19; 95% CI 62–94%) | **not met** |
| Recall | > 85% | 43.2% (16/37; 95% CI 29–59%) | **not met** |

* Precision counting only findings in the five target classes: 84.2% (16/19; 95% CI 62–94%).
* Recall requiring the *right* class (CWE) as well: 40.5% (15/37; 95% CI 26–56%).
* Safe (fixed) cases that still got a finding: 8.7% (2/23; 95% CI 2–27%).

Raw counts: 37 vulnerable cases (16 detected, 21 missed), 23 safe cases, 3 false-positive findings (3 in the target classes), 8 duplicate findings on already-detected sinks.

## Label amendments

Labels were frozen before the first scored run. They were amended once afterwards; everything is disclosed here.

**A1** (labels before: sha256 `347abb99db678107…`) — After the first scored run, one finding (express-path-join-resolve-traversal) landed on the path.join line of js-path-express-readfile instead of the fs.readFile line. It is the same vulnerability reported at a different, equally valid line, but it was scored as a false positive plus a miss because only the file-access line was labeled. The path-construction line was added as a sink to all three path-traversal cases that build the path on a separate line from the file access (js-path-express-readfile, py-path-flask-open, py-path-bare-open) so the cases are treated consistently. This amendment can only help Semgrep's numbers; the initial numbers are kept in results_initial.json.

| | Precision | Recall |
|---|---|---|
| As first scored (original labels) | 78.9% (15/19; 95% CI 57–92%) | 40.5% (15/37; 95% CI 26–56%) |
| After amendment (current) | see Headline | see Headline |

## Recall by vulnerability class

| Class | Recall | False-positive findings |
|---|---|---|
| sqli | 37.5% (3/8; 95% CI 14–69%) | 0 |
| xss | 50.0% (4/8; 95% CI 22–78%) | 2 |
| secret | 55.6% (5/9; 95% CI 27–81%) | 0 |
| path_traversal | 33.3% (2/6; 95% CI 10–70%) | 1 |
| eval | 33.3% (2/6; 95% CI 10–70%) | 0 |

## Recall by how the untrusted value arrives

Most Semgrep security rules are taint rules that need a recognisable source (e.g. `request.args`). `bare_param` cases pass the value as a plain function argument, which is common in real code but gives such rules nothing to start from.

| Source | Recall |
|---|---|
| bare_param | 9.1% (1/11; 95% CI 2–38%) |
| browser_source | 0.0% (0/2; 95% CI 0–66%) |
| framework | 66.7% (10/15; 95% CI 42–85%) |
| literal | 55.6% (5/9; 95% CI 27–81%) |

## Recall by language

| Language | Recall |
|---|---|
| javascript | 44.4% (8/18; 95% CI 25–66%) |
| python | 42.1% (8/19; 95% CI 23–64%) |

## Missed vulnerabilities (false negatives)

| Case | Class | Source | What it is |
|---|---|---|---|
| `js-eval-bare` | eval | bare_param | function argument passed to eval |
| `js-eval-new-function` | eval | bare_param | function argument compiled with the Function constructor |
| `js-path-bare-readfile` | path_traversal | bare_param | function argument concatenated into a path and read |
| `js-secret-github-token` | secret | literal | GitHub personal access token in source |
| `js-sqli-express-concat` | sqli | framework | request value concatenated into a query |
| `js-sqli-express-template` | sqli | framework | request value in a template-literal query |
| `js-sqli-bare-concat` | sqli | bare_param | function argument concatenated into a query |
| `js-xss-innerhtml-bare` | xss | bare_param | function argument written to innerHTML |
| `js-xss-innerhtml-location` | xss | browser_source | location.hash written to innerHTML |
| `js-xss-document-write` | xss | browser_source | location.search written with document.write |
| `py-eval-bare` | eval | bare_param | function argument passed to eval |
| `py-exec-bare` | eval | bare_param | function argument passed to exec |
| `py-path-flask-open` | path_traversal | framework | request value joined into a path and opened |
| `py-path-flask-send-file` | path_traversal | framework | request value passed straight to send_file |
| `py-path-bare-open` | path_traversal | bare_param | function argument joined into a path and opened |
| `py-secret-github-token` | secret | literal | GitHub personal access token in source |
| `py-secret-slack-token` | secret | literal | Slack bot token in source |
| `py-secret-db-password` | secret | literal | database password assigned as a string literal |
| `py-sqli-bare-concat` | sqli | bare_param | function argument concatenated into SQL |
| `py-sqli-bare-format` | sqli | bare_param | function argument %-formatted into SQL |
| `py-xss-flask-markup` | xss | framework | request value marked safe with Markup |

## Detected

| Case | Rule(s) | Right class? |
|---|---|---|
| `js-eval-express` | `code-string-concat` | yes |
| `js-path-express-readfile` | `express-path-join-resolve-traversal` | yes |
| `js-path-express-sendfile` | `express-res-sendfile` | yes |
| `js-secret-aws-keys` | `detected-aws-access-key-id-value`, `detected-aws-secret-access-key` | yes |
| `js-secret-stripe-live` | `detected-stripe-api-key` | yes |
| `js-secret-jwt-secret` | `hardcoded-jwt-secret` | yes |
| `js-xss-express-send` | `direct-response-write`, `raw-html-format` | yes |
| `jsx-xss-dangerously-set` | `react-dangerouslysetinnerhtml` | yes |
| `py-eval-flask` | `user-eval`, `eval-injection` | yes |
| `py-secret-aws-keys` | `detected-aws-access-key-id-value`, `detected-aws-secret-access-key` | yes |
| `py-secret-stripe-live` | `detected-stripe-api-key` | yes |
| `py-sqli-flask-concat` | `tainted-sql-string` | no |
| `py-sqli-flask-fstring` | `sql-injection-db-cursor-execute`, `tainted-sql-string` | yes |
| `py-sqli-django-raw` | `sql-injection-using-raw` | yes |
| `py-xss-flask-returned-fstring` | `raw-html-format`, `directly-returned-format-string`, `raw-html-format` | yes |
| `py-xss-flask-template-string` | `raw-html-format`, `raw-html-format` | yes |

## False-positive findings

| Where | Case | Line | Rule | Class |
|---|---|---|---|---|
| safe_case | `js-path-basename` | javascript/path_traversal.js:31 | `express-path-join-resolve-traversal` | path_traversal |
| safe_case | `py-xss-flask-escape` | python/xss.py:42 | `directly-returned-format-string` | xss |
| safe_case | `py-xss-flask-escape` | python/xss.py:42 | `raw-html-format` | xss |

## How to read this

* The suite is small, so each number comes with a 95% Wilson interval; one case moves a percentage by several points.
* Cases were written and labeled **before** the first scored run and were not adjusted to the output. See `backend/app/security/evaluation.py` for the exact scoring rules.
* This measures the rule set named at the top. A config that was tuned while looking at this same suite gives an optimistic result; only a suite the config was never tuned against is a fair estimate.
* Semgrep registry packs change over time; `semgrep_raw.json` is the exact output these numbers come from.
