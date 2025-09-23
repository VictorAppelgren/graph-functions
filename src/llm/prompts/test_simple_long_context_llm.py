test_simple_long_context_llm_prompt = """
    Repeat the following sentence exactly once: {text}
    
    Return your answer as JSON with this exact format:
    {{"response": "the repeated sentence here"}}
    """