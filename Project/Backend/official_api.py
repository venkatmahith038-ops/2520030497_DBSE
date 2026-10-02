import httpx
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import get_db, MetaConnection, Account, MonitoredPost, ProcessedComment, OptOut, log_to_db, MessageTemplate, get_workspace_settings
from backend.bot import comment_matches_trigger, MATCH_MODE_EXACT, MATCH_MODE_ANY
from backend.bot import parse_spintax
from backend.security import decrypt_secret, verify_meta_signature
from typing import Dict, Any

router = APIRouter(prefix="/api/webhooks", tags=["Meta Webhooks"])

@router.get("/instagram")
async def verify_webhook(
    db: Session = Depends(get_db),
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Handles Meta's Webhook verification challenge during configuration.
    The verification token belongs to the Lyvora Meta app, not to an end user.
    """
    expected_token = settings.META_WEBHOOK_VERIFY_TOKEN.strip()
    
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        log_to_db("SUCCESS", "Official Meta webhook verified successfully!")
        return PlainTextResponse(content=hub_challenge or "")
    
    log_to_db("WARNING", "Official Meta Webhook verification failed. Token mismatch.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@router.post("/instagram")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives real-time events (comments, messages) from Meta.
    Filters triggers, checks opt-out blocklists, and dispatches compliant replies.
    """
    raw_body = await request.body()
    if not verify_meta_signature(raw_body, request.headers.get("x-hub-signature-256")):
        log_to_db("WARNING", "Rejected Meta webhook payload with invalid signature.")
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        import json
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Meta webhook structure loops
    if payload.get("object") != "instagram":
        return {"status": "ignored", "reason": "Not an Instagram event"}

    processed = 0
    for entry in payload.get("entry", []):
        instagram_user_id = str(entry.get("id") or "")
        connection = db.query(MetaConnection).filter(
            MetaConnection.instagram_user_id == instagram_user_id,
            MetaConnection.status == "connected",
            MetaConnection.is_active == True,
        ).first()
        if not connection:
            log_to_db("WARNING", f"Ignored Meta webhook for an inactive or unknown Instagram account ID {instagram_user_id}.")
            continue
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})
            
            if field == "comments":
                await process_incoming_comment(value, connection, db)
                processed += 1
                
    return {"status": "processed", "events": processed}

async def process_incoming_comment(value: Dict[str, Any], connection: MetaConnection, db: Session):
    """
    Parses a comment, checks trigger matching, verifies consent/opt-out status,
    and dispatches a DM back to the creator's follower.
    """
    comment_id = value.get("id")
    comment_text = value.get("text", "").strip()
    media_info = value.get("media", {})
    post_ig_id = media_info.get("id") # Reel or Post ID
    commenter = value.get("from", {})
    commenter_username = commenter.get("username")
    commenter_id = commenter.get("id")
    
    if not comment_id or not commenter_username:
        return

    log_to_db("INFO", f"[Meta Webhook] Received comment from @{commenter_username}: '{comment_text}'")

    # 1. Opt-out keyword check (the connected workspace's own word list)
    ws_settings = get_workspace_settings(db, connection.workspace_id)
    opt_out_keywords = [k.strip().lower() for k in ws_settings["opt_out_keywords"].split(",") if k.strip()]
    
    if comment_text.lower() in opt_out_keywords:
        exists = db.query(OptOut).filter(
            OptOut.username == commenter_username.lower(),
            OptOut.workspace_id == connection.workspace_id,
        ).first()
        if not exists:
            db.add(OptOut(
                username=commenter_username.lower(),
                user_id=connection.connected_by_user_id,
                workspace_id=connection.workspace_id,
            ))
            db.commit()
        log_to_db("WARNING", f"[COMPLIANCE] Added @{commenter_username} to the workspace blocklist after an opt-out keyword.")
        return

    # 2. Query blocklist check
    blocked = db.query(OptOut).filter(
        OptOut.username == commenter_username.lower(),
        OptOut.workspace_id == connection.workspace_id,
    ).first()
    if blocked:
        log_to_db("WARNING", f"[COMPLIANCE] Ignored trigger: @{commenter_username} is in the blocklist.")
        return

    # 3. Look up active monitored post match by post URL or ID string
    # Meta webhook returns numeric ID. We search monitored posts containing this ID in URL or map them
    account_ids = [row[0] for row in db.query(Account.id).filter(
        Account.workspace_id == connection.workspace_id,
    ).all()]
    if not account_ids:
        return
    monitored_posts = db.query(MonitoredPost).filter(
        MonitoredPost.is_active == True,
        MonitoredPost.account_id.in_(account_ids),
    ).all()
    # A post set to "any" replies to every comment; "exact" still requires the
    # comment to be the keyword. Prefer a post whose URL carries this media id
    # so a keyword shared across posts cannot fire on the wrong one.
    candidates = [
        post for post in monitored_posts
        if comment_matches_trigger(comment_text, post.trigger_keyword,
                                   getattr(post, "match_mode", MATCH_MODE_EXACT))
    ]
    matched_post = next(
        (post for post in candidates if post_ig_id and post_ig_id in post.post_url),
        candidates[0] if candidates else None,
    )

    if not matched_post:
        return

    # 4. Check processed comments history (deduplication)
    history_exists = db.query(ProcessedComment).filter(
        ProcessedComment.username == commenter_username,
        ProcessedComment.post_id == matched_post.id
    ).first()
    
    if history_exists:
        log_to_db("INFO", f"Skipped processed comment from @{commenter_username} on post ID {matched_post.id} to prevent duplicate spam.")
        return

    # 5. Fetch and compile template
    template = db.query(MessageTemplate).filter(MessageTemplate.id == matched_post.template_id).first()
    if not template or not template.is_active:
        log_to_db("WARNING", f"No active template found for Monitored Post ID {matched_post.id}")
        return

    raw_message = template.content
    message_text = parse_spintax(raw_message).replace("{username}", commenter_username)

    # 6. Decrypt only inside the worker process and only for this workspace.
    access_token = decrypt_secret(connection.access_token) or ""
    
    if not access_token:
        connection.status = "invalid"
        connection.is_active = False
        log_to_db("ERROR", "Failed to send DM: this workspace's Meta token could not be decrypted.")
        # Mark as failed in history
        db.add(ProcessedComment(
            username=commenter_username,
            post_id=matched_post.id,
            comment_text=comment_text,
            status="failed"
        ))
        db.commit()
        return

    success = await send_official_meta_dm(
        comment_id,
        message_text,
        connection.instagram_user_id,
        access_token,
    )
    
    # 7. Record History
    db.add(ProcessedComment(
        username=commenter_username,
        post_id=matched_post.id,
        comment_text=comment_text,
        status="sent" if success else "failed"
    ))
    db.commit()
    
    if success:
        log_to_db("SUCCESS", f"[Meta API] Private DM sent to @{commenter_username} in response to comment.")
        await reply_to_official_comment(comment_id, access_token)
    else:
        log_to_db("ERROR", f"[Meta API] Failed to send private DM to @{commenter_username}.")

async def send_official_meta_dm(comment_id: str, text: str, instagram_user_id: str, access_token: str) -> bool:
    """
    Sends an official Instagram Private Reply to a comment.
    Utilizes Instagram Direct Messages API.
    """
    version = settings.META_GRAPH_API_VERSION.strip() or "v23.0"
    url = f"https://graph.instagram.com/{version}/{instagram_user_id}/messages"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    
    # Private reply payload structure linking comment_id
    payload = {
        "recipient": {
            "comment_id": comment_id
        },
        "message": {
            "text": text
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            res_data = response.json()
            if response.status_code == 200 and "message_id" in res_data:
                return True
            else:
                log_to_db("ERROR", f"Meta Send API error response: {res_data}")
                return False
    except Exception as e:
        log_to_db("ERROR", f"Meta Send API request exception: {e}")
        return False


async def reply_to_official_comment(comment_id: str, access_token: str) -> bool:
    """Post the promised public confirmation after the private reply succeeds."""
    version = settings.META_GRAPH_API_VERSION.strip() or "v23.0"
    url = f"https://graph.instagram.com/{version}/{comment_id}/replies"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"message": "We have sent the link to your DM. Please check your inbox."},
                headers=headers,
                timeout=10.0,
            )
        if response.status_code == 200:
            return True
        log_to_db("WARNING", f"Meta public comment reply failed with status {response.status_code}.")
    except Exception as error:
        log_to_db("WARNING", f"Meta public comment reply request failed: {type(error).__name__}.")
    return False
