import os
from uuid import UUID

import aiofiles

from ..betatester_types import FileClient, HtmlType, ScrapeSpec


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

    def _create_representation_path(
        self,
        scrape_id: UUID,
    ) -> str:
        path = os.path.join(self.save_path, "scrapes", f"{scrape_id}.json")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    async def save_trace(self, scrape_id: UUID, tmp_trace_path: str) -> str:
        path = self._create_traces_path(scrape_id)
        async with aiofiles.open(tmp_trace_path, "rb") as f:
            async with aiofiles.open(path, "wb") as f_out:
                await f_out.write(await f.read())

        return path

    async def save_img(
        self, scrape_id: UUID, step_id: UUID, img: bytes
    ) -> str:
        path = self._create_imgs_path(scrape_id, step_id)
        async with aiofiles.open(path, "wb") as f_out:
            await f_out.write(img)

        return path

    async def save_html(
        self, scrape_id: UUID, step_id: UUID, html: str, html_type: HtmlType
    ) -> str:
        path = self._create_html_path(scrape_id, step_id, html_type)
        async with aiofiles.open(path, "w") as f_out:
            await f_out.write(html)

        return path

    async def save_scrape_spec(self, scrape_id: UUID, spec: ScrapeSpec) -> str:
        path = self._create_representation_path(scrape_id)
        async with aiofiles.open(path, "w") as f_out:
            await f_out.write(spec.model_dump_json())

        return path

    async def load_scrape_spec(self, path: str) -> ScrapeSpec:
        async with aiofiles.open(path, "r") as f:
            return ScrapeSpec.model_validate_json(await f.read())

    def img_path(self, scrape_id: UUID, step_id: UUID) -> str:
        return self._create_imgs_path(scrape_id, step_id)

    def trace_path(self, scrape_id: UUID) -> str:
        return self._create_traces_path(scrape_id)
