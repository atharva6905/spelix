"""Standalone distillation pipeline (Phase 3 Batch 2).

A compiled LangGraph StateGraph that runs async after each completed
coaching analysis and emits candidate coach_brain entries for expert
review. Distinct lifecycle from the Phase 3 coaching agent per
ADR-BRAIN-07.
"""
