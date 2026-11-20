# Intentionally insecure examples, used to demonstrate the security scanner.
# Each function below trips a well-known Semgrep security rule.
import os
import sqlite3

API_KEY = "EXAMPLE_FAKE_KEY_DO_NOT_USE"  # hard-coded secret (CWE-798)


def get_user(conn, username):
    cur = conn.cursor()
    # String-built SQL -> SQL injection (CWE-89)
    cur.execute("SELECT * FROM users WHERE name = '" + username + "'")
    return cur.fetchone()


def run(expr):
    # Executing a caller-supplied string -> eval injection (CWE-95)
    return eval(expr)


def read_file(name):
    # 'name' is not validated -> path traversal (CWE-22)
    path = os.path.join("/data", name)
    with open(path) as fh:
        return fh.read()
