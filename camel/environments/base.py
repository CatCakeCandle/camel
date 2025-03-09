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

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from camel.agents import ChatAgent
from camel.datasets.base import BaseDataset, GenerativeDataset
from camel.extractors.base import Extractor
from camel.logger import get_logger
from camel.verifiers.base import (
    BaseVerifier,
    VerificationResult,
)
from camel.verifiers.models import (
    VerificationOutcome,
    VerifierInput,
)

logger = get_logger(__name__)

# TODO: Add MachineInfo into this file
# TODO: TeacherAgent should be renamed into neural_reward_model.
#       This is where PRMs or such could be useful.
#       Should probably be its own class and not just raw ChatAgent


class Action(BaseModel):
    r"""Represents an action taken in an environment.

    This class defines the input context, the LLM-generated output, and
    metadata required for verification and tracking within an RL
    framework.

    Attributes:
        problem_statement (str): The task or query given to the LLM as
            input.
        llm_response (str): The response generated by the LLM.
        final_answer (Optional[str]): The reference solution, if
            available, used for supervised learning or evaluation.
        metadata (Dict[str, Any]): Additional metadata such as model
            parameters, prompt details, or response confidence scores.
        timestamp (datetime): The timestamp when the action was
            generated (UTC).
    """

    problem_statement: str = Field(description="Problem statement for the LLM")
    llm_response: str = Field(description="Generated response from the LLM")
    final_answer: Optional[str] = Field(
        None, description="Reference solution if available"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the generation",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the response was generated (UTC)",
    )


class Observation(BaseModel):
    r"""Environment observation.

    Attributes:
        question: The question posed to the LLM.
        context: Additional context for the question.
        metadata: Optional metadata about the observation.
    """

    question: str = Field(..., description="The question posed to the LLM")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context for the question"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata about the observation"
    )


class StepResult(BaseModel):
    r"""Result of an environment step.

    Attributes:
        observation: The next observation.
        reward: Dictionary of reward scores for different aspects.
        done: Whether the episode is complete.
        info: Additional information about the step.
    """

    observation: Observation = Field(..., description="The next observation")
    reward: float = Field(..., description="Total reward of the action")
    rewards_dict: Dict[str, float] = Field(
        default_factory=dict,
        description="Dictionary of reward scores for different aspects",
    )
    done: bool = Field(..., description="Whether the episode is complete")
    info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional information about the step",
    )


class BaseEnvironment(ABC):
    r"""Base class for all RLVR training environments.

    An environment ties everything together. It:
    1. Holds state and manages curriculum progression
    2. Defines reward functions and hint generation
    3. Manages dataset and task selection
    4. Provides reset and step functions
    5. Handles verifier setup and teardown
    6. Enables proactive agent behavior
    7. Supports practice environment creation
    8. Facilitates chain-of-thought verification

    Key Features:
    - Curriculum learning with adaptive difficulty
    - Reward shaping based on solution quality
    - Hint generation from verified solutions
    - Task selection based on agent progress
    - Practice environment generation
    - Chain-of-thought validation
    """

    def __init__(
        self,
        dataset: BaseDataset,
        verifier: BaseVerifier,
        extractor: Extractor,
        max_steps: Optional[int] = None,
        teacher_agent: Optional[ChatAgent] = None,
        curriculum_config: Optional[Dict[str, Any]] = None,
        practice_env_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        r"""Initialize the environment.

        Args:
            dataset: Dataset to sample questions from.
            verifier: Verifier to check responses.
            extractor: Extractor to process LLM responses.
            max_steps: Maximum steps per episode.
            teacher_agent: Optional agent for reward shaping and hints
            curriculum_config: Configuration for curriculum learning including:
                - difficulty_levels: List of available difficulty levels
                - promotion_threshold: Score needed to advance
                - demotion_threshold: Score triggering level decrease
                - min_questions_per_level: Questions before promotion
            practice_env_config: Configuration for practice environments:
                - max_practice_envs: Maximum concurrent environments
                - difficulty_range: Allowed difficulty variation
                - focus_areas: Specific skills to practice
            **kwargs: Additional environment parameters.
        """
        self.dataset = dataset
        self.verifier = verifier
        self.extractor = extractor
        self.max_steps = max_steps
        self.teacher_agent = teacher_agent
        self._metadata = kwargs

        # State tracking
        self._is_setup: bool = False
        self._current_step: int = 0
        self._episode_ended: bool = False
        self._state: Dict[str, Any] = self._get_initial_state()
        self._last_observation: Optional[Observation] = None
        self._episode_history: List[Tuple[Observation, Action]] = []

    @abstractmethod
    async def setup(self) -> None:
        r"""Set up the environment, including verifier initialization."""
        if self._is_setup:
            return

        try:
            # Initialize core components
            if hasattr(self.verifier, 'setup'):
                await self.verifier.setup()
            if hasattr(self.dataset, 'setup'):
                await self.dataset.setup()
            if hasattr(self.extractor, 'setup'):
                await self.extractor.setup()

            # initialize agents if present
            if self.teacher_agent:
                await self.teacher_agent.reset()

            self._is_setup = True
            logger.info('Environment setup completed successfully')
        except Exception as e:
            logger.error(f'Failed to setup environment: {e}')
            raise

    @abstractmethod
    async def teardown(self) -> None:
        r"""Clean up resources, including verifier teardown."""
        if not self._is_setup:
            return

        try:
            # Cleanup components
            if hasattr(self.verifier, 'cleanup'):
                await self.verifier.cleanup()
            if hasattr(self.dataset, 'cleanup'):
                await self.dataset.cleanup()
            if hasattr(self.extractor, 'cleanup'):
                await self.extractor.cleanup()

            self._is_setup = False
            logger.info('Environment teardown completed successfully')
        except Exception as e:
            logger.error(f'Failed to teardown environment: {e}')
            raise

    @abstractmethod
    async def reset(self) -> Observation:
        r"""Reset the environment to initial state.

        Returns:
            Initial observation for the episode
        """

        if not self._is_setup:
            await self.setup()

        # Reset state
        self._current_step = 0
        self._episode_ended = False
        self._episode_history = []
        self._state = self._get_initial_state()

        # Get initial observation
        observation = self._get_next_observation()
        if observation is None:
            raise RuntimeError("Failed to get initial observation")

        self._last_observation = observation

        return observation

    @abstractmethod
    async def step(self, action: Action) -> StepResult:
        r"""Take a step in the environment.

        Args:
            action: Action containing everything that is needed
            to progress in the environment

        Returns:
            StepResult containing next observation, reward, done flag, and info
        """
        if self.max_steps and self._current_step >= self.max_steps:
            return StepResult(
                observation=self._get_terminal_observation(),
                reward=0,
                rewards_dict={},
                done=True,
                info={"reason": "max_steps_reached"},
            )

        if not self._is_setup:
            raise RuntimeError("Environment not set up. Call setup() first.")
        if self._episode_ended:
            raise RuntimeError("Episode has ended. Call reset() first.")
        if self._last_observation is None:
            raise RuntimeError("No current observation. Call reset() first.")

        self._current_step += 1

        current_obs: Observation = self._last_observation
        self._episode_history.append((current_obs, action))

        # extract verifiable part from llm response
        extraction_result = await self.extractor.extract(action.llm_response)

        # Ensure extraction_result is a string
        if extraction_result is None:
            extraction_result = ""

        # verify the extracted
        verification_result = await self.verifier.verify(
            VerifierInput(
                llm_response=extraction_result,
                ground_truth=action.final_answer,
            )
        )

        # compute rewards
        total_reward, rewards_dict = await self.compute_reward(
            action, extraction_result, verification_result
        )

        # check termination
        done = self._is_done()

        next_obs = (
            self._get_terminal_observation()
            if done
            else self._get_next_observation()
        )

        self._last_observation = next_obs
        self._episode_ended = done

        return StepResult(
            observation=next_obs,
            reward=total_reward,
            rewards_dict=rewards_dict,
            done=done,
            info={
                "extraction_result": extraction_result,
                "verification_result": verification_result,
                "step": self._current_step,
                "state": self._state,
            },
        )

    @abstractmethod
    def _get_initial_state(self) -> Dict[str, Any]:
        r"""Get initial environment state."""

        return {
            "current_datapoint": None,
            "attempts": 0,
            "success_rate": 0.0,
            "rewards": [],
            "termination_reason": None,
        }

    @abstractmethod
    def _get_next_observation(self) -> Observation:
        r"""Get the next observation for the environment.

        Returns:
            Observation for the next step
        """
        if not self.dataset or len(self.dataset) == 0:
            logger.warning(
                "Dataset is empty. Attempting to generate new data..."
            )
            if isinstance(self.dataset, GenerativeDataset):
                try:
                    asyncio.run(
                        self.dataset.generate_new(1)
                    )  # Generate at least one datapoint
                    logger.info("Generated new datapoint successfully.")
                except Exception as e:
                    logger.error(f"Failed to generate new data: {e}")
                    return self._get_terminal_observation()
            else:
                logger.error("Dataset is empty and not a GenerativeDataset.")
                return self._get_terminal_observation()

        try:
            # Ensure dataset is not empty after generation attempt
            if len(self.dataset) == 0:
                logger.error("Dataset is still empty after generation.")
                return self._get_terminal_observation()

            # Sample the next datapoint
            datapoint_idx = self._current_step % len(self.dataset)
            datapoint = self.dataset[datapoint_idx]

            if not datapoint:
                logger.error(f"Invalid datapoint at index {datapoint_idx}")
                return self._get_terminal_observation()

            self._state["current_datapoint"] = datapoint

            # Extract necessary attributes safely
            question = getattr(datapoint, "question", None)
            final_answer = getattr(datapoint, "final_answer", None)
            rationale = getattr(datapoint, "rationale", None)
            difficulty = getattr(datapoint, "difficulty", None)
            metadata = getattr(datapoint, "metadata", {})

            if not question or not final_answer:
                logger.error(
                    f"Datapoint at index {datapoint_idx} "
                    "is missing required fields."
                )
                return self._get_terminal_observation()

            observation = Observation(
                question=question,
                context={
                    "final_answer": final_answer,
                    "difficulty": difficulty,
                    "rationale": rationale,
                },
                metadata={
                    "step": self._current_step,
                    "datapoint_id": str(datapoint_idx),
                    "verified": metadata.get("verified", False),
                    **metadata,
                },
            )

            logger.debug(
                f"Generated observation for step {self._current_step}"
            )
            return observation

        except (IndexError, AttributeError) as e:
            logger.error(f"Error getting next observation: {e}")
            return self._get_terminal_observation()
        except Exception as e:
            logger.error(f"Unexpected error getting next observation: {e}")
            return self._get_terminal_observation()

    @abstractmethod
    def _get_terminal_observation(self) -> Observation:
        r"""Get the terminal observation when episode ends.

        Returns:
            Terminal observation
        """
        return Observation(
            question="Episode completed",
            context={},
            metadata={"terminal": True, "final_step": self._current_step},
        )

    @abstractmethod
    async def compute_reward(
        self,
        action: Action,
        extraction_result: str,
        verification_result: VerificationResult,
    ) -> Tuple[float, Dict[str, float]]:
        r"""Compute reward scores for different aspects of the response.

        Args:
            response: The response.
            extraction_result: Extracted information from response
            verification_result: Result from the verifier.

        Returns:
            - Total reward
            - Dictionary of reward scores for different aspects.
        """
        rewards: Dict[str, float] = {}

        # Get success from verification result status
        verification_success = float(
            verification_result.status == VerificationOutcome.SUCCESS
        )
        rewards["correctness"] = 1.0 if verification_success > 0.5 else 0.0

        # Update state
        self._state["rewards"].append(rewards)
        total_attempts = self._state["attempts"] + 1
        self._state["success_rate"] = (
            self._state["success_rate"] * (total_attempts - 1)
            + verification_success
        ) / total_attempts

        further_rewards = await self._compute_reward(
            action, extraction_result, verification_result
        )

        rewards = rewards | further_rewards

        return sum(rewards.values()), rewards

    @abstractmethod
    async def _compute_reward(
        self,
        action: Action,
        extraction_result: str,
        verification_result: VerificationResult,
    ) -> Dict[str, float]:
        pass

    def _is_done(self) -> bool:
        r"""Check if episode should terminate."""
        if self.max_steps and self._current_step >= self.max_steps:
            return True
        return False

    @property
    def metadata(self) -> Dict[str, Any]:
        r"""Get environment metadata."""
        return self._metadata.copy()

    @property
    def current_step(self) -> int:
        r"""Get current step number."""
        return self._current_step
