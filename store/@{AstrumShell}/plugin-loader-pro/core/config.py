"""Pro 配置模型"""


class CircuitBreakerConfig:
    """熔断器配置"""
    def __init__(self, config: dict = None):
        config = config or {}
        self.failure_threshold = config.get("failure_threshold", 3)
        self.recovery_timeout = config.get("recovery_timeout", 60)
        self.half_open_requests = config.get("half_open_requests", 1)


class RetryConfig:
    """重试配置"""
    def __init__(self, config: dict = None):
        config = config or {}
        self.max_retries = config.get("max_retries", 3)
        self.backoff_factor = config.get("backoff_factor", 2)
        self.initial_delay = config.get("initial_delay", 1)


class HealthCheckConfig:
    """健康检查配置"""
    def __init__(self, config: dict = None):
        config = config or {}
        self.interval = config.get("interval", 30)
        self.timeout = config.get("timeout", 5)
        self.max_failures = config.get("max_failures", 5)


class AutoRecoveryConfig:
    """自动恢复配置"""
    def __init__(self, config: dict = None):
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.max_attempts = config.get("max_attempts", 3)
        self.delay = config.get("delay", 10)


class IsolationConfig:
    """隔离配置"""
    def __init__(self, config: dict = None):
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.timeout_per_plugin = config.get("timeout_per_plugin", 30)


class ProConfig:
    """Pro 总配置"""
    def __init__(self, config: dict = None):
        config = config or {}
        self.circuit_breaker = CircuitBreakerConfig(config.get("circuit_breaker"))
        self.retry = RetryConfig(config.get("retry"))
        self.health_check = HealthCheckConfig(config.get("health_check"))
        self.auto_recovery = AutoRecoveryConfig(config.get("auto_recovery"))
        self.isolation = IsolationConfig(config.get("isolation"))
