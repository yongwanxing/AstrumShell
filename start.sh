#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  AstrumShell 智能启动脚本 - Linux
#  自动检测环境 / 安装依赖 / 进度显示 / 守护重启
# ═══════════════════════════════════════════════════════════

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[1;34m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m'

# ── 工具函数 ──
info()  { echo -e "${CYAN}[信息]${NC} $1"; }
ok()    { echo -e "${GREEN}[成功]${NC} $1"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $1"; }
err()   { echo -e "${RED}[错误]${NC} $1"; }
step()  { echo -e "\n${BOLD}${BLUE}▶ $1${NC}"; }

# 进度条
progress_bar() {
    local current=$1
    local total=$2
    local label=$3
    local pct=$((current * 100 / total))
    local filled=$((pct / 2))
    local empty=$((50 - filled))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    echo -ne "\r  ${GREEN}[${bar}]${NC} ${WHITE}${pct}%${NC} - ${label}"
}

# ── Logo ──
echo -e "${BOLD}${CYAN}"
echo " ███████╗ ██████╗  ██████╗  ██████╗ ██████╗  ██████╗ "
echo " ██╔════╝ ██╔══██╗ ██╔══██╗ ██╔══██╗ ██╔══██╗██╔════╝ "
echo " █████╗   ██████╔╝ ██████╔╝ ██████╔╝ ██║  ██║██║  ███╗"
echo " ██╔══╝   ██╔══██╗ ██╔══██╗ ██╔══██╗ ██║  ██║██║   ██║"
echo " ██║      ██║  ██║ ██║  ██║ ██║  ██║ ██████╔╝╚██████╔╝"
echo " ╚═╝      ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ "
echo -e "${NC}"
echo -e "${WHITE}         开发者通用工具套组 · 一切皆为插件${NC}"
echo -e "${WHITE}         https://gitee.com/yongwanxing/astrum-shell${NC}"
echo ""

# ── 守护模式 ──
DAEMON=false
if [[ "$1" == "--daemon" || "$1" == "-d" ]]; then
    DAEMON=true
fi

# ═══════════════════════════════════════════════════════════
#  1. 检测操作系统
# ═══════════════════════════════════════════════════════════
step "环境检测"

PKG_MANAGER=""
OS_NAME=""

if [[ -f /etc/os-release ]]; then
    OS_NAME=$(. /etc/os-release && echo "$PRETTY_NAME")
    info "操作系统: $OS_NAME"
fi

if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    ok "包管理器: apt (Debian/Ubuntu)"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
    ok "包管理器: yum (CentOS/RHEL)"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    ok "包管理器: dnf (Fedora)"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    ok "包管理器: pacman (Arch Linux)"
elif command -v apk &>/dev/null; then
    PKG_MANAGER="apk"
    ok "包管理器: apk (Alpine)"
else
    warn "未检测到已知包管理器，将尝试使用系统自带工具"
fi

install_pkg() {
    local pkg=$1
    case $PKG_MANAGER in
        apt)   sudo apt-get install -y -qq "$pkg" 2>/dev/null ;;
        yum)   sudo yum install -y -q "$pkg" 2>/dev/null ;;
        dnf)   sudo dnf install -y -q "$pkg" 2>/dev/null ;;
        pacman) sudo pacman -S --noconfirm "$pkg" 2>/dev/null ;;
        apk)   sudo apk add --quiet "$pkg" 2>/dev/null ;;
        *)     warn "无法自动安装 $pkg" ; return 1 ;;
    esac
}

update_pkg_cache() {
    case $PKG_MANAGER in
        apt)   sudo apt-get update -qq 2>/dev/null ;;
        yum)   sudo yum makecache -q 2>/dev/null ;;
        dnf)   sudo dnf makecache -q 2>/dev/null ;;
        pacman) sudo pacman -Sy --quiet 2>/dev/null ;;
        apk)   sudo apk update --quiet 2>/dev/null ;;
    esac
}

TOTAL_STEPS=6
CURRENT_STEP=0

# ═══════════════════════════════════════════════════════════
#  2. 安装系统依赖
# ═══════════════════════════════════════════════════════════
step "安装系统依赖"

# 系统命令依赖和PHP扩展分开处理
CMD_DEPENDENCIES=("git" "curl" "wget" "php" "python3")
PHP_EXTENSIONS=("php-cli" "php-mbstring" "php-xml" "php-zip")
PYTHON_PKGS=("pip" "venv")

DEPENDENCIES=(${CMD_DEPENDENCIES[@]} ${PHP_EXTENSIONS[@]} "python3-pip" "python3-venv")
DEP_TOTAL=${#DEPENDENCIES[@]}
DEP_INSTALLED=0

for dep in "${DEPENDENCIES[@]}"; do
    DEP_INSTALLED=$((DEP_INSTALLED + 1))
    progress_bar $DEP_INSTALLED $DEP_TOTAL "检测 $dep"

    # PHP扩展包不通过command检测，跳过
    if [[ "$dep" == php-* ]]; then
        continue
    fi
    # python3-venv也不通过command检测
    if [[ "$dep" == "python3-venv" || "$dep" == "python3-pip" ]]; then
        continue
    fi

    if command -v "$dep" &>/dev/null; then
        continue
    fi

    # 尝试安装
    if ! install_pkg "$dep" 2>/dev/null; then
        # 更新缓存后重试
        update_pkg_cache 2>/dev/null
        install_pkg "$dep" 2>/dev/null || true
    fi

    if command -v "$dep" &>/dev/null; then
        continue
    fi
done

echo -e "\n"

# 验证关键依赖
if command -v php &>/dev/null; then
    ok "PHP: $(php --version 2>&1 | head -n 1)"
else
    warn "PHP 未安装，WebUI 可能无法正常工作"
fi

if command -v python3 &>/dev/null; then
    ok "Python: $(python3 --version 2>&1)"
else
    err "Python3 未安装，无法继续"
    exit 1
fi

# ═══════════════════════════════════════════════════════════
#  3. Python 虚拟环境
# ═══════════════════════════════════════════════════════════
step "配置 Python 环境"

PYTHON_CMD="python3"
VENV_DIR=".venv"

if [[ ! -d "$VENV_DIR" ]]; then
    info "创建虚拟环境..."
    $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null || {
        warn "venv 模块缺失，尝试安装..."
        case $PKG_MANAGER in
            apt)   install_pkg "python3-venv" ;;
            yum)   install_pkg "python3-virtualenv" ;;
            dnf)   install_pkg "python3-virtualenv" ;;
            pacman) ;;
            apk)   install_pkg "py3-virtualenv" ;;
        esac
        $PYTHON_CMD -m venv "$VENV_DIR" 2>/dev/null || {
            err "无法创建虚拟环境"
            exit 1
        }
    }
    ok "虚拟环境已创建"
else
    ok "虚拟环境已存在"
fi

source "$VENV_DIR/bin/activate"
PIP_CMD="$VENV_DIR/bin/pip"

# ═══════════════════════════════════════════════════════════
#  检测虚拟环境依赖完整性
# ═══════════════════════════════════════════════════════════
info "检测虚拟环境依赖完整性..."

VENV_INCOMPLETE=false
MISSING_VENV_DEPS=()

for pkg in "${CORE_DEPS[@]}"; do
    import_name="${PKG_IMPORT_MAP[$pkg]}"
    if ! $PYTHON_CMD -c "import $import_name" 2>/dev/null; then
        VENV_INCOMPLETE=true
        MISSING_VENV_DEPS+=("$pkg")
    fi
done

# 同时检测 requirements.txt 中的依赖
if [[ -f "requirements.txt" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        # 跳过空行和注释
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # 提取包名（去除版本号）
        pkg_name=$(echo "$line" | sed -E 's/([a-zA-Z0-9_-]+).*/\1/')
        [[ -z "$pkg_name" ]] && continue
        # 尝试导入（将连字符替换为下划线）
        import_name="${pkg_name//-/_}"
        if ! $PYTHON_CMD -c "import $import_name" 2>/dev/null; then
            # 不在核心依赖列表中的才添加
            if [[ ! " ${CORE_DEPS[@]} " =~ " ${pkg_name} " ]]; then
                VENV_INCOMPLETE=true
                MISSING_VENV_DEPS+=("$pkg_name")
            fi
        fi
    done < "requirements.txt"
fi

if $VENV_INCOMPLETE; then
    warn "虚拟环境依赖不完整，缺失: ${MISSING_VENV_DEPS[*]}"
    info "正在安装缺失的依赖..."
    for pkg in "${MISSING_VENV_DEPS[@]}"; do
        $PIP_CMD install "$pkg" -q 2>/dev/null || \
        $PIP_CMD install "$pkg" --break-system-packages -q 2>/dev/null || \
        warn "无法安装 $pkg"
    done
else
    ok "虚拟环境依赖完整"
fi

# ═══════════════════════════════════════════════════════════
#  4. 安装 Python 依赖
# ═══════════════════════════════════════════════════════════
step "安装 Python 依赖"

# 包名到导入名的映射
declare -A PKG_IMPORT_MAP=(
    ["click"]="click"
    ["pyyaml"]="yaml"
    ["websockets"]="websockets"
    ["psutil"]="psutil"
    ["cryptography"]="cryptography"
)

CORE_DEPS=("click" "pyyaml" "websockets" "psutil" "cryptography")
DEP_COUNT=${#CORE_DEPS[@]}
DEP_CURRENT=0

for pkg in "${CORE_DEPS[@]}"; do
    DEP_CURRENT=$((DEP_CURRENT + 1))
    progress_bar $DEP_CURRENT $DEP_COUNT "安装 $pkg"

    # 使用正确的导入名检测
    import_name="${PKG_IMPORT_MAP[$pkg]}"
    $PYTHON_CMD -c "import $import_name" 2>/dev/null && continue

    $PIP_CMD install "$pkg" -q 2>/dev/null || \
    $PIP_CMD install "$pkg" --break-system-packages -q 2>/dev/null || true
done

echo -e "\n"

# 安装项目依赖
if [[ -f "pyproject.toml" ]]; then
    info "安装项目配置依赖..."
    $PIP_CMD install -e . -q 2>/dev/null || true
fi

if [[ -f "requirements.txt" ]]; then
    info "安装 requirements.txt..."
    $PIP_CMD install -r requirements.txt -q 2>/dev/null || true
fi

ok "Python 依赖安装完成"

# ═══════════════════════════════════════════════════════════
#  5. 创建数据目录
# ═══════════════════════════════════════════════════════════
step "初始化数据目录"

DATA_DIRS=("data" "data/html-render" "data/web-toolkit" "data/plugin-storage" "data/DCIM" "data/signature-verifier/keys/private" "data/signature-verifier/keys/public" "logs")
DIR_COUNT=${#DATA_DIRS[@]}
DIR_CURRENT=0

for dir in "${DATA_DIRS[@]}"; do
    DIR_CURRENT=$((DIR_CURRENT + 1))
    progress_bar $DIR_CURRENT $DIR_COUNT "创建 $dir"
    mkdir -p "$dir"
done

echo -e "\n"
ok "数据目录已就绪"

# ═══════════════════════════════════════════════════════════
#  6. 检查 MySQL (可选)
# ═══════════════════════════════════════════════════════════
step "检查数据库 (可选)"

if command -v mysql &>/dev/null; then
    ok "MySQL: $(mysql --version 2>&1)"
    if pgrep mysqld > /dev/null 2>&1 || pgrep mariadbd > /dev/null 2>&1; then
        ok "MySQL 服务运行中"
        mysql -u root -e "CREATE DATABASE IF NOT EXISTS astrumshell CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null && \
            ok "数据库 astrumshell 已就绪" || \
            warn "无法创建数据库，请检查权限"
    else
        warn "MySQL 服务未运行"
        info "启动命令: sudo systemctl start mysql (或 mariadb)"
    fi
else
    info "MySQL 未安装 (可选功能)"
    info "安装: sudo apt install mysql-server (Debian/Ubuntu)"
    info "      sudo yum install mysql-server (CentOS/RHEL)"
fi

# ═══════════════════════════════════════════════════════════
#  7. 启动服务
# ═══════════════════════════════════════════════════════════
step "启动 AstrumShell"

if $DAEMON; then
    LOG_FILE="logs/astrumshell.log"
    # 统一使用服务自身写入的 .pid（oss/cli.py，真实进程号），两种启动方式互不冲突
    PID_FILE=".pid"

    if [[ -f "$PID_FILE" ]]; then
        OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
        if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
            warn "已有进程运行 (PID: $OLD_PID)"
            info "停止: kill $OLD_PID 或 bash start.sh stop"
            exit 0
        fi
    fi

    nohup $PYTHON_CMD -m oss.cli serve > "$LOG_FILE" 2>&1 &
    NEW_PID=$!
    # 服务启动后会自己写入 .pid；这里兜底写一次，保证启动瞬间也有记录
    echo "$NEW_PID" > "$PID_FILE"
    ok "守护进程已启动 (PID: $NEW_PID)"
    info "日志文件: $LOG_FILE"
    sleep 2
    curl -s http://localhost:8080/health &>/dev/null && ok "服务就绪: http://localhost:8080" || warn "服务启动中，请稍候..."
    exit 0
fi

# 前台模式 + 崩溃自动重启
echo -e "${WHITE}运行中... 按 Ctrl+C 停止${NC}"
echo ""

RESTART_DELAY=3
RESTART_COUNT=0

while true; do
    $PYTHON_CMD -m oss.cli serve
    EXIT_CODE=$?

    if [[ $EXIT_CODE -eq 0 ]]; then
        ok "服务正常退出"
        break
    fi

    RESTART_COUNT=$((RESTART_COUNT + 1))
    warn "服务异常退出 (code: $EXIT_CODE)，${RESTART_DELAY}s 后重启... (第 $RESTART_COUNT 次)"
    sleep $RESTART_DELAY

    # 指数退避
    if [[ $RESTART_DELAY -lt 30 ]]; then
        RESTART_DELAY=$((RESTART_DELAY * 2))
    fi
done

deactivate 2>/dev/null || true
