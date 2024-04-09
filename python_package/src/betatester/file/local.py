import os
from uuid import UUID

import aiofiles

from ..betatester_types import FileClient, HtmlType


class LocalFileClient(FileClient):
    def __init__(self, save_path: str):
        self.save_path = save_path

    def _create_imgs_path(
        self,
        scrape_id: UUID,
        step_id: UUID,
    ) -> str:
        path = os.path.join(
            self.save_path,
            "imgs",
            str(scrape_id),
            f"{step_id}.png",
        )

        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _create_html_path(
        self,
        scrape_id: UUID,
        step_id: UUID,
        html_type: HtmlType,
    ) -> str:
        path = os.path.join(
            self.save_path,
            "htmls",
            str(scrape_id),
            str(step_id),
            f"{html_type.value}.html",
        )

        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _create_traces_path(
        self,
        scrape_id: UUID,
    ) -> str:
        path = os.path.join(self.save_path, "traces", f"{scrape_id}.zip")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    async def save_trace(self, scrape_id: UUID, tmp_trace_path: str) -> None:
        path = self._create_traces_path(scrape_id)
        async with aiofiles.open(tmp_trace_path, "rb") as f:
            async with aiofiles.open(path, "wb") as f_out:
                await f_out.write(await f.read())

    async def save_img(
        self, scrape_id: UUID, step_id: UUID, img: bytes
    ) -> None:
        path = self._create_imgs_path(scrape_id, step_id)
        async with aiofiles.open(path, "wb") as f_out:
            await f_out.write(img)

    async def save_html(
        self, scrape_id: UUID, step_id: UUID, html: str, html_type: HtmlType
    ) -> None:
        path = self._create_html_path(scrape_id, step_id, html_type)
        async with aiofiles.open(path, "w") as f_out:
            await f_out.write(html)

    def img_path(self, scrape_id: UUID, step_id: UUID) -> str:
        return self._create_imgs_path(scrape_id, step_id)

    def trace_path(self, scrape_id: UUID) -> str:
        return self._create_traces_path(scrape_id)
