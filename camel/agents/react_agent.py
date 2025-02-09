# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from camel.agents import ChatAgent
from camel.logger import get_logger
from camel.messages import BaseMessage
from camel.models import BaseModelBackend
from camel.responses import ChatAgentResponse
from camel.toolkits import FunctionTool
from camel.types import RoleType

logger = get_logger(__name__)

# AgentOps decorator setting
try:
    import os

    if os.getenv("AGENTOPS_API_KEY") is not None:
        from agentops import track_agent
    else:
        raise ImportError
except (ImportError, AttributeError):
    from camel.utils import track_agent


class ReActStep(BaseModel):
    """Structured format for ReAct steps"""

    thought: str = Field(description="Reasoning about current situation")
    action: str = Field(description="Action to take (Search/Lookup/Finish)")
    observation: Optional[str] = Field(
        None, description="Results of the action"
    )


class ReActActionSpace(Enum):
    r"""Available actions in the ReAct framework as
    defined in the original paper.

    References:
        https://arxiv.org/pdf/2210.03629
    """

    SEARCH = "Search"
    LOOKUP = "Lookup"
    FINISH = "Finish"


@track_agent(name="ReActAgent")
class ReActAgent(ChatAgent):
    r"""ReAct Agent that combines reasoning and acting through:
    - Thought: Reasoning about current state
    - Action: Deciding what action to take
    - Observation: Getting results of actions

    Args:
        system_message (BaseMessage): The system message for initializing the
            agent's conversation context.
        model (Optional[BaseModelBackend], optional): The model backend to use
            for response generation. (default: :obj:`None`)
        tools (Optional[List[Union[FunctionTool, Callable]]], optional): List
            of available tools that can be used to execute actions. Tools can
            be either FunctionTool instances or callable functions.
            (default: :obj:`None`)
        max_steps (int, optional): Maximum number of reasoning steps before
            forced termination. Prevents infinite loops.
            (default: :obj:`10`)
    """

    def __init__(
        self,
        system_message: BaseMessage,
        model: Optional[BaseModelBackend] = None,
        tools: Optional[List[Union[FunctionTool, Callable]]] = None,
        max_steps: int = 10,
    ) -> None:
        super().__init__(system_message=system_message, model=model)
        self.tools: List[FunctionTool] = [
            t if isinstance(t, FunctionTool) else FunctionTool(t)
            for t in (tools or [])
        ]
        self.scratchpad: List[Dict[str, Optional[str]]] = []
        self._set_react_prompt()
        self.step_count = 0
        self.max_steps = max_steps
        logger.debug("ReActAgent initialized with %d tools", len(self.tools))

    def _set_react_prompt(self) -> None:
        r"""Set up the ReAct prompt template following the paper's format.

        This method initializes the prompt template that guides the agent's
        response format and behavior.
        """
        self.react_prompt = (
            "Respond with a JSON object containing:\n"
            "- thought: Your analysis of the current situation\n"
            "- action: EXACTLY ONE of:\n"
            "  - Search(query=<search terms>)\n"
            "  - Lookup(key=<exact key>)\n"
            "  - Finish(answer=<final answer>)\n"
            "\nExample response:\n"
            '{\n'
            '    "thought": "I need to find population data",\n'
            '    "action": "Search(query=Paris population 2024)"\n'
            '}\n\n'
            "Current scratchpad:\n"
            "{scratchpad}"
        )
        logger.debug("ReAct prompt template set")

    def _format_scratchpad(self) -> str:
        r"""Format the scratchpad history for inclusion in prompts.

        Returns:
            str: A formatted string containing the history of thoughts,
                actions, and observations. Returns empty string if no
                history exists.
        """
        if not self.scratchpad:
            return ""

        formatted = "Previous steps:\n"
        for step in self.scratchpad:
            for key, value in step.items():
                if value:
                    formatted += f"{key}: {value}\n"
            formatted += "\n"
        return formatted

    def _handle_max_steps(self) -> ChatAgentResponse:
        r"""Handle the case when maximum steps are reached.

        Returns:
            ChatAgentResponse: A response object containing:
                - msgs: List[BaseMessage] with termination message
                - terminated: Set to True
                - info: Dictionary with thought, action, observation details
        """
        logger.warning("Maximum steps reached, terminating execution")
        final_message = BaseMessage(
            role_name="Assistant",
            role_type=RoleType.ASSISTANT,
            meta_dict={},
            content="Maximum number of steps reached. Terminating execution.",
        )

        return ChatAgentResponse(
            msgs=[final_message],
            terminated=True,
            info={
                "thought": "Maximum steps reached",
                "action": "",
                "observation": "Task terminated due to step limit",
            },
        )

    def _execute_action(self, action: str) -> str:
        r"""Execute an action using available tools.

        Args:
            action (str): The action string to execute in format Action(params)
                Must be one of the supported action types (Search, Lookup, or
                Finish).

        Returns:
            str: The result of the action execution. Returns error message if
                action execution fails or no suitable tool is found.
        """
        logger.debug("Executing action: %s", action)

        if action.startswith("Finish"):
            logger.info("Task completion requested")
            return "Task completed."

        if not self.tools:
            logger.warning("No tools available to execute action")
            return "No tools available to execute action."

        for tool in self.tools:
            try:
                if hasattr(tool, 'can_handle') and tool.can_handle(action):
                    logger.debug("Found tool to handle action")
                    if hasattr(tool, 'execute'):
                        return tool.execute(action)
                    elif callable(tool):
                        return tool(action)
                    else:
                        logger.error(
                            "Tool has no execute method or is not callable"
                        )
                        return "Error: Tool implementation is invalid"
            except Exception as e:
                logger.error("Error executing action: %s", str(e))
                return f"Error executing action: {e!s}"

        logger.warning("No suitable tool found for action: %s", action)
        return "Action could not be executed with available tools."

    def step(
        self,
        input_message: Union[BaseMessage, str],
        response_format: Optional[type[BaseModel]] = None,
        **kwargs: Any,
    ) -> ChatAgentResponse:
        r"""Perform one step of the ReAct cycle (Reasoning, Acting, Observing).

        Args:
            input_message (Union[BaseMessage, str]): Input message to process.
                If string, it will be converted to BaseMessage. This will be
                augmented with the scratchpad history and ReAct prompt.
            response_format (Optional[type[BaseModel]], optional): The expected
                response format. (default: :obj:`None`)
            **kwargs: Additional keyword arguments passed to the underlying
                model call.

        Returns:
            ChatAgentResponse: A response object containing:
                - msgs: List with a single message containing the thought,
                    action, and observation
                - terminated: True if action is Finish or max steps reached
                - info: Dictionary with parsed thought, action, and observation
        """
        # Convert string input to BaseMessage if needed
        if isinstance(input_message, str):
            input_message = BaseMessage(
                role_name="User",
                role_type=RoleType.USER,
                meta_dict={},
                content=input_message,
            )

        if self.step_count >= self.max_steps:
            logger.warning("Maximum steps (%d) reached", self.max_steps)
            return self._handle_max_steps()

        self.step_count += 1
        logger.debug("Starting step %d", self.step_count)

        # Include scratchpad history in the prompt
        history = self._format_scratchpad()
        augmented_content = (
            f"{input_message.content}\n\n"
            f"{history}\n"
            f"{self.react_prompt}"
        )
        augmented_message = BaseMessage(
            role_name=input_message.role_name,
            role_type=input_message.role_type,
            meta_dict=input_message.meta_dict,
            content=augmented_content,
        )

        # Get initial response
        response = super().step(augmented_message, response_format=ReActStep)

        # Parse response into ReActStep model
        if (
            hasattr(response.msgs[0], 'parsed')
            and response.msgs[0].parsed
            and isinstance(response.msgs[0].parsed, ReActStep)
        ):
            react_step = response.msgs[0].parsed
            thought = react_step.thought
            action = react_step.action
            observation = react_step.observation
        else:
            thought = ""
            action = ""
            observation = None

        # Execute action if specified
        if action:
            logger.debug("Executing action: %s", action)
            actual_observation = self._execute_action(action)
            observation = actual_observation

        # Update scratchpad
        self.scratchpad.append(
            {
                "Thought": thought or "",
                "Action": action or "",
                "Observation": observation or "",
            }
        )

        # Create final response
        final_content = "\n".join(
            filter(
                None,
                [
                    f"Thought: {thought}" if thought else None,
                    f"Action: {action}" if action else None,
                    f"Observation: {observation}" if observation else None,
                ],
            )
        )

        final_message = BaseMessage(
            role_name=response.msgs[0].role_name,
            role_type=RoleType.ASSISTANT,
            meta_dict=response.msgs[0].meta_dict,
            content=final_content,
        )

        # Check if the action was Finish
        terminated = bool(action and action.startswith("Finish"))
        if terminated:
            logger.info("Task completed after %d steps", self.step_count)

        return ChatAgentResponse(
            msgs=[final_message],
            terminated=terminated,
            info={
                "thought": thought or "",
                "action": action or "",
                "observation": observation or "",
            },
        )
