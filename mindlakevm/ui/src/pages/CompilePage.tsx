import { useEffect, useState } from 'react'
import { FileText, Zap, ChevronDown, ChevronUp } from 'lucide-react'
import { compileDoc, getSkillFile, type CompileResponse } from '../api'
import RNETPanel from '../components/RNETPanel'

const EXAMPLE_SOP = `# 生产环境故障应急响应 SOP

## 1. 故障分级
| 级别 | 受影响用户 | 响应时限 |
|------|-----------|--------|
| SEV1 | > 1000 | 5 分钟内响应 |
| SEV2 | 100-1000 | 15 分钟内响应 |
| SEV3 | < 100 | 1 小时内响应 |

## 2. 应急响应步骤
### Step 1：评估影响范围
- 确认受影响的服务名称
- 统计受影响用户数量

### Step 2：升级通知
- 受影响用户 > 1000：立即通知 CTO 并召集 War Room

## 3. 禁止事项（红线）
1. **高峰期禁止扩缩容**：高峰期（08:00-22:00）禁止任何扩缩容操作，除非 CTO 书面授权
2. **生产数据库只读**：故障期间生产数据库仅允许只读操作，写操作需 DBA 审批
3. **外部通告时限**：受影响用户超过 1000 人时，必须在 15 分钟内发送外部通告`

export default function CompilePage() {
  const [taskDesc, setTaskDesc] = useState('SEV1 故障应急响应 SOP')
  const [docContent, setDocContent] = useState(EXAMPLE_SOP)
  const [strategy, setStrategy] = useState('default')
  const [enableProbe, setEnableProbe] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<CompileResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showArtifacts, setShowArtifacts] = useState(false)
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null)
  const [artifactContent, setArtifactContent] = useState<string>('')
  const [artifactError, setArtifactError] = useState<string | null>(null)
  const [artifactLoading, setArtifactLoading] = useState(false)

  const handleCompile = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await compileDoc({ task_description: taskDesc, document_content: docContent, strategy, enable_probe: enableProbe })
      setResult(res)
      setSelectedArtifact(res.artifacts.files_tree[0]?.path ?? null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!result || !selectedArtifact) {
      setArtifactContent('')
      setArtifactError(null)
      return
    }

    setArtifactLoading(true)
    setArtifactError(null)
    getSkillFile(result.artifacts.skill_id, selectedArtifact)
      .then(file => setArtifactContent(file.content))
      .catch((e: unknown) => setArtifactError(e instanceof Error ? e.message : String(e)))
      .finally(() => setArtifactLoading(false))
  }, [result, selectedArtifact])

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">编译文档</h1>
        <p className="text-gray-500 text-sm mt-1">将企业文档编译为 SemanticKernelIR（RNET 四核中间表示）</p>
      </div>

      {/* Input Form */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">任务描述</label>
          <input
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={taskDesc}
            onChange={e => setTaskDesc(e.target.value)}
            placeholder="例如：P0 事故应急响应 SOP"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">文档内容</label>
          <textarea
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={10}
            value={docContent}
            onChange={e => setDocContent(e.target.value)}
            placeholder="粘贴 SOP / 政策 / RFC 内容..."
          />
        </div>
        <div className="flex items-center gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">编译策略</label>
            <select
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={strategy}
              onChange={e => setStrategy(e.target.value)}
            >
              <option value="minimal">minimal — 最精简</option>
              <option value="default">default — 标准</option>
              <option value="detailed">detailed — 详尽</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer mt-5">
            <input type="checkbox" checked={enableProbe} onChange={e => setEnableProbe(e.target.checked)} className="rounded" />
            启用 MetaIgnoranceProbe（盲点探测）
          </label>
        </div>
        <button
          onClick={handleCompile}
          disabled={loading || !taskDesc.trim()}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Zap size={16} />
          {loading ? '编译中...' : '开始编译'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center gap-3 rounded-xl bg-green-50 border border-green-200 px-5 py-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-green-600 text-white text-sm font-bold">✓</div>
            <div>
              <div className="font-semibold text-green-800">编译成功</div>
              <div className="text-xs text-green-600">
                kernel_id: <span className="font-mono">{result.kernel_id}</span>
                {result.cache_hit && <span className="ml-2 rounded bg-green-200 px-1.5 py-0.5 text-xs">缓存命中</span>}
              </div>
            </div>
          </div>

          {/* RNET Panel */}
          <div>
            <h2 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <FileText size={16} />
              SemanticKernelIR — RNET 四核
            </h2>
            <RNETPanel ir={result.ir} />
          </div>

          {/* Artifacts */}
          <div className="rounded-xl border border-gray-200 bg-white">
            <button
              onClick={() => setShowArtifacts(!showArtifacts)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-xl"
            >
              <span>Skill 包产物（{result.artifacts.files_tree.length} 个文件）</span>
              {showArtifacts ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showArtifacts && (
              <div className="grid gap-4 border-t border-gray-100 px-5 pb-4 pt-4 md:grid-cols-[280px_1fr]">
                <div className="space-y-1.5">
                  {result.artifacts.files_tree.map((f, i) => (
                    <button
                      key={i}
                      onClick={() => setSelectedArtifact(f.path)}
                      className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                        selectedArtifact === f.path ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                          f.type === 'skill_main' ? 'bg-blue-100 text-blue-700' :
                          f.type === 'reference' ? 'bg-green-100 text-green-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>{f.type}</span>
                        <span className="font-mono text-gray-700">{f.path}</span>
                      </div>
                      {f.token_estimate && <div className="mt-1 text-xs text-gray-400">~{f.token_estimate} tokens</div>}
                    </button>
                  ))}
                </div>
                <div className="rounded-xl border border-gray-200 bg-gray-50">
                  <div className="border-b border-gray-200 px-4 py-2 text-sm font-medium text-gray-700">
                    {selectedArtifact ?? '选择文件查看内容'}
                  </div>
                  {artifactError ? (
                    <div className="p-4 text-sm text-red-700">{artifactError}</div>
                  ) : artifactLoading ? (
                    <div className="p-4 text-sm text-gray-500">加载中...</div>
                  ) : (
                    <pre className="max-h-96 overflow-auto whitespace-pre-wrap p-4 text-xs leading-relaxed text-gray-800">{artifactContent || '暂无内容'}</pre>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
