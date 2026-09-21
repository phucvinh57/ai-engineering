from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    RunnableBranch,
    RunnableLambda,
    RunnablePassthrough,
)

model = ChatOllama(
    model="llama3.2",
    temperature=0,
)

ROUTES = {"billing", "technical", "account", "unclear"}
FALLBACK_ROUTE = "unclear"

# --- Router: an LLM call that outputs a single label ---

router_prompt = ChatPromptTemplate.from_template("""
Analyse this customer support message and pick the team that should handle it.

Possible routes:
- billing: charges, invoices, refunds, payments
- technical: bugs, errors, something not working
- account: login problems, forgotten password, password reset, profile, plan changes
- unclear: greetings, or messages that do not describe a specific problem

Customer message:
{message}

Output ONE word only: billing, technical, account or unclear.
""")


def normalize_route(label: str) -> str:
    """Clean up the LLM output and fall back if it is not a known route."""
    label = label.strip().strip(".'\"`").lower()
    return label if label in ROUTES else FALLBACK_ROUTE


router_chain = router_prompt | model | StrOutputParser() | RunnableLambda(normalize_route)

# --- Database step: fetch the customer data the chosen route needs ---


class MockDB:
    """Stand-in for a real database. Swap the bodies for SQL / ORM queries."""

    _invoices = {
        "cus_001": [
            {"id": "INV-1042", "date": "2026-09-01", "amount": 19.0, "status": "paid"},
            {"id": "INV-1043", "date": "2026-09-01", "amount": 19.0, "status": "paid"},
            {"id": "INV-0987", "date": "2026-08-01", "amount": 19.0, "status": "paid"},
        ],
    }
    _accounts = {
        "cus_003": {"email": "sam@example.com", "plan": "pro", "last_login": "2026-08-14"},
    }
    _devices = {
        "cus_002": [{"os": "Android 14", "app_version": "3.8.1", "last_error": "SettingsActivity NPE"}],
    }

    def get_invoices(self, customer_id: str) -> list[dict]:
        return self._invoices.get(customer_id, [])

    def get_account(self, customer_id: str) -> dict | None:
        return self._accounts.get(customer_id)

    def get_devices(self, customer_id: str) -> list[dict]:
        return self._devices.get(customer_id, [])


db = MockDB()


def billing_context(customer_id: str) -> str:
    invoices = db.get_invoices(customer_id)
    return "\n".join(
        f"- {i['id']} on {i['date']}: ${i['amount']:.2f} ({i['status']})" for i in invoices
    )


def account_context(customer_id: str) -> str:
    account = db.get_account(customer_id)
    if account is None:
        return ""
    return "\n".join(f"- {key}: {value}" for key, value in account.items())


def technical_context(customer_id: str) -> str:
    devices = db.get_devices(customer_id)
    return "\n".join(
        f"- {d['os']}, app {d['app_version']}, last error: {d['last_error']}" for d in devices
    )


# Only query what the route needs; routes without an entry skip the database.
CONTEXT_FETCHERS = {
    "billing": billing_context,
    "technical": technical_context,
    "account": account_context,
}


def fetch_context(x: dict) -> str:
    """Runs after the router, so `x` already holds `route` and `customer_id`."""
    fetcher = CONTEXT_FETCHERS.get(x["route"])
    context = fetcher(x["customer_id"]) if fetcher else ""
    return context or "No records found for this customer."


# --- Handlers: one specialised chain per route ---

billing_prompt = ChatPromptTemplate.from_template("""
You are a billing support specialist.
Acknowledge the billing issue, explain the next step (e.g. verify the charge,
start a refund) and keep it concise.
Use the invoice records below to reference the exact invoices involved.
Do not invent information that is not provided.

Customer message:
{message}

Invoices from our database:
{context}
""")

technical_prompt = ChatPromptTemplate.from_template("""
You are a technical support engineer.
Suggest up to three troubleshooting steps and ask for any missing details
(error message, device, version).
Use the device records below and do not ask for details they already contain.
Do not invent information that is not provided.

Customer message:
{message}

Devices from our database:
{context}
""")

account_prompt = ChatPromptTemplate.from_template("""
You are an account support specialist.
Explain how the customer can resolve the account issue, and mention identity
verification when it is relevant.
Use the account record below; never reveal it in full, only confirm what is needed.
Do not invent information that is not provided.

Customer message:
{message}

Account from our database:
{context}
""")

billing_chain = billing_prompt | model | StrOutputParser()
technical_chain = technical_prompt | model | StrOutputParser()
account_chain = account_prompt | model | StrOutputParser()

# A route does not have to be an LLM call: this one is plain code.
clarify_chain = RunnableLambda(
    lambda _: (
        "Thanks for reaching out! Could you tell us a bit more about what you "
        "need help with? For example, is it about a payment, something not "
        "working, or your account?"
    )
)

# --- Dispatcher: read the route, then branch (the last branch is the default) ---

branch = RunnableBranch(
    (lambda x: x["route"] == "billing", billing_chain),
    (lambda x: x["route"] == "technical", technical_chain),
    (lambda x: x["route"] == "account", account_chain),
    clarify_chain,
)

# assign() adds a key to the input dict, so later steps still see the earlier keys:
# classify -> load data for that route from the DB -> generate the response
routing_chain = (
    RunnablePassthrough.assign(route=router_chain)
    | RunnablePassthrough.assign(context=RunnableLambda(fetch_context))
    | RunnablePassthrough.assign(response=branch)
)


def main():
    tickets = [
        ("cus_001", "I was charged twice for my subscription this month. Can you refund one?"),
        ("cus_002", "The app crashes every time I open the settings page on Android."),
        ("cus_003", "I forgot my password and the reset email never arrives."),
        ("cus_004", "Hello, can someone help me?"),
    ]

    for customer_id, message in tickets:
        result = routing_chain.invoke({"customer_id": customer_id, "message": message})

        print(f"=== Message ({customer_id}) ===\n{message}")
        print(f"\n=== Route ===\n{result['route']}")
        print(f"\n=== DB context ===\n{result['context']}")
        print(f"\n=== Response ===\n{result['response']}\n")
