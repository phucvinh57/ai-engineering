import re
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

model = ChatOllama(
    model="llama3.2",
    temperature=0,
)

MAX_ITERS = 3
MAX_WORDS = 120
APPROVED = "APPROVED"

SUPPORTER_PROMPT = f"""
You are a customer support agent. Write a professional reply to the customer.

Use only the facts provided. Do not invent information, amounts, dates or
policies that are not listed. Keep it under {MAX_WORDS} words.
Return only the reply text.
"""

REVIEWER_PROMPT = f"""
You are a meticulous support quality reviewer. You did not write the reply,
you only check it against the criteria below.

1. It addresses the customer's actual problem and request.
2. Every claim, amount, date and promise is backed by the facts provided.
   Anything not listed there is an unsupported claim.
3. It does not promise a refund, credit or deadline the policy does not allow.
4. It is polite and clear.

If the reply meets every criterion, output exactly: {APPROVED}
Otherwise output a bullet list of concrete problems, one per line, each
starting with "- ". Do not rewrite the reply.
"""

# --- Case: the facts are what the critic checks the draft against ---

CUSTOMER_MESSAGE = """
I was charged twice for my subscription this month and I need this fixed
today, I have a rent payment due. Can you refund one of the charges right now?
"""

FACTS = """
- Invoice INV-1042, 2026-09-01, $19.00, paid
- Invoice INV-1043, 2026-09-01, $19.00, paid (duplicate of INV-1042)
- Policy: duplicate charges are refunded after a billing review.
- Policy: a billing review takes 3-5 business days. It cannot be rushed.
- Policy: refunds go back to the original payment method.
"""


@dataclass
class Round:
    draft: str
    review: str
    approved: bool
    context_chars: int  # size of the producer's history when it wrote this draft


@dataclass
class ReflectionResult:
    final: str
    approved: bool
    rounds: list[Round] = field(default_factory=list)


def rule_checks(draft: str) -> list[str]:
    """Deterministic critic: the checks that do not need an LLM."""
    problems = []
    words = len(draft.split())
    if words > MAX_WORDS:
        problems.append(f"- It has {words} words, the limit is {MAX_WORDS}. Shorten it.")
    if placeholders := re.findall(r"\[[^\]]+\]", draft):
        problems.append(f"- It contains unfilled placeholders {placeholders}. Remove them.")
    return problems


def is_approved(review: str) -> bool:
    """The sentinel must open the reply, so 'not APPROVED: ...' does not count."""
    return review.upper().startswith(APPROVED)


def review_draft(message: str, facts: str, draft: str) -> str:
    """Rules and LLM critic are merged into one feedback message for the producer."""
    # A fresh call with the critic persona. It gets the task and the draft, not the
    # producer's history, so it is not anchored by the earlier rewrites.
    llm_review = model.invoke(
        [
            SystemMessage(REVIEWER_PROMPT),
            HumanMessage(f"Customer message:\n{message}\nFacts:\n{facts}\nReply:\n{draft}"),
        ]
    ).text
    problems = rule_checks(draft)
    if not is_approved(llm_review):
        problems.append(llm_review)
    return "\n".join(problems) or APPROVED


def chars_in(history: list[BaseMessage]) -> int:
    return sum(len(m.text) for m in history)


def reflect(message: str, facts: str, max_iters: int = MAX_ITERS) -> ReflectionResult:
    history: list[BaseMessage] = [
        SystemMessage(SUPPORTER_PROMPT),
        HumanMessage(f"Customer message:\n{message}\nFacts:\n{facts}"),
    ]
    result = ReflectionResult(final="", approved=False)

    for _ in range(max_iters):
        # 1. Execute: generate the first draft, or refine using the last review
        context_chars = chars_in(history)
        draft: AIMessage = model.invoke(history)

        # 2. Evaluate: rules plus a critic persona, merged into one review
        review = review_draft(message, facts, draft.text)

        approved = is_approved(review)
        result.rounds.append(Round(draft.text, review, approved, context_chars))
        result.final = draft.text

        # 3. Stop condition: approved, or the loop runs out of iterations
        if approved:
            result.approved = True
            break

        # 4. Refine: the draft and its review join the history, so the next
        #    round builds on the earlier attempts instead of starting over
        history += [draft, HumanMessage(f"Review:\n{review}\n\nRewrite the reply to fix every point.")]

    return result


def main():
    result = reflect(CUSTOMER_MESSAGE, FACTS)

    print("=== Customer message ===")
    print(CUSTOMER_MESSAGE)

    for i, r in enumerate(result.rounds, start=1):
        print(f"\n=== Draft {i} (producer history: {r.context_chars} chars) ===")
        print(r.draft)
        print(f"\n=== Critique {i} ===")
        print(r.review)

    print("\n=== Final reply ===")
    print(result.final)

    if result.approved:
        print(f"\nApproved by the critic after {len(result.rounds)} round(s).")
    else:
        print(f"\nStopped at the limit of {MAX_ITERS} rounds without approval, review manually.")
