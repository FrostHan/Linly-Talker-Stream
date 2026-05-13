// Linly-Talker-Stream (https://github.com/Kedreamix/Linly-Talker-Stream). Copyright [Linly-talker-stream@kedreamix]. Apache-2.0.
import { ref } from 'vue'

export function useSpeechRecognition(options = {}) {
  const {
    onResult = () => {},
    onFinalResult = () => {},
    onError = () => {},
    language = 'zh-CN',
    continuous = true
  } = options
  
  // Web Speech API 实际是否能用：仅有 API 存在不够，
  // Android Chrome / 国内手机需要连 Google 服务器，连不上会报 'network' 错。
  // 用 recognitionFailed 记录运行时是否报错，调用方可据此回落到后端 Whisper。
  const isSupported = ref(
    'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
  )
  const recognitionFailed = ref(false)
  
  let recognition = null
  let isRecognizing = false
  let shouldContinue = false

  const getSpeechRecognitionCtor = () => window.SpeechRecognition || window.webkitSpeechRecognition

  const setBackendFallback = (reason) => {
    recognitionFailed.value = true
    shouldContinue = false
    console.warn('Web Speech API 不可用，切换到后端 ASR:', reason)
  }

  const queryMicrophonePermission = async () => {
    if (!navigator.permissions || typeof navigator.permissions.query !== 'function') {
      return 'unknown'
    }

    try {
      const permission = await navigator.permissions.query({ name: 'microphone' })
      return permission.state
    } catch (error) {
      return 'unknown'
    }
  }
  
  if (isSupported.value) {
    const SpeechRecognition = getSpeechRecognitionCtor()
    recognition = new SpeechRecognition()
    
    recognition.continuous = continuous
    recognition.interimResults = true
    recognition.lang = language
    
    recognition.onresult = (event) => {
      let interimTranscript = ''
      let finalTranscript = ''
      
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript
        
        if (event.results[i].isFinal) {
          finalTranscript += transcript
        } else {
          interimTranscript += transcript
        }
      }
      
      if (interimTranscript) {
        onResult(interimTranscript)
      }
      
      if (finalTranscript) {
        onFinalResult(finalTranscript)
      }
    }
    
    recognition.onerror = (event) => {
      console.error('语音识别错误:', event.error)
      
      // 下面这些都是「正常产生」的错误，不报给用户：
      //   no-speech : 连续模式下没听到话，后续会重启
      //   aborted   : 主动调用 stop() 造成的、每次按住说话松手都会触发
      if ((event.error === 'no-speech' || event.error === 'aborted') && shouldContinue) {
        console.log('忽略识别事件:', event.error)
        return
      }
      if (event.error === 'aborted') {
        // 按住说话模式下，shouldContinue 已被 stopRecognition 设为 false，但这仍是正常停止
        console.log('识别被正常中止')
        return
      }
      
      // 网络 / 服务不可用 → 标记为失败，后续走后端 ASR 回落
      if (event.error === 'network' ||
          event.error === 'service-not-allowed' ||
          event.error === 'audio-capture' ||
          event.error === 'not-allowed') {
        recognitionFailed.value = true
        shouldContinue = false
        console.warn('Web Speech API 不可用（' + event.error + '），后续使用后端 ASR')
      }
      
      onError(event.error)
    }
    
    recognition.onend = () => {
      isRecognizing = false
      console.log('语音识别结束，shouldContinue:', shouldContinue)
      
      // 在连续模式下，如果标志为 true，则自动重启识别
      if (shouldContinue && !recognitionFailed.value) {
        console.log('连续模式：自动重启语音识别')
        setTimeout(() => {
          if (shouldContinue && !isRecognizing) {
            try {
              recognition.start()
              isRecognizing = true
            } catch (error) {
              console.error('重启语音识别失败:', error)
            }
          }
        }, 100)
      }
    }
  }
  
  const startRecognition = () => {
    if (recognition && !isRecognizing && !recognitionFailed.value) {
      try {
        shouldContinue = true
        recognition.start()
        isRecognizing = true
        console.log('启动语音识别，连续模式:', recognition.continuous)
      } catch (error) {
        console.error('启动语音识别失败:', error)
        recognitionFailed.value = true
      }
    }
  }
  
  const stopRecognition = () => {
    if (recognition) {
      try {
        shouldContinue = false
        if (isRecognizing) {
          recognition.stop()
        }
        console.log('停止语音识别')
      } catch (error) {
        console.error('停止语音识别失败:', error)
      }
    }
  }
  
  const updateSettings = (settings) => {
    if (recognition) {
      recognition.lang = settings.language || 'zh-CN'
      recognition.continuous = settings.continuous !== undefined ? settings.continuous : true
    }
  }

  const preflightRecognition = async ({ aggressive = false, timeoutMs = 3500 } = {}) => {
    if (!isSupported.value) {
      setBackendFallback('unsupported')
      return { ok: false, reason: 'unsupported' }
    }

    if (recognitionFailed.value) {
      return { ok: false, reason: 'already-failed' }
    }

    const permissionState = await queryMicrophonePermission()
    if (permissionState === 'denied') {
      setBackendFallback('microphone-denied')
      return { ok: false, reason: 'microphone-denied' }
    }

    // 页面加载时不主动弹麦克风权限；如果用户已经授权，才静默探测网络可用性。
    // 连接按钮点击后会以 aggressive=true 再测一次，仍然早于用户真正使用语音。
    if (!aggressive && permissionState === 'prompt') {
      return { ok: null, reason: 'permission-prompt' }
    }

    const SpeechRecognition = getSpeechRecognitionCtor()
    const probe = new SpeechRecognition()
    probe.continuous = false
    probe.interimResults = false
    probe.lang = recognition?.lang || language

    return await new Promise((resolve) => {
      let settled = false
      const finish = (ok, reason) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        try { probe.onresult = null; probe.onerror = null; probe.onend = null; probe.abort() } catch (_) {}
        if (!ok) setBackendFallback(reason)
        resolve({ ok, reason })
      }

      const timer = setTimeout(() => finish(true, 'timeout-no-error'), timeoutMs)

      probe.onresult = () => finish(true, 'result')
      probe.onerror = (event) => {
        const error = event.error || 'unknown'
        if (error === 'no-speech' || error === 'aborted') {
          finish(true, error)
          return
        }
        if (error === 'network' ||
            error === 'service-not-allowed' ||
            error === 'audio-capture' ||
            error === 'not-allowed') {
          finish(false, error)
          return
        }
        finish(false, error)
      }
      probe.onend = () => finish(true, 'ended')

      try {
        probe.start()
      } catch (error) {
        finish(false, error?.name || error?.message || 'start-failed')
      }
    })
  }
  
  return {
    isSupported: isSupported.value,
    recognitionFailed,
    startRecognition,
    stopRecognition,
    updateSettings,
    preflightRecognition
  }
}
