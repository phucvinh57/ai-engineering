import time
from operator import itemgetter

from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel

model = ChatOllama(
    model="llama3.2",
    temperature=0,
)

# --- Branches: independent analyses of the same message ---
# None of these needs another one's output, so they can run at the same time.

category_prompt = ChatPromptTemplate.from_template("""
Classify this customer support message.

Possible categories: billing, technical, account, refund, other.

Customer message:
{message}

Return only the category.
""")

sentiment_prompt = ChatPromptTemplate.from_template("""
Detect the customer's sentiment in this message.

Customer message:
{message}

Return only one word: positive, neutral, frustrated or angry.
""")

urgency_prompt = ChatPromptTemplate.from_template("""
Rate how urgent this customer support message is.

Customer message:
{message}

Return only one word: low, medium or high.
""")

extract_prompt = ChatPromptTemplate.from_template("""
Extract the important information from this customer message.

Return:
- problem
- requested_action
- relevant_details

Customer message:
{message}
""")

category_chain = category_prompt | model | StrOutputParser()
sentiment_chain = sentiment_prompt | model | StrOutputParser()
urgency_chain = urgency_prompt | model | StrOutputParser()
extract_chain = extract_prompt | model | StrOutputParser()

# --- Fan-out: RunnableParallel runs every branch concurrently on the same input ---
# The result is a dict with one key per branch. The original message is
# forwarded too, because the fan-in step needs it.

analysis_chain = RunnableParallel(
    {
        "category": category_chain,
        "sentiment": sentiment_chain,
        "urgency": urgency_chain,
        "information": extract_chain,
        "message": itemgetter("message"),
    }
)

# --- Fan-in: one LLM call that waits for every branch, then merges them ---

triage_prompt = ChatPromptTemplate.from_template("""
Write a short triage note for a support agent, then a professional reply
to the customer.

Use only the analysis below. Do not invent information that is not provided.

Category: {category}
Sentiment: {sentiment}
Urgency: {urgency}

Information extracted:
{information}

Customer message:
{message}
""")

triage_chain = triage_prompt | model | StrOutputParser()

# Fan-out then fan-in is just composition: analysis_chain | triage_chain

# --- The same analysis run one step after the other, for comparison ---


def run_sequential(message: str) -> dict:
    return {
        "category": category_chain.invoke({"message": message}),
        "sentiment": sentiment_chain.invoke({"message": message}),
        "urgency": urgency_chain.invoke({"message": message}),
        "information": extract_chain.invoke({"message": message}),
        "message": message,
    }


def main():
    message = """
    I was charged twice for my subscription this month and I need this fixed
    today, I have a rent payment due. Can you check what happened and refund
    one of the charges?
    """

    start = time.perf_counter()
    run_sequential(message)
    sequential_time = time.perf_counter() - start

    start = time.perf_counter()
    analysis = analysis_chain.invoke({"message": message})
    parallel_time = time.perf_counter() - start

    triage = triage_chain.invoke(analysis)

    print("=== Category ===")
    print(analysis["category"])

    print("\n=== Sentiment ===")
    print(analysis["sentiment"])

    print("\n=== Urgency ===")
    print(analysis["urgency"])

    print("\n=== Extracted information ===")
    print(analysis["information"])

    print("\n=== Triage note and reply ===")
    print(triage)

    print("\n=== Latency of the 4 analysis calls ===")
    print(f"sequential: {sequential_time:.1f}s")
    print(f"parallel:   {parallel_time:.1f}s")
