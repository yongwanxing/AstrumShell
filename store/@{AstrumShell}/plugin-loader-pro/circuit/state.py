"""熔断器状态枚举"""


class CircuitState:
    """熔断器状态"""
    CLOSED = "closed"          # 正常状态
    OPEN = "open"              # 熔断状态
    HALF_OPEN = "half_open"    # 半开状态
