import json

from betatester.utils import FileProviderType, settings

if settings.file_provider == FileProviderType.local:
    from .local import LocalFileClient

    save_path = json.loads(settings.file_provider_config)["save_path"]
    file_client = LocalFileClient(save_path)
else:
    raise ValueError(f"Invalid file provider: {settings.file_provider}")
