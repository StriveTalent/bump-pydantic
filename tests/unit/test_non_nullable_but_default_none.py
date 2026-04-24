import textwrap

import pytest
from bump_pydantic.codemods.non_nullable_but_default_none import NonNullableButDefaultNoneCommand

from .base import BPTest


class TestClassDefVisitor(BPTest):
    TRANSFORM = NonNullableButDefaultNoneCommand

    def test_no_default(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel, Field

            class Potato(BaseModel):
                a: Optional[str]
                b: str | None
                c: str
                d: Optional[str] = None
                e: str | None = None
                f: Optional[str] = Field(None)
                g: str | None = Field(None)
        """
        )
        self.assertCodemod(source, source)

    def test_with_str(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel

            class Potato(BaseModel):
                a: str = None
            """
        )
        expected = textwrap.dedent(
            """
            from pydantic import BaseModel

            class Potato(BaseModel):
                # TODO[pydantic]: Make field nullable or required as needed
                a: str = None
            """
        )
        self.assertCodemod(source, expected)

    def test_with_default_none_assignment(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel

            class Potato(BaseModel):
                a: str = None
            """
        )
        expected = textwrap.dedent(
            """
            from pydantic import BaseModel

            class Potato(BaseModel):
                # TODO[pydantic]: Make field nullable or required as needed
                a: str = None
            """
        )
        self.assertCodemod(source, expected)

    def test_with_none(self) -> None:
        source = textwrap.dedent(
            """
            from pydantic import BaseModel

            class Potato(BaseModel):
                a: None = None
            """
        )
        self.assertCodemod(source, source)
