import structlog
from fastapi import APIRouter, Request, BackgroundTasks
from typing import Any
from config.settings import settings
from utils.queue_client import get_redis_pool

log = structlog.get_logger()
router = APIRouter(prefix="/slack", tags=["Slack Events"])

@router.post("/events")
async def handle_slack_events(request: Request, background_tasks: BackgroundTasks) -> Any:
    """Xử lý các sự kiện gửi về từ Slack Event API"""
    payload = await request.json()
    
    # 1. Verification Challenge (bắt buộc khi setup Slack App)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
        
    # 2. Xử lý các sự kiện thực tế
    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_type = event.get("type")
        
        channel_id = event.get("item", {}).get("channel") or event.get("channel")
        thread_ts = event.get("item", {}).get("ts") or event.get("thread_ts") or event.get("ts") # reaction = item.ts, message = ts
        
        should_trigger = False
        
        # Trigger khi có người bấm emoji 🎫 (ticket)
        if event_type == "reaction_added" and event.get("reaction") == "ticket":
            should_trigger = True
            
        # Trigger khi bot được tag (@KnowledgeBot chốt task)
        elif event_type == "app_mention":
            should_trigger = True
            
        if should_trigger and channel_id and thread_ts:
            log.info("slack.event.trigger", event_type=event_type, channel=channel_id, thread=thread_ts)
            
            # Đẩy vào Background Queue để không timeout phản hồi webhook Slack (3s limit)
            async def dispatch_sync():
                try:
                    redis = await get_redis_pool()
                    await redis.enqueue_job(
                        "scan_slack_thread_job",
                        channel_id,
                        thread_ts,
                        triggered_by="slack_event",
                        _queue_name=settings.ARQ_DEFAULT_QUEUE_NAME
                    )
                except Exception as e:
                    log.error("slack.event.enqueue_failed", error=str(e))
            
            background_tasks.add_task(dispatch_sync)

    return {"status": "ok"}
