from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

model = ChatOllama(
    model="llama3.2",
    temperature=0,
)

classify_prompt = ChatPromptTemplate.from_template("""
Classify this customer support message.

Possible categories:
- billing
- technical
- account
- refund
- other

Customer message:
{message}

Return only the category.
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

draft_prompt = ChatPromptTemplate.from_template("""
Write a professional customer support response.

Category:
{category}

Information extracted:
{information}

Keep the response concise and helpful.
Do not invent information that is not provided.
""")

review_prompt = ChatPromptTemplate.from_template("""
Review this customer support response.

Check:
1. Does it address the customer's problem?
2. Does it make unsupported claims?
3. Is it professional and clear?

If there are problems, rewrite it.
Otherwise, return it unchanged.

Customer message:
{message}

Response:
{response}
""")

classify_chain = classify_prompt | model
extract_chain = extract_prompt | model
draft_chain = draft_prompt | model
review_chain = review_prompt | model


def main():
    message = """
    I was charged twice for my subscription this month.
    Can you check what happened and refund one of the charges?
    """

    category = classify_chain.invoke({"message": message}).content

    information = extract_chain.invoke({"message": message}).content

    response = draft_chain.invoke(
        {
            "category": category,
            "information": information,
        }
    ).content

    final_response = review_chain.invoke(
        {
            "message": message,
            "response": response,
        }
    ).content

    print("=== Category ===")
    print(category)

    print("\n=== Extracted information ===")
    print(information)

    print("\n=== Draft ===")
    print(response)

    print("\n=== Final response ===")
    print(final_response)
