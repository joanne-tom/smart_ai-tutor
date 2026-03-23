# OS-related keywords that indicate the student wants Linux/POSIX documentation
# rather than a general encyclopaedia (Wikipedia) answer.
_OS_DOC_KEYWORDS = {
    "fork", "exec", "wait", "pipe", "signal", "syscall", "system call",
    "mmap", "malloc", "semaphore", "mutex", "pthread", "process",
    "thread", "inode", "socket", "file descriptor", "kernel",
    "interrupt", "scheduler", "paging", "segmentation", "virtual memory",
    "swap", "context switch", "deadlock", "race condition", "critical section",
    "monitor", "spinlock", "memory", "heap", "stack", "buffer",
    "posix", "linux", "unix", "command", "terminal", "chmod", "grep",
    "man page", "shell", "bash", "system", "cpu", "disk", "i/o",
}


def _needs_os_docs(doubt: str) -> bool:
    """Return True if the doubt seems to ask for Linux / OS reference docs."""
    doubt_lower = doubt.lower()
    return any(kw in doubt_lower for kw in _OS_DOC_KEYWORDS)


def choose_tool(route: dict) -> str:
    """
    Returns one of: "rag" | "wikipedia" | "os_docs"

    Routing logic:
        concept      → rag
        misconception → rag
        application  → if needs_external:
                            keyword contains OS/Linux term → os_docs
                            otherwise                      → wikipedia
                       else → rag
        anything else → rag
    """
    doubt = route.get("doubt", "")   # populated by app.py (optional hint)

    if route["type"] in ("concept", "misconception"):
        return "rag"

    if route["type"] == "application":
        if route.get("needs_external"):
            if _needs_os_docs(doubt):
                return "os_docs"
            return "wikipedia"
        return "rag"

    return "rag"