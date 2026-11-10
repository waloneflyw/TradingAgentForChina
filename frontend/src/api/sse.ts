// fetch-based POST SSE 客户端。
// 后端 SSE 端点都是 POST（/api/chat/stream、/api/analysis），浏览器 EventSource 只支持 GET，
// 故用 fetch + ReadableStream 逐帧解析 `event:` / `data:` 两行。

export interface StreamHandle {
  abort: () => void
}

type EventHandler = (event: string, data: any) => void

/**
 * 发起一个 POST SSE 流式请求。
 * @param url 端点路径（如 /api/chat/stream）
 * @param body 请求体（JSON）
 * @param onEvent 每个事件回调（event 类型 + data 对象）
 * @param onError 流中途失败回调（网络断 / 非 2xx）
 * @param onClose 流正常结束回调
 */
export function streamSse(
  url: string,
  body: unknown,
  onEvent: EventHandler,
  onError?: (err: Error) => void,
  onClose?: () => void,
): StreamHandle {
  const controller = new AbortController()

  void (async () => {
    let res: Response
    try {
      res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    } catch (e: any) {
      if (e?.name !== 'AbortError') onError?.(e as Error)
      return
    }

    if (!res.ok || !res.body) {
      let detail = `${res.status} ${res.statusText}`
      try {
        const j = await res.json()
        if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
      } catch {
        /* ignore */
      }
      onError?.(new Error(detail))
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const dispatch = (raw: string) => {
      // 解析一个 SSE 块：event: xxx\ndata: {...}
      let event = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
      }
      if (dataLines.length === 0) return
      let data: any = dataLines.join('\n')
      try {
        data = JSON.parse(data)
      } catch {
        /* 非 JSON，原样透传字符串 */
      }
      onEvent(event, data)
    }

    try {
      // 后端事件以空行分隔（\n\n）
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          if (block.trim()) dispatch(block)
        }
      }
      if (buffer.trim()) dispatch(buffer) // 兜底：无结尾空行的最后一块
      onClose?.()
    } catch (e: any) {
      if (e?.name !== 'AbortError') onError?.(e as Error)
    }
  })()

  return { abort: () => controller.abort() }
}
