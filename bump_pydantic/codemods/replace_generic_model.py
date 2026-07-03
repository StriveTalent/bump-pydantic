from __future__ import annotations

import libcst as cst
import libcst.matchers as m
from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor
from libcst.metadata import FullyQualifiedNameProvider

from bump_pydantic.codemods.class_def_visitor import is_a_base_model

GENERIC_MODEL_ARG = m.Arg(value=m.Name("GenericModel")) | m.Arg(
    value=m.Attribute(value=m.Name("generics"), attr=m.Name("GenericModel"))
)


class ReplaceGenericModelCommand(VisitorBasedCodemodCommand):
    METADATA_DEPENDENCIES = (FullyQualifiedNameProvider,)

    @m.leave(m.ClassDef(bases=[m.ZeroOrMore(), GENERIC_MODEL_ARG, m.ZeroOrMore()]))
    def leave_generic_model(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.ClassDef:
        is_base_model = is_a_base_model(self, original_node)
        RemoveImportsVisitor.remove_unused_import(context=self.context, module="pydantic.generics", obj="GenericModel")
        RemoveImportsVisitor.remove_unused_import(context=self.context, module="pydantic", obj="generics")
        if not is_base_model:
            AddImportsVisitor.add_needed_import(context=self.context, module="pydantic", obj="BaseModel")
        def swap_base(base):
            if m.matches(base, GENERIC_MODEL_ARG):
                if is_base_model:
                    return
                return cst.Arg(value=cst.Name("BaseModel"))
            return base
        new_bases = [swap_base(base) for base in updated_node.bases if swap_base(base)]
        return updated_node.with_changes(bases=new_bases)


if __name__ == "__main__":
    import textwrap

    from rich.console import Console

    console = Console()

    source = textwrap.dedent(
        """
        from typing import Generic, TypeVar

        from pydantic.generics import GenericModel

        T = TypeVar("T")

        class Potato(GenericModel, Generic[T]):
            ...
        """
    )
    console.print(source)
    # console.print("=" * 80)

    # mod = cst.parse_module(source)
    # context = CodemodContext(filename="main.py")

    # wrapper = cst.MetadataWrapper(mod)
    # command = ReplaceGenericModelCommand(context=context)
    # mod = wrapper.visit(command)

    # wrapper = cst.MetadataWrapper(mod)
    # command = RemoveImportsVisitor(context=context)  # type: ignore[assignment]
    # mod = wrapper.visit(command)

    # wrapper = cst.MetadataWrapper(mod)
    # command = AddImportsVisitor(context=context)  # type: ignore[assignment]
    # mod = wrapper.visit(command)
    # console.print(mod.code)
