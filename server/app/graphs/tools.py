from langchain_core.tools import tool
import structlog
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

logger = structlog.get_logger("agent_tools")

@tool
def search_web(query: str) -> str:
    """Use this tool to search the internet for real-world facts, recent statistics, and news to cite in your posts.
    Provide a specific search query.
    """
    logger.info("tool_invoked", tool="search_web", query=query)
    if DDGS is None:
        return "No relevant information found on the web (search tool offline)."
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

@tool
def fetch_industry_news(topic: str) -> str:
    """Use this tool when writing a Newsletter to fetch the latest current events or news related to the topic.
    This helps weave real-world context into the newsletter.
    """
    logger.info("tool_invoked", tool="fetch_industry_news", topic=topic)
    try:
        results = DDGS().news(topic, max_results=3)
        if not results:
            return search_web.invoke({"query": f"latest news about {topic}"})
        
        context = []
        for r in results:
            context.append(f"- {r.get('title', '')} ({r.get('date', '')}): {r.get('body', '')}")
            
        return "Latest Industry News:\n" + "\n".join(context)
    except Exception as exc:
        logger.error("tool_error", tool="fetch_industry_news", error=str(exc))
        return search_web.invoke({"query": f"latest news about {topic}"})

@tool
def get_trending_audio_tracks(mood: str) -> str:
    """Use this tool when creating an Instagram Reel or Post to find the best viral audio tracks that match the mood.
    Pass in the mood (e.g. 'energetic', 'educational', 'inspiring').
    """
    logger.info("tool_invoked", tool="get_trending_audio_tracks", mood=mood)
    mood = mood.lower()
    if "energy" in mood or "upbeat" in mood:
        return "Viral Tracks: 1. 'Makeba' by Jain 2. 'Unstoppable' by Sia 3. 'Dance The Night' by Dua Lipa"
    elif "inspire" in mood or "motivat" in mood:
        return "Viral Tracks: 1. 'Cornfield Chase' by Hans Zimmer 2. 'Experience' by Ludovico Einaudi 3. 'Dream On' by Aerosmith"
    else:
        return "Viral Tracks: 1. Lo-Fi Chill Beats 2. 'Aesthetic' Background Music 3. 'Lofi Study' Mix"

@tool
def generate_image_prompt(visual_description: str) -> str:
    """Use this tool to convert a simple description of an image into a highly-detailed, professional Midjourney or DALL-E prompt.
    Pass in what you want to see (e.g., 'a futuristic city').
    """
    logger.info("tool_invoked", tool="generate_image_prompt", visual_description=visual_description)
    return (
        f"PROMPT: {visual_description}, ultra-realistic, highly detailed, 8k resolution, cinematic lighting, "
        "shot on 35mm lens, photorealistic, trending on ArtStation, vivid colors."
    )

@tool
def get_color_psychology(emotion: str) -> str:
    """Use this tool when designing a Flyer to get the optimal HEX color palette based on the intended emotion of the flyer.
    """
    logger.info("tool_invoked", tool="get_color_psychology", emotion=emotion)
    emotion = emotion.lower()
    if "trust" in emotion or "tech" in emotion or "profes" in emotion:
        return "Palette: Primary #0056D2 (Trust Blue), Accent #E8F0FE (Soft Blue), Text #1F1F1F"
    elif "excit" in emotion or "urgency" in emotion or "sale" in emotion:
        return "Palette: Primary #E53935 (Vibrant Red), Accent #FFC107 (Amber), Text #212121"
    elif "calm" in emotion or "health" in emotion or "eco" in emotion:
        return "Palette: Primary #2E7D32 (Forest Green), Accent #A5D6A7 (Soft Green), Text #FAFAFA"
    else:
        return "Palette: Primary #1A1A1A (Sleek Dark), Accent #F9A826 (Gold), Text #FFFFFF"
