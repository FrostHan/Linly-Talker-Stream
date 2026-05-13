<!-- Linly-Talker-Stream (https://github.com/Kedreamix/Linly-Talker-Stream). Copyright [Linly-talker-stream@kedreamix]. Apache-2.0. -->
<template>
  <div class="app-wrapper" :class="{ mobile: isMobile }">
    <!-- 顶部导航栏 -->
    <header class="app-header">
      <div class="header-content">
        <div class="logo-section">
          <div class="logo-icon">
            <i class="bi bi-robot"></i>
          </div>
          <div class="logo-text">
            <h1>{{ t('header.title') }}</h1>
            <p v-if="!isMobile">{{ t('header.subtitle') }}</p>
          </div>
        </div>
        
        <div class="status-section">
          <div class="status-badge" :class="statusClass">
            <span class="status-dot"></span>
            <span class="status-text">{{ statusText }}</span>
          </div>
          <div class="session-info" v-if="sessionId > 0 && !isMobile">
            <i class="bi bi-hash"></i>
            <span>{{ t('header.session') }} {{ sessionId }}</span>
          </div>
          <SettingsPanel 
            @settings-changed="onSettingsChanged" 
            @notification="showNotification"
          />
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <div class="content-wrapper">
        <!-- 左侧：对话区域 -->
        <div class="chat-section">
          <div class="chat-header">
            <h2><i class="bi bi-chat-dots"></i> {{ t('chat.title') }}</h2>
            <div class="chat-actions">
              <button 
                class="action-btn" 
                :class="{ active: activeMode === 'chat' }"
                @click="activeMode = 'chat'"
              >
                <i class="bi bi-chat-text"></i>
                {{ t('chat.chatMode') }}
              </button>
              <button 
                class="action-btn"
                :class="{ active: activeMode === 'tts' }"
                @click="activeMode = 'tts'"
              >
                <i class="bi bi-volume-up"></i>
                {{ t('chat.ttsMode') }}
              </button>
              <button 
                class="action-btn clear-history-btn"
                @click="clearChatHistory"
                :disabled="!isConnected"
                :title="isConnected ? '清空对话历史' : '请先连接'"
              >
                <i class="bi bi-trash"></i>
                清空历史
              </button>
            </div>
          </div>

          <!-- 对话模式 -->
          <div v-if="activeMode === 'chat'" class="chat-mode">
            <div class="messages-container" ref="messagesRef">
              <div 
                v-for="(msg, index) in chatMessages" 
                :key="index"
                class="message"
                :class="msg.type === 'user' ? 'message-user' : 'message-ai'"
              >
                <div class="message-avatar">
                  <i :class="msg.type === 'user' ? 'bi bi-person-circle' : 'bi bi-robot'"></i>
                </div>
                <div class="message-content">
                  <div class="message-header">
                    <span class="message-sender">{{ msg.type === 'user' ? t('chat.you') : t('chat.ai') }}</span>
                    <span class="message-time" v-if="appSettings.showTimestamp">{{ msg.time }}</span>
                  </div>
                  <div class="message-text" v-html="renderMarkdown(msg.text)"></div>
                </div>
              </div>
              
              <div v-if="isThinking" class="message message-ai typing">
                <div class="message-avatar">
                  <i class="bi bi-robot"></i>
                </div>
                <div class="message-content">
                  <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>

            <div class="input-area">
              <div class="input-box">
                <div class="textarea-wrapper">
                  <textarea 
                    v-model="chatInput"
                    @keydown.enter.exact.prevent="sendChatMessage"
                    :placeholder="isConnected ? t('chat.inputPlaceholder') : t('chat.inputPlaceholderDisconnected')"
                    :disabled="!isConnected"
                    rows="1"
                  ></textarea>
                  <button 
                    v-if="chatInput.trim()"
                    class="clear-input-btn"
                    @click="clearInput"
                    title="清空输入框"
                  >
                    <i class="bi bi-x-circle-fill"></i>
                  </button>
                </div>
                <div class="input-actions">
                  <button 
                    class="voice-btn"
                    @mousedown="handleVoiceButtonPress"
                    @mouseup="handleVoiceButtonRelease"
                    @click="handleVoiceButtonClick"
                    @touchstart.prevent="handleVoiceButtonPress"
                    @touchend="handleVoiceButtonRelease"
                    :class="{ recording: isRecordingVoice, 'continuous-mode': appSettings.voiceContinuous }"
                    :disabled="!isConnected"
                    :title="getVoiceButtonTitle"
                  >
                    <div class="voice-icon-wrapper">
                      <i class="bi bi-mic-fill"></i>
                      <span v-if="isRecordingVoice" class="recording-pulse"></span>
                    </div>
                    <span class="voice-btn-text" v-if="appSettings.voiceContinuous">
                      {{ isRecordingVoice ? '点击停止' : '点击录音' }}
                    </span>
                    <span class="voice-btn-text" v-else>
                      {{ isRecordingVoice ? '松开发送' : '按住说话' }}
                    </span>
                  </button>
                  <button 
                    class="send-btn" 
                    @click="sendChatMessage" 
                    :disabled="!isConnected || !chatInput.trim()"
                    :title="!isConnected ? t('tooltips.connectDisabled') : ''"
                  >
                    <i class="bi bi-send-fill"></i>
                    <span>{{ t('chat.sendButton') }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 朗读模式 -->
          <div v-if="activeMode === 'tts'" class="tts-mode">
            <div class="tts-container">
              <h3><i class="bi bi-file-text"></i> {{ t('chat.ttsTitle') }}</h3>
              <textarea 
                v-model="ttsInput"
                :placeholder="isConnected ? t('chat.ttsInputPlaceholder') : t('chat.inputPlaceholderDisconnected')"
                :disabled="!isConnected"
                rows="12"
              ></textarea>
              <button 
                class="tts-btn" 
                @click="sendTTSMessage" 
                :disabled="!isConnected || !ttsInput.trim()"
                :title="!isConnected ? t('tooltips.connectDisabled') : ''"
              >
                <i class="bi bi-play-circle-fill"></i>
                {{ t('chat.ttsButton') }}
              </button>
            </div>
          </div>
        </div>

        <!-- 右侧：视频区域 -->
        <div class="video-section">
          <div class="video-card">
            <div class="video-header">
              <h2><i class="bi bi-camera-video"></i> {{ t('video.title') }}</h2>
              <div class="video-controls-top">
                <button 
                  v-if="!isConnected" 
                  class="connect-btn" 
                  @click="handleStartConnection"
                  :disabled="!backendReady"
                  :title="backendReady ? '' : t('tooltips.connectDisabled')"
                >
                  <i class="bi bi-play-circle" v-if="backendReady"></i>
                  <i class="bi bi-hourglass-split spin" v-else></i>
                  {{ backendReady ? t('video.connect') : t('video.backendStarting') }}
                </button>
                <button 
                  v-else 
                  class="disconnect-btn" 
                  @click="handleStopConnection"
                >
                  <i class="bi bi-stop-circle"></i>
                  {{ t('video.disconnect') }}
                </button>
              </div>
            </div>

            <div class="video-wrapper">
              <video id="video" autoplay playsinline webkit-playsinline></video>
              <div class="video-overlay" v-if="!isConnected">
                <i class="bi bi-camera-video-off" v-if="backendReady"></i>
                <i class="bi bi-hourglass-split spin" v-else style="font-size: 4rem;"></i>
                <p v-if="backendReady">{{ t('video.overlayTextReady') }}</p>
                <p v-else>{{ t('video.overlayTextLoading') }}</p>
              </div>
              <div class="recording-badge" v-if="isRecording">
                <i class="bi bi-record-circle"></i>
                {{ t('video.recording') }}
              </div>
            </div>

            <div class="video-controls">
              <div class="control-buttons">
                <button 
                  class="control-btn"
                  @click="handleStartRecord"
                  :disabled="!isConnected || isRecording"
                  :title="!isConnected ? t('tooltips.recordDisabled') : ''"
                >
                  <i class="bi bi-record-fill"></i>
                  {{ t('video.startRecord') }}
                </button>
                <button 
                  class="control-btn"
                  @click="handleStopRecord"
                  :disabled="!isRecording"
                >
                  <i class="bi bi-stop-fill"></i>
                  {{ t('video.stopRecord') }}
                </button>
                <button 
                  class="control-btn download-btn"
                  @click="downloadRecord"
                  :disabled="!lastRecordFile"
                  :title="lastRecordFile ? '' : t('tooltips.downloadDisabled')"
                >
                  <i class="bi bi-download"></i>
                  {{ t('video.download') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 调试面板 -->
    <DebugPanel 
      v-if="appSettings.showDebugPanel"
      :connection-status="connectionStatus"
      :session-id="sessionId"
    />
    
    <input type="hidden" id="sessionid" :value="sessionId">
    
    <!-- 通知提示 -->
    <div class="notification-container">
      <transition-group name="notification">
        <div 
          v-for="notification in notifications" 
          :key="notification.id"
          class="notification"
          :class="notification.type"
        >
          <i :class="getNotificationIcon(notification.type)"></i>
          <span>{{ notification.message }}</span>
        </div>
      </transition-group>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import DebugPanel from './components/DebugPanel.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import { useWebRTC } from './composables/useWebRTC'
import { useSpeechRecognition } from './composables/useSpeechRecognition'
import { useI18n } from './composables/useI18n'
import { setupRoomAuth } from './composables/useRoomAuth'
import { marked } from 'marked'
import hljs from 'highlight.js'

// 配置 marked
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch (err) {
        console.error('代码高亮失败:', err)
      }
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

const { t, setLocale, loadLocale } = useI18n()

// Markdown 渲染函数
const renderMarkdown = (text) => {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch (error) {
    console.error('Markdown 解析错误:', error)
    return text
  }
}

const sessionId = ref(0)
const connectionStatus = ref('disconnected')
const isRecording = ref(false)
const activeMode = ref('chat')
const chatInput = ref('')
const ttsInput = ref('')
const isThinking = ref(false)
const isRecordingVoice = ref(false)
const messagesRef = ref(null)
const notifications = ref([])
let notificationIdCounter = 0
const lastRecordFile = ref(null)  // 最后一次录制的文件信息
const backendReady = ref(false)  // 后端是否就绪

// 移动端自动检测：UA + 屏宽双重判断；窗口尺寸变化时实时更新
// 关键：用立即执行函数初始化 ref，确保首次渲染就拿到正确的 isMobile
//       否则 onMounted 之前会先按 desktop 渲染，再切到 mobile（且某些场景永远不会切）
const _initialMobile = (() => {
  if (typeof window === 'undefined') return false
  const ua = navigator.userAgent || ''
  const uaMobile = /iPhone|iPod|Android.*Mobile|BlackBerry|IEMobile|Opera Mini|Mobile Safari/i.test(ua)
  const narrow = window.matchMedia('(max-width: 768px)').matches
  const iPadLike = navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
  return uaMobile || iPadLike || narrow
})()
const isMobile = ref(_initialMobile)
const detectMobile = () => {
  const ua = navigator.userAgent || ''
  const uaMobile = /iPhone|iPod|Android.*Mobile|BlackBerry|IEMobile|Opera Mini|Mobile Safari/i.test(ua)
  const narrow = window.matchMedia('(max-width: 768px)').matches
  // iPad 在 iPadOS 13+ UA 里伪装成桌面 Mac，但有触控点
  const iPadLike = navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
  isMobile.value = uaMobile || iPadLike || narrow
}

// 应用设置
const appSettings = ref({
  useStun: true,
  stunServer: 'stun:stun.l.google.com:19302',
  customStunServer: '',
  autoRecord: false,
  recordFormat: 'mp4',
  showDebugPanel: false,
  showTimestamp: true,
  theme: 'dark',
  uiLanguage: 'zh-CN',
  videoSize: 100,
  voiceContinuous: false,
  voiceLanguage: 'zh-CN'
})

const chatMessages = ref([
  { 
    type: 'ai', 
    text: '',  // 将在 onMounted 中设置
    time: getCurrentTime()
  }
])

const isConnected = computed(() => connectionStatus.value === 'connected')

const statusClass = computed(() => {
  return {
    'status-connected': connectionStatus.value === 'connected',
    'status-connecting': connectionStatus.value === 'connecting',
    'status-disconnected': connectionStatus.value === 'disconnected'
  }
})

const statusText = computed(() => {
  const statusMap = {
    'connected': t('header.status.connected'),
    'connecting': t('header.status.connecting'),
    'disconnected': t('header.status.disconnected')
  }
  return statusMap[connectionStatus.value] || t('header.status.disconnected')
})

const getVoiceButtonTitle = computed(() => {
  if (!isConnected.value) {
    return t('tooltips.voiceDisabled')
  }
  if (appSettings.value.voiceContinuous) {
    return isRecordingVoice.value ? t('tooltips.voiceRecording') : t('tooltips.voiceContinuous')
  }
  return t('tooltips.voiceHold')
})

function getCurrentTime() {
  const now = new Date()
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
}

// 通知系统
const showNotification = (message, type = 'info') => {
  const id = notificationIdCounter++
  const notification = { id, message, type }
  notifications.value.push(notification)
  
  // 3秒后自动移除
  setTimeout(() => {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }, 3000)
}

const getNotificationIcon = (type) => {
  switch (type) {
    case 'success': return 'bi bi-check-circle-fill'
    case 'error': return 'bi bi-x-circle-fill'
    case 'warning': return 'bi bi-exclamation-triangle-fill'
    default: return 'bi bi-info-circle-fill'
  }
}

const { startPlay, stopPlay } = useWebRTC({
  onNotification: showNotification
})

// 设置变更处理
const onSettingsChanged = (newSettings) => {
  appSettings.value = { ...newSettings }
  console.log('设置已更新:', appSettings.value)
  
  // 更新语音识别设置
  if (updateSettings) {
    updateSettings({
      language: newSettings.voiceLanguage,
      continuous: newSettings.voiceContinuous
    })
  }
  
  // 更新视频大小
  updateVideoSize(newSettings.videoSize)
  
  // 更新主题
  updateTheme(newSettings.theme)
  
  // 更新界面语言
  if (newSettings.uiLanguage) {
    setLocale(newSettings.uiLanguage)
  }
}

const updateVideoSize = (size) => {
  const video = document.getElementById('video')
  if (video) {
    video.style.width = `${size}%`
  }
}

// 更新主题
const updateTheme = (theme) => {
  const root = document.documentElement
  
  if (theme === 'auto') {
    // 跟随系统
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    theme = prefersDark ? 'dark' : 'light'
  }
  
  if (theme === 'light') {
    // 浅色模式
    root.style.setProperty('--primary', '#6366f1')
    root.style.setProperty('--primary-dark', '#4f46e5')
    root.style.setProperty('--primary-light', '#818cf8')
    root.style.setProperty('--success', '#10b981')
    root.style.setProperty('--warning', '#f59e0b')
    root.style.setProperty('--danger', '#ef4444')
    root.style.setProperty('--bg-primary', '#ffffff')
    root.style.setProperty('--bg-secondary', '#f8fafc')
    root.style.setProperty('--bg-tertiary', '#e2e8f0')
    root.style.setProperty('--text-primary', '#0f172a')
    root.style.setProperty('--text-secondary', '#475569')
    root.style.setProperty('--text-muted', '#64748b')
    root.style.setProperty('--border', '#cbd5e1')
    root.style.setProperty('--shadow', '0 4px 6px -1px rgba(0, 0, 0, 0.1)')
    root.style.setProperty('--shadow-lg', '0 10px 15px -3px rgba(0, 0, 0, 0.15)')
    root.style.setProperty('--bg-gradient', 'linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%)')
  } else {
    // 深色模式（默认）
    root.style.setProperty('--primary', '#6366f1')
    root.style.setProperty('--primary-dark', '#4f46e5')
    root.style.setProperty('--primary-light', '#818cf8')
    root.style.setProperty('--success', '#10b981')
    root.style.setProperty('--warning', '#f59e0b')
    root.style.setProperty('--danger', '#ef4444')
    root.style.setProperty('--bg-primary', '#0f172a')
    root.style.setProperty('--bg-secondary', '#1e293b')
    root.style.setProperty('--bg-tertiary', '#334155')
    root.style.setProperty('--text-primary', '#f8fafc')
    root.style.setProperty('--text-secondary', '#cbd5e1')
    root.style.setProperty('--text-muted', '#94a3b8')
    root.style.setProperty('--border', '#475569')
    root.style.setProperty('--shadow', '0 4px 6px -1px rgba(0, 0, 0, 0.3)')
    root.style.setProperty('--shadow-lg', '0 10px 15px -3px rgba(0, 0, 0, 0.4)')
    root.style.setProperty('--bg-gradient', 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)')
  }
}

// 检查后端是否就绪
const checkBackendReady = async () => {
  try {
    const response = await fetch('/health')
    if (response.ok) {
      const data = await response.json()
      if (data.ready) {
        backendReady.value = true
        console.log('✅ 后端已就绪')
        return true
      }
    }
  } catch (error) {
    console.log('⏳ 等待后端启动...')
  }
  return false
}

const handleStartConnection = async () => {
  console.log('🚀 用户点击"开始连接"按钮')
  
  // 再次确认后端是否就绪
  if (!backendReady.value) {
    showNotification(t('notifications.backendNotReady'), 'warning')
    return
  }
  
  connectionStatus.value = 'connecting'
  
  try {
    // 使用设置中的 STUN 配置
    const stunUrl = appSettings.value.useStun 
      ? (appSettings.value.stunServer === 'custom' 
          ? appSettings.value.customStunServer 
          : appSettings.value.stunServer)
      : null
    
    const newSessionId = await startPlay(stunUrl)
    if (newSessionId) {
      sessionId.value = newSessionId
      showNotification(t('notifications.connectSuccess'), 'success')
    }
    
    const checkConnection = setInterval(() => {
      const video = document.getElementById('video')
      if (video && video.readyState >= 3 && video.videoWidth > 0) {
        connectionStatus.value = 'connected'
        clearInterval(checkConnection)
        
        // 自动录制
        if (appSettings.value.autoRecord) {
          setTimeout(() => {
            handleStartRecord()
          }, 1000)
        }
      }
    }, 2000)
    
    setTimeout(() => {
      if (connectionStatus.value === 'connecting') {
        connectionStatus.value = 'disconnected'
        showNotification(t('notifications.connectTimeout'), 'error')
      }
      clearInterval(checkConnection)
    }, 60000)
  } catch (error) {
    console.error('连接失败:', error)
    connectionStatus.value = 'disconnected'
    showNotification(t('notifications.connectFailed'), 'error')
  }
}

const handleStopConnection = () => {
  stopPlay()
  connectionStatus.value = 'disconnected'
  showNotification(t('notifications.disconnected'), 'info')
}

const handleStartRecord = async () => {
  if (!sessionId.value) {
    console.error('无法录制：sessionId 为空')
    showNotification(t('notifications.connectFirst'), 'warning')
    return
  }
  
  console.log('🔴 开始录制，sessionId:', sessionId.value)
  
  try {
    const response = await fetch('/record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'start_record',
        sessionid: sessionId.value
      })
    })
    
    console.log('录制请求响应状态:', response.status)
    
    if (response.ok) {
      const data = await response.json()
      console.log('录制开始成功:', data)
      isRecording.value = true
      showNotification(t('notifications.recordStart'), 'success')
    } else {
      const errorText = await response.text()
      console.error('录制开始失败:', response.status, errorText)
      showNotification(`${t('notifications.recordStartFailed')}: ${response.status}`, 'error')
    }
  } catch (error) {
    console.error('Failed to start recording:', error)
    showNotification(`${t('notifications.recordStartFailed')}: ${error.message}`, 'error')
  }
}

const handleStopRecord = async () => {
  if (!sessionId.value) {
    console.error('无法停止录制：sessionId 为空')
    return
  }
  
  console.log('⏹️ 停止录制，sessionId:', sessionId.value)
  
  try {
    const response = await fetch('/record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'end_record',
        sessionid: sessionId.value
      })
    })
    
    console.log('停止录制响应状态:', response.status)
    
    if (response.ok) {
      const data = await response.json()
      console.log('录制停止成功:', data)
      isRecording.value = false
      
      // 保存文件信息
      if (data.filename) {
        lastRecordFile.value = {
          filename: data.filename,
          filepath: data.filepath
        }
        showNotification(t('notifications.recordStop'), 'success')
      } else {
        showNotification(t('notifications.recordStopSimple'), 'success')
      }
    } else {
      const errorText = await response.text()
      console.error('停止录制失败:', response.status, errorText)
      showNotification(`${t('notifications.recordStopFailed')}: ${response.status}`, 'error')
    }
  } catch (error) {
    console.error('Failed to stop recording:', error)
    showNotification(`${t('notifications.recordStopFailed')}: ${error.message}`, 'error')
  }
}

const downloadRecord = () => {
  if (!lastRecordFile.value) {
    showNotification(t('notifications.noRecordFile'), 'warning')
    return
  }
  
  const downloadUrl = `/download/${lastRecordFile.value.filename}`
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = lastRecordFile.value.filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  showNotification(t('notifications.downloading'), 'info')
}

const addMessage = (text, type = 'user') => {
  chatMessages.value.push({ 
    text, 
    type, 
    time: getCurrentTime() 
  })
  
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 清空输入框
const clearInput = () => {
  chatInput.value = ''
}

const sendChatMessage = async () => {
  if (!chatInput.value.trim()) return
  
  // 检查是否已连接
  if (!isConnected.value) {
    showNotification(t('notifications.connectFirst'), 'warning')
    return
  }
  
  const message = chatInput.value
  addMessage(message, 'user')
  chatInput.value = ''
  
  isThinking.value = true
  
  try {
    const response = await fetch('/human', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: message,
        type: 'chat',
        interrupt: true,
        sessionid: sessionId.value
      })
    })
    
    if (response.ok) {
      const data = await response.json()
      console.log('收到大模型回复:', data)
      
      // 显示大模型的回复
      if (data.response || data.text) {
        isThinking.value = false
        addMessage(data.response || data.text, 'ai')
      }
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error) {
    console.error('Failed to send message:', error)
    showNotification(t('notifications.messageFailed'), 'error')
  } finally {
    isThinking.value = false
  }
}

const sendTTSMessage = async () => {
  if (!ttsInput.value.trim()) return
  
  // 检查是否已连接
  if (!isConnected.value) {
    showNotification(t('notifications.connectFirst'), 'warning')
    return
  }
  
  const message = ttsInput.value
  
  try {
    await fetch('/human', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: message,
        type: 'echo',
        interrupt: true,
        sessionid: sessionId.value
      })
    })
    
    addMessage(`已发送朗读请求：${message.substring(0, 50)}${message.length > 50 ? '...' : ''}`, 'system')
    ttsInput.value = ''
  } catch (error) {
    console.error('Failed to send TTS message:', error)
    showNotification(t('notifications.ttsFailed'), 'error')
  }
}

// 语音识别
let mediaRecorder = null
let audioChunks = []

const { startRecognition, stopRecognition, isSupported, updateSettings } = useSpeechRecognition({
  onResult: (text) => {
    // 实时显示识别的中间结果
    chatInput.value = text
  },
  language: appSettings.value.voiceLanguage,
  continuous: appSettings.value.voiceContinuous,
  onFinalResult: async (text) => {
    // 在非连续模式下，识别完成后自动停止录音
    if (!appSettings.value.voiceContinuous && isRecordingVoice.value && mediaRecorder) {
      console.log('识别完成，自动停止录音（非连续模式）')
      stopVoiceRecording()
    }
    
    if (text.trim()) {
      addMessage(text, 'user')
      // 清空输入框，准备下一次识别
      chatInput.value = ''
      isThinking.value = true
      
      try {
        const response = await fetch('/human', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            type: 'chat',
            interrupt: true,
            sessionid: sessionId.value
          })
        })
        
        if (response.ok) {
          const data = await response.json()
          console.log('收到大模型回复:', data)
          
          // 显示大模型的回复
          if (data.response || data.text) {
            isThinking.value = false
            addMessage(data.response || data.text, 'ai')
          }
        }
        } catch (error) {
        console.error('Failed to send voice message:', error)
        showNotification(t('notifications.voiceMessageFailed'), 'error')
      } finally {
        isThinking.value = false
      }
    }
  }
})

const startVoiceRecording = async () => {
  if (isRecordingVoice.value) return
  
  // 检查是否已连接
  if (!isConnected.value) {
    showNotification(t('notifications.connectFirst'), 'warning')
    return
  }
  
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    
    audioChunks = []
    mediaRecorder = new MediaRecorder(stream)
    
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        audioChunks.push(e.data)
      }
    }
    
    mediaRecorder.start()
    isRecordingVoice.value = true
    
    if (isSupported) {
      startRecognition()
    }
  } catch (error) {
    console.error('无法访问麦克风:', error)
    showNotification(t('notifications.micPermission'), 'error')
  }
}

const stopVoiceRecording = async () => {
  if (!isRecordingVoice.value || !mediaRecorder) return
  
  console.log('停止语音录音')
  
  mediaRecorder.stop()
  isRecordingVoice.value = false
  
  // 清空输入框中的临时识别结果
  chatInput.value = ''
  
  // 停止浏览器语音识别
  if (isSupported) {
    stopRecognition()
  }
  
  // 等待录音数据收集完成（用于可能的后端识别）
  mediaRecorder.onstop = async () => {
    // 关闭麦克风流
    mediaRecorder.stream.getTracks().forEach(track => track.stop())
    
    // 如果浏览器支持 Web Speech API，优先使用浏览器识别，不发送到后端
    // 浏览器识别的结果会通过 onFinalResult 回调处理
    if (isSupported) {
      console.log('使用浏览器语音识别，无需发送到后端')
      audioChunks = []
      return
    }
    
    // 浏览器不支持时，才发送音频到后端进行 ASR 识别
    if (audioChunks.length > 0) {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
      
      try {
        showNotification(t('notifications.voiceRecognizing'), 'info')
        
        const formData = new FormData()
        formData.append('file', audioBlob, 'voice.webm')
        formData.append('sessionid', sessionId.value)
        
        const response = await fetch('/asr', {
          method: 'POST',
          body: formData
        })
        
        if (response.ok) {
          const data = await response.json()
          console.log('ASR 识别成功:', data)
          
          if (data.text) {
            // 显示用户说的话
            addMessage(data.text, 'user')
            showNotification(t('notifications.voiceRecognized'), 'success')
            
            // 显示 AI 的回复
            if (data.response) {
              addMessage(data.response, 'ai')
            }
          } else {
            showNotification(t('notifications.voiceNoContent'), 'warning')
          }
        } else {
          console.error('ASR 识别失败:', response.status)
          showNotification(t('notifications.voiceFailed'), 'error')
        }
      } catch (error) {
        console.error('ASR 请求失败:', error)
        showNotification(t('notifications.voiceRequestFailed'), 'error')
      }
    }
    
    // 清空音频数据
    audioChunks = []
  }
}

// 处理语音按钮的按下事件（用于按住说话模式）
const handleVoiceButtonPress = (e) => {
  // 在连续识别模式下，不处理按下事件
  if (appSettings.value.voiceContinuous) {
    return
  }
  startVoiceRecording()
}

// 处理语音按钮的释放事件（用于按住说话模式）
const handleVoiceButtonRelease = (e) => {
  // 在连续识别模式下，不处理释放事件
  if (appSettings.value.voiceContinuous) {
    return
  }
  stopVoiceRecording()
}

// 处理语音按钮的点击事件（用于连续识别模式）
const handleVoiceButtonClick = (e) => {
  // 只在连续识别模式下处理点击事件
  if (!appSettings.value.voiceContinuous) {
    return
  }
  
  // 切换录音状态
  if (isRecordingVoice.value) {
    stopVoiceRecording()
  } else {
    startVoiceRecording()
  }
}

// 清空对话历史
const clearChatHistory = async () => {
  if (!isConnected.value) {
    showNotification('请先连接', 'warning')
    return
  }
  
  try {
    const response = await fetch('/clear_history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sessionid: sessionId.value
      })
    })
    
    if (response.ok) {
      // 清空前端显示的消息（保留欢迎消息）
      chatMessages.value = [
        { 
          type: 'ai', 
          text: t('chat.welcomeMessage'),
          time: getCurrentTime()
        }
      ]
      showNotification('对话历史已清空', 'success')
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error) {
    console.error('Failed to clear history:', error)
    showNotification('清空历史失败，请重试', 'error')
  }
}

onMounted(async () => {
  console.log('✅ Vue 应用已挂载')
  console.log('后端 API 地址: /offer (通过 Vite proxy 转发到 localhost:8010)')
  
  // 移动端检测
  detectMobile()
  window.addEventListener('resize', detectMobile)
  if (isMobile.value) {
    console.log('📱 检测到移动端浏览器，已启用移动端布局')
  }

  // 直播间口令保护：如果后端启用了 ROOM_PASSWORD，会弹窗让用户输入并自动加 header
  await setupRoomAuth({ onNotification: showNotification })

  // 加载语言设置
  loadLocale()
  
  // 设置欢迎消息
  if (chatMessages.value.length > 0 && !chatMessages.value[0].text) {
    chatMessages.value[0].text = t('chat.welcomeMessage')
  }
  
  // 应用初始主题
  updateTheme(appSettings.value.theme)
  
  // 开始轮询检查后端是否就绪：一直轮询直到成功，避免 60s 后按钮永远卡在"后端启动中"
  console.log('🔍 开始检查后端状态...')
  let checkCount = 0
  const checkInterval = setInterval(async () => {
    checkCount++
    const ready = await checkBackendReady()
    if (ready) {
      clearInterval(checkInterval)
      showNotification(t('notifications.backendReady'), 'success')
    } else if (checkCount === 30) {
      // 60s 还没好就提示一下，但继续轮询（不要彻底放弃）
      showNotification(t('notifications.backendTimeout'), 'warning')
    }
  }, 2000)
})
</script>

<style>
@import 'highlight.js/styles/atom-one-dark.css';

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --primary: #6366f1;
  --primary-dark: #4f46e5;
  --primary-light: #818cf8;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-tertiary: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #cbd5e1;
  --text-muted: #94a3b8;
  --border: #475569;
  --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg-gradient, linear-gradient(135deg, #0f172a 0%, #1e293b 100%));
  color: var(--text-primary);
  min-height: 100vh;
}

.app-wrapper {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 顶部导航栏 */
.app-header {
  background: var(--bg-secondary);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  padding: 1rem 2rem;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow);
}

.header-content {
  max-width: 1800px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.logo-icon {
  width: 50px;
  height: 50px;
  background: linear-gradient(135deg, var(--primary), var(--primary-light));
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
  box-shadow: var(--shadow);
}

.logo-text h1 {
  font-size: 1.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary-light), #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin: 0;
}

.logo-text p {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
}

.status-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

.status-connected .status-dot {
  background: var(--success);
}

.status-connecting .status-dot {
  background: var(--warning);
}

.status-disconnected .status-dot {
  background: var(--danger);
}

.session-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--bg-tertiary);
  border-radius: 20px;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.github-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.github-link:hover {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  transform: translateY(-2px);
}

.github-link i {
  font-size: 1.125rem;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 2rem;
}

.content-wrapper {
  max-width: 1800px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 500px;
  gap: 2rem;
  height: calc(100vh - 150px);
}

/* 左侧对话区 */
.chat-section {
  background: var(--bg-secondary);
  border-radius: 16px;
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}

.chat-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-tertiary);
}

.chat-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
}

.chat-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.action-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.action-btn.active {
  background: var(--primary);
  color: white;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.clear-history-btn:hover:not(:disabled) {
  background: var(--danger);
  color: white;
}

/* 对话模式 */
.chat-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  display: flex;
  gap: 1rem;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.message-user .message-avatar {
  background: var(--success);
}

.message-content {
  flex: 1;
  max-width: 70%;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.message-sender {
  font-weight: 600;
  font-size: 0.875rem;
}

.message-time {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.message-text {
  background: var(--bg-tertiary);
  padding: 0.75rem 1rem;
  border-radius: 12px;
  line-height: 1.6;
}

.message-user .message-text {
  background: var(--primary);
}

/* Markdown 样式 */
.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4),
.message-text :deep(h5),
.message-text :deep(h6) {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
  line-height: 1.3;
}

.message-text :deep(h1) { font-size: 1.5rem; }
.message-text :deep(h2) { font-size: 1.3rem; }
.message-text :deep(h3) { font-size: 1.1rem; }
.message-text :deep(h4) { font-size: 1rem; }

.message-text :deep(p) {
  margin: 0.5rem 0;
}

.message-text :deep(p:first-child) {
  margin-top: 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.message-text :deep(li) {
  margin: 0.25rem 0;
}

.message-text :deep(code) {
  background: rgba(0, 0, 0, 0.2);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9em;
}

.message-user .message-text :deep(code) {
  background: rgba(255, 255, 255, 0.2);
}

.message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.message-user .message-text :deep(pre) {
  background: rgba(0, 0, 0, 0.2);
}

.message-text :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  display: block;
  line-height: 1.5;
}

.message-text :deep(blockquote) {
  border-left: 4px solid var(--primary-light);
  padding-left: 1rem;
  margin: 0.5rem 0;
  color: var(--text-secondary);
  font-style: italic;
}

.message-text :deep(a) {
  color: var(--primary-light);
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
}

.message-text :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
}

.message-text :deep(table th),
.message-text :deep(table td) {
  border: 1px solid var(--border);
  padding: 0.5rem;
  text-align: left;
}

.message-text :deep(table th) {
  background: rgba(0, 0, 0, 0.2);
  font-weight: 600;
}

.message-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1rem 0;
}

.message-text :deep(strong) {
  font-weight: 700;
}

.message-text :deep(em) {
  font-style: italic;
}

.message-text :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 0.5rem 0;
}

.typing-indicator {
  display: flex;
  gap: 0.25rem;
  padding: 1rem;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-10px);
  }
}

/* 输入区 */
.input-area {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  background: var(--bg-tertiary);
}

.textarea-wrapper {
  position: relative;
  margin-bottom: 1rem;
}

.input-box textarea {
  width: 100%;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  padding-right: 3rem; /* 为清空按钮留空间 */
  color: var(--text-primary);
  font-size: 1rem;
  resize: none;
  min-height: 60px;
  max-height: 120px;
  transition: all 0.2s;
  font-family: inherit;
}

.input-box textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.input-box textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--bg-tertiary);
}

/* 清空输入框按钮 */
.clear-input-btn {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  font-size: 1.2rem;
}

.clear-input-btn:hover {
  color: var(--danger);
  transform: translateY(-50%) scale(1.1);
}

.input-actions {
  display: flex;
  gap: 1rem;
}

.voice-btn,
.send-btn {
  padding: 0.875rem 1.5rem;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  position: relative;
  overflow: hidden;
}

.voice-btn {
  flex: 1;
  background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
  color: var(--text-primary);
  border: 2px solid var(--border);
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.voice-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
  border-color: var(--primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.voice-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.voice-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--bg-secondary);
}

.voice-btn:disabled:hover {
  background: var(--bg-secondary);
  transform: none;
}

/* 录音状态样式 */
.voice-btn.recording {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
  border-color: #dc2626;
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4);
}

.voice-btn.recording:hover {
  background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(239, 68, 68, 0.5);
}

/* 连续模式样式 */
.voice-btn.continuous-mode:not(.recording) {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border-color: #2563eb;
}

.voice-btn.continuous-mode:not(.recording):hover {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
}

/* 语音按钮图标容器 */
.voice-icon-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

.voice-icon-wrapper i {
  font-size: 1.2rem;
  z-index: 1;
}

/* 录音脉冲动画 */
.recording-pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  animation: pulse-ring 1.5s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(2);
    opacity: 0;
  }
}

.voice-btn-text {
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.send-btn {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
  border: 2px solid transparent;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--primary-dark) 0%, #4338ca 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
}

.send-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-btn span {
  font-size: 0.95rem;
}

/* 朗读模式 */
.tts-mode {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
}

.tts-container {
  max-width: 800px;
  margin: 0 auto;
}

.tts-container h3 {
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tts-container textarea {
  width: 100%;
  background: var(--bg-secondary);
  border: 2px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem;
  color: var(--text-primary);
  font-size: 1rem;
  resize: vertical;
  margin-bottom: 1.5rem;
  min-height: 300px;
  transition: all 0.3s;
  font-family: inherit;
  line-height: 1.6;
}

.tts-container textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
  background: var(--bg-primary);
}

.tts-container textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--bg-secondary);
}

.tts-btn {
  width: 100%;
  padding: 1.125rem 1.5rem;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
  color: white;
  border: 2px solid transparent;
  border-radius: 12px;
  font-size: 1.05rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.625rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.tts-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--primary-dark) 0%, #4338ca 100%);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
}

.tts-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.tts-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.tts-btn i {
  font-size: 1.25rem;
}

/* 右侧视频区 */
.video-section {
  background: var(--bg-secondary);
  border-radius: 16px;
  border: 1px solid var(--border);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}

.video-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.video-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-tertiary);
}

.video-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
}

.connect-btn,
.disconnect-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}

.connect-btn {
  background: var(--success);
  color: white;
}

.connect-btn:hover:not(:disabled) {
  background: #059669;
}

.connect-btn:disabled {
  background: var(--text-muted);
  cursor: not-allowed;
  opacity: 0.6;
}

.disconnect-btn {
  background: var(--danger);
  color: white;
}

.disconnect-btn:hover {
  background: #dc2626;
}

.video-wrapper {
  flex: 1;
  position: relative;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-wrapper video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 3rem;
}

.video-overlay p {
  margin-top: 1rem;
  font-size: 1rem;
}

.recording-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: var(--danger);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  animation: pulse 2s infinite;
}

.video-controls {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  background: var(--bg-tertiary);
}

.control-buttons {
  display: flex;
  gap: 0.75rem;
}

.control-btn {
  flex: 1;
  padding: 0.875rem;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s;
  font-weight: 500;
}

.control-btn:hover:not(:disabled) {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  transform: translateY(-2px);
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.download-btn:not(:disabled) {
  background: var(--success, #10b981);
  border-color: var(--success, #10b981);
  color: white;
}

.download-btn:hover:not(:disabled) {
  background: #059669;
  border-color: #059669;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.spin {
  animation: spin 2s linear infinite;
}

/* 响应式 */
@media (max-width: 1400px) {
  .content-wrapper {
    grid-template-columns: 1fr 400px;
  }
}

@media (max-width: 1024px) {
  .content-wrapper {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr 400px;
  }
  
  .input-actions {
    flex-direction: column;
  }
  
  .voice-btn, .send-btn {
    width: 100%;
  }
}

@media (max-width: 768px) {
  .chat-header {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
  
  .chat-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  
  .action-btn {
    flex: 1;
    min-width: 100px;
  }
  
  .voice-btn-text {
    font-size: 0.875rem;
  }
  
  .send-btn span {
    display: none;
  }
  
  .send-btn i {
    font-size: 1.25rem;
  }
}

/* ============================================================
   移动端专用布局：通过 JS 检测 UA / 屏宽，给根节点加 .mobile class
   覆盖更激进，确保在 320~480px 窄屏也能用
   ============================================================ */
.app-wrapper.mobile {
  font-size: 14px;
}

.app-wrapper.mobile .app-header {
  padding: 0.5rem 0.75rem;
}

.app-wrapper.mobile .header-content {
  gap: 0.5rem;
}

.app-wrapper.mobile .logo-icon {
  width: 36px;
  height: 36px;
  font-size: 1.1rem;
}

.app-wrapper.mobile .logo-text h1 {
  font-size: 1rem;
  line-height: 1.2;
}

.app-wrapper.mobile .status-section {
  gap: 0.4rem;
  flex-shrink: 0;
}

.app-wrapper.mobile .status-badge {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.app-wrapper.mobile .status-text {
  display: none;       /* 只保留小绿/红点，省空间 */
}

.app-wrapper.mobile .main-content {
  padding: 0.5rem;
}

.app-wrapper.mobile .content-wrapper {
  grid-template-columns: 1fr;
  grid-template-rows: auto 1fr;        /* 视频在上、聊天在下 */
  gap: 0.5rem;
  height: calc(100vh - 60px);          /* 减去精简后的 header */
  height: calc(100dvh - 60px);          /* iOS 动态视口，避开地址栏 */
}

/* 视频区：移到顶部，按 1:1 比例占屏宽 */
.app-wrapper.mobile .video-section {
  order: -1;
  border-radius: 12px;
}

.app-wrapper.mobile .video-card {
  height: auto;
}

/* 移动端：完全隐藏视频面板的"数字人视频"标题栏，省出空间 */
/* 连接 / 断开连接按钮浮动到视频右上角 */
.app-wrapper.mobile .video-header {
  position: absolute;
  top: 0.4rem;
  right: 0.4rem;
  z-index: 5;
  padding: 0;
  background: transparent;
  border: none;
  width: auto;
}

.app-wrapper.mobile .video-header h2 {
  display: none;
}

.app-wrapper.mobile .video-section {
  position: relative;     /* 让 video-header 的 absolute 以此为基准 */
}

.app-wrapper.mobile .video-wrapper {
  width: 100%;
  aspect-ratio: 1 / 1;                 /* 数字人视频 450x450，按方形显示 */
  max-height: 32vh;                    /* 比之前的 45vh 矮一截，给聊天区更多空间 */
  flex: none;
}

/* 手机端：隐藏录制控件整行（开始 / 停止 / 下载录制） */
.app-wrapper.mobile .video-controls {
  display: none;
}

.app-wrapper.mobile .control-buttons {
  gap: 0.3rem;
}

.app-wrapper.mobile .control-btn {
  flex: 1;
  padding: 0.35rem 0.25rem;            /* 更矮 */
  font-size: 0.75rem;
  min-width: 0;
  line-height: 1.1;
}

.app-wrapper.mobile .control-btn .bi {
  font-size: 0.85rem;
}

.app-wrapper.mobile .control-btn span,
.app-wrapper.mobile .connect-btn,
.app-wrapper.mobile .disconnect-btn {
  font-size: 0.8rem;
}

.app-wrapper.mobile .connect-btn,
.app-wrapper.mobile .disconnect-btn {
  padding: 0.35rem 0.7rem;
  font-size: 0.78rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

/* 聊天区 */
.app-wrapper.mobile .chat-section {
  border-radius: 12px;
  min-height: 0;
}

.app-wrapper.mobile .chat-header {
  padding: 0.6rem 0.75rem;
  flex-direction: row;                 /* 单行仅显示标题 */
  gap: 0.5rem;
  align-items: center;
}

.app-wrapper.mobile .chat-header h2 {
  font-size: 0.95rem;
}

/* 手机端：隐藏「对话 / 朗读 / 清空」按钮组，默认只用对话模式 */
.app-wrapper.mobile .chat-actions {
  display: none;
}

.app-wrapper.mobile .action-btn {
  padding: 0.4rem 0.5rem;
  font-size: 0.8rem;
  min-width: 0;
}

.app-wrapper.mobile .action-btn .bi {
  font-size: 0.95rem;
}

/* 隐藏“清空历史”文字、只保留图标 */
.app-wrapper.mobile .clear-history-btn {
  font-size: 0;
}
.app-wrapper.mobile .clear-history-btn .bi {
  font-size: 1rem;
}

.app-wrapper.mobile .messages-container {
  padding: 0.5rem;
  gap: 0.5rem;
}

.app-wrapper.mobile .message {
  gap: 0.4rem;
}

.app-wrapper.mobile .message-avatar {
  width: 28px;
  height: 28px;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.app-wrapper.mobile .message-content {
  max-width: calc(100% - 36px);
}

.app-wrapper.mobile .message-text {
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  line-height: 1.5;
  word-break: break-word;
}

.app-wrapper.mobile .message-text :deep(pre) {
  font-size: 0.75rem;
  padding: 0.5rem;
  overflow-x: auto;
}

/* 输入区 */
.app-wrapper.mobile .input-area {
  padding: 0.5rem;
}

.app-wrapper.mobile .input-box {
  gap: 0.4rem;
}

.app-wrapper.mobile textarea {
  font-size: 16px;     /* iOS 小于 16px 会自动放大触发缩放 */
  padding: 0.6rem 0.75rem;
}

.app-wrapper.mobile .input-actions {
  flex-direction: row;
  gap: 0.4rem;
}

.app-wrapper.mobile .voice-btn,
.app-wrapper.mobile .send-btn {
  flex: 1;
  padding: 0.6rem 0.5rem;
  font-size: 0.85rem;
}

.app-wrapper.mobile .send-btn span {
  display: none;       /* 只剩纸飞机图标 */
}

/* TTS 模式 */
.app-wrapper.mobile .tts-mode {
  padding: 0.75rem;
}

.app-wrapper.mobile .tts-container textarea {
  padding: 0.75rem;
  font-size: 16px;
}

/* 通知：缩到屏边 */
.app-wrapper.mobile .notification-container {
  top: 60px;
  right: 8px;
  left: 8px;
}

.app-wrapper.mobile .notification {
  padding: 10px 12px;
  font-size: 0.85rem;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--bg-tertiary);
}

::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* 通知样式 */
.notification-container {
  position: fixed;
  top: 80px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notification {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--bg-secondary);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  border-left: 4px solid var(--primary);
  min-width: 280px;
  max-width: 400px;
}

.notification i {
  font-size: 20px;
  flex-shrink: 0;
}

.notification.success {
  border-left-color: #10b981;
}

.notification.success i {
  color: #10b981;
}

.notification.error {
  border-left-color: #ef4444;
}

.notification.error i {
  color: #ef4444;
}

.notification.warning {
  border-left-color: #f59e0b;
}

.notification.warning i {
  color: #f59e0b;
}

.notification.info {
  border-left-color: var(--primary);
}

.notification.info i {
  color: var(--primary);
}

/* 通知动画 */
.notification-enter-active {
  animation: notification-in 0.3s ease-out;
}

.notification-leave-active {
  animation: notification-out 0.3s ease-in;
}

@keyframes notification-in {
  from {
    opacity: 0;
    transform: translateX(100px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes notification-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100px);
  }
}
</style>
