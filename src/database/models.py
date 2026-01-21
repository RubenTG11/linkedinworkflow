"""Pydantic models for database entities."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field


class Customer(BaseModel):
    """Customer/Client model."""
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    name: str
    email: Optional[str] = None
    company_name: Optional[str] = None
    linkedin_url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LinkedInProfile(BaseModel):
    """LinkedIn profile model."""
    id: Optional[UUID] = None
    customer_id: UUID
    scraped_at: Optional[datetime] = None
    profile_data: Dict[str, Any]
    name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None


class LinkedInPost(BaseModel):
    """LinkedIn post model."""
    id: Optional[UUID] = None
    customer_id: UUID
    scraped_at: Optional[datetime] = None
    post_url: Optional[str] = None
    post_text: str
    post_date: Optional[datetime] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    raw_data: Optional[Dict[str, Any]] = None


class Topic(BaseModel):
    """Topic model."""
    id: Optional[UUID] = None
    customer_id: UUID
    created_at: Optional[datetime] = None
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    extracted_from_post_id: Optional[UUID] = None
    extraction_confidence: Optional[float] = None
    is_used: bool = False
    used_at: Optional[datetime] = None


class ProfileAnalysis(BaseModel):
    """Profile analysis model."""
    id: Optional[UUID] = None
    customer_id: UUID
    created_at: Optional[datetime] = None
    writing_style: Dict[str, Any]
    tone_analysis: Dict[str, Any]
    topic_patterns: Dict[str, Any]
    audience_insights: Dict[str, Any]
    full_analysis: Dict[str, Any]


class ResearchResult(BaseModel):
    """Research result model."""
    id: Optional[UUID] = None
    customer_id: UUID
    created_at: Optional[datetime] = None
    query: str
    results: Dict[str, Any]
    suggested_topics: List[Dict[str, Any]]
    source: str = "perplexity"


class GeneratedPost(BaseModel):
    """Generated post model."""
    id: Optional[UUID] = None
    customer_id: UUID
    created_at: Optional[datetime] = None
    topic_id: Optional[UUID] = None
    topic_title: str
    post_content: str
    iterations: int = 0
    writer_versions: List[str] = Field(default_factory=list)
    critic_feedback: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "draft"  # draft, approved, published, rejected
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
