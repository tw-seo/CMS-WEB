from typing import List, Optional

from ninja import Field, Schema
from pydantic import ConfigDict


class BuzzerInfo(Schema):
    buzzer_key: str = Field(default="", description="Buzzer primary key")
    buzzer_name: str = Field(default="", description="Buzzer name")
    buzzer_location: str = Field(default="", description="Location description")
    buzzer_time: int = Field(default=10, description="Alarm duration (seconds)")
    buzzer_brocker: str = Field(default="", description="MQ broker address")
    buzzer_topic: str = Field(default="", description="MQ topic name")


class CamInfo(Schema):
    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(alias="c5o_index")
    cam_name: str = Field(default="null", description="Camera name", alias="c5o_camName")
    cam_location: str = Field(default="null", description="Camera location", alias="c5o_camLocation")
    cam_rtsp_url1: Optional[str] = Field(default=None, description="Primary RTSP stream", alias="c5o_rtsp_url1")
    cam_rtsp_url2: Optional[str] = Field(default=None, description="Secondary RTSP stream", alias="c5o_rtsp_url2")
    cam_rtsp_rul3: Optional[str] = Field(default=None, description="Tertiary RTSP stream", alias="c5o_rtsp_url3")
    cam_ip: Optional[str] = Field(default=None, description="Camera IP", alias="c5o_ip")
    cam_port: Optional[str] = Field(default=None, description="RTSP port", alias="c5o_port")
    cam_main_stream: Optional[str] = Field(default=None, description="Main stream URL", alias="c5o_mainStream")
    cam_second_stream: Optional[str] = Field(default=None, description="Second stream URL", alias="c5o_secondStream")
    cam_third_stream: Optional[str] = Field(default=None, description="Third stream URL", alias="c5o_thirdStream")
    cam_id: Optional[str] = Field(default=None, description="Camera username", alias="c5o_cam_id")
    cam_pw: Optional[str] = Field(default=None, description="Camera password", alias="c5o_password")
    cam_rsolution_w: int = Field(default=-1, description="Image width", alias="c5o_img_width")
    cam_rsolution_h: int = Field(default=-1, description="Image height", alias="c5o_img_height")
    cam_chennal: int = Field(default=-1, description="Channel count", alias="c5o_img_channel")
    cam_info_key: Optional[str] = Field(default=None, description="Camera key", alias="c5o_camera_info_key")
    cam_view_index: int = Field(default=-1, description="View index", alias="c5o_viewIndex")
    is_thermal: bool = Field(default=False, description="Thermal camera flag", alias="c5o_is_thermal")


class EventInfo(Schema):
    event_key: Optional[str] = Field(default=None, description="Event key")
    cam_info_key: Optional[str] = Field(default=None, description="Camera key")
    rtsp_url: Optional[str] = Field(default=None, description="Event RTSP URL")
    evt_type_key: Optional[str] = Field(default=None, description="Event type key")
    event_info_roi: List[str] = Field(default_factory=list, description="ROI definition array")
    event_info_roi_multi: List[List[str]] = Field(default_factory=list, description="Multiple ROI definitions")
    shadow_rois: List[List[str]] = Field(default_factory=list, description="Shadow ROI definitions")
    edge_detect: bool = Field(default=True, description="Edge detection enabled")


class EventType(Schema):
    event_type_key: Optional[str] = Field(default=None, description="Event type key")
    event_type_name: Optional[str] = Field(default=None, description="Event type name")


class InterlockInfo(Schema):
    interlock_key: Optional[str] = Field(default=None, description="Interlock key")
    interlock_name: Optional[str] = Field(default=None, description="Interlock name")
    cam_key: Optional[str] = Field(default=None, description="Camera key")
    cam_name: Optional[str] = Field(default=None, description="Camera name")
    buzzer_key: Optional[str] = Field(default=None, description="Buzzer key")
    buzzername: Optional[str] = Field(default=None, description="Buzzer name")


class SMS_Info(Schema):
    name: Optional[str] = Field(default=None, description="Recipient name")
    ph_num: Optional[str] = Field(default=None, description="Phone number")
    department: Optional[str] = Field(default=None, description="Department label")
    title: Optional[str] = Field(default=None, description="Job title")
