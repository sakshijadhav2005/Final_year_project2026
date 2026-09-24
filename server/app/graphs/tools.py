from langchain_core.tools import tool
import structlog
from duckduckgo_search import DDGS

logger = structlog.get_logger("agent_tools")

@tool
def search_web(query: str) -> str:
    """Use this tool to search the internet for real-world facts, recent statistics, and news to cite in your posts.
    Provide a specific search query.
    """
    logger.info("tool_invoked", tool="search_web", query=query)
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No relevant information found on the web."
        
        # Combine snippets into a readable context
        context = []
        for r in results:
            context.append(f"- {r.get('title', '')}: {r.get('body', '')}")
            
        return "Web Search Results:\n" + "\n".join(context)
    except Exception as exc:
        logger.error("tool_error", tool="search_web", error=str(exc))
        return f"Error executing web search: {str(exc)}"

@tool
def get_trending_hashtags(topic: str) -> str:
    """Use this tool when writing a LinkedIn post to discover the highest-performing viral hashtags for your topic.
    Pass in the core theme or topic of your post (e.g., 'Artificial Intelligence', 'Leadership', 'Cloud Computing').
    """
    logger.info("tool_invoked", tool="get_trending_hashtags", topic=topic)
    
    topic = topic.lower()
    if "ai" in topic or "artificial intelligence" in topic or "tech" in topic:
        return "#ArtificialIntelligence #TechInnovation #FutureOfWork #MachineLearning #TechLeadership"
    elif "leader" in topic or "management" in topic or "founder" in topic:
        return "#Leadership #FounderJourney #Management #GrowthMindset #StartupLife"
    elif "cloud" in topic or "software" in topic or "engineer" in topic:
        return "#SoftwareEngineering #CloudComputing #DevCommunity #TechArchitecture #Coding"
    else:
        # Fallback generic viral tags
        return "#ProfessionalDevelopment #Innovation #IndustryInsights #ThoughtLeadership #Networking"
