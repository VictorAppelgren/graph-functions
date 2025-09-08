"""
Query 1: EURUSD and related economic factors.

This file contains a predefined query for retrieving news related to EURUSD
and associated economic factors for the news ingestion system.
"""

QUERY = """
(EURUSD OR EURUSD) OR (euro OR Euro* OR EUR OR eur*) OR (dollar OR Dollar* OR USD
  OR usd*) OR (exchange OR rate OR currency OR currencies OR forex OR foreign OR market
  OR markets) OR (inflation OR inflat* OR interest OR rate OR rates OR monetary OR
  policy OR central OR bank OR ECB OR Fed OR economic OR economy OR growth OR GDP
  OR recession OR recovery) OR (news OR update OR breaking OR recent OR latest OR
  today OR report OR analysis OR forecast OR outlook OR trend OR movement OR volatility
  OR fluctuation OR change OR shift OR impact) OR (trade OR trades OR trading OR trader
  OR speculation OR speculator OR investment OR investor OR hedge OR hedging OR position
  OR positioning) OR (geopolitical OR political OR event OR events OR risk OR risks
  OR sentiment OR sentiment* OR confidence OR uncertainty OR crisis OR crises OR development
  OR developments)
"""

def get_query():
    """Return the query string for EURUSD and related economic factors.
    
    Returns:
        str: The query string for EURUSD and related economic factors
    """
    return QUERY
