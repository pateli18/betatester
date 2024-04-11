import json

from betatester.betatester_types import FileClientType

from betatester_web_service.utils import settings

if settings.file_client_type == FileClientType.local:
    from betatester.file.local import LocalFileClient

    save_path = json.loads(settings.file_client_config)["save_path"]
    file_client = LocalFileClient(save_path)
else:
    raise ValueError(f"Invalid file provider: {settings.file_client_type}")
