import os
from pathlib import Path
from tempfile import TemporaryDirectory

from libcst import MetadataWrapper, parse_module
from libcst.codemod import CodemodContext, CodemodTest
from libcst.helpers import calculate_module_and_package
from libcst.metadata import FullRepoManager, FullyQualifiedNameProvider, ScopeProvider

from bump_pydantic.codemods.class_def_visitor import ClassDefVisitor


class BPTest(CodemodTest):
    def assertCodemod(self, before: str, after: str):
        with TemporaryDirectory(dir=os.getcwd()) as tmpdir:
            package = f"{tmpdir}/package"
            os.mkdir(package)
            filename = "a.py"
            filepath = f"{package}/{filename}"
            with open(filepath, "w") as f:
                f.write(before)

            input_tree = parse_module(CodemodTest.make_fixture_data(before))
            metadata_manager = FullRepoManager(package, [filepath], providers=self.TRANSFORM.METADATA_DEPENDENCIES)  # type: ignore[arg-type]
            metadata_manager.resolve_cache()

            module_and_package = calculate_module_and_package(str(package), filepath)
            context = CodemodContext(
                metadata_manager=metadata_manager,
                filename=filepath,
                full_module_name=module_and_package.name,
                full_package_name=module_and_package.package,
                scratch={},
            )

            classdef_visitor = ClassDefVisitor(context=context)
            classdef_visitor.transform_module(input_tree)

            instance = self.TRANSFORM(context=context)  # type: ignore[assignment]
            output_tree = instance.transform_module(input_tree)

            self.assertEqual(
                CodemodTest.make_fixture_data(after),
                CodemodTest.make_fixture_data(output_tree.code),
            )
