import { useId, useState } from 'react'
import type { TrendPoint } from '../types'

export default function TrendChart({series}: {series: TrendPoint[]}) {
  const gradient = useId().replace(/:/g, '')
  const [active, setActive] = useState<number | null>(null)
  const max = Math.max(4, ...series.map(point => point.requests))
  const x = (index: number) => 50 + index * (710 / Math.max(1, series.length - 1))
  const y = (value: number) => 180 - (value / max) * 144
  const line = series.map((point, index) => `${index ? 'L' : 'M'}${x(index)},${y(point.requests)}`).join(' ')
  const area = series.length ? `${line} L${x(series.length - 1)},180 L50,180 Z` : ''
  const ticks = [...new Set([max, Math.round(max * .75), Math.round(max * .5), Math.round(max * .25), 0])]
  const time = (point: TrendPoint) => new Date(point.time).toLocaleTimeString('zh-CN', {hour12: false, hour: '2-digit', minute: '2-digit'})
  const labels = series.map((point, index) => ({label: time(point), index})).filter(({index}) => index === 0 || index === series.length - 1 || index % Math.max(1, Math.floor(series.length / 5)) === 0)
  if (!series.length) return <div className="empty-state">当前时间范围内没有请求，发起测试后再来查看。</div>
  return <div className="trend-chart"><svg viewBox="0 0 800 225" role="img" aria-label="当前时间范围的请求量趋势">
    <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--primary)" stopOpacity=".14" /><stop offset="100%" stopColor="var(--primary)" stopOpacity=".01" /></linearGradient></defs>
    {ticks.map(tick => <g key={tick}><line x1="50" x2="760" y1={y(tick)} y2={y(tick)} stroke="var(--border)" strokeDasharray="3 5" /><text x="34" y={y(tick) + 4} textAnchor="end" className="chart-label">{tick}</text></g>)}
    <path d={area} fill={`url(#${gradient})`} /><path d={line} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    {series.map((point, index) => <g key={index} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} tabIndex={0} aria-label={`${time(point)}，${point.requests} 次请求，${point.errors} 次失败`}><circle cx={x(index)} cy={y(point.requests)} r="12" fill="transparent" />{active === index && <circle cx={x(index)} cy={y(point.requests)} r="4" fill="var(--primary)" />}<title>{time(point)} · {point.requests} 次请求，{point.errors} 次失败</title></g>)}
    {labels.map(({label, index}) => <text key={index} x={x(index)} y="211" textAnchor="middle" className="chart-label">{label}</text>)}
  </svg></div>
}
