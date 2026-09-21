# 12 — Exception Handling and Recovery

> **Source:** *Agentic Design Patterns* — Chapter 12: Exception Handling and Recovery (PDF pp. 194–201 of `Agentic_Design_Patterns_Complete.pdf`). Condensed rewrite.

## TL;DR

Agents in the real world will meet tool failures, network problems, bad data and odd inputs. This pattern gives them a structured way to **detect → handle → recover** so they fail gracefully (or don't fail at all) instead of crashing or silently going wrong.

## Three stages

### 1. Error detection
- Invalid or malformed tool output.
- API error codes (404, 500, …) and unusually long response times/timeouts.
- Incoherent or off-format model responses.
- Monitoring by other agents or dedicated monitors to catch anomalies early.

### 2. Error handling
| Technique | What it does |
|---|---|
| **Logging** | Record details for debugging and analysis. |
| **Retries** | Repeat, possibly with adjusted parameters — good for *transient* errors (use back-off; don't retry invalid requests forever). |
| **Fallbacks** | Use an alternative tool/method to keep some functionality. |
| **Graceful degradation** | Deliver partial value when full recovery isn't possible. |
| **Notification** | Alert humans or other agents when intervention is needed. |

### 3. Recovery
- **State rollback** – undo recent changes/transactions.
- **Diagnosis** – find the root cause to prevent recurrence.
- **Self-correction / re-planning** – change the plan, logic or parameters (pairs naturally with **reflection**, Ch. 4: analyse the failure, retry with a better prompt).
- **Escalation** – hand over to a human or higher-level system.

## Use cases

- **Support chatbot** with the database down: detect the API error, tell the user, suggest retry, or escalate to a human.
- **Trading bot** hitting "insufficient funds"/"market closed": log it, don't repeat the invalid trade, notify the user.
- **Smart home:** light won't turn on → retry → notify user for manual action.
- **Batch document processing:** skip a corrupted file, log it, continue, report skipped files at the end.
- **Web scraper** meets CAPTCHA/404/503: pause, use a proxy, report the failing URL.
- **Robotic arm** misses a pickup: re-align, retry, then alert an operator or switch component.

## Example (Google ADK): primary → fallback → response

A `SequentialAgent` of three agents gives a layered recovery:

```python
robust_location_agent = SequentialAgent(sub_agents=[
    primary_handler,   # calls get_precise_location_info; on failure sets state["primary_location_failed"]=True
    fallback_handler,  # if the flag is True: extract the city and call get_general_area_info
    response_agent,    # presents state["location_result"], or apologises if missing
])
```

State carries the failure signal between agents, so the fallback runs *only* when needed and the final agent always produces a sane answer.

## Practical tips

- Distinguish transient (retry) from permanent (fallback/escalate) errors.
- Validate tool outputs before feeding them into the next prompt — bad data poisons context.
- Cap retries and total time; make actions **idempotent** where you can.
- Return concise error messages to the LLM so it can reason about alternatives (also true for MCP servers, Ch. 10).

## When to use

Any agent deployed in a dynamic real-world environment where failures, network issues or unpredictable inputs are possible and reliability matters.

## Key takeaways

- Detect (validate outputs, check codes, timeouts) → handle (log, retry, fallback, degrade, notify) → recover (rollback, diagnose, self-correct, escalate).
- Layered fallbacks make agents robust rather than fragile.
- Combine with reflection and human-in-the-loop for hard cases.

**Prev:** [11 — Goal Setting and Monitoring](11-goal-setting-and-monitoring.md) · **Next:** [13 — Human-in-the-Loop](13-human-in-the-loop.md)
