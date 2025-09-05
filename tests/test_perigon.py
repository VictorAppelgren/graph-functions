# Minimal test for perigon ingestion pipeline
import sys, os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(PROJECT_ROOT, "main.py")) and PROJECT_ROOT != "/":
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from perigon.news_ingestion_orchestrator import NewsIngestionOrchestrator

def test_perigon():
    orchestrator = NewsIngestionOrchestrator(debug=True)
    results = orchestrator.run_complete_test()

    # Statistics
    stats = results["statistics"]
    print(f"\n📈 STATISTICS:")
    print(f"  • Queries executed:     {stats['queries_executed']}")
    print(f"  • Articles retrieved:   {stats['articles_retrieved']}")
    print(f"  • Articles scraped:     {stats['articles_scraped']}")
    print(f"  • Summaries generated:  {stats['articles_summarized']}")
    print(f"  • Articles stored:      {stats['articles_stored']}")
    print(f"  • Errors:               {stats['errors']}")
    
    # Sample articles
    if results["sample_articles"]:
        print("\n📝 SAMPLE ARTICLES:")
        for i, article in enumerate(results["sample_articles"]):
            print(f"\n  ARTICLE {i+1}: {article['title']}")
            print(f"  {'Source:':<12} {article['source']}")
            print(f"  {'Date:':<12} {article['date']}")
            print(f"  {'Content:':<12} {len(article.get('content',''))} chars")
            print(f"  {'Sources:':<12} {article['num_sources_scraped']} linked sources scraped")
    
    print("\n✅ Pipeline execution successful")
    return 0

if __name__ == "__main__":
    test_perigon()
