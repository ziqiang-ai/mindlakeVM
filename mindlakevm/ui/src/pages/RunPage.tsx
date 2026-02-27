import { useState, useEffect } from 'react'
import { Play, ShieldAlert, ShieldCheck, CheckCircle, XCircle, Clock } from 'lucide-react'
import { runSkill, listSkills, type RunResponse, type SkillSummary } from '../api'

export default function RunPage() {
  const [skills, setSkills] = useState<SkillSummary[]>([])
  const [skillId, setSkillId] = useState('')
  const [userInput, setUserInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RunResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSkills().then(d => {
      setSkills(d.skills)
      if (d.skills.length > 0) setSkillId(d.skills[0].skill_id)
    }).catch(() => {})
  }, [])

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await runSkill(skillId, userInput)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const traceStatusIcon = (status: string) => {
    if (status === 'completed') return <CheckCircle size={14} className="text-green-500" />
    if (status === 'blocked') return <XCircle size={14} className="text-red-500" />
    return <Clock size={14} className="text-gray-300" />
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">执行 Skill</h1>
        <p className="text-gray-500 text-sm mt-1">挂载已编译的 Skill，实时执行用户输入（含 E 核 Guardrail 拦截）</p>
      </div>

      {/* Input */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">选择 Skill</label>
          {skills.length === 0 ? (
            <div className="text-sm text-gray-400 rounded-lg border border-dashed border-gray-300 p-3">
              暂无已编译的 Skill，请先前往「编译文档」页面编译
            </div>
          ) : (
            <select
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={skillId}
              onChange={e => setSkillId(e.target.value)}
            >
              {skills.map(s => (
                <option key={s.skill_id} value={s.skill_id}>
                  {s.skill_id} — {s.domain} / {s.object_type}
                </option>
              ))}
            </select>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">用户输入</label>
          <textarea
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={4}
            value={userInput}
            onChange={e => setUserInput(e.target.value)}
            placeholder="例如：现在是晚上9点，需要立刻扩容 API 服务器到20个实例..."
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleRun}
            disabled={loading || !skillId || !userInput.trim()}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Play size={16} />
            {loading ? '执行中...' : '执行'}
          </button>
          <button
            onClick={() => setUserInput('现在是晚上9点，API 网关响应时间飙升到5秒，受影响用户约2000人。我需要立刻把 API 服务器扩容到20个实例，直接执行吧。')}
            className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            🔴 触发拦截示例
          </button>
          <button
            onClick={() => setUserInput('服务C出现偶发性超时，受影响用户约80人，现在是下午2点，应该怎么处理？')}
            className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            ✅ 正常执行示例
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">{error}</div>
      )}

      {result && (
        <div className="space-y-4">
          {/* Status banner */}
          {result.blocked ? (
            <div className="flex items-start gap-3 rounded-xl bg-red-50 border border-red-200 p-4">
              <ShieldAlert className="text-red-600 mt-0.5 shrink-0" size={20} />
              <div>
                <div className="font-semibold text-red-800 mb-1">⛔ 操作被 Guardrail 拦截</div>
                {result.violations.map((v, i) => (
                  <div key={i} className="mt-2 rounded-lg bg-red-100 p-3 text-sm">
                    <div className="font-medium text-red-800">约束：{v.constraint}</div>
                    <div className="text-red-600 mt-0.5">原因：{v.reason}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-xl bg-green-50 border border-green-200 px-5 py-3">
              <ShieldCheck className="text-green-600 shrink-0" size={20} />
              <div className="font-semibold text-green-800">✅ 通过 Guardrail 校验，正常执行</div>
              {result.usage && (
                <div className="ml-auto text-xs text-green-600">
                  tokens: {result.usage.total_tokens} (in: {result.usage.input_tokens} / out: {result.usage.output_tokens})
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-3 gap-4">
            {/* Output */}
            <div className="col-span-2 rounded-xl border border-gray-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">输出</h3>
              <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed">{result.output_text}</pre>
            </div>

            {/* Right column */}
            <div className="space-y-4">
              {/* T Core Trace */}
              <div className="rounded-xl border border-purple-200 bg-purple-50 p-4">
                <h3 className="text-sm font-semibold text-purple-800 mb-2">T 核 Trace</h3>
                <div className="space-y-1.5">
                  {result.trace.map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      {traceStatusIcon(step.status)}
                      <span className={`font-mono ${
                        step.status === 'completed' ? 'text-purple-800' :
                        step.status === 'blocked' ? 'text-red-600' : 'text-gray-400'
                      }`}>{step.step_id}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Evidence */}
              {result.evidence.length > 0 && (
                <div className="rounded-xl border border-green-200 bg-green-50 p-4">
                  <h3 className="text-sm font-semibold text-green-800 mb-2">N 核 Evidence</h3>
                  <div className="space-y-1.5">
                    {result.evidence.map((e, i) => (
                      <div key={i} className="text-xs">
                        <div className="font-mono text-green-700">{e.source_path}</div>
                        {e.relevance && <div className="text-green-600 mt-0.5">{e.relevance}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Validation */}
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">验证结果</h3>
                <div className="space-y-1 text-xs">
                  {[
                    ['schema_valid', 'V1 Schema'],
                    ['evidence_sufficient', 'V2 Evidence'],
                    ['stop_condition_met', 'V3 Stop'],
                  ].map(([key, label]) => {
                    const val = result.validation[key as keyof typeof result.validation]
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <span className={val === true ? 'text-red-500' : val === false ? 'text-green-500' : 'text-gray-400'}>
                          {val === null || val === undefined ? '—' : val ? '✗' : '✓'}
                        </span>
                        <span className="text-gray-600">{label}</span>
                      </div>
                    )
                  })}
                  {result.validation.warnings.filter(w => !w.startsWith('soft_constraint')).map((w, i) => (
                    <div key={i} className="text-orange-600 text-xs mt-1">⚠ {w}</div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
