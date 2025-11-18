/**
 * 前端密码加密工具
 * 使用纯 JavaScript 加密库实现 ECC 加密（不依赖 Web Crypto API）
 */

import axios from 'axios'
import { p256 } from '@noble/curves/nist' // secp256r1 / P-256
import { gcm } from '@noble/ciphers/aes'
import { hkdf } from '@noble/hashes/hkdf'
import { sha256 } from '@noble/hashes/sha2' // 从 sha2 模块导入

/**
 * 将十六进制字符串转换为 Uint8Array
 */
function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2)
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16)
  }
  return bytes
}

/**
 * 将 Uint8Array 转换为 Base64
 */
function bytesToBase64(bytes: Uint8Array): string {
  const binary = String.fromCharCode(...Array.from(bytes))
  return btoa(binary)
}

let cachedPublicKey: string | null = null

/**
 * 从后端获取公钥
 */
async function getPublicKey(): Promise<string> {
  if (cachedPublicKey) {
    return cachedPublicKey
  }

  const response = await axios.get('/api/crypto/public-key')
  const publicKey: string = response.data.public_key
  cachedPublicKey = publicKey
  return publicKey
}

/**
 * 使用 ECC 公钥加密密码（纯 JavaScript 实现，兼容所有环境）
 *
 * @param password 明文密码
 * @returns 加密后的密码（Base64 编码）
 */
export async function encryptPassword(password: string): Promise<string> {
  if (!password) {
    return password
  }

  try {
    console.log('开始加密密码...')

    // 获取后端公钥（十六进制格式，未压缩点 65 字节）
    const publicKeyHex = await getPublicKey()
    const serverPublicKeyBytes = hexToBytes(publicKeyHex)
    console.log('已获取服务器公钥，长度:', serverPublicKeyBytes.length)

    // 生成临时 ECDH 密钥对 (secp256r1 / P-256)
    const ephemeralPrivateKey = p256.utils.randomPrivateKey()
    const ephemeralPublicKey = p256.getPublicKey(ephemeralPrivateKey, false) // false = 未压缩格式 (65字节)
    console.log('已生成临时密钥对，公钥长度:', ephemeralPublicKey.length)

    // 执行 ECDH 密钥交换
    // getSharedSecret 返回未压缩点 (65字节: 0x04 + x + y)
    // Python cryptography 的 .exchange() 返回的是 x 坐标 (32字节)
    const sharedPoint = p256.getSharedSecret(ephemeralPrivateKey, serverPublicKeyBytes, false)
    const sharedSecret = sharedPoint.slice(1, 33) // 提取 x 坐标作为共享密钥
    console.log('ECDH 密钥交换完成，共享密钥长度:', sharedSecret.length)

    // 使用 HKDF 派生 AES 密钥
    const info = new TextEncoder().encode('password-encryption')
    const aesKey = hkdf(sha256, sharedSecret, undefined, info, 32)
    console.log('HKDF 密钥派生完成，AES密钥长度:', aesKey.length)

    // 使用 AES-GCM 加密密码
    const nonce = new Uint8Array(12) // 全零 nonce（与后端一致）
    const passwordBytes = new TextEncoder().encode(password)

    const aesGcm = gcm(aesKey, nonce)
    const encrypted = aesGcm.encrypt(passwordBytes)
    console.log('AES-GCM 加密完成，密文长度:', encrypted.length)

    // 组合：临时公钥 (65字节) + 密文
    const result = new Uint8Array(ephemeralPublicKey.length + encrypted.length)
    result.set(ephemeralPublicKey, 0)
    result.set(encrypted, ephemeralPublicKey.length)

    // 返回 Base64 编码
    const base64Result = bytesToBase64(result)
    console.log('加密完成，最终长度:', base64Result.length)
    return base64Result
  } catch (error) {
    console.error('密码加密失败:', error)
    throw new Error(`密码加密失败: ${error}`)
  }
}

/**
 * 清除缓存的公钥（用于重新获取）
 */
export function clearCachedPublicKey() {
  cachedPublicKey = null
}
