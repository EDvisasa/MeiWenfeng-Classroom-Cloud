import pytest
import os
from unittest.mock import patch, MagicMock

from backend.services.chroma_client import ChromaRAGClient
from backend.services.course_manager import set_active_course_id, reset_active_course_id


def test_chroma_sync_and_retrieve_course_isolation(tmp_path):
    """Verify ChromaRAGClient tags chunks with course_id and filters retrieval by course_id."""
    client = ChromaRAGClient()

    # Mock collection
    mock_collection = MagicMock()
    mock_collection.count.return_value = 10

    # Store upserted documents and metadatas
    stored_docs = []
    stored_metas = []

    def mock_upsert(documents, ids, metadatas):
        stored_docs.extend(documents)
        stored_metas.extend(metadatas)

    mock_collection.upsert.side_effect = mock_upsert

    def mock_query(query_texts, n_results, include, where=None):
        # Filter documents based on where clause
        filtered = []
        for doc, meta in zip(stored_docs, stored_metas):
            cid = meta.get("course_id")
            if where:
                if "$or" in where:
                    allowed = [cond["course_id"] for cond in where["$or"] if "course_id" in cond]
                    if cid in allowed:
                        filtered.append(doc)
                elif where.get("course_id"):
                    if cid == where["course_id"]:
                        filtered.append(doc)
            else:
                filtered.append(doc)
        return {"documents": [filtered], "distances": [[0.3] * len(filtered)]}

    mock_collection.query.side_effect = mock_query

    with patch.object(client, "_get_collection", return_value=mock_collection):
        # 1. Sync files for Course A: fluid_mechanics
        client.sync_knowledge(
            {"navier_stokes.md": "Navier-Stokes equations describe fluid motion and viscosity."},
            course_id="fluid_mechanics"
        )

        # 2. Sync files for Course B: quantum_physics
        client.sync_knowledge(
            {"schrodinger.md": "Schrodinger equation describes quantum wave function evolution."},
            course_id="quantum_physics"
        )

        # 3. Sync files for default course
        client.sync_knowledge(
            {"common_math.md": "Linear algebra vectors and matrix transformations."},
            course_id="default"
        )

        # 4. Verify metadatas have course_id
        cids = [m["course_id"] for m in stored_metas]
        assert "fluid_mechanics" in cids
        assert "quantum_physics" in cids
        assert "default" in cids

        # 5. Retrieve for Course A: should get fluid and default, NEVER quantum
        results_a = client.retrieve("equation", course_id="fluid_mechanics")
        combined_a = " ".join(results_a)
        assert "Navier-Stokes" in combined_a
        assert "Schrodinger" not in combined_a

        # 6. Retrieve for Course B: should get quantum and default, NEVER fluid
        results_b = client.retrieve("equation", course_id="quantum_physics")
        combined_b = " ".join(results_b)
        assert "Schrodinger" in combined_b
        assert "Navier-Stokes" not in combined_b


def test_context_manager_passes_active_course_to_rag(tmp_path):
    """Verify context_manager passes active_course_id to rag_client.retrieve."""
    from backend.services.context_manager import build_base_system_prompt

    set_active_course_id("robotics_motion")

    with patch("backend.services.rag_factory.get_rag_client") as mock_get_rag:
        mock_rag = MagicMock()
        mock_rag.retrieve.return_value = ["Robotics inverse kinematics chunk"]
        mock_rag.retrieve_memory.return_value = []
        mock_get_rag.return_value = mock_rag

        system_prompt, _, _ = build_base_system_prompt("Tell me about kinematics")

        assert mock_rag.retrieve.called
        # Verify course_id was passed
        kwargs = mock_rag.retrieve.call_args[1]
        assert kwargs.get("course_id") == "robotics_motion"

    reset_active_course_id()

