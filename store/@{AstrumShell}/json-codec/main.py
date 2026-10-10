"""JSON 编解码器 - 插件间 JSON 数据处理"""
import json
from typing import Any, Callable, Optional
from datetime import datetime

from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type


class JsonCodecError(Exception):
    """JSON 编解码错误"""
    pass


class JsonSerializer:
    """JSON 序列化器"""

    def __init__(self):
        self._custom_encoders: dict[type, Callable] = {}

    def register_encoder(self, type_class: type, encoder: Callable):
        """注册自定义类型编码器"""
        self._custom_encoders[type_class] = encoder

    def encode(self, data: Any, pretty: bool = False) -> str:
        """编码为 JSON 字符串"""
        def default_handler(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            for type_class, encoder in self._custom_encoders.items():
                if isinstance(obj, type_class):
                    return encoder(obj)
            raise TypeError(f"无法序列化类型: {type(obj).__name__}")

        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2, default=default_handler)
        return json.dumps(data, ensure_ascii=False, default=default_handler)

    def encode_to_bytes(self, data: Any) -> bytes:
        """编码为字节"""
        return self.encode(data).encode("utf-8")


class JsonDeserializer:
    """JSON 反序列化器"""

    def __init__(self):
        self._custom_decoders: dict[str, Callable] = {}

    def register_decoder(self, type_name: str, decoder: Callable):
        """注册自定义类型解码器"""
        self._custom_decoders[type_name] = decoder

    def decode(self, text: str) -> Any:
        """解码 JSON 字符串"""
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise JsonCodecError(f"JSON 解码失败: {e}")

    def decode_bytes(self, data: bytes) -> Any:
        """解码字节"""
        return self.decode(data.decode("utf-8"))

    def decode_file(self, path: str) -> Any:
        """解码 JSON 文件"""
        with open(path, "r", encoding="utf-8") as f:
            return self.decode(f.read())


class JsonValidator:
    """JSON 验证器"""

    def __init__(self):
        self._schemas: dict[str, dict] = {}

    def register_schema(self, name: str, schema: dict):
        """注册 schema"""
        self._schemas[name] = schema

    def validate(self, data: Any, schema_name: str) -> bool:
        """验证数据是否符合 schema"""
        if schema_name not in self._schemas:
            raise JsonCodecError(f"未知的 schema: {schema_name}")
        return self._check_schema(data, self._schemas[schema_name])

    def _check_schema(self, data: Any, schema: dict) -> bool:
        """检查 schema 匹配"""
        schema_type = schema.get("type")
        if schema_type == "object":
            if not isinstance(data, dict):
                return False
            required = schema.get("required", [])
            for field in required:
                if field not in data:
                    return False
            properties = schema.get("properties", {})
            for key, value in data.items():
                if key in properties:
                    if not self._check_schema(value, properties[key]):
                        return False
            return True
        elif schema_type == "array":
            if not isinstance(data, list):
                return False
            items_schema = schema.get("items", {})
            return all(self._check_schema(item, items_schema) for item in data)
        elif schema_type == "string":
            return isinstance(data, str)
        elif schema_type == "number":
            return isinstance(data, (int, float))
        elif schema_type == "boolean":
            return isinstance(data, bool)
        return True


class JsonCodecPlugin(Plugin):
    """JSON 编解码器插件"""

    def __init__(self):
        self.serializer = JsonSerializer()
        self.deserializer = JsonDeserializer()
        self.validator = JsonValidator()

    def init(self, deps: dict = None):
        """初始化"""
        pass

    def start(self):
        """启动"""
        Log.info("json-codec", "JSON 编解码器已启动")

    def stop(self):
        """停止"""
        pass

    def encode(self, data: Any, pretty: bool = False) -> str:
        """编码 JSON"""
        return self.serializer.encode(data, pretty)

    def decode(self, text: str) -> Any:
        """解码 JSON"""
        return self.deserializer.decode(text)

    def validate(self, data: Any, schema_name: str) -> bool:
        """验证 JSON schema"""
        return self.validator.validate(data, schema_name)

    def register_schema(self, name: str, schema: dict):
        """注册 schema"""
        self.validator.register_schema(name, schema)


# 注册类型
register_plugin_type("JsonSerializer", JsonSerializer)
register_plugin_type("JsonDeserializer", JsonDeserializer)
register_plugin_type("JsonValidator", JsonValidator)
register_plugin_type("JsonCodecError", JsonCodecError)


def New():
    return JsonCodecPlugin()
