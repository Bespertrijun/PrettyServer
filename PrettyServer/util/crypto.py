"""
密码加密/解密工具
使用 ECC (椭圆曲线加密) 进行密码保护
"""
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from util.log import log


class CryptoManager:
    """密码加密管理器 - 单例模式，使用 ECC"""

    _instance = None
    _private_key = None
    _public_key = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self._ensure_keys()
            self.initialized = True

    def _ensure_keys(self):
        """确保 ECC 密钥对存在，如果不存在则创建"""
        # 密钥文件路径：优先使用 /data (Docker)，否则使用项目根目录 (开发环境)
        if Path('/data').exists():
            key_dir = Path('/data')
        else:
            # 开发环境：使用项目根目录
            current_file = Path(__file__).resolve()
            key_dir = current_file.parent.parent.parent

        log.info(f"==== 检查 ECC 密钥对 ====")
        log.info(f"密钥存储路径: {key_dir}")

        # 确保目录存在
        key_dir.mkdir(parents=True, exist_ok=True)

        private_key_file = key_dir / '.private_key.pem'
        public_key_file = key_dir / '.public_key.pem'

        if private_key_file.exists() and public_key_file.exists():
            # 读取现有密钥对
            try:
                with open(private_key_file, 'rb') as f:
                    self._private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                with open(public_key_file, 'rb') as f:
                    self._public_key = serialization.load_pem_public_key(
                        f.read(),
                        backend=default_backend()
                    )
                log.info(f"✓ 已加载现有 ECC 密钥对")
                log.info(f"  私钥: {private_key_file}")
                log.info(f"  公钥: {public_key_file}")
            except Exception as e:
                log.error(f"✗ 密钥加载失败: {e}")
                log.info("重新生成密钥对...")
                private_key_file.unlink(missing_ok=True)
                public_key_file.unlink(missing_ok=True)
                self._ensure_keys()
                return
        else:
            # 生成新的 ECC 密钥对（使用 secp256r1 曲线）
            log.info("未找到现有密钥，生成新的 ECC 密钥对...")
            self._private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
            self._public_key = self._private_key.public_key()

            try:
                # 保存私钥
                with open(private_key_file, 'wb') as f:
                    f.write(self._private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ))

                # 保存公钥
                with open(public_key_file, 'wb') as f:
                    f.write(self._public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    ))

                log.info(f"✓ 已生成并保存新的 ECC 密钥对")
                log.info(f"  私钥: {private_key_file}")
                log.info(f"  公钥: {public_key_file}")
            except Exception as e:
                log.error(f"✗ 密钥保存失败: {e}")
                raise

        log.info("==== ECC 密钥检查完成 ====")

    def encrypt_password(self, password: str) -> str:
        """
        加密密码（使用 ECDH + AES-GCM）

        Args:
            password: 明文密码

        Returns:
            加密后的密码（base64编码）
        """
        if not password:
            return password

        try:
            # 生成临时密钥对用于 ECDH
            ephemeral_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
            shared_key = ephemeral_key.exchange(ec.ECDH(), self._public_key)

            # 使用 HKDF 派生 AES 密钥
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'password-encryption',
                backend=default_backend()
            ).derive(shared_key)

            # 使用 AES-GCM 加密
            aesgcm = AESGCM(derived_key)
            nonce = b'\x00' * 12  # 固定 nonce（简化版，生产环境应使用随机 nonce）
            ciphertext = aesgcm.encrypt(nonce, password.encode('utf-8'), None)

            # 组合：临时公钥 + 密文
            ephemeral_public_bytes = ephemeral_key.public_key().public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            result = ephemeral_public_bytes + ciphertext

            return base64.b64encode(result).decode('utf-8')
        except Exception as e:
            log.error(f"密码加密失败: {e}")
            raise

    def decrypt_password(self, encrypted_password: str) -> str:
        """
        解密密码

        Args:
            encrypted_password: 加密的密码

        Returns:
            明文密码
        """
        if not encrypted_password:
            return encrypted_password

        try:
            data = base64.b64decode(encrypted_password.encode('utf-8'))

            # 分离临时公钥和密文（secp256r1 未压缩点是 65 字节）
            ephemeral_public_bytes = data[:65]
            ciphertext = data[65:]

            # 恢复临时公钥
            ephemeral_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(),
                ephemeral_public_bytes
            )

            # 使用私钥进行 ECDH
            shared_key = self._private_key.exchange(ec.ECDH(), ephemeral_public_key)

            # 派生 AES 密钥
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'password-encryption',
                backend=default_backend()
            ).derive(shared_key)

            # 解密
            aesgcm = AESGCM(derived_key)
            nonce = b'\x00' * 12
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext.decode('utf-8')
        except Exception as e:
            # 如果解密失败，可能是明文密码（兼容旧配置）
            log.warning(f"密码解密失败，作为明文处理: {str(e)[:50]}")
            return encrypted_password

    def is_encrypted(self, password: str) -> bool:
        """
        判断密码是否已加密

        Args:
            password: 待判断的密码

        Returns:
            True 如果已加密，False 如果是明文
        """
        if not password:
            return False

        try:
            # 尝试 base64 解码
            data = base64.b64decode(password.encode('utf-8'))
            # ECC 加密的数据应该至少有 65 字节（公钥）+ 密文
            return len(data) >= 65
        except:
            return False

    def get_public_key_pem(self) -> str:
        """
        获取 PEM 格式的公钥（用于前端加密）

        Returns:
            PEM 格式的公钥字符串
        """
        public_key_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return public_key_pem.decode('utf-8')

    def get_public_key_hex(self) -> str:
        """
        获取十六进制格式的公钥（用于前端加密，更紧凑）

        Returns:
            十六进制格式的公钥字符串
        """
        public_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        return public_key_bytes.hex()


# 全局单例
crypto_manager = CryptoManager()
