# -*- coding: utf-8 -*-
# character_knowledge_validate 单元测试：doc_id / 三层 key

from backend.utils.character_knowledge_validate import (
    build_content,
    build_doc_id,
    hash_key,
    is_admin_manageable_doc_id,
    parse_doc_id,
    parse_key_from_content,
    validate_key,
)


class TestBuildDocId:
    def test_role_level(self):
        key = "外貌-体态-细节"
        doc_id = build_doc_id("character_global", key)
        assert doc_id == f"character_global_{hash_key(key)}_0"

    def test_user_level(self):
        key = "喜好-饮食-偏好"
        doc_id = build_doc_id("user", key, 42)
        assert doc_id == f"user_{hash_key(key)}_42"

    def test_same_key_same_hash(self):
        k = "兴趣-偏好-饮品"
        assert build_doc_id("character_global", k) == build_doc_id("character_global", k)


class TestParseDocId:
    def test_parse_role_level(self):
        doc_id = build_doc_id("character_global", "外貌-体态-细节")
        assert parse_doc_id(doc_id) == ("character_global", "0")

    def test_parse_user_level(self):
        doc_id = build_doc_id("user", "作息-惯性-熬夜", 5)
        assert parse_doc_id(doc_id) == ("user", "5")

    def test_invalid_legacy_colon_format(self):
        assert parse_doc_id("character_global:外貌-体态:") is None

    def test_admin_manageable(self):
        doc_id = build_doc_id("character_knowledge", "咖啡-萃取-时长")
        assert is_admin_manageable_doc_id(doc_id) is True

    def test_user_doc_not_admin_manageable(self):
        doc_id = build_doc_id("user", "作息-惯性-熬夜", 1)
        assert is_admin_manageable_doc_id(doc_id) is False


class TestValidateKey:
    def test_three_layers_ok(self):
        assert validate_key("外貌-体态-细节") is None

    def test_two_layers_rejected(self):
        err = validate_key("外貌-体态")
        assert err is not None
        assert "3 段" in err

    def test_no_hyphen_rejected(self):
        assert validate_key("真实姓名") is not None

    def test_four_layers_rejected(self):
        assert validate_key("a-b-c-d") is not None


class TestContentParse:
    def test_build_and_parse(self):
        content = build_content("外貌-体态-细节", "说话时肩膀略绷紧")
        assert content == "外貌-体态-细节：说话时肩膀略绷紧"
        assert parse_key_from_content(content) == "外貌-体态-细节"
