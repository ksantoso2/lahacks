import asyncio
from langchain.chains.llm import LLMChain
from .llms import gemini_llm
from .prompts import CONTENT_GENERATION_PROMPT, TITLE_GENERATION_PROMPT
from .tools import CreateGoogleDocTool  # Assuming the tool is defined properly

async def generate_doc_content_and_title(topic: str) -> tuple[str, str]:
    """Generates document content and a title based on the topic."""
    print(f"Generating content for topic: '{topic}'...")
    content_chain = LLMChain(llm=gemini_llm, prompt=CONTENT_GENERATION_PROMPT)
    content_result = await content_chain.ainvoke({"topic": topic})
    generated_content = content_result.get("text", "").strip()
    print(f"Content generated (first 100 chars): {generated_content[:100]}...")

    print("Generating title...")
    title_chain = LLMChain(llm=gemini_llm, prompt=TITLE_GENERATION_PROMPT)
    title_result = await title_chain.ainvoke({"topic": topic, "generated_content": generated_content})
    generated_title = title_result.get("text", "Untitled Document").strip().strip('"')  # Clean up potential quotes
    print(f"Title generated: '{generated_title}'")

    return generated_title, generated_content

async def run_generation_with_hitl(topic: str, access_token: str) -> str:
    """
    Full chain: Generate content, title, ask for human approval, then create doc.
    """
    # 1. Generate Title and Content
    try:
        generated_title, generated_content = await generate_doc_content_and_title(topic)
    except Exception as e:
        return f"Error during generation: {e}"

    # 2. Human-in-the-Loop (HITL)
    print("\n" + "="*30)
    print("HUMAN REVIEW STEP")
    print("="*30)
    print(f"Generated Title: {generated_title}")
    print("-" * 30)
    print("Generated Content:")
    print(generated_content[:500] + "..." if len(generated_content) > 500 else generated_content)
    print("=" * 30)

    while True:
        approve = input("Do you want to create this Google Doc? (y/n): ").lower().strip()
        if approve == 'y':
            print("Approval received. Proceeding with document creation...")
            break
        elif approve == 'n':
            print("Operation cancelled by user.")
            return "Document creation cancelled."
        else:
            print("Invalid input. Please enter 'y' or 'n'.")

    # 3. Create Google Doc (if approved)
    doc_tool = CreateGoogleDocTool()
    try:
        creation_result = await doc_tool.arun(tool_input={
            "title": generated_title,
            "content": generated_content,
            "access_token": access_token
        })
        return creation_result
    except Exception as e:
        return f"Error during document creation tool execution: {e}"
