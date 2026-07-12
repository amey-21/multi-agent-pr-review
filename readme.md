## Known Issues & Technical Notes

### MCP Server: Subprocess stdio Isolation

When running the MCP server (`mcp/server.py`), all subprocess-based 
tools (Semgrep, Bandit, Ruff, Radon, pydocstyle) explicitly set 
`stdin=subprocess.DEVNULL` on their `subprocess.run()` calls.

**Why:** MCP servers communicate with clients (Claude Desktop, the MCP 
Inspector) over stdio — a live, bidirectional stdin/stdout channel. By 
default, `subprocess.run()` causes child processes to inherit the 
parent's stdin file descriptor. Since the MCP server's stdin is 
actively in use by the MCP protocol transport, spawned tool subprocesses 
would hang waiting on that inherited handle, causing consistent timeouts 
— even though the exact same code runs correctly under pytest or a 
plain CLI invocation, where stdin is simply idle.

This is a good example of code that is correct in isolation but fails 
under a specific runtime context (an active stdio-based protocol) that 
doesn't reveal itself under normal testing.

### Semgrep Latency

Semgrep subprocess calls consistently take ~5-6 seconds per invocation, 
even though Semgrep's own internal profiling (`--time`) reports only 
~1.1s of actual scan work. The remaining latency is OS-level process 
startup/spawn overhead (Semgrep's runtime includes an OCaml core), not 
network or configuration resolution — verified via isolated timing 
measurements before ruling out a `--config` fix. This is accepted as a 
known architectural tradeoff of the subprocess-wrapping approach used 
for all CLI-based tools in this project (Bandit and Ruff are affected 
less severely, since they're lighter processes).


### MCP Server: PATH Resolution Under Claude Desktop

Subprocess-based tools (Semgrep, Bandit, Ruff, Radon, pydocstyle) failed 
specifically when the MCP server was launched by Claude Desktop, while 
working correctly under the MCP Inspector and direct terminal execution.

**Root cause:** Claude Desktop launches the server by invoking the venv's 
`python.exe` directly via its full path, but never runs venv activation. 
Activation is what normally prepends the venv's `Scripts/` directory 
(where `pip install`ed console tools like `semgrep.exe` and `bandit.exe` 
are placed) to `PATH`. Without activation, that directory is absent from 
the subprocess's `PATH`, so tool executables can't be located by name — 
even though the *interpreter itself* is unambiguously the correct venv 
Python.

Diagnosed by comparing Claude Desktop's own MCP server logs 
(`%LocalAppData%\...\Claude\logs\mcp-server-<name>.log` on Windows) 
against a direct terminal PATH dump, which revealed the venv's `Scripts` 
folder was the only meaningful difference between the two.

**Fix:** derive the venv's `Scripts` directory from `sys.executable` at 
server startup and prepend it to `os.environ["PATH"]` manually, rather 
than relying on venv activation or hardcoding an absolute path (which 
would break on any other machine or directory).

```python
venv_scripts_dir = os.path.dirname(sys.executable)
os.environ["PATH"] = venv_scripts_dir + os.pathsep + os.environ.get("PATH", "")
```

Note: this produced the *same symptom* as the stdio inheritance bug 
above (Semgrep/Bandit failing, secret scanner unaffected) but was a 
completely unrelated root cause — a reminder that identical symptoms 
across different execution contexts shouldn't be assumed to share a fix.


### Deployment: Cold Start on Fly.io

This app runs with `auto_stop_machines = 'stop'` and 
`min_machines_running = 0` to minimize hosting cost for what is 
currently a low-traffic portfolio project. This means the Fly.io 
machine fully stops after a period of inactivity and must cold-start 
(boot container, start Python, start Uvicorn) on the next incoming 
request — including a GitHub webhook delivery.

**Known tradeoff:** if a webhook arrives while the machine is stopped, 
GitHub may experience a delayed response during cold-start, risking a 
perceived delivery failure on GitHub's side (GitHub typically expects 
a response within several seconds). For a production deployment 
serving real users, `min_machines_running = 1` would eliminate this 
risk at a cost of approximately $5-8/month instead of near-zero for 
occasional/idle usage.