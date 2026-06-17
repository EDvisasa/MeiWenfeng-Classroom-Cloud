import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.chroma_client import chroma_rag_client
from backend.services.rag_factory import get_rag_client

def test_long_term_memory_retrieval():
    query = "6-2干了啥"

    # 1. Test Classroom_Knowledge
    print("Testing Classroom_Knowledge retrieval...")
    kb = chroma_rag_client.retrieve(query, dataset_names=["Classroom_Knowledge"])
    print(f"Results: {len(kb)}")

    # 2. Test Memory_Knowledge
    print("\nTesting Memory_Knowledge retrieval...")
    mem_kb = chroma_rag_client.retrieve(query, dataset_names=["Memory_Knowledge"])
    print(f"Results: {len(mem_kb)}")
    if mem_kb:
        print("Sample:", mem_kb[0][:100])

    # 3. Test raw conversation_memory
    print("\nTesting conversation_memory retrieval...")
    rag_client = get_rag_client()
    mem_raw = rag_client.retrieve_memory(query, n_results=3)
    print(f"Results: {len(mem_raw)}")
    if mem_raw:
        print("Sample:", mem_raw[0][:100])

if __name__ == "__main__":
    test_long_term_memory_retrieval()
