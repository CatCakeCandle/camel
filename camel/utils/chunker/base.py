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
from abc import ABC, abstractmethod
from typing import List, Union

from unstructured.documents.elements import Element


class BaseChunker(ABC):
    r"""An abstract base class for all CAMEL chunkers."""

    @abstractmethod
    def chunk(
        self, content: Union[str, Element, List[Element]]
    ) -> List[Union[str, Element]]:
        r"""Chunk the given content"""
        pass
