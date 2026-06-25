import json


class ParameterValidator:
    """工具参数验证器 —— 基于 JSON Schema 风格的工具参数校验"""

    TYPE_MAP = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    def __init__(self, tool_def):
        self.tool_def = tool_def
        self.param_schema = tool_def.get("parameters", {})

    def validate(self, params):
        errors = []
        required = self.param_schema.get("required", [])
        properties = self.param_schema.get("properties", {})

        for field in required:
            if field not in params:
                errors.append(f"缺少必填参数: '{field}'")

        for key, value in params.items():
            if key not in properties:
                continue

            prop_def = properties[key]
            expected_type = prop_def.get("type")

            if expected_type and not self._check_type(value, expected_type):
                errors.append(
                    f"参数 '{key}' 类型错误: 期望 {expected_type}, 实际 {type(value).__name__}"
                )

            if "enum" in prop_def and value not in prop_def["enum"]:
                errors.append(
                    f"参数 '{key}' 值 '{value}' 不在允许范围内: {prop_def['enum']}"
                )

            if "minLength" in prop_def and isinstance(value, str):
                if len(value) < prop_def["minLength"]:
                    errors.append(
                        f"参数 '{key}' 长度不足: 最少 {prop_def['minLength']}, 实际 {len(value)}"
                    )

        return len(errors) == 0, errors

    def _check_type(self, value, expected_type):
        python_type = self.TYPE_MAP.get(expected_type)
        if python_type is None:
            return True
        return isinstance(value, python_type)
