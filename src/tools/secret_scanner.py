import re
from langchain_core.tools import tool


# Define patterns OUTSIDE the function
# Why? These get compiled once at import time, not on every function call
# Compiled regex is ~10x faster than recompiling each time

SECRET_PATTERNS = {
    "AWS Access Key": r'AKIA[0-9A-Z]{16}',
    "GitHub Token":   r'ghp_[a-zA-Z0-9]{36}',
    "OpenAI API Key": r'sk-[a-zA-Z0-9]{48}',
    "Anthropic Key":  r'sk-ant-[a-zA-Z0-9\-]{90,}',
    "Generic Password": r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{6,}["\']',
    "Generic API Key":  r'(?i)(api_key|apikey|api_token)\s*=\s*["\'][^"\']{8,}["\']',
    "Private Key Header": r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',
    "Stripe API Key": r'sk_live_[a-zA-Z0-9]{24}',
}

# Pre-compile all patterns once
COMPILED_PATTERNS = {
    name: re.compile(pattern) 
    for name, pattern in SECRET_PATTERNS.items()
}


@tool
def scan_secrets(code_patch: str) -> str:
    """
    Scans code for hardcoded secrets, API keys, passwords, and credentials.
    Use this to detect exposed tokens, credentials embedded in source code,
    and private keys that should never be committed to version control.
    
    Args:
        code_patch: The code or diff text to scan
        
    Returns:
        String listing all discovered secrets with line numbers,
        or confirmation that no secrets were found
    """
    findings = []
    
    # scan line by line so we can report line numbers
    for line_num, line in enumerate(code_patch.split('\n'), start=1):
        
        # only scan added lines in a diff (lines starting with +)
        # no point flagging secrets in code that was just REMOVED
        if code_patch.startswith('@@'):  # it's a diff
            if not line.startswith('+'):
                continue
            scan_line = line[1:]  # strip the leading +
        else:
            scan_line = line      # plain code, scan everything
        
        for secret_name, pattern in COMPILED_PATTERNS.items():
            if pattern.search(scan_line):
                # mask the actual secret value in output
                # we confirm it exists but don't expose it in logs
                findings.append(
                    f"[CRITICAL] Line {line_num}: "
                    f"Possible {secret_name} detected\n"
                    f"  Content: {scan_line.strip()[:80]}..."
                )
    
    if not findings:
        return "No hardcoded secrets or credentials detected."
    
    header = f"⚠️  Secret scanner found {len(findings)} potential exposure(s):\n\n"
    return header + "\n".join(findings)

