"""Lossless intent documents inside a JSON scalar, including IEEE float values.

MySQL's native JSON number serialization can change a floating-point value's
last bits. Pending intent hashes must compare the original document, so the SQL
JSON column stores one canonical JSON string; Python consumers still get a dict.
No SQL JSON-path reader may bypass this codec. Terminal cleanup sets SQL NULL.
"""
import json
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator


class ExactJSONDocument(TypeDecorator):
    impl = JSON(none_as_null=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError('intent_document_invalid')
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError('intent_document_encoding_invalid')
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise ValueError('intent_document_invalid')
        return decoded
