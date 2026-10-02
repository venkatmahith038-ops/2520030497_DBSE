import re
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

# An uploaded attachment is referenced by its stored file name only. Anything
# with a separator, a drive letter, or ".." is refused here so a scheduled post
# can never point the sender at a file outside the upload directory.
_SAFE_UPLOAD_NAME = re.compile(r"^[A-Za-z0-9._\- ]{1,255}$")


def validate_media_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if value.startswith(("http://", "https://")):
        return value
    if ".." in value or not _SAFE_UPLOAD_NAME.match(value):
        raise ValueError("media_path must be an uploaded file name or an http(s) URL")
    return value


def validate_batch_messages(value: Optional[list]) -> Optional[list]:
    """Each follow-up message carries its own attachment, so apply the same rule."""
    if not value:
        return value
    for message in value:
        if isinstance(message, dict):
            validate_media_path(message.get("media_path"))
    return value

# --- Auth Schemas ---
class UserRegisterSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)

class UserLoginSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    is_admin: bool
    username: str

class UserResponseSchema(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

# --- Instagram Account Proxy Updates ---
class AccountSchema(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: Optional[str] = Field(None, max_length=200)
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None

class AccountResponse(BaseModel):
    id: int
    username: str
    status: str
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- Monitored Posts CRUD updates ---
class MonitoredPostCreate(BaseModel):
    post_url: str = Field(..., min_length=10)
    # Not required when match_mode is "any" — there is no keyword to match.
    trigger_keyword: str = ""
    match_mode: str = "exact"
    template_id: int
    account_id: int
    is_active: bool = True

    @field_validator("match_mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        value = (value or "exact").strip().lower()
        if value not in {"exact", "any"}:
            raise ValueError("match_mode must be 'exact' or 'any'")
        return value

    @model_validator(mode="after")
    def _keyword_required_for_exact(self):
        self.trigger_keyword = (self.trigger_keyword or "").strip()
        if self.match_mode == "exact" and not self.trigger_keyword:
            raise ValueError("A trigger keyword is required when match_mode is 'exact'")
        if self.match_mode == "any":
            # Any stored keyword would be misleading — nothing reads it.
            self.trigger_keyword = ""
        return self

class MonitoredPostResponse(BaseModel):
    id: int
    post_url: str
    trigger_keyword: str
    match_mode: str = "exact"
    template_id: int
    account_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# --- Target Queue Updates ---
class TargetCreateSchema(BaseModel):
    usernames: List[str]
    account_id: int

class TargetResponse(BaseModel):
    id: int
    username: str
    status: str
    account_id: int
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    message_sent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- Message Templates ---
class MessageTemplateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    is_active: bool = True

class MessageTemplateUpdateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)

class MessageTemplateResponse(BaseModel):
    id: int
    name: str
    content: str
    is_active: bool
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# --- Admin Monitoring Schemas ---
class AdminUserDetailResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    is_enabled: bool = True
    is_approved: bool = False
    created_at: datetime
    accounts: List[AccountResponse] = []
    ig_accounts: int = 0
    dms_sent: int = 0
    dms_failed: int = 0
    pending: int = 0
    tg_bots: int = 0
    tg_channels: int = 0
    tg_posts_sent: int = 0
    ig_cost: float = 0.0
    tg_cost: float = 0.0
    total_cost: float = 0.0

    class Config:
        from_attributes = True

class AdminSystemStatsResponse(BaseModel):
    ig_bot_running: bool = False
    tg_service_running: bool = False
    bot_running: bool = False
    total_users: int = 0
    total_accounts: int = 0
    total_dms_sent: int = 0
    total_dms_failed: int = 0
    total_pending_targets: int = 0
    total_tg_bots: int = 0
    total_tg_channels: int = 0
    total_tg_posts_sent: int = 0
    total_tg_posts_pending: int = 0
    total_ig_cost: float = 0.0
    total_tg_cost: float = 0.0
    total_system_cost: float = 0.0


# ── Telegram Schemas ──────────────────────────────────────────────────────────

class TgBotConfigCreate(BaseModel):
    bot_token: str = Field(..., min_length=10)

class TgScheduledPostCreate(BaseModel):
    channel_id: int
    content: str = ""
    scheduled_at: datetime
    message_type: str = "text"
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    batch_messages: Optional[list] = None

    _check_media_path = field_validator("media_path")(validate_media_path)
    _check_batch = field_validator("batch_messages")(validate_batch_messages)

class TgScheduledPostUpdate(BaseModel):
    content: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    message_type: Optional[str] = None
    media_type: Optional[str] = None
    media_path: Optional[str] = None
    is_recurring: Optional[bool] = None
    recurrence_rule: Optional[str] = None
    batch_messages: Optional[list] = None

    _check_media_path = field_validator("media_path")(validate_media_path)
    _check_batch = field_validator("batch_messages")(validate_batch_messages)

class TgModerationRuleCreate(BaseModel):
    channel_id: int
    rule_type: str = Field(..., min_length=1)
    config: str


# ── Notification Schemas ─────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    category: str
    is_read: bool
    link: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Media Library Schemas ────────────────────────────────────────────────────

class MediaFileResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    mime_type: Optional[str] = None
    file_size: int
    folder: str
    tags: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Contact CRM Schemas ─────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    platform: str = "instagram"
    display_name: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: str = "lead"

class ContactUpdate(BaseModel):
    display_name: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class ContactResponse(BaseModel):
    id: int
    username: str
    platform: str
    display_name: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    status: str
    last_contacted_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Feature Flag Schemas ─────────────────────────────────────────────────────

class FeatureFlagCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = "on"
    scope: str = "global"
    scope_id: Optional[int] = None

class FeatureFlagUpdate(BaseModel):
    value: Optional[str] = None
    scope: Optional[str] = None
    scope_id: Optional[int] = None

class FeatureFlagResponse(BaseModel):
    id: int
    key: str
    value: str
    scope: str
    scope_id: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Analytics Schemas ────────────────────────────────────────────────────────

class AnalyticsPointSchema(BaseModel):
    date: str
    sent: int
    failed: int
    pending: int

class AnalyticsDashboardResponse(BaseModel):
    total_sent: int
    total_failed: int
    total_pending: int
    total_contacts: int
    total_templates: int
    total_accounts: int
    total_ig_sent: int = 0
    total_tg_sent: int = 0
    ig_cost: float = 0.0
    tg_cost: float = 0.0
    total_cost: float = 0.0
    time_series: List[AnalyticsPointSchema]


# ── Audit Log Schema ────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: int
    action: str
    user_id: Optional[int] = None
    workspace_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── AI (Sophie) Schemas ─────────────────────────────────────────────────────

class AISophieRequest(BaseModel):
    prompt: str
    platform: Optional[str] = "instagram"
    tone: Optional[str] = "friendly"

class AISophieResponse(BaseModel):
    text: str

