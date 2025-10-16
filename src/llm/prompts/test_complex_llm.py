test_complex_llm_prompt = """
    Analyze the market implications of this news in 2-3 sentences:
    News: {news}
    
    Return your answer as JSON with this exact format:
    {{"response": "your 2-3 sentence market analysis here"}}
    """