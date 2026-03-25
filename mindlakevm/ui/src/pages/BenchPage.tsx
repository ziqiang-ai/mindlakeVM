import { useState } from 'react'
import { BarChart2, TrendingUp, Shield, Coins } from 'lucide-react'
import { runBench, type BenchResponse, type BenchRow } from '../api'

const SCENARIOS = [
  { id: 'sop-scale-guardrail', label: 'SOP 高峰期扩容门禁', desc: '核心路演场景：Vanilla 漏拦截 vs MindLakeOS 精准拦截' },
  { id: 'policy-reimbursement-json', label: '政策报销审批矩阵', desc: '结构化 JSON 输出 + 条件分支决策' },
  { id: 'rfc-schema-output', label: 'RFC API 网关设计', desc: 'RFC 文档 → 可校验的 JSON Schema 输出' },
  { id: 'llmos-kernel-architecture', label: 'LLMOS Kernel 架构案例', desc: '项目设计对话沉淀为案例文档后的编译、问答与评测链路' },
]

const BASELINE_LABELS: Record<string, string> = {
  vanilla: 'Vanilla（L1）',
  rag: 'RAG（L2）',
  mindlakevm: 'MindLakeOS（L4）',
}

const BASELINE_COLORS: Record<string, string> = {
  vanilla: 'bg-gray-500',
  rag: 'bg-yellow-500',
  mindlakevm: 'bg-blue-600',
}

function MetricBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.min(Math.max(value / max, 0), 1) * 100
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono w-10 text-right">{(value * 100).toFixed(0)}%</span>
    </div>
  )
}

function ResultRow({ row }: { row: BenchRow }) {
  return (
    <tr className="border-t border-gray-100">
      <td className="py-3 px-4">
        <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold text-white ${BASELINE_COLORS[row.baseline] ?? 'bg-gray-400'}`}>
          {BASELINE_LABELS[row.baseline] ?? row.baseline}
        </span>
      </td>
      <td className="py-3 px-4">
        <MetricBar value={row.success_rate} />
      </td>
      <td className="py-3 px-4">
        <MetricBar value={row.guardrail_block_rate} />
      </td>
      <td className="py-3 px-4">
        <span className={`text-sm font-mono ${row.false_positive_rate > 0 ? 'text-red-600' : 'text-green-600'}`}>
          {(row.false_positive_rate * 100).toFixed(0)}%
        </span>
      </td>
      <td className="py-3 px-4">
        <MetricBar value={row.citation_rate} />
      </td>
      <td className="py-3 px-4 text-xs text-gray-500 font-mono">
        {row.token_cost.total_tokens.toLocaleString()}
      </td>
    </tr>
  )
}

export default function BenchPage() {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id)
  const [baselines, setBaselines] = useState(['vanilla', 'mindlakevm'])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BenchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const toggleBaseline = (b: string) => {
    setBaselines(prev => prev.includes(b) ? prev.filter(x => x !== b) : [...prev, b])
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await runBench(scenarioId, baselines)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const ml = result?.results_table.find(r => r.baseline === 'mindlakevm')
  const vanilla = result?.results_table.find(r => r.baseline === 'vanilla')

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Bench 评测</h1>
        <p className="text-gray-500 text-sm mt-1">对比 Vanilla / RAG / MindLakeOS 在标准场景上的表现</p>
      </div>

      {/* Config */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">评测场景</label>
          <div className="space-y-2">
            {SCENARIOS.map(s => (
              <label key={s.id} className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                scenarioId === s.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
              }`}>
                <input type="radio" name="scenario" value={s.id} checked={scenarioId === s.id} onChange={() => setScenarioId(s.id)} className="mt-0.5" />
                <div>
                  <div className="text-sm font-medium text-gray-800">{s.label}</div>
                  <div className="text-xs text-gray-500">{s.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">参与对比的 Baseline</label>
          <div className="flex gap-3">
            {(['vanilla', 'rag', 'mindlakevm'] as const).map(b => (
              <label key={b} className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer transition-colors ${
                baselines.includes(b) ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium' : 'border-gray-200 text-gray-600'
              }`}>
                <input type="checkbox" checked={baselines.includes(b)} onChange={() => toggleBaseline(b)} className="rounded" />
                {BASELINE_LABELS[b]}
              </label>
            ))}
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={loading || baselines.length === 0}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <BarChart2 size={16} />
          {loading ? '评测中（需要 30-60s）...' : '开始评测'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Summary cards */}
          {result.report_summary.highlight && (
            <div className="rounded-xl bg-blue-600 text-white p-5">
              <div className="text-xs font-medium opacity-75 mb-1">路演摘要</div>
              <div className="text-lg font-bold">{result.report_summary.highlight}</div>
            </div>
          )}

          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-gray-200 bg-white p-4 flex items-start gap-3">
              <TrendingUp className="text-blue-500 mt-0.5 shrink-0" size={20} />
              <div>
                <div className="text-xs text-gray-500">成功率提升</div>
                <div className="text-2xl font-bold text-gray-900">
                  +{(result.report_summary.success_rate_delta * 100).toFixed(0)}%
                </div>
                {vanilla && ml && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    {(vanilla.success_rate * 100).toFixed(0)}% → {(ml.success_rate * 100).toFixed(0)}%
                  </div>
                )}
              </div>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-4 flex items-start gap-3">
              <Shield className="text-green-500 mt-0.5 shrink-0" size={20} />
              <div>
                <div className="text-xs text-gray-500">门禁准确率</div>
                <div className="text-2xl font-bold text-gray-900">
                  {(result.report_summary.guardrail_accuracy * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-400 mt-0.5">误报率 {ml ? (ml.false_positive_rate * 100).toFixed(0) : '—'}%</div>
              </div>
            </div>
            <div className="rounded-xl border border-gray-200 bg-white p-4 flex items-start gap-3">
              <Coins className="text-orange-500 mt-0.5 shrink-0" size={20} />
              <div>
                <div className="text-xs text-gray-500">Token 节省</div>
                <div className={`text-2xl font-bold ${result.report_summary.token_savings_pct >= 0 ? 'text-gray-900' : 'text-red-500'}`}>
                  {result.report_summary.token_savings_pct >= 0 ? '' : ''}{(result.report_summary.token_savings_pct * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-400 mt-0.5">vs Vanilla</div>
              </div>
            </div>
          </div>

          {/* Results table */}
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100 text-sm font-semibold text-gray-700">详细对比</div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <tr>
                  <th className="py-2 px-4 text-left font-medium">Baseline</th>
                  <th className="py-2 px-4 text-left font-medium">成功率</th>
                  <th className="py-2 px-4 text-left font-medium">门禁拦截率</th>
                  <th className="py-2 px-4 text-left font-medium">误报率</th>
                  <th className="py-2 px-4 text-left font-medium">引用率</th>
                  <th className="py-2 px-4 text-left font-medium">Total Tokens</th>
                </tr>
              </thead>
              <tbody>
                {result.results_table.map(row => <ResultRow key={row.baseline} row={row} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
