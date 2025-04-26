from langchain.prompts import PromptTemplate

# Prompt for generating the main document content
content_generation_template = """
Based on these instructions: "{topic}", please generate comprehensive and well-structured content suitable for a Google Document.
The content should be as informative as the user requests it to be.
Format the output clearly.

Generated Content:
"""
CONTENT_GENERATION_PROMPT = PromptTemplate(
    input_variables=["topic"],
    template=content_generation_template,
)

# Prompt for generating a concise title based on the content
title_generation_template = """
Given the following topic and generated document content, create a short, relevant, and engaging title for the Google Document.

Topic: {topic}

Generated Content:
{generated_content}

Concise Title:
"""
TITLE_GENERATION_PROMPT = PromptTemplate(
    input_variables=["topic", "generated_content"],
    template=title_generation_template,
)
