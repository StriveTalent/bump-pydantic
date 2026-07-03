import textwrap

import pytest
from bump_pydantic.codemods.add_default_none import AddDefaultNoneCommand

from .base import BPTest


class TestClassDefVisitor(BPTest):
    TRANSFORM = AddDefaultNoneCommand

    def test_no_annotations(self) -> None:
        source = textwrap.dedent(
            """class Potato:
            a: Optional[str]
        """
        )
        self.assertCodemod(source, source)

    def test_with_optional(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel

            class Potato(BaseModel):
                a: Optional[str]
            """
        )
        expected = textwrap.dedent(
            """from pydantic import BaseModel

class Potato(BaseModel):
    a: Optional[str] = None
"""
        )
        self.assertCodemod(source, expected)

    def test_with_union_none(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel
            from typing import Union

            class Potato(BaseModel):
                a: Union[str, None]
            """
        )
        expected = textwrap.dedent(
            """from pydantic import BaseModel
from typing import Union

class Potato(BaseModel):
    a: Union[str, None] = None
"""
        )
        self.assertCodemod(source, expected)

    def test_with_multiple_classes(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel
            from typing import Optional

            class Potato(BaseModel):
                a: Optional[str]

            class Carrot(Potato):
                b: Optional[str]
            """
        )
        expected = textwrap.dedent(
            """from pydantic import BaseModel
from typing import Optional

class Potato(BaseModel):
    a: Optional[str] = None

class Carrot(Potato):
    b: Optional[str] = None
            """
        )
        self.assertCodemod(source, expected)

    def test_any(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel
            from typing import Any

            class Potato(BaseModel):
                a: Any
            """
        )
        expected = textwrap.dedent(
            """from pydantic import BaseModel
from typing import Any

class Potato(BaseModel):
    a: Any = None
"""
        )
        self.assertCodemod(source, expected)

    @pytest.mark.xfail(reason="Recursive Union is not supported")
    def test_union_of_union(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel
            from typing import Union

            class Potato(BaseModel):
                a: Union[Union[str, None], int]
            """
        )
        expected = textwrap.dedent(
            """from pydantic import BaseModel
from typing import Union

class Potato(BaseModel):
    a: Union[Union[str, None], int] = None
"""
        )
        self.assertCodemod(source, expected)
