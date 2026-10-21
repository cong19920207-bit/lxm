"""BGM management reads. GET never initializes, recovers or cleans business rows."""
from datetime import timedelta
from typing import get_args
from sqlalchemy import case, func, select

from backend.constants.bgm import HIDDEN_DELETE_WAIT_SECONDS
from backend.models.bgm import BgmAsset, BgmCatalog, BgmOperation, BgmTrack
from backend.schemas.bgm import BgmAudioFailureCategory, BgmCleanupResult, BgmCoverResult, BgmDirectoryResult, BgmOperationRead, BgmTrackCleanupSummary, BgmTrackRead, utc_iso


_AUDIO_FAILURE_CATEGORIES = frozenset(get_args(BgmAudioFailureCategory))


async def catalog_head(db):
    row = await db.get(BgmCatalog, 1)
    return (row.catalog_version, row.default_track_id) if row else (0, None)


async def management_status(db, tracks):
    """Read page-level status in bounded queries without exposing internal rows."""
    result = {track.id: dict(failure_category=None,
                            cleanup_summary=BgmTrackCleanupSummary().model_dump()) for track in tracks}
    if not result:
        return result
    failed_ids = [track.id for track in tracks if track.audio_state == 'failed']
    if failed_ids:
        latest = select(
            BgmOperation.track_id, BgmOperation.failure_category,
            func.row_number().over(partition_by=BgmOperation.track_id,
                order_by=(BgmOperation.created_at.desc(), BgmOperation.id.desc())).label('position'),
        ).where(BgmOperation.track_id.in_(failed_ids), BgmOperation.state == 'failed',
                BgmOperation.action.in_(['upload_audio', 'retry_audio'])).subquery()
        failures = await db.execute(select(latest.c.track_id, latest.c.failure_category)
                                    .where(latest.c.position == 1))
        for track_id, category in failures:
            result[track_id]['failure_category'] = (
                category if category in _AUDIO_FAILURE_CATEGORIES else 'processing_failed')
    counts = await db.execute(select(BgmAsset.track_id, BgmAsset.kind, BgmAsset.cleanup_state, func.count())
        .where(BgmAsset.track_id.in_(result), BgmAsset.state != 'deleted',
               BgmAsset.cleanup_state.in_(['pending', 'deleting', 'failed']))
        .group_by(BgmAsset.track_id, BgmAsset.kind, BgmAsset.cleanup_state))
    for track_id, kind, state, count in counts:
        # In-flight deletion is still outstanding; GET does not advance it.
        result[track_id]['cleanup_summary'][kind]['failed' if state == 'failed' else 'pending'] += count
    return result


async def track_projection(db, track, default_id, *, status=None):
    if status is None:
        status = (await management_status(db, [track]))[track.id]
    audio = await db.get(BgmAsset, track.audio_asset_id) if track.audio_asset_id else None
    cover = await db.get(BgmAsset, track.cover_asset_id) if track.cover_asset_id else None
    # Ownership checks also protect projections against an inconsistent association.
    def public_url(asset, kind):
        if (track.audio_state not in {'deleting','delete_failed','deleted'} and asset and asset.track_id == track.id and asset.kind == kind
                and asset.state == 'ready' and (asset.public_url or '').startswith('https://')):
            return asset.public_url
        return None
    deletable_at = None
    if not track.enabled and track.ever_published and track.hidden_at:
        deletable_at = track.hidden_at + timedelta(seconds=HIDDEN_DELETE_WAIT_SECONDS)
    return BgmTrackRead(
        id=track.id, name=track.name, record_version=track.record_version,
        audio_state=track.audio_state, enabled=track.enabled,
        is_default=track.id == default_id, sort_position=track.sort_position,
        media_version=track.media_version, cover_version=track.cover_version,
        audio_url=public_url(audio, 'audio'), cover_url=public_url(cover, 'cover'),
        duration_seconds=track.duration_seconds, size_bytes=track.size_bytes,
        ever_published=track.ever_published, hidden_at=utc_iso(track.hidden_at),
        deletable_at=utc_iso(deletable_at), created_at=utc_iso(track.created_at),
        updated_at=utc_iso(track.updated_at), **status,
    ).model_dump()


async def list_tracks(db, *, page=1, page_size=20, search='', state=None, filter='all', sort='created'):
    conditions = [BgmTrack.audio_state != 'deleted']
    if search:
        conditions.append(BgmTrack.name.contains(search, autoescape=True))
    if state:
        conditions.append(BgmTrack.audio_state == state)
    enabled = BgmTrack.enabled.is_(True)
    hidden = (BgmTrack.audio_state == 'ready') & BgmTrack.enabled.is_(False)
    failed = BgmTrack.audio_state.in_(['failed', 'delete_failed'])
    if filter in {'enabled', 'hidden', 'failed'}:
        conditions.append({'enabled': enabled, 'hidden': hidden, 'failed': failed}[filter])
    version, default_id = await catalog_head(db)
    summary = (await db.execute(select(
        func.count().label('total'),
        func.coalesce(func.sum(case((enabled, 1), else_=0)), 0).label('enabled'),
        func.coalesce(func.sum(case((hidden, 1), else_=0)), 0).label('hidden'),
        func.coalesce(func.sum(case((failed, 1), else_=0)), 0).label('failed'),
    ).select_from(BgmTrack).where(BgmTrack.audio_state != 'deleted'))).mappings().one()
    default_track = (await db.execute(select(BgmTrack.id, BgmTrack.name)
        .where(BgmTrack.id == default_id, BgmTrack.audio_state != 'deleted'))).mappings().first() if default_id else None
    total = await db.scalar(select(func.count()).select_from(BgmTrack).where(*conditions))
    ordering = [BgmTrack.created_at.desc(), BgmTrack.id]
    if sort == 'playlist':
        ordering = [BgmTrack.enabled.desc(), case((enabled, BgmTrack.sort_position), else_=None), *ordering]
    tracks = (await db.scalars(select(BgmTrack).where(*conditions)
              .order_by(*ordering)
              .offset((page - 1) * page_size).limit(page_size))).all()
    statuses = await management_status(db, tracks)
    return dict(list=[await track_projection(db, row, default_id, status=statuses[row.id]) for row in tracks],
                total=total, page=page, page_size=page_size,
                catalog_version=version, default_track_id=default_id,
                summary=dict(summary), default_track=dict(default_track) if default_track else None)


async def track_detail(db, track_id):
    track = await db.get(BgmTrack, track_id)
    if track is None or track.audio_state == 'deleted':
        return None
    version, default_id = await catalog_head(db)
    return dict(track=await track_projection(db, track, default_id), catalog_version=version)


async def operation_detail(db, operation_id):
    row = await db.get(BgmOperation, operation_id)
    if row is None:
        return None
    projection = BgmOperationRead(
        id=row.id, track_id=row.track_id, action=row.action, state=row.state, attempt=row.attempt,
        deadline_at=utc_iso(row.deadline_at), created_at=utc_iso(row.created_at),
        finished_at=utc_iso(row.finished_at),
        failure_category=row.failure_category,
        result=(BgmDirectoryResult(**row.result) if row.action in {'rename','enable','hide','set_default','reorder'}
                else BgmCoverResult(**row.result) if row.action in {'upload_cover','remove_cover'}
                else BgmCleanupResult(**row.result) if row.action in {'delete_track','cleanup_retry'} else None) if row.result else None,
    ).model_dump()
    if projection['result'] is None:
        projection.pop('result')
    return projection
