// 前端现算技术指标（基于前复权 close 序列）。K 线图子图复用。

export function calcMA(closes: number[], n: number): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null)
  let sum = 0
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i]
    if (i >= n) sum -= closes[i - n]
    if (i >= n - 1) out[i] = sum / n
  }
  return out
}

export function calcEMA(closes: number[], n: number): number[] {
  const out: number[] = new Array(closes.length).fill(NaN)
  const k = 2 / (n + 1)
  let prev = closes[0]
  out[0] = prev
  for (let i = 1; i < closes.length; i++) {
    prev = closes[i] * k + prev * (1 - k)
    out[i] = prev
  }
  return out
}

export interface MacdResult {
  dif: number[]
  dea: number[]
  macd: number[]
}

export function calcMACD(closes: number[]): MacdResult {
  const ema12 = calcEMA(closes, 12)
  const ema26 = calcEMA(closes, 26)
  const dif = ema12.map((v, i) => v - ema26[i])
  const dea = calcEMA(dif, 9)
  const macd = dif.map((v, i) => (v - dea[i]) * 2)
  return { dif, dea, macd }
}

export function calcRSI(closes: number[], n = 14): (number | null)[] {
  const out: (number | null)[] = new Array(closes.length).fill(null)
  let avgGain = 0
  let avgLoss = 0
  for (let i = 1; i < closes.length; i++) {
    const chg = closes[i] - closes[i - 1]
    const gain = Math.max(chg, 0)
    const loss = Math.max(-chg, 0)
    if (i <= n) {
      avgGain += gain / n
      avgLoss += loss / n
      if (i === n) out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    } else {
      avgGain = (avgGain * (n - 1) + gain) / n
      avgLoss = (avgLoss * (n - 1) + loss) / n
      out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    }
  }
  return out
}

export interface BollResult {
  mid: number[]
  upper: number[]
  lower: number[]
}

export function calcBOLL(closes: number[], n = 20, k = 2): BollResult {
  const mid = calcMA(closes, n)
  const upper: number[] = new Array(closes.length).fill(NaN)
  const lower: number[] = new Array(closes.length).fill(NaN)
  for (let i = n - 1; i < closes.length; i++) {
    const slice = closes.slice(i - n + 1, i + 1)
    const mean = mid[i]!
    const variance = slice.reduce((s, v) => s + (v - mean) ** 2, 0) / n
    const sd = Math.sqrt(variance)
    upper[i] = mean + k * sd
    lower[i] = mean - k * sd
  }
  return { mid: mid as number[], upper, lower }
}
