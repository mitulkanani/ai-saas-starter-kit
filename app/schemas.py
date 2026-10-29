from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=5, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=128)
    organization_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str


class OrganizationOut(BaseModel):
    id: str
    name: str
    slug: str
    role: str
    monthly_token_limit: int
    monthly_used_tokens: int
    usage_month: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut
    organizations: list[OrganizationOut]


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)


class MeResponse(BaseModel):
    id: str
    email: str


class SummarizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: str = Field(min_length=36, max_length=36)
    input_text: str = Field(min_length=10, max_length=30000)
    max_output_tokens: int = Field(default=160, ge=32, le=500)


class SummarizeResponse(BaseModel):
    organization_id: str
    summary: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    usage_month: str
    usage_used_tokens: int
    usage_limit_tokens: int
    remaining_tokens: int


class UsageResponse(BaseModel):
    organization_id: str
    billing_month: str
    used_tokens: int
    limit_tokens: int
    remaining_tokens: int
    event_count: int
    estimated_cost_usd: float


class UsageEventOut(BaseModel):
    id: str
    user_id: str
    operation: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    billing_month: str
    created_at: str
