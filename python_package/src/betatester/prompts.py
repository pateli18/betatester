from .betatester_types import (
    ActionType,
    ModelChat,
    ModelChatType,
    ModelFunction,
    ScrapeFiles,
    ScrapeVariables,
    SpecialInstruction,
    Tool,
    ToolChoiceFunction,
    ToolChoiceObject,
)


def create_next_step_system_prompt(
    high_level_goal: str,
    previous_steps: list[str],
) -> ModelChat:
    previous_steps_str = (
        "\n".join([f"{i}. {step}" for i, step in enumerate(previous_steps)])
        if previous_steps
        else "None"
    )

    system_prompt = f"""
### FACTS
- You are an expert website tester
- You are given a HIGH_LEVEL_GOAL to accomplish on a website and a screenshot of the website
- You are given PREVIOUS_STEPS that have been proposed to accomplish the HIGH_LEVEL_GOAL

### RULES
- You should provide the next step (e.g. click a specific button, fill a specific form, etc.) to accomplish the HIGH_LEVEL_GOAL given the PREVIOUS_STEPS
- Only provide one step at a time
- Avoid proposing steps that have already been proposed in the PREVIOUS_STEPS unless you have a good reason to do so
- If the page has not been loaded, return {SpecialInstruction.WAIT.value}
- If the HIGH_LEVEL_GOAL has been accomplished, return {SpecialInstruction.DONE.value}
    - Only return DONE if the screen you are looking at indicates the goal is complete

HIGH_LEVEL_GOAL: {high_level_goal}

PREVIOUS_STEPS:
{previous_steps_str}
"""

    return ModelChat(
        role=ModelChatType.system,
        content=system_prompt,
    )


def create_choose_action_user_message(
    instruction: str, html: str
) -> ModelChat:
    return ModelChat(
        role=ModelChatType.user,
        content=f"""
INSTRUCTION:
{instruction}

HTML:
{html}
""",
    )


def create_choose_action_system_prompt(
    variables: ScrapeVariables,
    files: ScrapeFiles,
) -> ModelChat:
    variable_keys = (
        "\n".join([f"- {key}" for key in variables.keys()])
        if variables
        else "None"
    )

    file_keys = (
        "\n".join([f"- {key}" for key in files.keys()]) if files else "None"
    )

    system_prompt = f"""
### FACTS
- You are an expert website tester and developer
- You have been given an INSTRUCTION to take on a page, the HTML of the page, and the keys of VARIABLES and FILES

VARIABLES:
{variable_keys}

FILES:
{file_keys}

### RULES
- Your task is to select the `element`, `action_type`, and optionally `action_value` necessary to complete the INSTRUCTION
- For the element, you should provide the `role` and `name`. Only provide the `selector` if it is impossible to select the right element with the `name` and `role`. All values must appear in the provided html and resolve to only one element
- For the action value, either return a relevant value from VARIABLES or FILES or provide a custom value
- If there's a large discrepancy between the INSTRUCTION and the HTML, use the action_type `none` to indicate that the INSTRUCTION needs to be updated
"""
    return ModelChat(
        role=ModelChatType.system,
        content=system_prompt,
    )


def create_choose_action_tools() -> tuple[list[Tool], ToolChoiceObject]:
    action_types = [
        action_type.value for action_type in ActionType.__members__.values()
    ]

    tool_name = "choose_action"
    tool = ModelFunction(
        name=tool_name,
        description="choose the action to execute",
        parameters={
            "type": "object",
            "properties": {
                "element": {
                    "description": "the element to interact with. provide the `role` and `name`. Only provide the `selector` if it is impossible to select the right element with the `name` and `role`. For all of the values, they MUST appear in the provided html",
                    "type": "object",
                    "properties": {
                        "role": {
                            "description": "the ARIA role of the element, e.g. 'button', 'input', 'select', etc. This must appear in the provided html",
                            "type": "string",
                        },
                        "name": {
                            "description": "the name of the element if available, e.g. 'submit', 'username', etc. This must appear in the provided html",
                            "type": "string",
                        },
                        "selector": {
                            "description": "the css selector of the element. This must appear in the provided html",
                        },
                    },
                },
                "action_type": {
                    "description": "the type of action to execute",
                    "type": "string",
                    "enum": action_types,
                },
                "action_value": {
                    "description": "the value to use as part of the action, can be a variable from VARIABLES or FILES or a custom value",
                    "type": "string",
                },
            },
            "required": ["element", "action_type"],
        },
    )

    return [Tool(function=tool)], ToolChoiceObject(
        function=ToolChoiceFunction(name="choose_action")
    )
