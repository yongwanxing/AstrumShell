"""报告格式化器"""


class ReportFormatter:
    """报告格式化器"""

    def __init__(self, format_type: str = "console"):
        self.format_type = format_type

    def format(self, result: dict) -> str:
        """格式化报告"""
        if self.format_type == "console":
            return self._format_console(result)
        elif self.format_type == "json":
            return self._format_json(result)
        return str(result)

    def _format_console(self, result: dict) -> str:
        """控制台格式"""
        lines = []
        lines.append("=" * 60)
        lines.append("代码审查报告")
        lines.append("=" * 60)
        lines.append(f"扫描文件: {result['files_scanned']}")
        lines.append(f"发现问题: {result['total_issues']}")
        lines.append(f"扫描时间: {result['scan_time']}s")
        lines.append("")

        # 按严重程度分类
        critical = [i for i in result['issues'] if i['severity'] == 'critical']
        warning = [i for i in result['issues'] if i['severity'] == 'warning']
        info = [i for i in result['issues'] if i['severity'] == 'info']

        lines.append(f"🔴 严重: {len(critical)}")
        lines.append(f"🟡 警告: {len(warning)}")
        lines.append(f"🔵 提示: {len(info)}")
        lines.append("")

        if critical:
            lines.append("严重问题:")
            for issue in critical:
                lines.append(f"  - {issue['file']}:{issue['line']} - {issue['message']}")
            lines.append("")

        if warning:
            lines.append("警告:")
            for issue in warning[:10]:  # 最多显示10个
                lines.append(f"  - {issue['file']}:{issue['line']} - {issue['message']}")
            if len(warning) > 10:
                lines.append(f"  ... 还有 {len(warning) - 10} 个警告")
            lines.append("")

        lines.append("=" * 60)
        return '\n'.join(lines)

    def _format_json(self, result: dict) -> str:
        """JSON 格式"""
        import json
        return json.dumps(result, indent=2, ensure_ascii=False)
