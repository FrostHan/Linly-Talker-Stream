// Linly-Talker-Stream (https://github.com/Kedreamix/Linly-Talker-Stream). Copyright [Linly-talker-stream@kedreamix]. Apache-2.0.
export function useWebRTC(options = {}) {
  let pc = null
  let sessionIdValue = 0
  let connecting = false   // 防重入：用户连点两次"启动连接"会让 pc 在 await 中被清空
  const { onNotification } = options

  const logCandidatePairStats = async (peerConnection, reason) => {
    try {
      const stats = await peerConnection.getStats()
      const reports = new Map()
      stats.forEach(report => reports.set(report.id, report))
      stats.forEach(report => {
        if (report.type === 'candidate-pair' && (report.selected || report.nominated)) {
          const local = reports.get(report.localCandidateId)
          const remote = reports.get(report.remoteCandidateId)
          console.log('📊 ICE candidate-pair(%s): state=%s nominated=%s local=%s/%s remote=%s/%s bytes=%s/%s rtt=%s',
            reason,
            report.state,
            report.nominated,
            local?.candidateType,
            local?.protocol,
            remote?.candidateType,
            remote?.protocol,
            report.bytesSent,
            report.bytesReceived,
            report.currentRoundTripTime)
        }
      })
    } catch (error) {
      console.warn('获取 ICE candidate-pair stats 失败:', error)
    }
  }

  const countCandidates = (sdp = '') => {
    const lines = sdp.split('\n')
    return {
      host: lines.filter(line => line.includes(' typ host ')).length,
      srflx: lines.filter(line => line.includes(' typ srflx ')).length,
      relay: lines.filter(line => line.includes(' typ relay ')).length
    }
  }

  const waitForIceGatheringComplete = (peerConnection, timeoutMs = 15000) => {
    if (peerConnection.iceGatheringState === 'complete') return Promise.resolve(true)
    return new Promise(resolve => {
      let done = false
      const finish = (ok) => {
        if (done) return
        done = true
        clearTimeout(timer)
        peerConnection.removeEventListener('icegatheringstatechange', onStateChange)
        resolve(ok)
      }
      const onStateChange = () => {
        console.log('🧊 ICE gathering 状态:', peerConnection.iceGatheringState)
        if (peerConnection.iceGatheringState === 'complete') finish(true)
      }
      const timer = setTimeout(() => finish(false), timeoutMs)
      peerConnection.addEventListener('icegatheringstatechange', onStateChange)
    })
  }

  const waitForIceConnected = (peerConnection, timeoutMs = 25000) => {
    if (['connected', 'completed'].includes(peerConnection.iceConnectionState)) return Promise.resolve(true)
    if (['failed', 'closed'].includes(peerConnection.iceConnectionState)) return Promise.resolve(false)
    return new Promise(resolve => {
      let done = false
      const finish = (ok) => {
        if (done) return
        done = true
        clearTimeout(timer)
        peerConnection.removeEventListener('iceconnectionstatechange', onStateChange)
        resolve(ok)
      }
      const onStateChange = () => {
        if (['connected', 'completed'].includes(peerConnection.iceConnectionState)) finish(true)
        if (['failed', 'closed'].includes(peerConnection.iceConnectionState)) finish(false)
      }
      const timer = setTimeout(() => finish(false), timeoutMs)
      peerConnection.addEventListener('iceconnectionstatechange', onStateChange)
    })
  }
  
  const startPlay = async (stunServer = 'stun:stun.miwifi.com:3478') => {
    console.log('开始连接 WebRTC...')

    if (connecting) {
      console.warn('⏳ 上一次连接还没完成，忽略本次点击')
      return
    }
    connecting = true

    // 关闭之前的连接
    if (pc) {
      console.log('关闭旧连接...')
      pc.close()
      pc = null
    }

    // 全程使用 localPc，避免 await 期间外部把 pc 改掉导致 null 解引用
    let localPc = null
    
    try {
      console.log('✅ 创建 RTCPeerConnection...')
      
      // 创建 RTCPeerConnection 配置：优先用后端 /ice 下发的配置（含 TURN 凭据），
      // 失败时回退到设置面板里的 STUN
      const configuration = { iceServers: [] }
      let usedRemoteIce = false
      try {
        const r = await fetch('/ice')
        if (r.ok) {
          const j = await r.json()
          if (Array.isArray(j.iceServers) && j.iceServers.length > 0) {
            configuration.iceServers = j.iceServers
            usedRemoteIce = true
            console.log('🌐 使用后端 /ice 下发的 ICE 配置:', j.iceServers.map(s => s.urls))
          }
        }
      } catch (e) {
        console.warn('获取 /ice 失败，使用本地 STUN:', e)
      }
      if (!usedRemoteIce && stunServer) {
        configuration.iceServers.push({ urls: stunServer })
        console.log('🧊 使用本地 STUN 服务器:', stunServer)
      }

      const isPublicHost = !['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
      const hasTurn = configuration.iceServers.some(server => {
        const urls = Array.isArray(server.urls) ? server.urls : [server.urls]
        return urls.some(url => typeof url === 'string' && url.startsWith('turn'))
      })
      if (isPublicHost && hasTurn) {
        // 公网访问时 STUN/srflx 在部分运营商网络会短暂 checking 后失败；强制 relay 更稳。
        // 再优先保留 TURN TCP/TLS，避开移动/校园/企业网常见的 UDP 限制。
        const relayServers = configuration.iceServers
          .map(server => {
            const urls = Array.isArray(server.urls) ? server.urls : [server.urls]
            const turnUrls = urls.filter(url => {
              if (typeof url !== 'string' || !url.startsWith('turn')) return false
              return url.startsWith('turns:') || url.includes('transport=tcp')
            })
            if (turnUrls.length === 0) return null
            return { ...server, urls: turnUrls }
          })
          .filter(Boolean)
        if (relayServers.length > 0) {
          configuration.iceServers = relayServers
        }
        configuration.iceTransportPolicy = 'relay'
        console.log('🛡️ 公网访问检测到 TURN，启用 relay-only ICE policy:', configuration.iceServers.map(s => s.urls))
      }
      
      pc = new RTCPeerConnection(configuration)
      localPc = pc
      window.__pc = pc   // 诊断用：App.vue 取到 pc.getStats() 看 inbound RTP
      
      // 添加接收 track 的处理
      pc.ontrack = (event) => {
        console.log('📺 收到媒体流:', event.track.kind, 'streams=', event.streams?.length)
        const video = document.getElementById('video')
        if (!video) {
          console.error('❌ 找不到 #video 元素')
          return
        }
        if (event.streams && event.streams[0]) {
          // 同一个 stream 会被 audio/video 两个 track 各触发一次 ontrack，赋同一对象幂等
          if (video.srcObject !== event.streams[0]) {
            video.srcObject = event.streams[0]
            console.log('✅ 视频流已设置到 video 元素 (tracks:', event.streams[0].getTracks().map(t => t.kind).join(','), ')')
          }
          // 移动端 autoplay 必须 muted；先 muted 播起来，UI 上提供「解除静音」按钮
          video.muted = true
          const playPromise = video.play()
          if (playPromise && typeof playPromise.then === 'function') {
            playPromise
              .then(() => console.log('▶️ video.play() 成功'))
              .catch(err => console.warn('⚠️ video.play() 被拦截:', err.name, err.message))
          }
        }
      }
      
      // 监听连接状态
      pc.onconnectionstatechange = () => {
        console.log('📡 连接状态:', pc.connectionState)
        if (['connected', 'failed', 'disconnected'].includes(pc.connectionState)) {
          logCandidatePairStats(pc, `connection:${pc.connectionState}`)
        }
      }
      
      pc.oniceconnectionstatechange = () => {
        console.log('🧊 ICE 连接状态:', pc.iceConnectionState)
        if (['connected', 'completed', 'failed', 'disconnected'].includes(pc.iceConnectionState)) {
          logCandidatePairStats(pc, `ice:${pc.iceConnectionState}`)
        }
      }
      
      // 添加 transceiver 来接收音视频
      pc.addTransceiver('audio', { direction: 'recvonly' })
      pc.addTransceiver('video', { direction: 'recvonly' })
      
      console.log('📤 创建 Offer...')
      const offer = await localPc.createOffer()
      await localPc.setLocalDescription(offer)

      // 本项目没有实现 trickle ICE；必须等 candidate 都写进 SDP 后再把 offer 发给后端。
      // relay-only 时 TURN 候选通常要几秒，不等这里后端会一直 ICE checking。
      const gathered = await waitForIceGatheringComplete(localPc)
      const localCandidates = countCandidates(localPc.localDescription?.sdp || '')
      console.log('🧊 本地 ICE candidates: host=%d srflx=%d relay=%d complete=%s',
        localCandidates.host, localCandidates.srflx, localCandidates.relay, gathered)
      if (configuration.iceTransportPolicy === 'relay' && localCandidates.relay === 0) {
        throw new Error('未获取到 TURN relay candidate，请检查 TURN 在当前网络是否可达')
      }
      
      console.log('🔗 发送 Offer 到服务器...')
      const response = await fetch('/offer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sdp: localPc.localDescription.sdp,
          type: localPc.localDescription.type
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('📥 收到服务器响应，会话ID:', data.sessionid)
      
      // 保存 sessionId
      sessionIdValue = data.sessionid
      const sessionInput = document.getElementById('sessionid')
      if (sessionInput) {
        sessionInput.value = data.sessionid
      }
      
      // 期间如果用户主动 stopPlay() 把 pc 关了，就不要再 setRemoteDescription
      if (localPc.signalingState === 'closed') {
        console.warn('⚠️ 连接已被关闭，丢弃 answer')
        return sessionIdValue
      }
      
      // 设置远程描述
      const answer = new RTCSessionDescription({
        sdp: data.sdp,
        type: data.type
      })
      await localPc.setRemoteDescription(answer)

      const iceConnected = await waitForIceConnected(localPc)
      await logCandidatePairStats(localPc, iceConnected ? 'post-answer:connected' : 'post-answer:not-connected')
      if (!iceConnected) {
        throw new Error(`ICE 未连接成功，当前状态: ${localPc.iceConnectionState}`)
      }
      
      console.log('✅ WebRTC 连接建立成功！')
      
      return sessionIdValue
      
    } catch (error) {
      console.error('❌ WebRTC 连接失败:', error)
      if (onNotification) {
        onNotification(`WebRTC 连接失败: ${error.message}`, 'error')
      }
      // 只关掉本次的 pc，避免误关后续重试时新建的连接
      if (localPc) {
        try { localPc.close() } catch (_) {}
        if (pc === localPc) pc = null
      }
      throw error
    } finally {
      connecting = false
    }
  }
  
  const stopPlay = () => {
    console.log('停止 WebRTC 连接...')
    
    if (pc) {
      pc.close()
      pc = null
      window.__pc = null
      console.log('✅ WebRTC 连接已关闭')
    }
    
    const video = document.getElementById('video')
    if (video) {
      video.srcObject = null
    }
  }
  
  return {
    startPlay,
    stopPlay
  }
}
