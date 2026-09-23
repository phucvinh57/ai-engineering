from datetime import datetime, timedelta

import psutil
import platform
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

model = ChatOllama(
    model="llama3.2",
    temperature=0,
)

MAX_STEPS = 4

AGENT_PROMPT = """
You are a system information assistant for this computer.

You may only discuss this machine's operating system, CPU, memory, disk and
uptime, and only by calling the tools provided. Never guess these values from
your own knowledge, always call a tool.

If the user asks about anything else, refuse and explain that you can only
answer questions about this computer's system information. Do not call a tool
for an off-topic question.
"""

# --- 1. Define tools: name, purpose and typed parameters come from the
#        function signature and docstring, which is what the model reads. ---


@tool
def get_os_info() -> str:
    """Returns the operating system name, release and machine architecture."""
    return (
        f"system={platform.system()} release={platform.release()} "
        f"version={platform.version()} machine={platform.machine()}"
    )


@tool
def get_cpu_info() -> str:
    """Returns the CPU core counts and current per-core utilisation percentages."""
    percents = psutil.cpu_percent(interval=0.5, percpu=True)
    return (
        f"physical_cores={psutil.cpu_count(logical=False)} "
        f"logical_cores={psutil.cpu_count(logical=True)} "
        f"per_core_usage_pct={percents}"
    )


@tool
def get_memory_info() -> str:
    """Returns total, used and available RAM in gigabytes, plus usage percent."""
    mem = psutil.virtual_memory()
    gb = 1024**3
    return (
        f"total_gb={mem.total / gb:.1f} used_gb={mem.used / gb:.1f} "
        f"available_gb={mem.available / gb:.1f} used_pct={mem.percent}"
    )


@tool
def get_disk_usage(path: str = "/") -> str:
    """Returns total, used and free disk space in gigabytes for the given mount path."""
    usage = psutil.disk_usage(path)
    gb = 1024**3
    return (
        f"path={path} total_gb={usage.total / gb:.1f} used_gb={usage.used / gb:.1f} "
        f"free_gb={usage.free / gb:.1f} used_pct={usage.percent}"
    )


@tool
def get_uptime() -> str:
    """Returns how long this machine has been running since it last booted."""
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = timedelta(seconds=(datetime.now() - boot).total_seconds())
    return f"booted_at={boot.isoformat(timespec='seconds')} uptime={uptime}"


TOOLS = [get_os_info, get_cpu_info, get_memory_info, get_disk_usage, get_uptime]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

model = model.bind_tools(TOOLS)


def run_agent(question: str, max_steps: int = MAX_STEPS) -> str:
    history: list[BaseMessage] = [SystemMessage(AGENT_PROMPT), HumanMessage(question)]

    for _ in range(max_steps):
        # 2 & 3. LLM decides whether it needs a tool and, if so, generates
        #        a structured call (name + typed args) instead of plain text.
        response = model.invoke(history)
        history.append(response)

        if not response.tool_calls:
            # 6. Process: no more tool calls, this is the final answer.
            return response.text

        for call in response.tool_calls:
            print(f"  -> tool call: {call['name']}({call['args']})")
            # 4. Execute: the orchestration layer runs the real function,
            #    the model never touches psutil/platform directly.
            tool_fn = TOOLS_BY_NAME[call["name"]]
            result = tool_fn.invoke(call["args"])
            print(f"  <- observation: {result}")
            # 5. Observe: the result is handed back as a ToolMessage, tied
            #    to the call via tool_call_id, so the next turn can use it.
            history.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    return "Gave up after too many tool-call rounds, see the log above."


def main():
    questions = [
        "What OS and CPU does this machine have?",
        "How much free space is left on the root disk, and how long has the machine been up?",
        "What's the capital of France?",  # off-topic: should be refused, no tool call
    ]

    for question in questions:
        print(f"=== Question ===\n{question}\n")
        answer = run_agent(question)
        print(f"\n=== Answer ===\n{answer}\n")
