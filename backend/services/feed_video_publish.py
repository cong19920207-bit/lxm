"""One edit, one explicit commit and one durable response."""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select

from backend.models.feed_post import FeedPost
from backend.models.feed_video import FeedPublication, FeedVideoAsset, FeedVideoEdit, FeedVideoSelection, FeedVideoTask
from backend.models.feed_video_upload import FeedVideoSubmission
from backend.services.feed_service import feed_now
from backend.services.feed_publish_service import draw_engagement_counts, manual_post_location
from backend.services.feed_video_drafts import RECEIVE_FAILURES, edit_row, lock_admission, upload_issue
from backend.utils.admin_auth import log_operation

CONFLICT = "帖子已更新，请刷新后重新编辑"


async def selected_assets(db, selection):
    if not selection:
        return {}
    assets = (await db.scalars(select(FeedVideoAsset).where(
        FeedVideoAsset.media_version==selection.media_version,
        or_(FeedVideoAsset.kind.in_(("video","preview")),FeedVideoAsset.variant==selection.cover_variant),
        FeedVideoAsset.verified_at.is_not(None),FeedVideoAsset.public_url.is_not(None)))).all()
    return {asset.kind:asset for asset in assets}


async def submit(db,actor,eid,body):
    await lock_admission(db)
    key = str(body.request_id)
    previous = await db.scalar(select(FeedVideoSubmission).where(FeedVideoSubmission.request_id==key).with_for_update())
    if previous:
        if (previous.edit_id,previous.actor_id,previous.edit_version)!=(eid,actor.id,body.version):
            raise HTTPException(409, "提交请求已用于其他编辑")
        return previous.result
    edit = await edit_row(db,eid,write=True)
    post = await db.scalar(select(FeedPost).where(FeedPost.id==edit.post_id).with_for_update())
    if edit.edit_version!=body.version or post.post_version!=edit.base_post_version:
        raise HTTPException(409,CONFLICT)
    pointer = await db.get(FeedPublication,post.id,with_for_update=True)
    issue = await upload_issue(db, eid, lock=True)
    selection = await db.get(FeedVideoSelection,eid,with_for_update=True)
    task = (await db.scalar(select(FeedVideoTask).where(FeedVideoTask.media_version==selection.media_version).with_for_update())
            if selection else None)
    if issue and issue["state"] in RECEIVE_FAILURES:
        message = "本次视频上传失败，请重新上传"
        if task and task.state == "ready":
            message += "或确认沿用原视频"
        raise HTTPException(409, message)
    if not edit.content_text.strip():
        raise HTTPException(422,"请先填写文案")
    assets = await selected_assets(db,selection)
    if issue or not task or task.state!="ready" or set(assets)!={"video","preview","cover_small","cover_large"}:
        raise HTTPException(409,"视频及所选封面尚未就绪")
    now = feed_now().replace(microsecond=0)
    if not pointer:
        if edit.scheduled_publish_time and edit.scheduled_publish_time<=now:
            raise HTTPException(422,"预设时间已过，请修改或清空后提交")
        post.city, post.season = await manual_post_location(None, now.date())
        for field, value in (await draw_engagement_counts()).items():
            setattr(post, field, value)
        post.scheduled_publish_time = edit.scheduled_publish_time or now
        post.generation_status = "ready"
        db.add(FeedPublication(post_id=post.id,edit_id=eid,submitted_at=datetime.utcnow()))
        action = "scheduled" if edit.scheduled_publish_time else "published"
    else:
        old = await db.get(FeedVideoEdit,pointer.edit_id)
        old_selection = await db.get(FeedVideoSelection,old.id)
        old.state = "superseded"
        pointer.edit_id,pointer.submitted_at = eid,datetime.utcnow()
        action = "replaced"
    post.content_text = edit.content_text.strip()
    post.hashtags = edit.hashtags or []
    post.emotion = edit.emotion
    post.post_version += 1
    edit.state = "submitted"
    result = dict(post_id=post.id,edit_id=eid,post_version=post.post_version,action=action,
                  media_version=selection.media_version,scheduled_publish_time=post.scheduled_publish_time.isoformat())
    db.add(FeedVideoSubmission(request_id=key,edit_id=eid,actor_id=actor.id,edit_version=body.version,result=result))
    await log_operation(db,actor,"feed","video_submit",f"视频提交 {action}：帖子 {post.id}，编辑 {eid}，成功")
    if action=="replaced":
        from backend.services.feed_video_retention import refresh_references
        for version in {selection.media_version,old_selection.media_version}:
            await refresh_references(db,version,datetime.utcnow())
    return result


async def begin_replacement(db,actor,post_id,body):
    import hashlib
    from backend.models.feed_video_upload import FeedDraftRequest
    from backend.services.feed_video_drafts import edit_view
    await lock_admission(db)
    key = str(body.request_id)
    fingerprint = hashlib.sha256(f"replace:{post_id}:{body.version}".encode()).hexdigest()
    receipt = await db.scalar(select(FeedDraftRequest).where(FeedDraftRequest.request_id==key).with_for_update())
    if receipt:
        if receipt.actor_id!=actor.id or receipt.request_digest!=fingerprint:
            raise HTTPException(409,"建稿请求已用于其他内容")
        return await edit_view(db,await edit_row(db,receipt.edit_id))
    post = await db.scalar(select(FeedPost).where(FeedPost.id==post_id).with_for_update())
    original = await db.get(FeedPublication,post_id,with_for_update=True)
    if not post or not original or post.media_kind!="video":
        raise HTTPException(409,"请选择已提交的视频帖")
    if post.post_version!=body.version:
        raise HTTPException(409,CONFLICT)
    old_edit = await edit_row(db,original.edit_id)
    old_media = await db.get(FeedVideoSelection,old_edit.id)
    edit = FeedVideoEdit(post_id=post.id,admin_id=actor.id,base_post_version=post.post_version,
                         content_text=post.content_text, hashtags=post.hashtags or [], emotion=post.emotion,
                         scheduled_publish_time=post.scheduled_publish_time,
                         frame_mode=old_edit.frame_mode,frame_position=old_edit.frame_position)
    db.add(edit)
    await db.flush()
    db.add(FeedVideoSelection(post_id=post.id,edit_id=edit.id,media_version=old_media.media_version,
                              cover_variant=old_media.cover_variant))
    db.add(FeedDraftRequest(request_id=key,edit_id=edit.id,actor_id=actor.id,request_digest=fingerprint))
    await log_operation(db,actor,"feed","video_replace_edit",f"开启替换编辑 {edit.id}，帖子 {post_id}")
    return await edit_view(db,edit)
