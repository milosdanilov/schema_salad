import os
from typing import Any, Dict, cast, List, Text

from schema_salad.schema import load_schema
from schema_salad import codegen
from .test_java_codegen import cwl_file_uri, metaschema_file_uri, t_directory


def test_cwl_gen():
    with t_directory() as test_dir:
        src_target = os.path.join(test_dir, "src.py")
        python_codegen(cwl_file_uri, src_target)
        assert os.path.exists(src_target)
        with open(src_target, "r") as f:
            assert "class Workflow(Process)" in f.read()


def test_meta_schema_gen():
    with t_directory() as test_dir:
        src_target = os.path.join(test_dir, "src.py")
        python_codegen(metaschema_file_uri, src_target)
        assert os.path.exists(src_target)
        with open(src_target, "r") as f:
            assert "class RecordSchema(Savable):" in f.read()


def python_codegen(file_uri, target):
    document_loader, avsc_names, schema_metadata, metaschema_loader = load_schema(
        file_uri
    )
    schema_raw_doc = metaschema_loader.fetch(file_uri)
    schema_doc, schema_metadata = metaschema_loader.resolve_all(
        schema_raw_doc, file_uri
    )
    codegen.codegen(
        "python",
        cast(List[Dict[Text, Any]], schema_doc),
        schema_metadata,
        document_loader,
        target=target,
    )
