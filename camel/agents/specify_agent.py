# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
from typing import Any, Optional, Union

from camel.agents import ChatAgent, clarify_agent
from camel.messages import BaseMessage
from camel.prompts import TextPrompt
from camel.types import ModelType, RoleType


class TaskSpecifyAgent(ChatAgent):
    r"""An agent that specify the initial task from the question answer
    pairs generated by the task clarifier agent.

    Args:
        model (ModelType, optional): The type of model to use for the agent.
            (default: :obj:`ModelType.GPT_3_5_TURBO`)
        model_config (Any, optional): The configuration for the model.
            (default: :obj:`None`)
    """

    def __init__(
        self,
        model: Optional[ModelType] = None,
        model_config: Optional[Any] = None,
    ) -> None:
        system_message = BaseMessage(
            role_name="Task Specifier",
            role_type=RoleType.ASSISTANT,
            meta_dict=None,
            content="You can generate specified task from clarifications.",
        )
        super().__init__(system_message, model, model_config)

    def run(
        self,
        task_prompt: Union[str, TextPrompt],
        question_answer_pairs: dict[str, str],
    ) -> Union[str, TextPrompt]:
        r"""Generate specified task from clarifications.
        Args:
            task_prompt (Union[str, TextPrompt]): The prompt that needs to be
                specified.
            question_answer_pairs (dict[str, str]): The question answer pairs
                generated by the task clarifier agent.

        Returns:
            Union[str, TextPrompt]: The specified task prompt.
        """

        # For Specification #

        specify_prompt = TextPrompt(
            "As a task specifier agent, your objective is to refine " +
            f"the initial task '{task_prompt}' by incorporating " +
            "details from the generated question-answer pairs: " +
            f" {question_answer_pairs}.\n" +
            "Your task specification should be succinct yet comprehensive, " +
            "clearly integrating the user's requirements. Focus on " +
            "including specific details such as quantities, values, " +
            "key entities, and any critical parameters highlighted " +
            "in the question-answer pairs. " +
            "The goal is to create a well-defined" +
            "task that is aligned with the user's needs " +
            "and provides clear guidance for execution.\n" +
            "Please specify the task in a short summarized way."
        )

        specify_prompt = TextPrompt(specify_prompt)
        specify_prompt = specify_prompt.format(
            task_prompt=task_prompt,
            question_answer_pairs=question_answer_pairs,
        )

        specify_msg = BaseMessage.make_user_message(role_name="Task Specifier",
                                                    content=specify_prompt)

        response = self.step(specify_msg)

        if response.terminated:
            raise ValueError("The specification of the task failed.\n" +
                             f"Error:\n{response.info}")
        msg = response.msg

        return msg.content


if __name__ == "__main__":
    task_prompt = "Develop a trading bot for stock market"
    task_clarify_agent = clarify_agent.TaskClarifyAgent()
    clarify_insights = task_clarify_agent.run(task_prompt=task_prompt)
    task_specify_agent = TaskSpecifyAgent()
    specified_task = \
        task_specify_agent.run(task_prompt=task_prompt,
                               question_answer_pairs=clarify_agent)
    print(f"The specified task is: {specified_task}")
