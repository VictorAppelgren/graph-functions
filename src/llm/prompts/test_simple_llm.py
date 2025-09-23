test_simple_llm_prompt = """
    Classify this text as either "positive" or "negative":
    Text: {text}
    
    Return your answer as JSON with this exact format:
    {{"response": "positive"}} or {{"response": "negative"}}
    """