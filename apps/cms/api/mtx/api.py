from ninja import Router

from apps.mediamtx.schemas import MediaStreamRtspMapSchema
from apps.mediamtx.services.registry import get_rtsp_mapping_snapshot

router = Router(tags=["MTX"])


@router.post(
    "/select_mtx_infos/",
    summary="Select MTX infos",
    response=list[MediaStreamRtspMapSchema],
)
def select_mtx_infos(request):
    snapshot = get_rtsp_mapping_snapshot()
    results: list[MediaStreamRtspMapSchema] = []
    for camera_key, values in snapshot.items():
        original_rtsp = values[0] if len(values) > 0 else ""
        mediamtx_rtsp = values[1] if len(values) > 1 else ""
        dl_rtsp = values[2] if len(values) > 2 else ""
        mtx_dl_rtsp = values[3] if len(values) > 3 else ""
        results.append(
            MediaStreamRtspMapSchema(
                camera_key=camera_key,
                original_rtsp=original_rtsp,
                mediamtx_rtsp=mediamtx_rtsp,
                dl_rtsp=dl_rtsp,
                mtx_dl_rtsp=mtx_dl_rtsp,
            )
        )
    return results
