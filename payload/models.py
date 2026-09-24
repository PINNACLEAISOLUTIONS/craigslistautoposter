from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class AccountCredentials(BaseModel):
    account_id: str
    email: str
    password: Optional[str] = None
    session_file: Optional[str] = None

class PostAttributes(BaseModel):
    condition: Optional[str] = None  # new, like new, excellent, good, fair, salvage
    make_manufacturer: Optional[str] = None
    model_name_number: Optional[str] = None
    size_dimensions: Optional[str] = None
    cryptocurrency_ok: bool = False
    delivery_available: bool = False
    more_ads_by_user: bool = False

class PostPayload(BaseModel):
    id: str = Field(default="job-001", description="Unique identifier for post job")
    subdomain: str = Field(..., description="Craigslist city subdomain, e.g. sfbay, losangeles, austin")
    type_of_post: str = Field(default="for sale by owner", description="Posting category group")
    category: str = Field(..., description="Specific subcategory name, e.g. electronics - by owner, general for sale")
    sub_area: Optional[str] = Field(None, description="Sub-area option, e.g. city of san francisco, south bay")
    
    title_spintax: str = Field(..., description="Title with spintax format, e.g. '{Brand New|Like New} iPhone 15 Pro'")
    body_spintax: str = Field(..., description="Body with spintax format")
    price: Optional[str] = Field(None, description="Item price, e.g. '450'")
    postal_code: str = Field(..., description="Zip/Postal code")
    neighborhood: Optional[str] = Field(None, description="Neighborhood name, e.g. Downtown / SOMA")
    
    attributes: PostAttributes = Field(default_factory=PostAttributes)
    images: List[str] = Field(default_factory=list, description="File paths to images to upload")
    
    show_phone_ok: bool = False
    phone_number: Optional[str] = None
    contact_name: Optional[str] = None

class JobResult(BaseModel):
    job_id: str
    success: bool
    post_url: Optional[str] = None
    generated_title: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str
