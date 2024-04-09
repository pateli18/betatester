import asyncio
import base64
import json
import logging
import re
import tempfile
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import (
    Page,
    TimeoutError,
    ViewportSize,
    async_playwright,
)

from .betatester_types import (
    Action,
    ActionType,
    ExecutorMessage,
    FileClient,
    HtmlType,
    ModelChat,
    ModelChatType,
    ModelType,
    OpenAiChatInput,
    ScrapeFiles,
    ScrapeVariables,
)
from .model import openai_stream_response_generator, send_openai_request
from .prompts import (
    create_choose_action_system_prompt,
    create_choose_action_tools,
    create_choose_action_user_message,
    create_next_step_system_prompt,
)

logger = logging.getLogger(__name__)

ALLOWED_TAG_SET = set(["id", "for", "type", "allow"])


class ActionNotFoundException(Exception):
    pass


class MaxPageViewsReachedException(Exception):
    pass


class NextStepNotFoundException(Exception):
    pass


class MaxTotalActionsReachedException(Exception):
    pass


class MaxActionAttemptsReachedException(Exception):
    pass


# Function to strip attributes except for 'id'
def _strip_attributes_except_allowed_set(element):
    for tag in element.find_all(True):  # True finds all tags
        attrs = dict(
            tag.attrs
        )  # Make a copy to avoid changing size during iteration
        for attr in attrs:
            if attr not in ALLOWED_TAG_SET:
                del tag.attrs[attr]


class ExecutorBase:
    def __init__(
        self,
        subscriptions: Optional[set[asyncio.Queue[ExecutorMessage]]] = None,
    ) -> None:
        self.subscriptions: set[asyncio.Queue[ExecutorMessage]] = (
            subscriptions or set()
        )

    def publish(self, message: ExecutorMessage) -> None:
        for queue in self.subscriptions:
            queue.put_nowait(message)


class ScrapeStepExecutor(ExecutorBase):
    def __init__(
        self,
        page: Page,
        variables: ScrapeVariables,
        files: ScrapeFiles,
        next_step_chat: list[ModelChat],
        openai_api_key: str,
        max_action_attempts: Optional[int] = 5,
        scrape_id: Optional[UUID] = None,
        step_id: Optional[UUID] = None,
        file_client: Optional[FileClient] = None,
        model_client: Optional[httpx.AsyncClient] = None,
        subscriptions: Optional[set[asyncio.Queue[ExecutorMessage]]] = None,
    ) -> None:
        super().__init__(subscriptions)
        self.page = page
        self.variables = variables
        self.files = files
        self.scrape_id = scrape_id or uuid4()
        self.step_id = step_id or uuid4()
        self.actions_count = 0
        self.max_action_attempts = max_action_attempts
        self._openai_api_key = openai_api_key

        self.next_step_chat = next_step_chat
        self.choose_action_chat = [
            create_choose_action_system_prompt(self.variables, self.files)
        ]

        self.choose_action_tools, self.choose_action_tool_choice = (
            create_choose_action_tools()
        )

        self.file_client = file_client

        self.model_client = model_client

    async def _take_screenshot(self) -> str:
        screenshot_bytes = await self.page.screenshot(full_page=True)
        if self.file_client is not None:
            logger.info("Saving screenshot")
            await self.file_client.save_img(
                self.scrape_id, self.step_id, screenshot_bytes
            )
        # base64 encode the screenshot
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        return screenshot_b64

    async def _get_html(self) -> str:
        html_content = await self.page.content()
        soup = BeautifulSoup(html_content, "lxml")
        # get body tag
        clean_html = soup.find("body")
        _strip_attributes_except_allowed_set(clean_html)
        clean_html = str(clean_html)
        if self.file_client is not None:
            await asyncio.gather(
                self.file_client.save_html(
                    self.scrape_id, self.step_id, html_content, HtmlType.full
                ),
                self.file_client.save_html(
                    self.scrape_id, self.step_id, clean_html, HtmlType.clean
                ),
            )

        html_mrkdown = f"```html\n{clean_html}\n```"

        return html_mrkdown

    async def _get_next_step(
        self, encoded_image: str, model_client: httpx.AsyncClient
    ) -> str:
        self.next_step_chat.append(
            ModelChat.from_b64_image(
                role=ModelChatType.user, b64_image=encoded_image
            )
        )

        openai_chat_input = OpenAiChatInput(
            model=ModelType.gpt4vision,
            messages=self.next_step_chat,
            stream=True,
            max_tokens=1000,
            stop="<<END>>",
        )

        next_instruction = ""
        async for output in openai_stream_response_generator(
            model_client, openai_chat_input, self._openai_api_key
        ):
            if "error" in output:
                raise NextStepNotFoundException(output["error"])
            else:
                next_instruction = output["content"]
                self.publish(
                    ExecutorMessage(
                        step_id=self.step_id,
                        next_step=next_instruction,
                    )
                )
        self.next_step_chat.append(
            ModelChat(
                role=ModelChatType.assistant,
                content=next_instruction,
            )
        )

        self.publish(
            ExecutorMessage(
                step_id=self.step_id,
                next_step_chat=self.next_step_chat,
            )
        )

        return next_instruction

    async def _choose_action(self, model_client: httpx.AsyncClient) -> Action:

        prompt = OpenAiChatInput(
            messages=self.choose_action_chat,
            model=ModelType.gpt4turbo,
            tool_choice=self.choose_action_tool_choice,
            tools=self.choose_action_tools,
        )

        response = await send_openai_request(
            model_client,
            prompt.data,
            "chat/completions",
            self._openai_api_key,
        )

        action_raw = response["choices"][0]["message"]["tool_calls"][0][
            "function"
        ]["arguments"]

        self.choose_action_chat.append(
            ModelChat(
                role=ModelChatType.assistant,
                content=json.dumps(action_raw, indent=2),
            )
        )

        action = Action(**json.loads(action_raw))

        return action

    async def _execute_action(
        self,
        action: Action,
    ):
        # strip non space and alphanumeric characters from the element name
        if action.element.selector is not None:
            element = self.page.locator(f"{action.element.selector}")
        elif (
            action.element.role is not None and action.element.name is not None
        ):
            element_name = "".join(
                char
                for char in action.element.name
                if char.isalnum() or char.isspace()
            ).strip()
            element = self.page.get_by_role(action.element.role, name=re.compile(element_name, re.IGNORECASE))  # type: ignore
        else:
            raise ActionNotFoundException(
                "Action requires either an id or both a role and name"
            )

        action_kwargs: dict[str, Any] = {"timeout": 10000}
        if action.action_type == ActionType.click:
            await element.click(**action_kwargs)
        elif action.action_type == ActionType.fill:
            if action.action_value is None:
                raise ActionNotFoundException(
                    "Action type 'fill' requires an action_value"
                )
            action_value = self.variables.get(
                action.action_value, action.action_value
            )
            await element.fill(action_value, **action_kwargs)
        elif action.action_type == ActionType.select:
            await element.select_option(action.action_value, **action_kwargs)
        elif action.action_type == ActionType.check:
            await element.check(**action_kwargs)
        elif action.action_type == ActionType.upload_file:
            if action.action_value is None:
                raise ActionNotFoundException(
                    "Action type 'upload' requires an action_value and files"
                )
            file = self.files.get(action.action_value)
            if file is None:
                raise ActionNotFoundException(
                    f"Action value {action.action_value} not found in files"
                )

            await element.set_input_files(file.model_dump(by_alias=True))  # type: ignore
        else:
            raise ActionNotFoundException(
                f"Action type {action.action_type} not found"
            )

    async def _choose_and_execute_action(
        self, next_instruction: str, html: str, model_client: httpx.AsyncClient
    ) -> None:
        self.choose_action_chat.append(
            create_choose_action_user_message(next_instruction, html)
        )
        while True:
            action = await self._choose_action(model_client)

            self.actions_count += 1
            self.publish(
                ExecutorMessage(
                    step_id=self.step_id,
                    action=action,
                    step_action_count=self.actions_count,
                    choose_action_chat=self.choose_action_chat,
                )
            )

            try:
                await self._execute_action(action)
                break
            except TimeoutError:
                self.choose_action_chat.append(
                    ModelChat(
                        role=ModelChatType.user,
                        content="Looks like that element could not be found in the page, are you sure you selected the right one?",
                    )
                )
            except Exception as e:
                if "is not a valid selector" in str(e):
                    self.choose_action_chat.append(
                        ModelChat(
                            role=ModelChatType.user,
                            content="The selector you provided is invalid, try to use `role` and `name` instead",
                        )
                    )
                elif "strict mode violation" in str(e):
                    self.choose_action_chat.append(
                        ModelChat(
                            role=ModelChatType.user,
                            content="The locator resolved to more than one element, try to use `role` and `name` instead",
                        )
                    )
                else:
                    raise e

            if (
                self.max_action_attempts is not None
                and self.actions_count >= self.max_action_attempts
            ):
                raise MaxActionAttemptsReachedException(
                    f"Max action attempts ({self.actions_count}) reached"
                )

    async def run(self) -> bool:
        if self.model_client is None:
            model_client = httpx.AsyncClient()
        else:
            model_client = self.model_client

        try:
            encoded_image = await self._take_screenshot()
            html_coro = self._get_html()
            next_instruction = await self._get_next_step(
                encoded_image, model_client
            )
            html = await html_coro
            if "DONE" in next_instruction:
                # stop the html coroutine if we are done
                return True
            elif "WAIT" in next_instruction:
                return False

            await self._choose_and_execute_action(
                next_instruction, html, model_client
            )
        finally:
            if self.model_client is None:
                await model_client.aclose()
        return False


class ScrapeExecutor(ExecutorBase):
    def __init__(
        self,
        url: str,
        high_level_goal: str,
        openai_api_key: str,
        max_page_views: Optional[int] = 10,
        max_total_actions: Optional[int] = 20,
        max_action_attempts_per_step: Optional[int] = 5,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        variables: Optional[ScrapeVariables] = None,
        files: Optional[ScrapeFiles] = None,
        scrape_id: Optional[UUID] = None,
        file_client: Optional[FileClient] = None,
        save_playwright_trace: bool = True,
        model_client: Optional[httpx.AsyncClient] = None,
        subscriptions: Optional[set[asyncio.Queue[ExecutorMessage]]] = None,
    ) -> None:
        super().__init__(subscriptions)
        if file_client is None and save_playwright_trace:
            raise ValueError(
                "file_client must be provided when save_playwright_trace is True"
            )

        self.scrape_id = scrape_id or uuid4()
        self.url = url
        self.high_level_goal = high_level_goal
        self._openai_api_key = openai_api_key
        self.max_page_views = max_page_views
        self.max_total_actions = max_total_actions
        self.max_action_attempts_per_step = max_action_attempts_per_step
        self.viewport = ViewportSize(
            width=viewport_width, height=viewport_height
        )
        self.variables = variables or {}
        self.files = files or {}

        self.next_step_chat = [create_next_step_system_prompt(high_level_goal)]
        self.scrape_page_view_count = 0
        self.scrape_action_count = 0

        self.file_client = file_client
        self.save_playwright_trace = save_playwright_trace

        self.model_client = model_client

    async def run(self) -> None:
        async with async_playwright() as p:
            # initial setup and navigation
            browser = await p.chromium.launch()
            context = await browser.new_context(
                viewport=self.viewport,
            )
            if self.save_playwright_trace:
                await context.tracing.start(screenshots=True, snapshots=True)
            page = await context.new_page()

            if self.model_client is None:
                model_client = httpx.AsyncClient()
            else:
                model_client = self.model_client

            try:
                await self._execute(page, model_client)
            finally:
                # cleanup trace
                if self.save_playwright_trace:
                    trace_tempdir = tempfile.TemporaryDirectory()
                    output_path = f"{trace_tempdir.name}/{self.scrape_id}.zip"
                    await context.tracing.stop(path=output_path)
                    if self.file_client is not None:
                        await self.file_client.save_trace(output_path)
                    trace_tempdir.cleanup()

                # cleanup playwright
                await context.close()
                await browser.close()

                # cleanup model client
                if self.model_client is None:
                    await model_client.aclose()

    @property
    def max_action_attempts(self) -> Optional[int]:
        max_action_attempts = None
        if self.max_action_attempts_per_step is not None:
            if self.max_total_actions is not None:
                max_action_attempts = min(
                    self.max_action_attempts_per_step,
                    self.max_total_actions - self.scrape_action_count,
                )
            else:
                max_action_attempts = self.max_action_attempts_per_step

        return max_action_attempts

    async def _execute(
        self, page: Page, model_client: httpx.AsyncClient
    ) -> None:
        done = False
        await page.goto(self.url)
        while True:
            if (
                self.max_page_views is not None
                and self.scrape_page_view_count >= self.max_page_views
            ):
                raise MaxPageViewsReachedException(
                    f"Max page views ({self.scrape_page_view_count}) reached"
                )

            self.scrape_page_view_count += 1
            self.publish(
                ExecutorMessage(
                    scrape_page_view_count=self.scrape_page_view_count,
                    scrape_action_count=self.scrape_action_count,
                )
            )

            step_executor = ScrapeStepExecutor(
                page=page,
                variables=self.variables,
                files=self.files,
                next_step_chat=self.next_step_chat,
                openai_api_key=self._openai_api_key,
                max_action_attempts=self.max_action_attempts,
                subscriptions=self.subscriptions,
                file_client=self.file_client,
                scrape_id=self.scrape_id,
                model_client=model_client,
            )
            try:
                done = await step_executor.run()
            except MaxActionAttemptsReachedException as e:
                logger.warning(e)
            self.next_step_chat = step_executor.next_step_chat
            self.scrape_action_count += step_executor.actions_count

            if done:
                break

            if (
                self.max_total_actions is not None
                and self.scrape_action_count >= self.max_total_actions
            ):
                raise MaxTotalActionsReachedException(
                    f"Max total actions ({self.scrape_action_count}) reached"
                )
