import asyncio
from pathlib import Path
from app.graphs.pipeline import get_compiled_graph
from app.graphs.state import JobGraphState

async def test_dynamic_pipeline():
    print("Testing dynamic pipeline...")
    
    # Load mock transcript
    root_dir = Path(__file__).resolve().parent.parent
    transcript_path = root_dir / "data" / "samples" / "clean_event_session.txt"
    transcript_text = transcript_path.read_text() if transcript_path.exists() else "Sample transcript text"

    # Setup graph state requesting ONLY linkedin
    state: JobGraphState = {
        "job_id": "test_123",
        "user_id": "user_456",
        "transcript_text": transcript_text,
        "requested_types": ["linkedin"],  # DYNAMIC FAN-OUT TO LINKEDIN ONLY
        "user_memory": {
            "full_name": "Durvas Harkulkar",
            "organization": "Tech Community",
            "brand_tone": "innovative, professional",
            "linkedin_handle": "@durvas",
        },
        "generated": []
    }

    graph = get_compiled_graph()
    
    # Start execution starting from "content_planner" to skip audio validation phase
    print("Invoking graph from content_planner...")
    result = await graph.ainvoke(state)
    
    print("\n=== PIPELINE EXECUTION COMPLETE ===")
    generated_pieces = result.get("generated", [])
    print(f"Generated {len(generated_pieces)} post(s).\n")
    
    for piece in generated_pieces:
        print(f"Type: {piece.get('type')}")
        print(f"Title: {piece.get('title')}")
        print("-" * 40)
        print(piece.get('body'))
        print("\n==================================\n")

if __name__ == "__main__":
    # We must load env variables so Gemini API key is found
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    
    asyncio.run(test_dynamic_pipeline())
