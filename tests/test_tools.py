from src.tools.semgrep_tool import run_semgrep
from src.tools.secret_scanner import scan_secrets
from src.tools.bandit_tool import run_bandit

# --- Test data: intentionally vulnerable code ---

VULNERABLE_CODE = """
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()
"""

CODE_WITH_SECRET = """
import requests

API_KEY = "sk-ant-api03-abc123def456ghi789"
GITHUB_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz123456789012"

def call_api():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.get("https://api.example.com", headers=headers)
"""

CLEAN_CODE = """
def add(a: int, b: int) -> int:
    return a + b
"""


def test_semgrep_finds_sql_injection():
    result = run_semgrep.invoke({"code_patch": VULNERABLE_CODE})
    print(f"\nSemgrep result:\n{result}")
    assert "No security" not in result or "injection" in result.lower()


def test_secret_scanner_finds_keys():
    result = scan_secrets.invoke({"code_patch": CODE_WITH_SECRET})
    print(f"\nSecret scanner result:\n{result}")
    assert "No hardcoded" not in result


def test_clean_code_passes():
    semgrep_result = run_semgrep.invoke({"code_patch": CLEAN_CODE})
    secret_result  = scan_secrets.invoke({"code_patch": CLEAN_CODE})
    print(f"\nClean code semgrep: {semgrep_result}")
    print(f"Clean code secrets: {secret_result}")
    assert "No security" in semgrep_result or "No hardcoded" in secret_result


def test_run_bandit():
    vulnerable_code = """
import subprocess
import hashlib
import pickle

password = "admin123"

# Command injection risk
subprocess.run("ls -la", shell=True)

# Weak hashing algorithm
hashlib.md5(b"password").hexdigest()

# Unsafe deserialization
pickle.loads(b"some_data")
"""

    result = run_bandit.invoke({"code_patch": vulnerable_code})

    print("=== Bandit Test Result ===")
    print(result)

    assert result is not None
    assert result.strip()
    assert "No security issues found" not in result

    print("Test passed: Bandit detected security issues.")



if __name__ == "__main__":
    test_semgrep_finds_sql_injection()
    test_secret_scanner_finds_keys()
    test_clean_code_passes()
    test_run_bandit()
    print("\n✅ All tool tests passed")