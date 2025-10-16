test_medium_llm_prompt = """
    Summarize this text in one sentence:
    Text: {text}
    
    Return your answer as JSON with this exact format:
    {{"response": "your one sentence summary here"}}
    """