"""agents package"""
from agents.base_agent import BaseAgent, AgentResult
from agents.discovery_agent import DiscoveryAgent
from agents.reviewer_agent import ReviewerAgent
from agents.methodology_agent import MethodologyAgent
from agents.citation_agent import CitationAgent
from agents.writing_agent import WritingAgent

__all__ = [
    "BaseAgent", "AgentResult",
    "DiscoveryAgent", "ReviewerAgent",
    "MethodologyAgent", "CitationAgent", "WritingAgent",
]
