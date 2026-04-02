from os.path import basename


class FileInfoMixin:
    def get_file_info(self, request) -> dict[str, str]:
        if not self.attachment:
            return {}
        return {
            "file_url": request.build_absolute_uri(self.attachment.url),
            "file_name": basename(self.attachment.name),
        }
