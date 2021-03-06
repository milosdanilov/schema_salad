"""Python code generator for a given schema salad definition."""
from typing import IO, Any, Dict, List, MutableMapping, MutableSequence, Union

from pkg_resources import resource_stream
from six import iteritems, itervalues, text_type
from io import StringIO
from typing_extensions import Text  # pylint: disable=unused-import

from . import schema
from .exceptions import SchemaException
from .codegen_base import CodeGenBase, TypeDef
from .schema import shortname

# move to a regular typing import when Python 3.3-3.6 is no longer supported


class PythonCodeGen(CodeGenBase):
    """Generation of Python code for a given Schema Salad definition."""

    def __init__(self, out):
        # type: (IO[Text]) -> None
        super(PythonCodeGen, self).__init__()
        self.out = out
        self.current_class_is_abstract = False
        self.serializer = StringIO()
        self.idfield = u""

    @staticmethod
    def safe_name(name):  # type: (Text) -> Text
        avn = schema.avro_name(name)
        if avn in ("class", "in"):
            # reserved words
            avn = avn + "_"
        return avn

    def prologue(self):
        # type: () -> None

        self.out.write(
            u"""#
# This file was autogenerated using schema-salad-tool --codegen=python
# The code itself is released under the Apache 2.0 license and the help text is
# subject to the license of the original schema.
#
"""
        )

        stream = resource_stream(__name__, "python_codegen_support.py")
        self.out.write(stream.read().decode("UTF-8"))
        stream.close()
        self.out.write(u"\n\n")

        for primative in itervalues(self.prims):
            self.declare_type(primative)

    def begin_class(
        self,  # pylint: disable=too-many-arguments
        classname,  # type: Text
        extends,  # type: MutableSequence[Text]
        doc,  # type: Text
        abstract,  # type: bool
        field_names,  # type: MutableSequence[Text]
        idfield,  # type: Text
    ):  # type: (...) -> None
        classname = self.safe_name(classname)

        if extends:
            ext = ", ".join(self.safe_name(e) for e in extends)
        else:
            ext = "Savable"

        self.out.write(u"class {}({}):\n".format(classname, ext))

        if doc:
            self.out.write(u'    """\n')
            self.out.write(text_type(doc))
            self.out.write(u'\n    """\n')

        self.serializer = StringIO()

        self.current_class_is_abstract = abstract
        if self.current_class_is_abstract:
            self.out.write(u"    pass\n\n\n")
            return

        safe_inits = ["        self,"]  # type: List[Text]
        safe_inits.extend(
            [
                "        {},  # type: Any".format(self.safe_name(f))
                for f in field_names
                if f != "class"
            ]
        )
        self.out.write(
            u"    def __init__(\n"
            + u"\n".join(safe_inits)
            + u"\n        extension_fields=None,  "
            + u"# type: Optional[Dict[Text, Any]]"
            + u"\n        loadingOptions=None  # type: Optional[LoadingOptions]"
            + u"\n    ):  # type: (...) -> None\n"
            + u"""
        if extension_fields:
            self.extension_fields = extension_fields
        else:
            self.extension_fields = yaml.comments.CommentedMap()
        if loadingOptions:
            self.loadingOptions = loadingOptions
        else:
            self.loadingOptions = LoadingOptions()
"""
        )
        field_inits = u""
        for name in field_names:
            if name == "class":
                field_inits += u"""        self.class_ = "{}"
""".format(
                    classname
                )
            else:
                field_inits += u"""        self.{0} = {0}
""".format(
                    self.safe_name(name)
                )
        self.out.write(
            field_inits
            + u"""
    @classmethod
    def fromDoc(cls, doc, baseuri, loadingOptions, docRoot=None):
        # type: (Any, Text, LoadingOptions, Optional[Text]) -> {}

        _doc = copy.copy(doc)
        if hasattr(doc, 'lc'):
            _doc.lc.data = doc.lc.data
            _doc.lc.filename = doc.lc.filename
        _errors__ = []
""".format(
                classname
            )
        )

        self.idfield = idfield

        self.serializer.write(
            u"""
    def save(self, top=False, base_url="", relative_uris=True):
        # type: (bool, Text, bool) -> Dict[Text, Any]
        r = yaml.comments.CommentedMap()  # type: Dict[Text, Any]
        for ef in self.extension_fields:
            r[prefix_url(ef, self.loadingOptions.vocab)] = self.extension_fields[ef]
"""
        )

        if "class" in field_names:
            self.out.write(
                u"""
        if _doc.get('class') != '{class_}':
            raise ValidationException("Not a {class_}")

""".format(
                    class_=classname
                )
            )

            self.serializer.write(
                u"""
        r['class'] = '{class_}'
""".format(
                    class_=classname
                )
            )

    def end_class(self, classname, field_names):
        # type: (Text, List[Text]) -> None

        if self.current_class_is_abstract:
            return

        self.out.write(
            u"""
        extension_fields = yaml.comments.CommentedMap()
        for k in _doc.keys():
            if k not in cls.attrs:
                if ":" in k:
                    ex = expand_url(k,
                                    u"",
                                    loadingOptions,
                                    scoped_id=False,
                                    vocab_term=False)
                    extension_fields[ex] = _doc[k]
                else:
                    _errors__.append(
                        ValidationException(
                            "invalid field `%s`, expected one of: {attrstr}" % (k),
                            SourceLine(_doc, k, str)
                        )
                    )
                    break

        if _errors__:
            raise ValidationException(\"Trying '{class_}'\", None, _errors__)
""".format(
                attrstr=", ".join(["`{}`".format(f) for f in field_names]),
                class_=self.safe_name(classname),
            )
        )

        self.serializer.write(
            u"""
        if top and self.loadingOptions.namespaces:
            r["$namespaces"] = self.loadingOptions.namespaces

"""
        )

        self.serializer.write(u"        return r\n\n")

        self.serializer.write(
            u"    attrs = frozenset({attrs})\n".format(attrs=field_names)
        )

        safe_inits = [
            self.safe_name(f) for f in field_names if f != "class"
        ]  # type: List[Text]

        safe_inits.extend(
            ["extension_fields=extension_fields", "loadingOptions=loadingOptions"]
        )

        self.out.write(
            u"""        loadingOptions = copy.deepcopy(loadingOptions)
        loadingOptions.original_doc = _doc
"""
        )
        self.out.write(u"        return cls(" + ", ".join(safe_inits) + ")\n")

        self.out.write(text_type(self.serializer.getvalue()))

        self.out.write(u"\n\n")

    prims = {
        u"http://www.w3.org/2001/XMLSchema#string": TypeDef(
            "strtype", "_PrimitiveLoader((str, text_type))"
        ),
        u"http://www.w3.org/2001/XMLSchema#int": TypeDef(
            "inttype", "_PrimitiveLoader(int)"
        ),
        u"http://www.w3.org/2001/XMLSchema#long": TypeDef(
            "inttype", "_PrimitiveLoader(int)"
        ),
        u"http://www.w3.org/2001/XMLSchema#float": TypeDef(
            "floattype", "_PrimitiveLoader(float)"
        ),
        u"http://www.w3.org/2001/XMLSchema#double": TypeDef(
            "floattype", "_PrimitiveLoader(float)"
        ),
        u"http://www.w3.org/2001/XMLSchema#boolean": TypeDef(
            "booltype", "_PrimitiveLoader(bool)"
        ),
        u"https://w3id.org/cwl/salad#null": TypeDef(
            "None_type", "_PrimitiveLoader(type(None))"
        ),
        u"https://w3id.org/cwl/salad#Any": TypeDef("Any_type", "_AnyLoader()"),
    }

    def type_loader(self, type_declaration):
        # type: (Union[List[Any], Dict[Text, Any], Text]) -> TypeDef

        if isinstance(type_declaration, MutableSequence):
            sub = [self.type_loader(i) for i in type_declaration]
            return self.declare_type(
                TypeDef(
                    "union_of_{}".format("_or_".join(s.name for s in sub)),
                    "_UnionLoader(({},))".format(", ".join(s.name for s in sub)),
                )
            )
        if isinstance(type_declaration, MutableMapping):
            if type_declaration["type"] in (
                "array",
                "https://w3id.org/cwl/salad#array",
            ):
                i = self.type_loader(type_declaration["items"])
                return self.declare_type(
                    TypeDef(
                        "array_of_{}".format(i.name), "_ArrayLoader({})".format(i.name)
                    )
                )
            if type_declaration["type"] in ("enum", "https://w3id.org/cwl/salad#enum"):
                for sym in type_declaration["symbols"]:
                    self.add_vocab(shortname(sym), sym)
                return self.declare_type(
                    TypeDef(
                        self.safe_name(type_declaration["name"]) + "Loader",
                        '_EnumLoader(("{}",))'.format(
                            '", "'.join(
                                self.safe_name(sym)
                                for sym in type_declaration["symbols"]
                            )
                        ),
                    )
                )
            if type_declaration["type"] in (
                "record",
                "https://w3id.org/cwl/salad#record",
            ):
                return self.declare_type(
                    TypeDef(
                        self.safe_name(type_declaration["name"]) + "Loader",
                        "_RecordLoader({})".format(
                            self.safe_name(type_declaration["name"])
                        ),
                    )
                )
            raise SchemaException("wft {}".format(type_declaration["type"]))
        if type_declaration in self.prims:
            return self.prims[type_declaration]
        return self.collected_types[self.safe_name(type_declaration) + "Loader"]

    def declare_id_field(self, name, fieldtype, doc, optional):
        # type: (Text, TypeDef, Text, bool) -> None

        if self.current_class_is_abstract:
            return

        self.declare_field(name, fieldtype, doc, True)

        if optional:
            opt = """{safename} = "_:" + str(_uuid__.uuid4())""".format(
                safename=self.safe_name(name)
            )
        else:
            opt = """raise ValidationException("Missing {fieldname}")""".format(
                fieldname=shortname(name)
            )

        self.out.write(
            u"""
        if {safename} is None:
            if docRoot is not None:
                {safename} = docRoot
            else:
                {opt}
        baseuri = {safename}
""".format(
                safename=self.safe_name(name), fieldname=shortname(name), opt=opt
            )
        )

    def declare_field(self, name, fieldtype, doc, optional):
        # type: (Text, TypeDef, Text, bool) -> None

        if self.current_class_is_abstract:
            return

        if shortname(name) == "class":
            return

        if optional:
            self.out.write(
                u"        if '{fieldname}' in _doc:\n".format(fieldname=shortname(name))
            )
            spc = "    "
        else:
            spc = ""
        self.out.write(
            u"""{spc}        try:
{spc}            {safename} = load_field(_doc.get(
{spc}                '{fieldname}'), {fieldtype}, baseuri, loadingOptions)
{spc}        except ValidationException as e:
{spc}            _errors__.append(
{spc}                ValidationException(
{spc}                    \"the `{fieldname}` field is not valid because:\",
{spc}                    SourceLine(_doc, '{fieldname}', str),
{spc}                    [e]
{spc}                )
{spc}            )
""".format(
                safename=self.safe_name(name),
                fieldname=shortname(name),
                fieldtype=fieldtype.name,
                spc=spc,
            )
        )
        if optional:
            self.out.write(
                u"""        else:
            {safename} = None
""".format(
                    safename=self.safe_name(name)
                )
            )

        if name == self.idfield or not self.idfield:
            baseurl = "base_url"
        else:
            baseurl = "self.{}".format(self.safe_name(self.idfield))

        if fieldtype.is_uri:
            self.serializer.write(
                u"""
        if self.{safename} is not None:
            u = save_relative_uri(
                self.{safename},
                {baseurl},
                {scoped_id},
                {ref_scope},
                relative_uris)
            if u:
                r['{fieldname}'] = u
""".format(
                    safename=self.safe_name(name),
                    fieldname=shortname(name).strip(),
                    baseurl=baseurl,
                    scoped_id=fieldtype.scoped_id,
                    ref_scope=fieldtype.ref_scope,
                )
            )
        else:
            self.serializer.write(
                u"""
        if self.{safename} is not None:
            r['{fieldname}'] = save(
                self.{safename},
                top=False,
                base_url={baseurl},
                relative_uris=relative_uris)
""".format(
                    safename=self.safe_name(name),
                    fieldname=shortname(name),
                    baseurl=baseurl,
                )
            )

    def uri_loader(self, inner, scoped_id, vocab_term, ref_scope):
        # type: (TypeDef, bool, bool, Union[int, None]) -> TypeDef
        return self.declare_type(
            TypeDef(
                "uri_{}_{}_{}_{}".format(inner.name, scoped_id, vocab_term, ref_scope),
                "_URILoader({}, {}, {}, {})".format(
                    inner.name, scoped_id, vocab_term, ref_scope
                ),
                is_uri=True,
                scoped_id=scoped_id,
                ref_scope=ref_scope,
            )
        )

    def idmap_loader(self, field, inner, map_subject, map_predicate):
        # type: (Text, TypeDef, Text, Union[Text, None]) -> TypeDef
        return self.declare_type(
            TypeDef(
                "idmap_{}_{}".format(self.safe_name(field), inner.name),
                "_IdMapLoader({}, '{}', '{}')".format(
                    inner.name, map_subject, map_predicate
                ),
            )
        )

    def typedsl_loader(self, inner, ref_scope):
        # type: (TypeDef, Union[int, None]) -> TypeDef
        return self.declare_type(
            TypeDef(
                "typedsl_{}_{}".format(inner.name, ref_scope),
                "_TypeDSLLoader({}, {})".format(inner.name, ref_scope),
            )
        )

    def epilogue(self, root_loader):
        # type: (TypeDef) -> None
        self.out.write(u"_vocab = {\n")
        for k in sorted(self.vocab.keys()):
            self.out.write(u'    "{}": "{}",\n'.format(k, self.vocab[k]))
        self.out.write(u"}\n")

        self.out.write(u"_rvocab = {\n")
        for k in sorted(self.vocab.keys()):
            self.out.write(u'    "{}": "{}",\n'.format(self.vocab[k], k))
        self.out.write(u"}\n\n")

        for _, collected_type in iteritems(self.collected_types):
            self.out.write(
                u"{} = {}\n".format(collected_type.name, collected_type.init)
            )
        self.out.write(u"\n")

        self.out.write(
            u"""
def load_document(doc, baseuri=None, loadingOptions=None):
    # type: (Any, Optional[Text], Optional[LoadingOptions]) -> Any
    if baseuri is None:
        baseuri = file_uri(os.getcwd()) + "/"
    if loadingOptions is None:
        loadingOptions = LoadingOptions()
    return _document_load(%(name)s, doc, baseuri, loadingOptions)


def load_document_by_string(string, uri, loadingOptions=None):
    # type: (Any, Text, Optional[LoadingOptions]) -> Any
    result = yaml.round_trip_load(string, preserve_quotes=True)
    add_lc_filename(result, uri)

    if loadingOptions is None:
        loadingOptions = LoadingOptions(fileuri=uri)
    loadingOptions.idx[uri] = result

    return _document_load(%(name)s, result, uri, loadingOptions)
"""
            % dict(name=root_loader.name)
        )
