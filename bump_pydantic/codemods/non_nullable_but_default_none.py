from __future__ import annotations

import libcst as cst
import libcst.matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.metadata import FullyQualifiedNameProvider, QualifiedName

from bump_pydantic.codemods.class_def_visitor import is_a_base_model


COMMENT = "# TODO[pydantic]: Make field nullable or required as needed"


class NonNullableButDefaultNoneCommand(VisitorBasedCodemodCommand):
    """This codemod adds a comment to fields that has `None` as the default value but the the field type is not nullable.

    Example::
        # Before
        ```py
        from pydantic import BaseModel

        class Foo(BaseModel):
            bar: str = None
        ```

        # After
        ```py
        from pydantic import BaseModel

        class Foo(BaseModel):
            # TODO[pydantic]: Make field nullable or required as needed
            bar: str = None
        ```
    """

    METADATA_DEPENDENCIES = (FullyQualifiedNameProvider,)

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)

        self.inside_base_model = False
        self.base_model_fields: set[cst.Assign | cst.AnnAssign | cst.SimpleStatementLine] = set()
        self.statement: cst.SimpleStatementLine | None = None
        self.has_comment = False
        self.needs_comment = False
        self.is_nullable_field = False

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        if is_a_base_model(self, node):
            self.inside_base_model = True
            self.base_model_fields = {
                child for child in node.body.children if isinstance(child, cst.SimpleStatementLine)
            }

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        self.inside_base_model = False
        self.base_model_fields = set()
        return updated_node

    def visit_SimpleStatementLine(self, node: cst.SimpleStatementLine) -> None:
        if node not in self.base_model_fields:
            return
        if not self.inside_base_model:
            return
        for line in node.leading_lines:
            if m.matches(line, m.EmptyLine(comment=m.Comment(value=COMMENT))):
                self.has_comment = True

    def leave_SimpleStatementLine(
        self, original_node: cst.SimpleStatementLine, updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine:
        if original_node not in self.base_model_fields:
            return updated_node
        if self.needs_comment and not self.has_comment:
            updated_node = updated_node.with_changes(
                leading_lines=[
                    *updated_node.leading_lines,
                    cst.EmptyLine(comment=cst.Comment(value=(COMMENT))),
                ],
                body=[
                    *updated_node.body,
                ],
            )
        self.needs_comment = False
        self.has_comment = False
        return updated_node

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        if m.matches(
            node.annotation.annotation,
            m.Subscript(m.Name("Optional") | m.Attribute(m.Name("typing"), m.Name("Optional")))
            | m.Subscript(
                m.Name("Union") | m.Attribute(m.Name("typing"), m.Name("Union")),
                slice=[
                    m.ZeroOrMore(),
                    m.SubscriptElement(slice=m.Index(m.Name("None"))),
                    m.ZeroOrMore(),
                ],
            )
            | m.Name("Any")
            | m.Name("None")
            | m.Attribute(m.Name("typing"), m.Name("Any"))
            # TODO: This can be recursive. Can it?
            | m.BinaryOperation(operator=m.BitOr(), left=m.Name("None"))
            | m.BinaryOperation(operator=m.BitOr(), right=m.Name("None")),
        ):
            self.is_nullable_field = True
        return None

    def leave_AnnAssign(self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign) -> cst.AnnAssign:
        if self.inside_base_model and not self.is_nullable_field:
            if updated_node.value is None:
                # NOTE: This is a required field. Nothing to do.
                ...
            elif m.matches(updated_node.value, cst.Name("None")):
                self.needs_comment = True
            elif m.matches(updated_node.value, m.Call(func=m.Name("Field"))):
                assert isinstance(updated_node.value, cst.Call)
                args = updated_node.value.args
                if args:
                    # NOTE: It has a "default" value as positional argument. Nothing to do.
                    if args[0].keyword is None:
                        if m.matches(args[0].value, cst.Name("None")):
                            self.needs_comment = True
                    # NOTE: It has a "default" or "default_factory" keyword argument. Nothing to do.
                    elif default_kwarg := next((arg for arg in args if arg.keyword and arg.keyword.value == "default"), None):
                        if m.matches(default_kwarg.value, cst.Name("None")):
                            self.needs_comment = True


                # NOTE: This is the case where `Field` is called without any arguments e.g. `Field()`. Nothing to do.
                else:
                    ...

        self.is_nullable_field = False
        return updated_node
