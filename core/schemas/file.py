from os.path import basename

from ninja import Schema


class FileSchema(Schema):
    file_url: str | None
    file_name: str | None

    @classmethod
    def from_field(cls, field, request):
        if not field:
            return cls(file_url=None, file_name=None)
        return cls(
            file_url=request.build_absolute_uri(field.url),
            file_name=basename(field.name),
        )
