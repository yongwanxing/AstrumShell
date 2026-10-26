"""
插件签名验证服务
- 验证官方插件的完整性与来源真实性
- 支持多签名者（Upstream 独特性签名）
- RSA-SHA256 非对称加密方案
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from oss.plugin.types import Plugin
from oss.plugin.content_hash import plugin_tree_hash
from oss.config import get_config


# ========== 内置信任锚（Upstream 公钥） ==========
# 这是 Upstream 的官方公钥，用于验证所有官方签名的插件
UPSTREAM_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEApSx8pgGqWyGCddDJiuLY
0O3fHw2XSqjURK6sv05TmDY+3ejSMMBB+H54mcfPKvUBIGGwqGhs8iMzuGB473BG
2IoTWR8UnphnpuA1NA4Wz1dgLHeHHVZpn9uMMrIisWxe5Rql0fVzTD5pr/8cNQNf
D53ImYOKk+dlIsV83A4FkIERdqn9+4PcvoljNYjiVSd4vuzYZrBXxUqR4ve+yiNm
EHf+YApFvdO/2OwQoRGLkfroaKIezJRlmAlbs/MS3GjMUm3vV5QF7A//2MBbRyLt
9IizDySqfRZBLbz+kM/M20mcIfvXcLDkdToeEeYVvtV7HVgleeqGbmfXXKubb110
8vRzKqkCvCS35KhdVXpc/1BBLsSvuEjufdp1Oyf2AkmCx/Qf6Xtaa+AunRHGFcYk
gT2IxiYZi9fsl+SwTckR1QtmYAWynZCu7KESC24zaiS5x3CLcdoM3dMNEkJXo/r7
+QlkM9i7kbEBVMOQ1f0r+P9JqZZIGDZuGBnvUHzmYyraeWREvTbTEZdkFmAYTFVj
fC2LuUTxvBbgtW8FNhNK9dnNZwUl5FK7SCPg8XPEZHNduW3vQzhOEcJrTeWADFaP
mXrxvBCggEFpTuW8yMgY37j5EYLqebtH8hYklsPbNRlRbOJhhyc5D/fNbgX3Sa2w
7XKCF4268G3nweHQFO4BTyECAwEAAQ==
-----END PUBLIC KEY-----"""

# AstrumShell 官方公钥
ASTRUMSHELL_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA23qHKv5K3+UZReGsdFPu
Ccip833j6r0SBIYAmPAl/FmCZXSxw8yezjx4p2ZPhGQ5Huaxf9LbZsr4jT97vizY
AnpBWHMJY6IZZxkKwlIdMdnal4r1FdSQk1M2Os9+X+qV4fjlVUqwS8SS9QZTQTbB
rzJiTbZj2ObiexO3ZWLTiV39D6wuQoV1nQZL6W3qzrL4RCB8GwNoQUAs1MPvN2C4
IT+MqYbDbKM0MPzakqO1Rd9fin4DN7g2gggH57N/eHe5qDQv+AQ2Zg/GG3/eBkMl
O2tSv8hQmhdMMaLKPEtyBdqvFnL9CQLvciBgIxbTjfDYD2c54tKDsbgIS3xaJpLf
c+7oFfxRAu7pwwTzjoK1P2L5P3gPSo/QGnVsLnJ8XFP9RmHZyF0DBjy2OjeETDFL
VUKotRQrWW/RXBq3r+DsYqEQHtBg7B6XIb69LWPZ4TdsB8b+mpjateWznqsVCadI
WbnIQgj8iRP5ifEfvwVTAGLf3PdvHNTI4tGX/CXaywkL1nXQjVHzQbp3fB36cCtx
HA+LQnWetj1PlBXWK/DYfq+8cW79tlFeT911vUs6LJ62iHgpqFXEhbFWqjc/I/C0
qbSqKaS1p+p5RjB9qHCTrCZTAyVYJ2VgXwiLNai293RIIzi7CVFe/BO7ZT88vo7x
H+0pZej1iwWJmt8nqbBM44MCAwEAAQ==
-----END PUBLIC KEY-----"""


class SignatureError(Exception):
    """签名验证失败异常"""
    pass


class SignatureVerifier:
    """签名验证器"""

    def __init__(self, key_dir: str = None):
        config = get_config()
        self.key_dir = Path(key_dir or str(config.get("SIGNATURE_KEYS_DIR", "./data/signature-verifier/keys")))
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self.public_keys: Dict[str, bytes] = {}
        self._load_builtin_keys()

    def _load_builtin_keys(self):
        """加载内置信任锚"""
        # Upstream 官方公钥
        self.public_keys["Upstream"] = UPSTREAM_PUBLIC_KEY_PEM.encode()
        # AstrumShell 官方公钥
        self.public_keys["AstrumShell"] = ASTRUMSHELL_PUBLIC_KEY_PEM.encode()
        # 加载额外密钥
        self._load_extra_keys()

    def _load_extra_keys(self):
        """从密钥目录加载额外的公钥"""
        pub_dir = self.key_dir / "public"
        if not pub_dir.exists():
            return
        for key_file in pub_dir.glob("*.pem"):
            author_name = key_file.stem
            self.public_keys[author_name] = key_file.read_bytes()

    def _compute_plugin_hash(self, plugin_dir: Path) -> str:
        """
        计算插件目录的内容哈希

        统一调用 oss.plugin.content_hash.plugin_tree_hash：文本文件按 LF 归一化、
        相对路径按 ``/`` 分隔，保证 Windows / Linux / macOS 结果一致。
        """
        return plugin_tree_hash(plugin_dir)

    def verify_plugin(self, plugin_dir: Path, author: str = "Upstream") -> Tuple[bool, str]:
        """
        验证插件签名
        返回: (是否有效, 详细信息)
        """
        signature_file = plugin_dir / "SIGNATURE"
        
        if not signature_file.exists():
            return False, f"插件缺少签名文件: {plugin_dir}"
        
        # 加载签名（显式 UTF-8：避免 Windows 默认用 GBK 读取导致解析失败）
        try:
            sig_data = json.loads(signature_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return False, f"签名文件格式错误: {e}"
        
        # 检查必需字段
        required_fields = ["signature", "signer", "algorithm", "timestamp"]
        for field in required_fields:
            if field not in sig_data:
                return False, f"签名文件缺少必需字段: {field}"
        
        signer = sig_data["signer"]
        signature = base64.b64decode(sig_data["signature"])
        
        # 获取对应公钥
        if signer not in self.public_keys:
            return False, f"未知签名者: {signer}"
        
        try:
            public_key = serialization.load_pem_public_key(
                self.public_keys[signer],
                backend=default_backend()
            )
        except Exception as e:
            return False, f"公钥加载失败: {e}"
        
        # 计算当前哈希
        current_hash = self._compute_plugin_hash(plugin_dir)
        
        # 验证签名
        try:
            # 签名的是 "作者:哈希值" 的组合
            signed_data = f"{author}:{current_hash}".encode("utf-8")
            public_key.verify(
                signature,
                signed_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True, f"签名验证通过 (签名者: {signer})"
        except InvalidSignature:
            return False, f"签名不匹配！插件可能已被篡改 (签名者: {signer})"
        except Exception as e:
            return False, f"签名验证异常: {e}"

    def is_official_plugin(self, plugin_dir: Path) -> bool:
        """检查是否是官方插件（Upstream 或 AstrumShell 签名）"""
        return self.verify_plugin(plugin_dir, "Upstream")[0] or \
               self.verify_plugin(plugin_dir, "AstrumShell")[0]


class SignatureSigner:
    """签名生成器（仅用于密钥持有者）"""

    def __init__(self, private_key_path: Optional[str] = None):
        self.private_key = None
        if private_key_path:
            self.load_private_key(private_key_path)

    def load_private_key(self, key_path: str):
        """加载私钥"""
        with open(key_path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )

    def load_private_key_from_pem(self, pem_data: str):
        """从 PEM 字符串加载私钥"""
        self.private_key = serialization.load_pem_private_key(
            pem_data.encode(),
            password=None,
            backend=default_backend()
        )

    def sign_plugin(self, plugin_dir: Path, signer_name: str, author: str = "Upstream") -> str:
        """
        为插件生成签名
        返回: 签名的文件路径
        """
        if not self.private_key:
            raise ValueError("未加载私钥")
        
        # 计算插件哈希（与验签端使用同一实现，保证跨平台一致）
        plugin_hash = plugin_tree_hash(plugin_dir)
        
        # 签名
        import time
        signed_data = f"{author}:{plugin_hash}".encode("utf-8")
        signature = self.private_key.sign(
            signed_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # 写入签名文件
        sig_data = {
            "signature": base64.b64encode(signature).decode(),
            "signer": signer_name,
            "algorithm": "RSA-SHA256",
            "timestamp": time.time(),
            "plugin_hash": plugin_hash,
            "author": author
        }
        
        signature_file = plugin_dir / "SIGNATURE"
        # 固定用 LF 换行 + UTF-8 写入：避免 Windows 下写出 CRLF / GBK 导致
        # 同一签名在不同平台产生字节差异（git 每次都会显示该文件被修改）
        signature_file.write_text(json.dumps(sig_data, indent=2), encoding="utf-8", newline="\n")
        
        return str(signature_file)


class SignatureVerifierPlugin(Plugin):
    """签名验证插件入口"""

    def __init__(self):
        self.storage = None
        self.verifier = None
        self.signer = None
        self.enforce_official = True

    def set_plugin_storage(self, instance):
        self.storage = instance

    def init(self, deps: dict = None):
        # 从配置获取密钥目录
        config = get_config()
        key_dir = str(config.get("SIGNATURE_KEYS_DIR", "./data/signature-verifier/keys"))
        
        # 初始化验证器
        self.verifier = SignatureVerifier(key_dir=key_dir)
        
        # 初始化签名器（如果有私钥）
        private_key_path = Path(key_dir) / "private" / "upstream_private.pem"
        if Path(private_key_path).exists():
            self.signer = SignatureSigner(private_key_path)
        
        # 加载配置
        if self.storage:
            storage = self.storage.get_storage("signature-verifier")
            self.enforce_official = storage.get("enforce_official", True)

    def start(self):
        pass

    def stop(self):
        pass

    # ========== 对外 API ==========

    def verify(self, plugin_dir: Path, author: str = "Upstream") -> Tuple[bool, str]:
        """验证插件签名"""
        return self.verifier.verify_plugin(plugin_dir, author)

    def is_official(self, plugin_dir: Path) -> bool:
        """检查是否是官方插件"""
        return self.verifier.is_official_plugin(plugin_dir)

    def sign(self, plugin_dir: Path, signer_name: str = "Upstream", author: str = "Upstream") -> str:
        """为插件签名（需要私钥）"""
        if not self.signer:
            raise SignatureError("未加载私钥，无法签名")
        return self.signer.sign_plugin(plugin_dir, signer_name, author)

    def generate_keypair(self, author: str, key_dir: str = None):
        """生成新的密钥对"""
        if key_dir is None:
            key_dir = self.key_dir
        
        key_path = Path(key_dir)
        key_path.mkdir(parents=True, exist_ok=True)
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # 保存私钥
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        priv_file = key_path / "private" / f"{author.lower()}_private.pem"
        priv_file.parent.mkdir(parents=True, exist_ok=True)
        priv_file.write_bytes(private_pem)
        
        # 保存公钥
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        pub_file = key_path / "public" / f"{author}.pem"
        pub_file.parent.mkdir(parents=True, exist_ok=True)
        pub_file.write_bytes(public_pem)
        
        return str(priv_file), str(pub_file)


def New():
    return SignatureVerifierPlugin()
