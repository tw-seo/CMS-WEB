from typing import Any, List, Optional
from typing import Union
from ninja import Schema, Field
from pydantic import AliasChoices, ConfigDict, RootModel
from apps.common import (
    BuzzerInfo,
    CamInfo,
    EventInfo,
    EventType,
    InterlockInfo,
)
from apps.mediamtx.schemas import MediaStreamRtspMapSchema


class CamInfoListOut(RootModel[List[CamInfo]]):
    pass



class ApplyBuzzerInfosIn(Schema):
    buzzer_infos: List[BuzzerInfo] = Field(default_factory=list, description="Buzzer entries to apply")
    delete_keys: List[str] = Field(default_factory=list, description="Buzzer info keys to delete")


class ApplyCamInfosIn(Schema):
    model_config = ConfigDict(populate_by_name=True)

    cam_infos: List[CamInfo] = Field(
        default_factory=list,
        description="Camera entries to apply",
        alias="a4c5_camera_infos",
    )
    delete_keys: List[str] = Field(
        default_factory=list,
        description="Camera info keys to delete",
        alias="a4c5_delete_keys",
    )


class ApplyInterlockIn(Schema):
    model_config = ConfigDict(populate_by_name=True)

    interlock_infos: List[InterlockInfo] = Field(
        default_factory=list,
        description="Interlock entries to apply",
        alias="InterlockInfos",
        validation_alias=AliasChoices("interlock_infos", "InterlockInfos", "interlockInfos"),
    )
    delete_keys: List[str] = Field(default_factory=list, description="Interlock keys to delete")


class EventOccurIn(Schema):
    event_register_key: Optional[str] = Field(default=None, description="Event key")
    camera_info_key: Optional[str] = Field(default=None, description="Camera key")
    event_type_key: Optional[str] = Field(default=None, description="Event type key")
    object_class: Optional[str] = Field(default=None, description="Object class")
    img_path: Optional[str] = Field(default=None, description="Saved image full path")
    event_occur_time: Optional[str] = Field(default=None, description="ISO time or epoch seconds")
    event_occur_point: List[str] = Field(default_factory=list, description="Points like '(x,y)'")


class ReportRequest(Schema):
    start_date: Optional[str] = Field(default=None, description="Start time (ISO or epoch seconds)")
    end_date: Optional[str] = Field(default=None, description="End time (ISO or epoch seconds)")
    event_types: List[str] = Field(default_factory=list, description="Event type keys")
    camera_info_keys: List[str] = Field(default_factory=list, description="Camera info keys")
    page_size: int = Field(default=20, description="Events per page")
    page: int = Field(default=1, description="1-based page number")
    sort_order: str = Field(default="latest", description="latest or oldest")


class ReportInfo(Schema):
    occur_no: int = Field(description="Occurrence id")
    event_register_key: Optional[str] = Field(default=None, description="Event key")
    camera_info_key: Optional[str] = Field(default=None, description="Camera key")
    camera_name: Optional[str] = Field(default=None, description="Camera name")
    event_type_key: Optional[str] = Field(default=None, description="Event type key")
    object_class: Optional[str] = Field(default=None, description="Object class")
    img_path: Optional[str] = Field(default=None, description="Saved image full path")
    event_occur_time: Optional[str] = Field(default=None, description="ISO time")
    event_occur_point: List[str] = Field(default_factory=list, description="Points like '(x,y)'")


class ReportResponse(Schema):
    items: List[ReportInfo] = Field(default_factory=list, description="Event log items")
    total_count: int = Field(default=0, description="Total matching count")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")


class SimpleEventLogRequest(Schema):
    cam_info_key: Optional[str] = Field(default=None, description="Camera key")
    event_type_key: Optional[str] = Field(
        default=None, description="Deprecated: ignored for count summaries"
    )
    start_time: Optional[str] = Field(default=None, description="Start time (ISO or epoch seconds)")
    end_time: Optional[str] = Field(default=None, description="End time (ISO or epoch seconds)")


class SimpleEventLogCount(Schema):
    camera_info_key: Optional[str] = Field(default=None, description="Camera key")
    invasion_count: int = Field(default=0, description="E2024-11-19-001 count")
    loiter_count: int = Field(default=0, description="E2024-11-19-002 count")
    fire_count: int = Field(default=0, description="E2024-11-19-003 count")
    fall_count: int = Field(default=0, description="E2025-01-20-001 count")
    hit_count: int = Field(default=0, description="E2025-07-29-001 count")
    jam_count: int = Field(default=0, description="E2025-07-29-002 count")


class DeleteEventLogRequest(Schema):
    event_types: Union[str, List[str]] = Field(
        description="Event type keys list or '*' for all"
    )
    camera_info_keys: Union[str, List[str]] = Field(
        description="Camera info keys list or '*' for all"
    )
    start_date: Optional[str] = Field(
        default=None, description="Start time (ISO or epoch seconds)"
    )
    end_date: Optional[str] = Field(
        default=None, description="End time (ISO or epoch seconds)"
    )


class EventLogCountResponse(Schema):
    count: int = Field(default=0, description="Matched event log count")


class All_Info_Dto(Schema):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    cam_infos: List[CamInfo] = Field(
        default_factory=list,
        description="Camera info list",
        alias="camInfos",
        validation_alias=AliasChoices("camInfos", "CamInfos"),
    )
    event_infos: List[EventInfo] = Field(
        default_factory=list,
        description="Event info list",
        alias="eventInfos",
        validation_alias=AliasChoices("eventInfos", "EventInfos"),
    )
    event_types: List[EventType] = Field(
        default_factory=list,
        description="Event type list",
        alias="eventTypes",
        validation_alias=AliasChoices("eventTypes", "EventTypes"),
    )
    buzzer_infos: List[BuzzerInfo] = Field(
        default_factory=list,
        description="Buzzer info list",
        alias="buzzerInfos",
        validation_alias=AliasChoices("buzzerInfos", "BuzzerInfos"),
    )
    interlock_infos: List[InterlockInfo] = Field(
        default_factory=list,
        description="Interlock info list",
        alias="interlockInfos",
        validation_alias=AliasChoices("interlockInfos", "InterlockInfos"),
    )
    mtx_infos: List[MediaStreamRtspMapSchema] = Field(
        default_factory=list,
        description="MediaMTX RTSP 매핑 목록",
        alias="mtxInfos",
        validation_alias=AliasChoices("mtxInfos", "mtx_infos"),
    )


class SMSInfo(Schema):
    """Represents the SMS contact information described in the legacy C# struct."""

    name: Optional[str] = Field(default=None, description="Contact person name")
    ph_num: Optional[str] = Field(default=None, description="Phone number")
    department: Optional[str] = Field(default=None, description="Department label")
    title: Optional[str] = Field(default=None, description="Job title or role")


class AccountInfo(Schema):
    account_key: Optional[str] = Field(default=None, description="Account key")
    pw: Optional[str] = Field(default=None, description="Password (optional)")
    is_superuser: bool = Field(description="Superuser flag")
    user_name: Optional[str] = Field(default=None, description="User display name")
    user_id: str = Field(description="Login id")
    is_admin: bool = Field(description="Admin flag")
    is_activate: bool = Field(description="Active flag")
    created_by: Optional[str] = Field(default=None, description="Created by")
    is_delete: bool = Field(description="Deleted flag")


class AccountVerifyRequest(Schema):
    user_id: str = Field(description="Login id")
    pw: str = Field(description="Password")
    client_type: Optional[str] = Field(
        default=None,
        description="Client runtime type (main_viewer or sub_viewer)",
    )
    agent_id: Optional[str] = Field(default=None, description="Local agent node id")


class ApplyAccountInfo(Schema):
    account_infos: List[AccountInfo] = Field(
        default_factory=list, description="Accounts to insert/update"
    )
    delete_keys: List[str] = Field(
        default_factory=list, description="Account keys to delete"
    )


class Viewer_Manager_Set_Info(Schema):
    viewer_manager_key: Optional[str] = Field(default=None, description="Viewer manage key")
    camera_keys: List[str] = Field(default_factory=list, description="Camera info keys")
    setter_id: Optional[str] = Field(default=None, description="Setter account id")
    setter_key: Optional[str] = Field(default=None, description="Setter account key")
    user_id: Optional[str] = Field(default=None, description="User account id")
    user_key: Optional[str] = Field(default=None, description="User account key")
    assignment_version: int = Field(default=0, description="Assignment version")


class Cam_Key_And_Name(Schema):
    cam_key: str = Field(description="Camera key")
    cam_name: str = Field(description="Camera name")


class AgentHeartbeatAgent(Schema):
    node_id: Optional[str] = Field(default=None, description="Agent node id")
    role: Optional[str] = Field(default=None, description="Agent role")
    hostname: Optional[str] = Field(default=None, description="Host name")


class AgentHeartbeatTarget(Schema):
    name: str = Field(description="Target name")
    kind: Optional[str] = Field(default=None, description="Target kind")
    enabled: Optional[bool] = Field(default=True, description="Enabled flag")
    running: Optional[bool] = Field(default=None, description="Current running status")
    fail_count: int = Field(default=0, description="Consecutive failure count")
    restart_count: int = Field(default=0, description="Restart count")
    last_checked_at: Optional[str] = Field(default=None, description="ISO timestamp")
    last_restart_at: Optional[str] = Field(default=None, description="ISO timestamp")
    last_error: Optional[str] = Field(default=None, description="Last error text")


class AgentHeartbeatRequest(Schema):
    timestamp: Optional[str] = Field(default=None, description="Heartbeat timestamp")
    status: Optional[str] = Field(default=None, description="Overall status")
    agent: AgentHeartbeatAgent = Field(default_factory=AgentHeartbeatAgent)
    targets: List[AgentHeartbeatTarget] = Field(
        default_factory=list, description="Target status list"
    )
    heartbeat: Optional[dict[str, Any]] = Field(
        default=None, description="Additional heartbeat metadata"
    )


class AgentPolicyTarget(Schema):
    name: str = Field(description="Target name")
    enabled: bool = Field(default=True, description="Enable monitoring")
    auto_restart: bool = Field(default=True, description="Enable auto restart")


class AgentPolicyResponse(Schema):
    agent_id: str = Field(description="Agent node id")
    account_key: Optional[str] = Field(default=None, description="Mapped account key")
    client_type: str = Field(description="Applied client type")
    role: str = Field(description="Mapped account role")
    policy_version: int = Field(description="Policy version")
    targets: List[AgentPolicyTarget] = Field(default_factory=list, description="Target policy")
