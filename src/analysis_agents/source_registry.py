"""
Source Registry - Track all sources through the pipeline

Ensures every piece of information is traceable back to its source.
"""

from typing import List, Dict, Any, Set
from dataclasses import dataclass, field


@dataclass
class SourceRegistry:
    """
    Tracks all sources used in analysis generation.
    
    Each agent adds sources it uses, and the registry is passed
    through the entire pipeline.
    """
    
    # All articles found by graph exploration
    articles_found: List[Dict[str, Any]] = field(default_factory=list)
    
    # Articles selected by each agent
    articles_selected_by_agent: Dict[str, List[str]] = field(default_factory=dict)
    
    # Related topics found
    related_topics_found: List[Dict[str, Any]] = field(default_factory=list)
    
    # All article IDs mentioned in any output
    article_ids_mentioned: Set[str] = field(default_factory=set)
    
    # Topic IDs mentioned
    topic_ids_mentioned: Set[str] = field(default_factory=set)
    
    def add_articles_found(self, articles: List[Dict[str, Any]], agent_name: str):
        """Record articles found by an agent"""
        self.articles_found.extend(articles)
        article_ids = [a.get('id', 'unknown') for a in articles]
        self.articles_selected_by_agent[agent_name] = article_ids
        self.article_ids_mentioned.update(article_ids)
    
    def add_related_topics(self, topics: List[Dict[str, Any]]):
        """Record related topics found"""
        self.related_topics_found.extend(topics)
        topic_ids = [t.get('topic_id', 'unknown') for t in topics]
        self.topic_ids_mentioned.update(topic_ids)
    
    def add_article_mention(self, article_id: str):
        """Record that an article was mentioned in output"""
        self.article_ids_mentioned.add(article_id)
    
    def get_summary(self) -> str:
        """Get human-readable summary of sources"""
        lines = []
        lines.append(f"📚 Total articles found: {len(self.articles_found)}")
        lines.append(f"🔗 Related topics found: {len(self.related_topics_found)}")
        lines.append(f"📝 Article IDs mentioned: {len(self.article_ids_mentioned)}")
        
        if self.articles_selected_by_agent:
            lines.append(f"\n📊 Articles selected by agent:")
            for agent, ids in self.articles_selected_by_agent.items():
                lines.append(f"   • {agent}: {len(ids)} articles")
                lines.append(f"     IDs: {', '.join(ids[:5])}" + (f" (+{len(ids)-5} more)" if len(ids) > 5 else ""))
        
        if self.related_topics_found:
            lines.append(f"\n🔗 Related topics:")
            for topic in self.related_topics_found[:5]:
                lines.append(f"   • {topic.get('topic_name', 'unknown')} ({topic.get('topic_id', 'unknown')})")
        
        return "\n".join(lines)
    
    def get_article_details(self, article_id: str) -> Dict[str, Any]:
        """Get full details for an article"""
        for article in self.articles_found:
            if article.get('id') == article_id:
                return article
        return {}
    
    def get_all_article_ids(self) -> List[str]:
        """Get all unique article IDs"""
        return list(self.article_ids_mentioned)
