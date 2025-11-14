"""
Database Schemas for Voting App

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal

# Core domain models

AllowedCategory = Literal["websites", "tools", "apps", "ideas", "misc"]

class Votingitem(BaseModel):
    """
    Voting items submitted by users
    Collection name: "votingitem"
    """
    title: str = Field(..., description="Item title, e.g., 'Best JS Framework'")
    category: AllowedCategory = Field(..., description="Item category")
    description: Optional[str] = Field(None, description="Optional description")
    image: Optional[HttpUrl] = Field(None, description="Optional image URL")
    link: Optional[HttpUrl] = Field(None, description="Optional external link")
    upvotes: int = Field(0, ge=0, description="Total upvotes")
    downvotes: int = Field(0, ge=0, description="Total downvotes")
    score: int = Field(0, description="Computed: upvotes - downvotes")

class Vote(BaseModel):
    """
    Votes on items
    Collection name: "vote"
    """
    item_id: str = Field(..., description="Target item id (as string)")
    direction: Literal["up", "down"] = Field(..., description="Vote direction")
    # Anti-duplication identifiers
    session_id: Optional[str] = Field(None, description="Anonymous session identifier")
    user_id: Optional[str] = Field(None, description="Authenticated user id if logged in")
