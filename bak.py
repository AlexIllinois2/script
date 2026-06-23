#!/usr/bin/env python3

"""
通用目录/文件 备份/恢复工具
- 备份：打包指定的目录或文件到 tar.gz
- 恢复：从备份包解压到对应位置
"""

import argparse
import inspect
import os
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

HOME = Path.home()
SCRIPT_DIR = Path(__file__).parent

# Windows 终端 ANSI 颜色支持
if sys.platform == "win32":
    os.system("color")

# ============ 配置 ============
# 默认要备份的路径列表（可被命令行参数覆盖）
# 使用 ~ 表示 home 目录
DEFAULT_PATHS: List[str] = [
    "~/.local/bin/nvim",
    "~/.local/share/fonts/SauceCodePro-NerdFont",
    "~/.local/share/nvim",
    "~/.config/nvim",
]

# ============ 颜色输出 ============
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def info(msg): print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")
def success(msg): print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")
def warn(msg): print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")
def error(msg): print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")
def step(msg): print(f"\n{Colors.CYAN}▶{Colors.NC} {msg}")
def title(msg): print(f"\n{Colors.MAGENTA}═══ {msg} ═══{Colors.NC}")

# ============ 核心函数 ============

def expand_path(path: str) -> Path:
    """展开路径中的 ~ 和环境变量"""
    return Path(os.path.expanduser(os.path.expandvars(path)))

def get_backup_filename(prefix: str = "backup") -> str:
    """生成带时间戳的备份文件名"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}.tar.gz"

def human_size(size_bytes: int) -> str:
    """人类可读的文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def get_path_size(path: Path) -> int:
    """获取文件或目录的大小"""
    if path.is_file():
        return path.stat().st_size
    elif path.is_dir():
        return sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())
    return 0

def get_path_count(path: Path) -> int:
    """获取目录下的文件数量"""
    if path.is_file():
        return 1
    elif path.is_dir():
        return sum(1 for _ in path.glob('**/*') if _.is_file())
    return 0

# ============ 安全解压 ============

def safe_extractall(tar: tarfile.TarFile, path: Path):
    """安全解压，兼容旧版 Python 并防止 Zip Slip 攻击"""
    path_resolved = Path(path).resolve()
    if 'filter' in inspect.signature(tarfile.TarFile.extractall).parameters:
        tar.extractall(path=path, filter='data')
    else:
        # 手动校验路径安全，防止 Zip Slip
        for member in tar.getmembers():
            target = (path_resolved / member.name).resolve()
            if not (str(target).startswith(str(path_resolved) + os.sep) or target == path_resolved):
                raise Exception(
                    f"安全错误: 路径 '{member.name}' 试图逃逸到 {target}"
                )
        tar.extractall(path=path)

# ============ 备份功能 ============

def backup(paths: List[str] = None, output_dir: str = ".",
           prefix: str = "backup", verbose: bool = True) -> Optional[Path]:
    """创建完整备份"""
    if paths is None:
        paths = DEFAULT_PATHS

    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    backup_filename = get_backup_filename(prefix)
    backup_path = output_path / backup_filename

    title("开始备份")

    if verbose:
        info(f"备份目录: {output_path}")
        info(f"备份文件: {backup_filename}")
        info(f"备份项数: {len(paths)}")
        print()

    # 检查要备份的文件
    items_to_backup = []
    total_size = 0
    total_files = 0

    for path_str in paths:
        src = expand_path(path_str)
        if src.exists():
            size = get_path_size(src)
            count = get_path_count(src)
            total_size += size
            total_files += count
            items_to_backup.append((src, path_str))
            if verbose:
                print(f"  ✅ {path_str} ({human_size(size)}, {count} 个文件)")
        else:
            if verbose:
                print(f"  ⚠️  {path_str} (不存在，跳过)")

    if not items_to_backup:
        error("没有找到任何要备份的文件！")
        return None

    print()
    info(f"共 {len(items_to_backup)} 项, {total_files} 个文件, 总大小: {human_size(total_size)}")

    # 创建 tar.gz 备份
    step("正在打包压缩...")

    try:
        with tarfile.open(backup_path, "w:gz") as tar:
            for src, path_str in items_to_backup:
                # 相对路径：优先用相对于 HOME 的路径，不在 HOME 下的用绝对路径根
                try:
                    rel_path = src.relative_to(HOME)
                except ValueError:
                    rel_path = Path(str(src).lstrip('/'))
                tar.add(src, arcname=str(rel_path))

        actual_size = backup_path.stat().st_size

        print()
        success(f"✅ 备份完成!")
        print(f"   文件: {backup_path}")
        print(f"   大小: {human_size(actual_size)}")

        return backup_path

    except Exception as e:
        error(f"备份失败: {e}")
        if backup_path.exists():
            backup_path.unlink()
        return None

# ============ 恢复功能 ============

def get_backup_info(backup_path: Path) -> dict:
    """获取备份包信息"""
    info_obj = {
        "filename": backup_path.name,
        "size": 0,
        "created": None,
        "items": []
    }

    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            members = tar.getmembers()
            info_obj["items"] = [m.name for m in members if not m.isdir()]
            # 使用备份文件自身的修改时间，而非第一个成员的 mtime
            info_obj["created"] = datetime.fromtimestamp(backup_path.stat().st_mtime)
            total_size = sum(m.size for m in members)
            info_obj["size"] = total_size
    except Exception as e:
        warn(f"无法读取备份包信息: {e}")

    return info_obj


def list_backup(backup_path: Path):
    """列出备份包内容"""
    title(f"查看备份包: {backup_path.name}")

    info_obj = get_backup_info(backup_path)
    print(f"  大小: {human_size(info_obj['size'])}")
    print(f"  文件数: {len(info_obj['items'])}")
    if info_obj['created']:
        print(f"  创建时间: {info_obj['created'].strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n包含内容:")
    # 按目录分组显示
    dirs = {}
    for item in info_obj['items']:
        parts = item.split('/')
        if len(parts) >= 2:
            key = '/'.join(parts[:2]) if len(parts) > 1 else parts[0]
            if key not in dirs:
                dirs[key] = []
            dirs[key].append(item)

    for dir_name, files in sorted(dirs.items()):
        print(f"\n  📁 {dir_name}/")
        for f in files[:10]:
            print(f"    📄 {f}")
        if len(files) > 10:
            print(f"    ... 共 {len(files)} 项")

    return info_obj


def check_conflicts(backup_path: Path) -> List[Path]:
    """检查恢复时可能冲突的文件"""
    conflicts = []

    with tarfile.open(backup_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            target_path = HOME / member.name
            if target_path.exists():
                conflicts.append(target_path)

    return conflicts


def restore(backup_path: str, force: bool = False, backup_first: bool = False,
            dry_run: bool = False, verbose: bool = True) -> bool:
    """从备份包恢复"""
    backup_file = Path(backup_path).expanduser().resolve()

    if not backup_file.exists():
        error(f"备份文件不存在: {backup_file}")
        return False

    if backup_file.suffix not in ['.gz', '.tgz']:
        error(f"不是有效的 tar.gz 文件: {backup_file}")
        return False

    title(f"恢复: {backup_file.name}")

    # 显示备份信息
    info_obj = get_backup_info(backup_file)
    print(f"  大小: {human_size(info_obj['size'])}")
    print(f"  文件数: {len(info_obj['items'])}")
    if info_obj['created']:
        print(f"  创建时间: {info_obj['created'].strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查冲突
    step("检查冲突...")
    conflicts = check_conflicts(backup_file)

    if conflicts:
        print(f"  发现 {len(conflicts)} 个冲突文件/目录:")
        for c in conflicts[:10]:
            print(f"    ⚠️  {c}")
        if len(conflicts) > 10:
            print(f"    ... 共 {len(conflicts)} 项")
        print()

        if not force and not dry_run:
            warn("使用 --force 强制覆盖, 或 --backup 先备份")
            return False

        if backup_first and not dry_run:
            info("创建冲突文件备份...")
            backup_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_conflict_dir = HOME / f".conflict-backup-{backup_timestamp}"
            backup_conflict_dir.mkdir(exist_ok=True)

            for conflict in conflicts:
                if conflict.exists():
                    # 保持相对路径结构
                    rel_path = conflict.relative_to(HOME)
                    dst = backup_conflict_dir / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if conflict.is_dir():
                        shutil.copytree(conflict, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(conflict, dst)
            info(f"冲突文件已备份到: {backup_conflict_dir}")
            print()

    if dry_run:
        step("DRY RUN - 以下是将要恢复的文件 (前20项)")
        for item in info_obj['items'][:20]:
            target = HOME / item
            print(f"  📄 {target}")
        if len(info_obj['items']) > 20:
            print(f"  ... 共 {len(info_obj['items'])} 项")
        print()
        info("⚠️ 这只是预览，没有实际执行")
        return True

    # 执行恢复
    step("正在恢复文件...")

    try:
        with tarfile.open(backup_file, "r:gz") as tar:
            # 先删除要覆盖的文件
            if force:
                for member in tar.getmembers():
                    if member.isdir():
                        continue
                    target = HOME / member.name
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()

            # 安全解压（兼容旧版 Python + 防 Zip Slip）
            safe_extractall(tar, HOME)

        success("✅ 恢复完成!")

        # 显示恢复的文件
        step("恢复的文件:")
        for item in info_obj['items'][:10]:
            target = HOME / item
            status = "✅" if target.exists() else "❌"
            print(f"  {status} {item}")
        if len(info_obj['items']) > 10:
            print(f"  ... 共 {len(info_obj['items'])} 项")

        return True

    except Exception as e:
        error(f"恢复失败: {e}")
        return False


# ============ 命令行界面 ============

def print_help():
    help_text = """
╔══════════════════════════════════════════════════════════════════╗
║              通用文件/目录 备份/恢复工具                        ║
╚══════════════════════════════════════════════════════════════════╝

用法:
    python bak.py [COMMAND] [OPTIONS] [PATHS...]

命令:
    backup (b)       创建备份 (默认)
    restore (r)      从备份包恢复
    list (l)         查看备份包内容

选项:
    -o, --output DIR   备份输出目录 (默认: 当前目录)
    -p, --prefix NAME  备份文件名前缀 (默认: backup)
    -f, --force        强制覆盖已存在的文件
    -b, --backup       恢复前先备份冲突文件
    -d, --dry-run      预览操作，不实际执行
    -v, --verbose      显示详细信息
    -h, --help         显示此帮助

参数:
    PATHS...           备份路径 (backup) 或备份包路径 (restore/list)

示例:
    # 备份 (使用默认配置)
    python bak.py

    # 备份指定路径
    python bak.py backup ~/.config/nvim ~/.local/share/nvim

    # 备份到指定目录
    python bak.py -o ~/backups -p myconfig ~/.config ~/.local

    # 恢复
    python bak.py restore backup-20260623-143052.tar.gz

    # 强制恢复
    python bak.py restore -f backup-20260623-143052.tar.gz

    # 恢复前备份冲突文件
    python bak.py restore -b backup-20260623-143052.tar.gz

    # 预览恢复
    python bak.py restore -d backup-20260623-143052.tar.gz

    # 查看备份包内容
    python bak.py list backup-20260623-143052.tar.gz
"""
    print(help_text)


def main():
    parser = argparse.ArgumentParser(
        description="通用文件/目录 备份/恢复工具",
        add_help=False
    )

    # 命令
    parser.add_argument("command", nargs="?",
                        choices=["backup", "b", "restore", "r", "list", "l"],
                        help="操作命令")

    # paths 同时承担两种角色：
    #   backup 命令 → 要备份的路径列表
    #   restore/list 命令 → 第一个元素为备份包路径
    parser.add_argument("paths", nargs="*",
                        help="备份路径 (backup) 或备份包路径 (restore/list)")
    parser.add_argument("-o", "--output", default=".",
                        help="备份输出目录")
    parser.add_argument("-p", "--prefix", default="backup",
                        help="备份文件名前缀")
    parser.add_argument("-f", "--force", action="store_true",
                        help="强制覆盖")
    parser.add_argument("-b", "--backup", action="store_true",
                        help="恢复前备份冲突文件")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="预览模式")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示详细信息")
    parser.add_argument("-h", "--help", action="store_true",
                        help="显示帮助")

    args = parser.parse_args()

    if args.help:
        print_help()
        sys.exit(0)

    # 默认命令
    if not args.command:
        args.command = "backup"

    # 执行命令
    if args.command in ["backup", "b"]:
        paths = args.paths if args.paths else DEFAULT_PATHS
        backup(paths, args.output, args.prefix, args.verbose)

    elif args.command in ["restore", "r"]:
        if not args.paths:
            error("请指定备份包路径")
            print("  python bak.py restore <backup.tar.gz>")
            sys.exit(1)
        restore(args.paths[0], args.force, args.backup, args.dry_run, args.verbose)

    elif args.command in ["list", "l"]:
        if not args.paths:
            error("请指定备份包路径")
            print("  python bak.py list <backup.tar.gz>")
            sys.exit(1)
        list_backup(Path(args.paths[0]).expanduser())


if __name__ == "__main__":
    main()
