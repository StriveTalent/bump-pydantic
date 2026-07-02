from enum import Enum
from typing import List, Type

from libcst.codemod import ContextAwareTransformer
from libcst.codemod.visitors import AddImportsVisitor, RemoveImportsVisitor

from bump_pydantic.codemods.add_annotations import AddAnnotationsCommand
from bump_pydantic.codemods.add_default_none import AddDefaultNoneCommand
from bump_pydantic.codemods.con_func import ConFuncCallCommand
from bump_pydantic.codemods.custom_types import CustomTypeCodemod
from bump_pydantic.codemods.field import FieldCodemod
from bump_pydantic.codemods.replace_config import ReplaceConfigCodemod
from bump_pydantic.codemods.replace_generic_model import ReplaceGenericModelCommand
from bump_pydantic.codemods.replace_imports import ReplaceImportsCodemod
from bump_pydantic.codemods.root_model import RootModelCommand
from bump_pydantic.codemods.validator import ValidatorCodemod
from bump_pydantic.codemods.non_nullable_but_default_none import NonNullableButDefaultNoneCommand


class Rule(str, Enum):
    BP001 = "BP001"
    """Add default `None` to `Optional[T]`, `Union[T, None]` and `Any` fields"""
    BP002 = "BP002"
    """Replace `Config` class with `model_config` attribute."""
    BP003 = "BP003"
    """Replace `Field` old parameters with new ones."""
    BP004 = "BP004"
    """Replace imports that have been moved."""
    BP005 = "BP005"
    """Replace `GenericModel` with `BaseModel`."""
    BP006 = "BP006"
    """Replace `BaseModel.__root__ = T` with `RootModel[T]`."""
    BP007 = "BP007"
    """Replace `@validator` with `@field_validator`."""
    BP008 = "BP008"
    """Replace `con*` functions by `Annotated` versions."""
    BP009 = "BP009"
    """Mark Pydantic "protocol" functions in custom types with proper TODOs."""
    BP010 = "BP010"
    """Add type annotations or TODOs to fields without them."""
    BP011 = "BP011"
    """Add TODOs to non-nullable fields with a None default."""


def gather_codemods(disabled: List[Rule], enabled: List[Rule]) -> List[Type[ContextAwareTransformer]]:
    codemods: List[Type[ContextAwareTransformer]] = []

    def is_enabled(rule: Rule) -> bool:
        if disabled:
            return rule not in disabled
        if enabled:
            return rule in enabled
        return True

    if is_enabled(Rule.BP001):
        codemods.append(AddDefaultNoneCommand)

    if is_enabled(Rule.BP002):
        codemods.append(ReplaceConfigCodemod)

    # The `ConFuncCallCommand` needs to run before the `FieldCodemod`.
    if is_enabled(Rule.BP008):
        codemods.append(ConFuncCallCommand)

    if is_enabled(Rule.BP003):
        codemods.append(FieldCodemod)

    if is_enabled(Rule.BP004):
        codemods.append(ReplaceImportsCodemod)

    if is_enabled(Rule.BP005):
        codemods.append(ReplaceGenericModelCommand)

    if is_enabled(Rule.BP006):
        codemods.append(RootModelCommand)

    if is_enabled(Rule.BP007):
        codemods.append(ValidatorCodemod)

    if is_enabled(Rule.BP009):
        codemods.append(CustomTypeCodemod)

    if is_enabled(Rule.BP010):
        codemods.append(AddAnnotationsCommand)

    if is_enabled(Rule.BP011):
        codemods.append(NonNullableButDefaultNoneCommand)

    # Those codemods need to be the last ones.
    codemods.extend([RemoveImportsVisitor, AddImportsVisitor])
    return codemods
