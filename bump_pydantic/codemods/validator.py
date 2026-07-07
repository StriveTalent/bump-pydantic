from typing import List

import libcst as cst
from libcst import matchers as m
from libcst._nodes.module import Module
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor
from libcst.metadata import FullyQualifiedNameProvider

from bump_pydantic.codemods.class_def_visitor import is_a_base_model

PREFIX_COMMENT = "# TODO[pydantic]: "
REFACTOR_COMMENT = (
    f"{PREFIX_COMMENT}We couldn't refactor the `{{old_name}}`, please replace it by `{{new_name}}` manually."
)
VALIDATOR_COMMENT = REFACTOR_COMMENT.format(old_name="validator", new_name="field_validator")
ROOT_VALIDATOR_COMMENT = REFACTOR_COMMENT.format(old_name="root_validator", new_name="model_validator")
CHECK_LINK_COMMENT = "# Check https://pydantic.dev/docs/validation/latest/get-started/migration/#changes-to-validators for more information."

IMPORT_VALIDATOR = m.Module(
    body=[
        m.ZeroOrMore(),
        m.SimpleStatementLine(
            body=[
                m.ZeroOrMore(),
                m.ImportFrom(
                    module=m.Name("pydantic"),
                    names=[
                        m.ZeroOrMore(),
                        m.ImportAlias(name=m.Name("validator")),
                        m.ZeroOrMore(),
                    ],
                ),
                m.ZeroOrMore(),
            ],
        ),
        m.ZeroOrMore(),
    ]
)
VALIDATOR_DECORATOR = m.Decorator(decorator=m.Call(func=m.Name("validator")))
VALIDATOR_FUNCTION = m.FunctionDef(decorators=[m.ZeroOrMore(), VALIDATOR_DECORATOR, m.ZeroOrMore()])

IMPORT_ROOT_VALIDATOR = m.Module(
    body=[
        m.ZeroOrMore(),
        m.SimpleStatementLine(
            body=[
                m.ZeroOrMore(),
                m.ImportFrom(
                    module=m.Name("pydantic"),
                    names=[
                        m.ZeroOrMore(),
                        m.ImportAlias(name=m.Name("root_validator")),
                        m.ZeroOrMore(),
                    ],
                ),
                m.ZeroOrMore(),
            ],
        ),
        m.ZeroOrMore(),
    ]
)
ROOT_VALIDATOR_DECORATOR_CALL = m.Decorator(decorator=m.Call(func=m.Name("root_validator")))
ROOT_VALIDATOR_DECORATOR_NAME = m.Decorator(decorator=m.Name("root_validator"))
ROOT_VALIDATOR_FUNCTION = m.FunctionDef(decorators=[
    m.ZeroOrMore(),
    ROOT_VALIDATOR_DECORATOR_CALL | ROOT_VALIDATOR_DECORATOR_NAME,
    m.ZeroOrMore()])


class ValidatorCodemod(VisitorBasedCodemodCommand):
    METADATA_DEPENDENCIES = (FullyQualifiedNameProvider,)

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)

        self._inside_base_model = False
        self._import_pydantic_validator = self._import_pydantic_root_validator = False
        self._already_modified = False
        self._should_add_comment = False
        self._has_comment = False
        self._args: List[cst.Arg] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        if is_a_base_model(self, node):
            self._inside_base_model = True

    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        if is_a_base_model(self, original_node):
            self._inside_base_model = False
        return updated_node

    @m.visit(IMPORT_VALIDATOR)
    def visit_import_validator(self, node: cst.CSTNode) -> None:
        self._import_pydantic_validator = True
        self._import_pydantic_root_validator = True

    def leave_Module(self, original_node: Module, updated_node: Module) -> Module:
        self._import_pydantic_validator = False
        self._import_pydantic_root_validator = False
        return updated_node

    @m.visit(VALIDATOR_DECORATOR | ROOT_VALIDATOR_DECORATOR_CALL)
    def visit_validator_decorator(self, node: cst.Decorator) -> None:
        if not self._inside_base_model:
            return
        if m.matches(node.decorator, m.Call()):
            is_root_decorator = m.matches(node, ROOT_VALIDATOR_DECORATOR_CALL)
            for arg in node.decorator.args:  # type: ignore[attr-defined]
                pre_false = m.Arg(keyword=m.Name("pre"), value=m.Name("False"))
                pre_true = m.Arg(keyword=m.Name("pre"), value=m.Name("True"))
                if m.matches(arg, m.Arg(keyword=m.Name("allow_reuse"))):
                    # allow_reuse keyword arg no longer necessary in v2
                    continue
                if m.matches(arg, pre_false):
                    if is_root_decorator:
                        self._should_add_comment = True
                    continue
                if m.matches(arg, pre_true):
                    self._args.append(arg.with_changes(keyword=cst.Name("mode"), value=cst.SimpleString('"before"')))
                elif m.matches(arg.keyword, m.Name(value=m.MatchIfTrue(lambda v: v in ("each_item", "always")))):
                    self._should_add_comment = True
                else:
                    # The `check_fields` kw-argument and all positional arguments can be just copied.
                    self._args.append(arg)
        else:
            """This only happens for `@validator`, not with `@validator()`. The parenthesis makes it not be a `Call`"""
            self._should_add_comment = True

        # Removes the trailing comma on the last argument e.g.
        # `@validator(allow_reuse=True, )` -> `@validator(allow_reuse=True)`
        if self._args:
            self._args[-1] = self._args[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT)

    @m.visit(VALIDATOR_FUNCTION)
    def visit_validator_func(self, node: cst.FunctionDef) -> None:
        if not self._inside_base_model:
            return
        for line in node.leading_lines:
            if m.matches(line, m.EmptyLine(comment=m.Comment(value=CHECK_LINK_COMMENT))):
                self._has_comment = True
        # We are only able to refactor the `@validator` when the function has only `cls` and `v` as arguments.
        if len(node.params.params) > 2:
            self._should_add_comment = True

    @m.visit(ROOT_VALIDATOR_FUNCTION)
    def visit_root_validator_func(self, node: cst.FunctionDef) -> None:
        if not self._inside_base_model:
            return
        for line in node.leading_lines:
            if m.matches(line, m.EmptyLine(comment=m.Comment(value=CHECK_LINK_COMMENT))):
                self._has_comment = True

    @m.leave(ROOT_VALIDATOR_DECORATOR_CALL)
    def leave_root_validator_decorator_call(self, original_node: cst.Decorator, updated_node: cst.Decorator) -> cst.Decorator:
        if not self._inside_base_model:
            return updated_node

        if self._has_comment:
            return updated_node

        if self._should_add_comment:
            return self._decorator_with_leading_comment(
                updated_node,
                ROOT_VALIDATOR_COMMENT,
                post_link_comments=[
                    '# @model_validator(mode="after")',
                ])

        return self._replace_validators(updated_node, "root_validator", "model_validator")

    @m.leave(ROOT_VALIDATOR_DECORATOR_NAME)
    def leave_root_validator_decorator_name(self, original_node: cst.Decorator, updated_node: cst.Decorator) -> cst.Decorator:
        if not self._inside_base_model:
            return updated_node

        if self._has_comment:
            return updated_node

        # @root_validator defaults to pre=False, which means mode="after",
        # which we can't autofix.
        self._should_add_comment = True
        return self._decorator_with_leading_comment(
            updated_node,
            ROOT_VALIDATOR_COMMENT,
            post_link_comments=[
                '# @model_validator(mode="after")',
            ])

    @m.leave(VALIDATOR_DECORATOR)
    def leave_validator_decorator(self, original_node: cst.Decorator, updated_node: cst.Decorator) -> cst.Decorator:
        if not self._inside_base_model:
            return updated_node

        if self._has_comment:
            return updated_node

        if self._should_add_comment:
            return self._decorator_with_leading_comment(updated_node, VALIDATOR_COMMENT)

        return self._replace_validators(updated_node, "validator", "field_validator")

    @m.leave(VALIDATOR_FUNCTION | ROOT_VALIDATOR_FUNCTION)
    def leave_validator_func(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        if not self._inside_base_model:
            return updated_node

        self._args = []
        self._has_comment = False
        if self._should_add_comment:
            self._should_add_comment = False
            return updated_node

        classmethod_decorator = cst.Decorator(decorator=cst.Name("classmethod"))
        return updated_node.with_changes(decorators=[*updated_node.decorators, classmethod_decorator])

    def _decorator_with_leading_comment(self, node: cst.Decorator, pre_link_comment: str, post_link_comments: list[str] | None = None) -> cst.Decorator:
        return node.with_changes(
            leading_lines=[
                *node.leading_lines,
                cst.EmptyLine(comment=cst.Comment(value=(pre_link_comment))),
                cst.EmptyLine(comment=cst.Comment(value=(CHECK_LINK_COMMENT))),
                *[cst.EmptyLine(comment=cst.Comment(value=(comment))) for comment in post_link_comments or []],
            ]
        )

    def _replace_validators(self, node: cst.Decorator, old_name: str, new_name: str) -> cst.Decorator:
        RemoveImportsVisitor.remove_unused_import(self.context, "pydantic", old_name)
        AddImportsVisitor.add_needed_import(self.context, "pydantic", new_name)
        decorator = node.decorator.with_changes(func=cst.Name(new_name), args=self._args)
        return node.with_changes(decorator=decorator)


if __name__ == "__main__":
    import textwrap

    from rich.console import Console

    console = Console()

    source = textwrap.dedent(
        """
        from pydantic import BaseModel, validator

        class Foo(BaseModel):
            bar: str

            @validator("bar", pre=True, always=True)
            def bar_validator(cls, v):
                return v
        """
    )
    console.print(source)
    console.print("=" * 80)

    mod = cst.parse_module(source)
    context = CodemodContext(filename="main.py")
    wrapper = cst.MetadataWrapper(mod)
    command = ValidatorCodemod(context=context)
    # console.print(mod)

    mod = wrapper.visit(command)
    wrapper = cst.MetadataWrapper(mod)
    command = AddImportsVisitor(context=context)  # type: ignore[assignment]
    mod = wrapper.visit(command)
    console.print(mod.code)
