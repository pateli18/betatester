import asyncio
import base64
import json
import logging
import re
import tempfile
from abc import abstractmethod
from typing import Any, Optional, Union, cast
from uuid import UUID, uuid4

import httpx
from bs4 import BeautifulSoup, Tag
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
    ScrapeEvent,
    ScrapeFiles,
    ScrapeSpec,
    ScrapeVariables,
    SpecialInstruction,
)
from .model import openai_stream_response_generator, send_openai_request
from .prompts import (
    create_choose_action_system_prompt,
    create_choose_action_tools,
    create_choose_action_user_message,
    create_next_step_system_prompt,
)

logger = logging.getLogger("betatester")

ALLOWED_TAG_SET = set(["id", "for", "type", "allow", "aria-label"])


class ActionNotFoundException(Exception):
    pass


class MaxPageViewsReachedException(Exception):
    pass


class NextStepNotFoundException(Exception):
    pass


class MaxTotalActionsReachedException(Exception):
    pass


async def _execute_action(
    page: Page,
    action: Action,
    variables: ScrapeVariables,
    files: ScrapeFiles,
):
    # strip non space and alphanumeric characters from the element name
    if action.element.selector is not None:
        element = page.locator(f"{action.element.selector}")
    elif action.element.role is not None:
        kwargs: dict[str, Union[str, re.Pattern]] = {
            "role": action.element.role
        }
        if action.element.name is not None:
            kwargs["name"] = re.compile(
                "".join(
                    char
                    for char in action.element.name
                    if char.isalnum() or char.isspace()
                ).strip(),
                re.IGNORECASE,
            )
        element = page.get_by_role(**kwargs)  # type: ignore
    else:
        raise ActionNotFoundException("Action requires either an id or a role")

    action_kwargs: dict[str, Any] = {"timeout": 10000}
    if action.action_type == ActionType.click:
        await element.click(**action_kwargs)
    elif action.action_type == ActionType.fill:
        if action.action_value is None:
            raise ActionNotFoundException(
                "Action type 'fill' requires an action_value"
            )
        action_value = variables.get(action.action_value, action.action_value)
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
        file = files.get(action.action_value)
        if file is None:
            raise ActionNotFoundException(
                f"Action value {action.action_value} not found in files"
            )

        await element.set_input_files(file.input_files)  # type: ignore
    elif action.action_type == ActionType.none:
        pass
    else:
        raise ActionNotFoundException(
            f"Action type {action.action_type} not found"
        )


# Function to strip attributes except for 'id'
def _strip_attributes_except_allowed_set(element: Tag):
    for tag in element.find_all(True) + [element]:
        attrs = dict(
            tag.attrs
        )  # Make a copy to avoid changing size during iteration
        for attr in attrs:
            if attr not in ALLOWED_TAG_SET:
                del tag.attrs[attr]


def _strip_all_script_and_style_tags(element: Tag):
    for tag in element.find_all("script"):
        tag.decompose()

    for tag in element.find_all("style"):
        tag.decompose()


class _AiExecutorBase:
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


class _ScrapeExecutorBase:
    def __init__(
        self,
        url: str,
        viewport_width: int,
        viewport_height: int,
        file_client: Optional[FileClient] = None,
        scrape_id: Optional[UUID] = None,
        save_playwright_trace: bool = False,
        headless: bool = True,
    ) -> None:
        if file_client is None and save_playwright_trace:
            raise ValueError(
                "file_client must be provided when save_playwright_trace is True"
            )
        self.scrape_id = scrape_id or uuid4()
        self.url = url
        self.file_client = file_client
        self.viewport = ViewportSize(
            width=viewport_width, height=viewport_height
        )

        self.headless = headless
        self.save_playwright_trace = save_playwright_trace

    @abstractmethod
    async def _execute(self, page: Page) -> None:
        pass

    async def _run_start_callback(self) -> None:
        pass

    async def _run_end_callback(self) -> None:
        pass

    async def run(self) -> None:
        """
        Runs the test until the high level goal is completed or it errors out
        """

        logger.info("Starting to test %s", self.url)
        logger.info("===============================================")
        async with async_playwright() as p:
            # initial setup and navigation
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport=self.viewport,
            )
            if self.save_playwright_trace:
                logger.info("Starting playwright tracing...")
                await context.tracing.start(screenshots=True, snapshots=True)
            page = await context.new_page()

            await self._run_start_callback()

            try:
                await self._execute(page)
            finally:
                # cleanup trace
                if self.save_playwright_trace:
                    trace_tempdir = tempfile.TemporaryDirectory()
                    output_path = f"{trace_tempdir.name}/{self.scrape_id}.zip"
                    await context.tracing.stop(path=output_path)
                    if self.file_client is not None:
                        save_path = await self.file_client.save_trace(
                            self.scrape_id, output_path
                        )
                        logger.info("Saved trace to %s", save_path)
                    trace_tempdir.cleanup()

                # cleanup playwright
                await context.close()
                await browser.close()

                await self._run_end_callback()

        logger.info("Test %s completed", self.url)
        logger.info(
            "=============================================================="
        )


class ScrapeStepAiExecutor(_AiExecutorBase):
    def __init__(
        self,
        high_level_goal: str,
        previous_steps: list[str],
        page: Page,
        variables: ScrapeVariables,
        files: ScrapeFiles,
        openai_api_key: str,
        max_action_attempts: Optional[int] = 5,
        scrape_id: Optional[UUID] = None,
        step_id: Optional[UUID] = None,
        file_client: Optional[FileClient] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        subscriptions: Optional[set[asyncio.Queue[ExecutorMessage]]] = None,
    ) -> None:
        """
        Executes a single test step

        Examples:
            ```python
            scrape_step_executor = ScrapeStepAiExecutor(
                high_level_goal="Find images of cats",
                previous_steps=["Navigate to google.com"],
                page=page,
                variables={},
                files={},
                openai_api_key="...",
            )
            await scrape_step_executor.run()
            ```

        Args:
            high_level_goal (str): High level goal to accomplish at the URL
            previous_steps (list[str]): Previous steps taken in the test
            page (Page): Playwright page object
            variables (ScrapeVariables): Variables to use in the scrape, e.g. for filling in a username and password to log in
            files (ScrapeFiles): Files to use in the scrape, e.g. for uploading some data as part of the goal
            openai_api_key (str): OpenAI API key, see https://platform.openai.com/api-keys
            max_action_attempts (Optional[int], optional): Max actions to take on a single page. Defaults to 5.
            scrape_id (Optional[UUID], optional): Scrape ID. Defaults to None.
            step_id (Optional[UUID], optional): Step ID. Defaults to None.
            file_client (Optional[FileClient], optional): File client to use for saving images, html, and traces. Defaults to None.
            http_client (Optional[httpx.AsyncClient], optional): Http client to use for making requests, pass one through to reuse across tests. Defaults to None.
            subscriptions (Optional[set[asyncio.Queue[ExecutorMessage]], optional): Subscriptions that will receive messages from the executor as it progresses. Defaults to None.
        """
        super().__init__(subscriptions)
        self.page = page
        self.variables = variables
        self.files = files
        self.scrape_id = scrape_id or uuid4()
        self.step_id = step_id or uuid4()
        self.actions_count = 0
        self.max_action_attempts = max_action_attempts
        self._openai_api_key = openai_api_key

        self.next_step_chat = [
            create_next_step_system_prompt(high_level_goal, previous_steps)
        ]
        self.choose_action_chat = [
            create_choose_action_system_prompt(self.variables, self.files)
        ]

        self.choose_action_tools, self.choose_action_tool_choice = (
            create_choose_action_tools()
        )

        self.file_client = file_client

        self.http_client = http_client

    async def _take_screenshot(self) -> str:
        screenshot_bytes = await self.page.screenshot(full_page=True)
        if self.file_client is not None:
            path = await self.file_client.save_img(
                self.scrape_id, self.step_id, screenshot_bytes
            )
            logger.info("Saved screenshot to %s", path)
        # base64 encode the screenshot
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        return screenshot_b64

    async def _get_html(self) -> str:
        html_content = await self.page.content()
        soup = BeautifulSoup(html_content, "lxml")
        # get body tag
        clean_html = cast(Tag, soup.find("body"))
        _strip_all_script_and_style_tags(clean_html)
        _strip_attributes_except_allowed_set(clean_html)
        clean_html = str(clean_html)
        if self.file_client is not None:
            full_path, clean_path = await asyncio.gather(
                self.file_client.save_html(
                    self.scrape_id, self.step_id, html_content, HtmlType.full
                ),
                self.file_client.save_html(
                    self.scrape_id, self.step_id, clean_html, HtmlType.clean
                ),
            )
            logger.info("Saved full html to %s", full_path)
            logger.info("Saved clean html to %s", clean_path)

        html_mrkdown = f"```html\n{clean_html}\n```"

        return html_mrkdown

    async def _get_next_step(
        self, encoded_image: str, http_client: httpx.AsyncClient
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
            http_client, openai_chat_input, self._openai_api_key
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
        logger.info("\x1b[1;34mNext instruction\x1b[0m: %s", next_instruction)
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

    async def _choose_action(self, http_client: httpx.AsyncClient) -> Action:

        prompt = OpenAiChatInput(
            messages=self.choose_action_chat,
            model=ModelType.gpt4turbo,
            tool_choice=self.choose_action_tool_choice,
            tools=self.choose_action_tools,
        )

        response = await send_openai_request(
            http_client,
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
        logger.info("%s. Chose action: %s", self.actions_count, action)

        return action

    async def _choose_and_execute_action(
        self,
        next_instruction: str,
        html: str,
        http_client: httpx.AsyncClient,
    ) -> tuple[Optional[Action], int]:
        self.choose_action_chat.append(
            create_choose_action_user_message(next_instruction, html)
        )
        while True:
            action = await self._choose_action(http_client)

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
                await _execute_action(
                    self.page, action, self.variables, self.files
                )
                break
            except TimeoutError:
                logger.info("Action timed out, retrying action %s", action)
                self.choose_action_chat.append(
                    ModelChat(
                        role=ModelChatType.user,
                        content="Looks like that element could not be found in the page, are you sure you selected the right one?",
                    )
                )
            except Exception as e:
                if "is not a valid selector" in str(e):
                    logger.info(
                        "Invalid selector, retrying action %s",
                        action,
                    )
                    self.choose_action_chat.append(
                        ModelChat(
                            role=ModelChatType.user,
                            content="The selector you provided is invalid, try to use `role` and `name` instead",
                        )
                    )
                elif "strict mode violation" in str(e):
                    logger.info(
                        "Locator resolved to more than one element, retrying action %s",
                        action,
                    )
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
                logger.warning(
                    "Max action attempts (%s) reached",
                    self.max_action_attempts,
                )
                return None, self.actions_count

        return action, self.actions_count

    async def run(self) -> tuple[Optional[str], Optional[Action], int]:
        if self.http_client is None:
            http_client = httpx.AsyncClient()
        else:
            http_client = self.http_client

        next_instruction = None
        action = None
        try:
            encoded_image = await self._take_screenshot()
            html_coro = self._get_html()
            next_instruction = await self._get_next_step(
                encoded_image, http_client
            )
            html = await html_coro
            if "DONE" in next_instruction or "WAIT" in next_instruction:
                return next_instruction, None, 0

            action, action_count = await self._choose_and_execute_action(
                next_instruction, html, http_client
            )
        finally:
            if self.http_client is None:
                await http_client.aclose()
        return next_instruction, action, action_count


class ScrapeAiExecutor(_AiExecutorBase, _ScrapeExecutorBase):
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
        save_playwright_trace: bool = False,
        http_client: Optional[httpx.AsyncClient] = None,
        subscriptions: Optional[set[asyncio.Queue[ExecutorMessage]]] = None,
        headless: bool = True,
    ) -> None:
        """
        Runs a test on a given URL with a high level goal until the goal is completed or it errors out

        Examples:
            ```python
            scrape_executor = ScrapeAiExecutor(
                url="https://google.com",
                high_level_goal="Find images of cats",
                openai_api_key="...",
            )
            await scrape_executor.run()
            ```

        Args:
            url (str): URL to test
            high_level_goal (str): High level goal to accomplish at the URL
            openai_api_key (str): OpenAI API key, see https://platform.openai.com/api-keys
            max_page_views (Optional[int], optional): Max page views to take across the entire test. Defaults to 10.
            max_total_actions (Optional[int], optional): Max total actions to take across the entire test. Defaults to 20.
            max_action_attempts_per_step (Optional[int], optional): Max actions to take on a single page. Defaults to 5.
            viewport_width (int, optional): Viewport width in pixels. Defaults to 1280.
            viewport_height (int, optional): Viewport height in pixels. Defaults to 720.
            variables (Optional[ScrapeVariables], optional): Variables to use in the scrape, e.g. for filling in a username and password to log in. Defaults to None.
            files (Optional[ScrapeFiles], optional): Files to use in the scrape, e.g. for uploading some data as part of the goal. Defaults to None.
            scrape_id (Optional[UUID], optional): Scrape ID. Defaults to None.
            file_client (Optional[FileClient], optional): File client to use for saving images, html, and traces. Defaults to None.
            save_playwright_trace (bool, optional): Whether to save the playwright trace, see https://playwright.dev/python/docs/trace-viewer-intro for more information. You must provide a file_client to use this option. Defaults to False.
            http_client (Optional[httpx.AsyncClient], optional): Http client to use for making requests, pass one through to reuse across tests. Defaults to None.
            subscriptions (Optional[set[asyncio.Queue[ExecutorMessage]], optional): Subscriptions that will receive messages from the executor as it progresses. Defaults to None.
            headless (bool, optional): Whether to run the browser in headless mode, if False a chromium browswer will display the actions of the test in real time. Defaults to True.
        """
        _ScrapeExecutorBase.__init__(
            self,
            url=url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            file_client=file_client,
            scrape_id=scrape_id,
            save_playwright_trace=save_playwright_trace,
            headless=headless,
        )
        _AiExecutorBase.__init__(self, subscriptions=subscriptions)
        self.high_level_goal = high_level_goal
        self._openai_api_key = openai_api_key
        self.max_page_views = max_page_views
        self.max_total_actions = max_total_actions
        self.max_action_attempts_per_step = max_action_attempts_per_step
        self.variables = variables or {}
        self.files = files or {}

        self.scrape_page_view_count = 0
        self.scrape_action_count = 0

        self.http_client = http_client
        self.close_http_client = http_client is None

        self.previous_steps: list[str] = []

        self.scrape_events: list[ScrapeEvent] = []

    async def _run_start_callback(self) -> None:
        if self.http_client is None:
            self.http_client = httpx.AsyncClient()

    async def _run_end_callback(self) -> None:
        # save scrape spec
        if self.file_client is not None:
            spec = ScrapeSpec(
                url=self.url,
                scrape_events=self.scrape_events,
                variables=self.variables,
                files=self.files,
                viewport_height=self.viewport["height"],
                viewport_width=self.viewport["width"],
            )
            spec_save_path = await self.file_client.save_scrape_spec(
                self.scrape_id, spec
            )
            logger.info(
                "Saved scrape spec to %s",
                spec_save_path,
            )

        # cleanup model client
        if self.close_http_client and self.http_client is not None:
            await self.http_client.aclose()

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

    async def _execute(self, page: Page) -> None:
        logger.info(
            "\x1b[1;34mHigh Level Goal\x1b[0m: %s", self.high_level_goal
        )
        await page.goto(self.url)
        logger.info("Navigated to %s", self.url)
        while True:
            self.scrape_page_view_count += 1
            self.publish(
                ExecutorMessage(
                    scrape_page_view_count=self.scrape_page_view_count,
                    scrape_action_count=self.scrape_action_count,
                )
            )

            logger.info("Starting scrape step %s", self.scrape_page_view_count)
            logger.info("---------------------------------")

            # initialize scraper
            step_executor = ScrapeStepAiExecutor(
                high_level_goal=self.high_level_goal,
                previous_steps=self.previous_steps,
                page=page,
                variables=self.variables,
                files=self.files,
                openai_api_key=self._openai_api_key,
                max_action_attempts=self.max_action_attempts,
                subscriptions=self.subscriptions,
                file_client=self.file_client,
                scrape_id=self.scrape_id,
                http_client=self.http_client,
            )

            # run the step
            next_instruction, action, action_count = await step_executor.run()

            # process next instruction
            next_instruction_fmt = None
            if next_instruction is not None:
                self.previous_steps.append(next_instruction)
                if "DONE" in next_instruction:
                    logger.info("High level goal accomplished")
                    next_instruction_fmt = SpecialInstruction.DONE
                elif "WAIT" in next_instruction:
                    logger.info("Waiting for page to load")
                    next_instruction_fmt = SpecialInstruction.WAIT

            # update action count
            self.scrape_action_count += action_count
            logger.info(
                "Scrape step %s completed, total number of actions across scrape: %s",
                self.scrape_page_view_count,
                self.scrape_action_count,
            )
            logger.info("---------------------------------")

            # update action history
            if action is not None:
                self.scrape_events.append(action)
            if next_instruction_fmt is not None:
                self.scrape_events.append(next_instruction_fmt)

            # end test if high level goal is completed
            if next_instruction_fmt == SpecialInstruction.DONE:
                break

            # check if max total actions reached
            if (
                self.max_total_actions is not None
                and self.scrape_action_count >= self.max_total_actions
            ):
                raise MaxTotalActionsReachedException(
                    f"Max total actions ({self.scrape_action_count}) reached"
                )

            # check if max page views reached
            if (
                self.max_page_views is not None
                and self.scrape_page_view_count >= self.max_page_views
            ):
                raise MaxPageViewsReachedException(
                    f"Max page views ({self.scrape_page_view_count}) reached"
                )


class ScrapeSpecExecutor(_ScrapeExecutorBase):
    def __init__(
        self,
        scrape_spec: ScrapeSpec,
        scrape_id: Optional[UUID] = None,
        file_client: Optional[FileClient] = None,
        save_playwright_trace: bool = False,
        headless: bool = True,
    ) -> None:
        """
        Executes a test on a given URL from a previously saved scrape spec

        Examples:
            ```python
            from betatester import ScrapeSpecExecutor
            from betatester.file.local import LocalFileClient

            file_client = LocalFileClient("...")
            scrape_spec = file_client.load_scrape_spec("/path/to/scrape_spec.json")

            scrape_spec_executor = ScrapeSpecExecutor(
                scrape_spec=scrape_spec,
            )
            await scrape_spec_executor.run()
            ```

        Args:
            scrape_spec (ScrapeSpec): Scrape spec to execute, this will have been saved by a ScrapeAiExecutor run
            scrape_id (Optional[UUID], optional): Scrape ID. Defaults to None.
            file_client (Optional[FileClient], optional): File client to use for saving images, html, and traces. Defaults to None.
            save_playwright_trace (bool, optional): Whether to save the playwright trace, see https://playwright.dev/python/docs/trace-viewer-int for more information. You must provide a file_client to use this option. Defaults to False.
            headless (bool, optional): Whether to run the browser in headless mode, if False a chromium browswer will display the actions of the test in real time. Defaults to True.
        """
        _ScrapeExecutorBase.__init__(
            self,
            url=scrape_spec.url,
            viewport_width=scrape_spec.viewport_width,
            viewport_height=scrape_spec.viewport_height,
            file_client=file_client,
            scrape_id=scrape_id,
            save_playwright_trace=save_playwright_trace,
            headless=headless,
        )
        self.scrape_events = scrape_spec.scrape_events
        self.variables = scrape_spec.variables
        self.files = scrape_spec.files

    async def _execute(self, page: Page) -> None:
        await page.goto(self.url)
        logger.info("Navigated to %s", self.url)
        for scrape_event in self.scrape_events:
            if isinstance(scrape_event, Action):
                logger.info("Executing action: %s", scrape_event)
                await _execute_action(
                    page, scrape_event, self.variables, self.files
                )
            elif scrape_event == SpecialInstruction.DONE:
                await page.wait_for_timeout(5000)
                logger.info("High level goal accomplished")
            elif scrape_event == SpecialInstruction.WAIT:
                logger.info("Waiting 5 seconds for page to load")
                await page.wait_for_timeout(5000)
            else:
                raise ValueError(f"Invalid scrape event: {scrape_event}")
