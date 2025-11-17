/**
 * 前端密码加密工具
 * 使用 Web Crypto API 实现 ECC 加密
 */

import axios from 'axios'

/**
 * 将十六进制字符串转换为 Uint8Array
 */
function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2)
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substr(i, 2), 16)
  }
  return bytes
}

/**
 * 将 Uint8Array 转换为十六进制字符串
 */
function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
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
 * 使用 ECC 公钥加密密码
 *
 * @param password 明文密码
 * @returns 加密后的密码（Base64 编码）
 */
export async function encryptPassword(password: string): Promise<string> {
  if (!password) {
    return password
  }

  try {
    // 获取后端公钥（十六进制格式）
    const publicKeyHex = await getPublicKey()
    const publicKeyBytes = hexToBytes(publicKeyHex)

    // 生成临时 ECDH 密钥对
    const ephemeralKeyPair = await crypto.subtle.generateKey(
      {
        name: 'ECDH',
        namedCurve: 'P-256' // secp256r1
      },
      true,
      ['deriveBits']
    )

    // 导入后端公钥
    const serverPublicKey = await crypto.subtle.importKey(
      'raw',
      publicKeyBytes as BufferSource,
      {
        name: 'ECDH',
        namedCurve: 'P-256'
      },
      false,
      []
    )

    // 执行 ECDH 密钥交换
    const sharedSecret = await crypto.subtle.deriveBits(
      {
        name: 'ECDH',
        public: serverPublicKey
      },
      ephemeralKeyPair.privateKey,
      256
    )

    // 使用 HKDF 派生 AES 密钥
    const sharedSecretKey = await crypto.subtle.importKey(
      'raw',
      new Uint8Array(sharedSecret),
      'HKDF',
      false,
      ['deriveBits']
    )

    const aesKeyMaterial = await crypto.subtle.deriveBits(
      {
        name: 'HKDF',
        hash: 'SHA-256',
        salt: new Uint8Array(0),
        info: new TextEncoder().encode('password-encryption')
      },
      sharedSecretKey,
      256
    )

    // 导入 AES-GCM 密钥
    const aesKey = await crypto.subtle.importKey(
      'raw',
      new Uint8Array(aesKeyMaterial),
      'AES-GCM',
      false,
      ['encrypt']
    )

    // 加密密码
    const nonce = new Uint8Array(12) // 全零 nonce（与后端一致）
    const encrypted = await crypto.subtle.encrypt(
      {
        name: 'AES-GCM',
        iv: nonce
      },
      aesKey,
      new TextEncoder().encode(password)
    )

    // 导出临时公钥
    const ephemeralPublicKeyBytes = await crypto.subtle.exportKey(
      'raw',
      ephemeralKeyPair.publicKey
    )

    // 组合：临时公钥 + 密文
    const result = new Uint8Array(ephemeralPublicKeyBytes.byteLength + encrypted.byteLength)
    result.set(new Uint8Array(ephemeralPublicKeyBytes), 0)
    result.set(new Uint8Array(encrypted), ephemeralPublicKeyBytes.byteLength)

    // 返回 Base64 编码
    return bytesToBase64(result)
  } catch (error) {
    console.error('密码加密失败:', error)
    throw new Error('密码加密失败')
  }
}

/**
 * 清除缓存的公钥（用于重新获取）
 */
export function clearCachedPublicKey() {
  cachedPublicKey = null
}
