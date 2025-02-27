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
from typing import Any, Dict, Optional

from pydantic import BaseModel


class Chunk(BaseModel):
    r"""A chunk of text with metadata.

    Args:
        text (str): The text of the chunk.
        metadata (Optional[(Dict[str, Any])): The metadata of the chunk. The
            key of the metadata can be anything that is returned by the
            tools used to create the chunk.
    """

    text: str
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_uio_chunks(cls, uio_chunks, extra_info=None):
        return [
            cls(
                text=str(uio_chunk),
                metadata={
                    **{
                        key: value
                        for key, value in (
                            uio_chunk.metadata.to_dict().items()
                        )
                        if key != "orig_elements"
                    },
                    "extra_info": extra_info or {},
                },
            )
            for uio_chunk in uio_chunks
        ]
