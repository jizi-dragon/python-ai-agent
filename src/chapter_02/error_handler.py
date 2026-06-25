class ErrorHandler:
    """统一错误处理器 —— 将异常分类为可重试 / 不可重试，并给出友好提示"""

    RETRYABLE_ERRORS = (
        TimeoutError,
        ConnectionError,
        ConnectionRefusedError,
        ConnectionResetError,
        OSError,
    )

    ERROR_CATEGORIES = {
        TimeoutError: {"message": "请求超时", "suggestion": "请稍后重试，或检查网络连接"},
        ConnectionError: {"message": "网络连接失败", "suggestion": "请检查网络是否正常"},
        ConnectionRefusedError: {"message": "服务拒绝连接", "suggestion": "目标服务可能未启动或端口错误"},
        ConnectionResetError: {"message": "连接被重置", "suggestion": "服务端主动断开了连接，请重试"},
        PermissionError: {"message": "权限不足", "suggestion": "请检查 API 密钥或访问权限"},
        ValueError: {"message": "参数值不合法", "suggestion": "请检查输入参数是否正确"},
        KeyError: {"message": "缺少关键数据", "suggestion": "API 返回数据格式异常"},
        TypeError: {"message": "参数类型错误", "suggestion": "请检查工具调用参数的类型"},
    }

    def handle(self, exception, context=None):
        exc_type = type(exception)

        retryable = issubclass(exc_type, self.RETRYABLE_ERRORS)

        for err_type, info in self.ERROR_CATEGORIES.items():
            if issubclass(exc_type, err_type):
                return {
                    "error": f"{info['message']}: {str(exception)}",
                    "retryable": retryable,
                    "suggestion": info["suggestion"],
                }

        return {
            "error": f"未知错误: {str(exception)}",
            "retryable": retryable,
            "suggestion": "请检查输入或联系管理员",
        }
