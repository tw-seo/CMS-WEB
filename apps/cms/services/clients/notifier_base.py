from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

import requests


@dataclass(slots=True)
class NotifyTarget:
    ip: str
    port: str

    def build_url(self, path: str) -> str:
        normalized_path = path or "/"
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        return f"http://{self.ip}:{self.port}{normalized_path}"


class HttpJsonNotifierBase:
    def __init__(
        self,
        targets: Iterable[NotifyTarget],
        *,
        timeout_seconds: float,
        logger_name: str,
        label: str,
    ) -> None:
        self.targets = [
            NotifyTarget(ip=(t.ip or "").strip(), port=(t.port or "").strip())
            for t in targets
            if (t.ip or "").strip() and (t.port or "").strip()
        ]
        self.timeout_seconds = float(timeout_seconds or 5)
        self.label = label
        self.logger = logging.getLogger(logger_name)

    @staticmethod
    def parse_targets(raw: Optional[str]) -> list[NotifyTarget]:
        text = (raw or "").strip()
        if not text:
            return []

        # JSON list format: [{"ip":"127.0.0.1","port":"8901"}, ...]
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = []
            targets: list[NotifyTarget] = []
            if isinstance(parsed, list):
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    ip = str(item.get("ip") or "").strip()
                    port = str(item.get("port") or "").strip()
                    if ip and port:
                        targets.append(NotifyTarget(ip=ip, port=port))
            return targets

        # CSV format: "127.0.0.1:8901,127.0.0.1:8902"
        targets = []
        for token in text.split(","):
            token = token.strip()
            if not token or ":" not in token:
                continue
            ip, port = token.rsplit(":", 1)
            ip = ip.strip()
            port = port.strip()
            if ip and port:
                targets.append(NotifyTarget(ip=ip, port=port))
        return targets

    def notify(self, path: str, payload: object, reason: Optional[str] = None) -> bool:
        if not self.targets:
            self.logger.warning("[%s] notify target not configured; skipping", self.label)
            return False

        has_success = False
        for target in self.targets:
            url = target.build_url(path)
            if self._post_json(url, payload, reason):
                has_success = True
        return has_success

    def _post_json(self, url: str, payload: object, reason: Optional[str]) -> bool:
        try:
            response = requests.post(url, json=payload, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            self.logger.warning("[%s] request failed (reason=%s): %s", self.label, reason, exc)
            return False

        if response.ok:
            self.logger.info("[%s] notified %s (reason=%s)", self.label, url, reason)
            return True

        body = (response.text or "").strip()
        if len(body) > 200:
            body = body[:200]
        self.logger.warning(
            "[%s] request failed (reason=%s): status=%s body=%s",
            self.label,
            reason,
            response.status_code,
            body,
        )
        return False
