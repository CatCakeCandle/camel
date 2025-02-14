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

from typing import Any, ClassVar, Dict
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from camel.messages import BaseMessage, FunctionCallingMessage, OpenAIMessage
from camel.messages.acl_parameter import Content
from camel.types import OpenAIBackendRole


class MemoryRecord(BaseModel):
    r"""The basic message storing unit in the CAMEL memory system.

    Attributes:
        message (BaseMessage): The main content of the record.
        role_at_backend (OpenAIBackendRole): An enumeration value representing
            the role this message played at the OpenAI backend. Note that this
            value is different from the :obj:`RoleType` used in the CAMEL role
            playing system.
        uuid (UUID, optional): A universally unique identifier for this record.
            This is used to uniquely identify this record in the memory system.
            If not given, it will be assigned with a random UUID.
        extra_info (Dict[str, str], optional): A dictionary of additional
            key-value pairs that provide more information. If not given, it
            will be an empty `Dict`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: BaseMessage
    role_at_backend: OpenAIBackendRole
    uuid: UUID = Field(default_factory=uuid4)
    extra_info: Dict[str, str] = Field(default_factory=dict)

    _MESSAGE_TYPES: ClassVar[dict] = {
        "BaseMessage": BaseMessage,
        "FunctionCallingMessage": FunctionCallingMessage,
    }

    @classmethod
    def from_dict(cls, record_dict: Dict[str, Any]) -> "MemoryRecord":
        r"""Reconstruct a :obj:`MemoryRecord` from the input dict.

        Args:
            record_dict(Dict[str, Any]): A dict generated by :meth:`to_dict`.
        """
        message_data = record_dict["message"]
        message_class = message_data.get('__class__')

        # Extract common data
        role_name = message_data['role_name']
        role_type = message_data['role_type']
        content_data = message_data['content']

        # Determine content type
        if content_data.get('image_list'):
            content = Content.from_dict(content_data)
        elif content_data.get('video_bytes'):
            content = Content.from_dict(content_data)
        else:
            content = Content(text=content_data)

        # Reconstruct the correct message type
        if message_class == 'BaseMessage':
            reconstructed_message = BaseMessage(role_name, role_type, content)
        elif message_class == 'FunctionCallingMessage':
            func_name = message_data['func_name']
            args = message_data['args']
            result = message_data['result']
            tool_call_id = message_data['tool_call_id']
            reconstructed_message = FunctionCallingMessage(
                role_name=role_name,
                role_type=role_type,
                content=content,
                func_name=func_name,
                args=args,
                result=result,
                tool_call_id=tool_call_id,
            )
        else:
            raise ValueError(f"Unsupported message type: {message_class}")

        # Return the reconstructed MemoryRecord
        return cls(
            uuid=UUID(record_dict["uuid"]),
            message=reconstructed_message,
            role_at_backend=record_dict["role_at_backend"],
            extra_info=record_dict["extra_info"],
        )

    def to_dict(self) -> Dict[str, Any]:
        r"""Convert the :obj:`MemoryRecord` to a dict for serialization
        purposes.
        """
        message_dict = {}
        message_dict = {
            "__class__": self.message.__class__.__name__,
        }
        message_dict.update(self.message.to_dict())
        return {
            "uuid": str(self.uuid),
            "message": message_dict,
            "role_at_backend": self.role_at_backend,
            "extra_info": self.extra_info,
        }

    def to_openai_message(self) -> OpenAIMessage:
        r"""Converts the record to an :obj:`OpenAIMessage` object."""
        return self.message.to_openai_message(self.role_at_backend)


class ContextRecord(BaseModel):
    r"""The result of memory retrieving."""

    memory_record: MemoryRecord
    score: float
