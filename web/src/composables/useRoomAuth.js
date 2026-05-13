// Linly-Talker-Stream (https://github.com/Kedreamix/Linly-Talker-Stream). Copyright [Linly-talker-stream@kedreamix]. Apache-2.0.
//
// 直播间口令：当后端 ROOM_PASSWORD 环境变量被设置时，所有受保护接口要求
// X-Room-Password header。这里在 app 启动时：
//   1. GET /auth_required 看是否需要密码
//   2. 需要则从 sessionStorage 读，否则弹 prompt 让用户输
//   3. 用 monkey-patch 包装 window.fetch，给所有相对路径请求自动加 header
//   4. 任意请求 401 → 清缓存 + 重新弹

const STORAGE_KEY = 'roomPassword'
const HEADER = 'X-Room-Password'

let installed = false
let cachedPassword = ''

const promptPassword = (message) => {
  // 用浏览器原生 prompt，移动端兼容性最好
  const v = window.prompt(message || '请输入直播间密码：', '')
  return v == null ? '' : v.trim()
}

const isProtectedPath = (url) => {
  // 简单判定：相对路径或同源即视为后端请求
  if (typeof url !== 'string') return false
  if (url.startsWith('/')) return true
  try {
    const u = new URL(url, window.location.origin)
    return u.origin === window.location.origin
  } catch {
    return false
  }
}

export async function setupRoomAuth({ onNotification } = {}) {
  if (installed) return
  installed = true

  // 1. 探测后端是否需要密码
  let required = false
  try {
    const r = await fetch('/auth_required')
    if (r.ok) {
      const j = await r.json()
      required = !!j.required
    }
  } catch (e) {
    console.warn('查询 /auth_required 失败，假定不需要密码：', e)
    return
  }

  if (!required) {
    console.log('🔓 后端未启用密码保护')
    return
  }

  console.log('🔒 后端启用了密码保护，准备口令...')

  // 2. 读缓存或弹窗
  cachedPassword = sessionStorage.getItem(STORAGE_KEY) || ''
  while (!cachedPassword) {
    cachedPassword = promptPassword()
    if (!cachedPassword) {
      // 用户取消 → 给提示但不强制刷新，下次请求时会再触发
      if (onNotification) onNotification('未输入密码，受保护接口将无法使用', 'warning')
      break
    }
    sessionStorage.setItem(STORAGE_KEY, cachedPassword)
  }

  // 3. 包装 window.fetch
  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : (input && input.url) || ''
    if (!isProtectedPath(url)) {
      return originalFetch(input, init)
    }

    const newInit = { ...init }
    const headers = new Headers(init.headers || (typeof input !== 'string' ? input.headers : undefined))
    if (cachedPassword) {
      headers.set(HEADER, cachedPassword)
    }
    newInit.headers = headers

    let resp = await originalFetch(input, newInit)

    // 4. 401 → 清缓存重弹一次
    if (resp.status === 401) {
      console.warn('🔒 收到 401，密码可能错误，重新输入...')
      sessionStorage.removeItem(STORAGE_KEY)
      cachedPassword = ''
      const retry = promptPassword('密码错误或已失效，请重新输入：')
      if (retry) {
        cachedPassword = retry
        sessionStorage.setItem(STORAGE_KEY, retry)
        headers.set(HEADER, retry)
        resp = await originalFetch(input, { ...newInit, headers })
      } else if (onNotification) {
        onNotification('密码验证失败', 'error')
      }
    }

    return resp
  }
}
