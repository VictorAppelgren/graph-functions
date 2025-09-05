"""
Query 2: AI data centers and related investment topics.

This file contains a predefined query for retrieving news related to AI data centers
and associated investment topics for the news ingestion system.
"""

QUERY = """
(AI_data_centers OR AI_data_centers* OR artificial intelligence data centers OR
  AI infrastructure OR AI computing facilities OR AI server farms OR AI cloud OR AI
  hosting OR AI storage) OR (investment OR investments OR funding OR fund* OR financing
  OR capital OR venture OR back* OR raise* OR round OR acquisition OR buyout OR partnership
  OR joint venture OR expansion OR growth OR development OR market OR markets OR opportunity
  OR opportunities OR entry OR launch OR build OR construction OR establish OR establish*)
  OR (news OR recent OR latest OR breaking OR break* OR today OR update OR announcement
  OR report OR release OR insight OR analysis OR trend OR trends OR forecast OR outlook
  OR overview) OR (data center OR data centers OR datacenter OR datacenters OR colocation
  OR colocation centers OR edge computing OR cloud computing OR hyperscale OR server
  OR servers OR infrastructure OR facility OR facilities OR network OR networks)
"""

def get_query():
    """Return the query string for AI data centers and related investment topics.
    
    Returns:
        str: The query string for AI data centers and related investment topics
    """
    return QUERY
