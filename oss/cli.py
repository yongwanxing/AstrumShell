"""CLI 入口"""
import click
import signal
import os
import sys

# Windows 控制台兼容：控制台保留系统编码（中文正常显示），只把无法编码的字符降级为替换符；
# 输出被重定向/管道时统一用 UTF-8，避免日志文件乱码。日志里的 emoji（⚠/✅）不会再让服务崩溃。
for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream.isatty():
            _stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        else:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

from oss import __version__
from oss.logger.logger import Logger
from oss.plugin.manager import PluginManager
from oss.config import init_config, get_config
from pathlib import Path


# 深度隐藏的成就系统导入
try:
    from oss.core.achievements import init_achievements, get_validator, _cmd_echo, _cmd_help_internal, _cmd_list_all, _cmd_stats, _cmd_reset_progress, _cmd_export, _cmd_import, _cmd_verify, _cmd_debug, _cmd_info
    _ACHIEVEMENTS_ENABLED = True
except ImportError:
    _ACHIEVEMENTS_ENABLED = False


@click.group()
@click.option('--config', '-c', type=str, help='配置文件路径')
@click.pass_context
def cli(ctx, config):
    """AstrumShell - 一切皆为插件"""
    # 初始化配置
    ctx.ensure_object(dict)
    ctx.obj['config'] = init_config(config)
    
    # 初始化成就系统（如果启用）
    if _ACHIEVEMENTS_ENABLED:
        try:
            init_achievements()
        except Exception:
            pass  # 静默失败，不影响主功能


@cli.command()
@click.option('--host', type=str, default=None, help='监听地址')
@click.option('--port', type=int, default=None, help='HTTP API 端口')
@click.option('--tcp-port', type=int, default=None, help='HTTP TCP 端口')
@click.pass_context
def serve(ctx, host, port, tcp_port):
    """启动 AstrumShell"""
    config = ctx.obj.get('config', get_config())
    
    # 命令行参数覆盖配置
    if host:
        config.set('HOST', host)
    if port:
        config.set('HTTP_API_PORT', port)
    if tcp_port:
        config.set('HTTP_TCP_PORT', tcp_port)
    
    log = Logger()
    log.info(f"AstrumShell {__version__} 启动")
    log.info(f"监听地址：{config.host}:{config.http_api_port}")
    log.info(f"数据目录：{config.data_dir.absolute()}")
    log.info(f"插件仓库：{config.store_dir.absolute()}")

    plugin_mgr = PluginManager()
    plugin_mgr.load()
    plugin_mgr.start()

    log.info("就绪")

    # 写入真实 PID，供 start.bat / start.sh 判断实例是否已在运行（退出时清理）
    pid_file = Path(__file__).resolve().parent.parent / ".pid"
    try:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        log.warn(f"写入 PID 文件失败：{e}")

    stopped = {"done": False}

    def shutdown(sig, frame):
        # 幂等：Ctrl+C 与信号可能同时触发，避免重复 stop
        if stopped["done"]:
            return
        stopped["done"] = True
        log.info("停止中...")
        try:
            plugin_mgr.stop()
        except Exception as e:  # 停插件失败也必须能正常退出
            log.warn(f"停止插件时出错：{e}")
        log.info("已停止")
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if hasattr(signal, "SIGBREAK"):  # Windows：Ctrl+Break 也能优雅退出
        signal.signal(signal.SIGBREAK, shutdown)

    import time
    try:
        if hasattr(signal, "pause"):
            # POSIX：阻塞等待信号
            signal.pause()
        else:
            # Windows 没有 signal.pause：轮询等待，同时响应 Ctrl+C
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown(None, None)
    finally:
        # 无论正常退出还是被信号中断，都要清理 PID 文件
        try:
            if pid_file.exists():
                pid_file.unlink()
        except Exception:
            pass


@cli.command()
def version():
    """显示版本"""
    click.echo(f"AstrumShell {__version__}")


@cli.command()
@click.pass_context
def info(ctx):
    """显示系统信息"""
    import random
    
    config = ctx.obj.get('config', get_config())
    click.echo(f"AstrumShell {__version__}")
    click.echo(f"配置文件：{config._config_file or '无'}")
    click.echo(f"HTTP API 端口：{config.http_api_port}")
    click.echo(f"HTTP TCP 端口：{config.http_tcp_port}")
    click.echo(f"主机地址：{config.host}")
    click.echo(f"数据目录：{config.data_dir.absolute()}")
    click.echo(f"插件仓库：{config.store_dir.absolute()}")
    click.echo(f"日志级别：{config.log_level}")
    click.echo(f"权限检查：{'启用' if config.permission_check else '禁用'}")
    
    # 小提示：有些功能需要特殊方式访问 (4675747572654f53)
    # 随机显示隐藏提示（约 10% 概率）
    click.echo("")
    if random.random() < 0.1:  # 10% 概率显示彩蛋提示
        click.echo("✨ 奇怪的提示：试试在命令前加两个感叹号会怎样？比如 !!help")
    elif random.random() < 0.05:  # 额外 5% 概率显示另一种提示
        click.echo("🤔 听说有人用 !! 开头的命令发现了不得了的东西...")


def main():
    # 检查隐藏命令前缀
    if len(sys.argv) > 1 and sys.argv[1].startswith("!!"):
        if _ACHIEVEMENTS_ENABLED:
            cmd = sys.argv[1][2:]  # 去掉 !! 前缀
            args = sys.argv[2:]
            
            # 映射隐藏命令
            cmd_map = {
                "echo": _cmd_echo,
                "help": _cmd_help_internal,
                "list": _cmd_list_all,
                "stats": _cmd_stats,
                "reset": _cmd_reset_progress,
                "export": _cmd_export,
                "import": _cmd_import,
                "verify": _cmd_verify,
                "debug": _cmd_debug,
                "info": _cmd_info,
            }
            
            if cmd in cmd_map:
                validator = get_validator()
                validator.use_hidden_command(cmd)
                cmd_map[cmd](args)
                return
            else:
                print(f"未知命令：!!{cmd}")
                return
        else:
            print("成就系统未启用")
            return
    
    cli()


if __name__ == "__main__":
    main()
