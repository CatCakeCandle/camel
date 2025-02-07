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

from pprint import pprint

from datasets import Dataset

from camel.verifiers import CodeVerifier


def main():
    print("\nExample 1: Basic Function Test")
    verifier = CodeVerifier(require_confirmation=False)
    result = verifier.verify(
        {
            "code": ["def add(a, b): return a + b"],
            "language": ["python"],
            "test_cases": [
                [
                    {"inputs": {"a": 1, "b": 2}, "expected": {"add(a, b)": 3}},
                    {
                        "inputs": {"a": -1, "b": 1},
                        "expected": {"add(a, b)": 0},
                    },
                ]
            ],
        }
    )
    pprint(result[0]["verification_result"])

    # Example 2: Multiple Solutions
    print("\nExample 2: Multiple Solutions")
    data = Dataset.from_dict(
        {
            "code": [
                "def factorial(n): return 1 if n <= 1 else n * factorial(n-1)",
                "def factorial(n): return n * factorial(n-1) if n > 1 else 1",
            ],
            "language": ["python", "python"],
            "test_cases": [
                [{"inputs": {"n": 5}, "expected": {"factorial(n)": 120}}],
                [{"inputs": {"n": 5}, "expected": {"factorial(n)": 120}}],
            ],
        }
    )
    results = verifier.verify(data)
    for i, result in enumerate(results):
        print(f"Solution {i+1} result:", result["verification_result"])

    # Example 3: Using subprocess interpreter
    print("\nExample 3: External Imports")
    verifier = CodeVerifier(interpreter="subprocess")
    result = verifier.verify(
        {
            "code": [
                """
import numpy as np
def process_array():
    arr = np.array([1, 2, 3])
    return arr.mean()
        """
            ],
            "language": ["python"],
            "test_cases": [
                [{"inputs": {}, "expected": {"process_array()": 2.0}}]
            ],
        }
    )
    print("Result:", result[0]["verification_result"])

    # Example 4: Syntax Error
    print("\nExample 4: Syntax Error")
    result = verifier.verify(
        {
            "code": ["def broken_function(x: return x"],  # Syntax error
            "language": ["python"],
        }
    )
    print("Result:", result[0]["verification_result"])


if __name__ == "__main__":
    main()


"""
Example Output:

Example 1: Basic Function Test
Map: 100%|██████████| 1/1 [00:00<00:00, 14.90 examples/s]
{
    'details': {
        'test_count': 2,
        'tests': [
            {
                'output': 'Test passed: 3\n',
                'status': 'passed', 
                'test_case': 1
            },
            {
                'output': 'Test passed: 0\n',
                'status': 'passed',
                'test_case': 2
            }
        ]
    },
    'error': None,
    'passed': True,
    'test_results': [True, True]
}

Example 2: Multiple Solutions
Map: 100%|██████████| 2/2 [00:00<00:00, 25.12 examples/s]
Solution 1 result: {
    'details': {
        'test_count': 1,
        'tests': [
            {
                'output': 'Test passed: 120\n',
                'status': 'passed',
                'test_case': 1
            }
        ]
    },
    'error': None,
    'passed': True,
    'test_results': [True]
}
Solution 2 result: {
    'details': {
        'test_count': 1,
        'tests': [
            {
                'output': 'Test passed: 120\n',
                'status': 'passed',
                'test_case': 1
            }
        ]
    },
    'error': None,
    'passed': True,
    'test_results': [True]
}

Example 3: External Imports
Map: 100%|██████████| 1/1 [00:00<00:00,  3.33 examples/s]
Result: {
    'details': {
        'test_count': 1,
        'tests': [
            {
                'output': 'Test passed: 2.0\n',
                'status': 'passed',
                'test_case': 1
            }
        ]
    },
    'error': None,
    'passed': True,
    'test_results': [True]
}

Example 4: Syntax Error
Map: 100%|██████████| 1/1 [00:00<00:00, 661.88 examples/s]
Result: {
    'details': {
        'line': 1,
        'offset': 24,
        'text': 'def broken_function(x: return x\n',
        'type': 'syntax_error'
    },
    'error': 'Syntax error: invalid syntax (<string>, line 1)',
    'passed': False,
    'test_results': []
}
"""
