import type { SemanticKernelIR } from '../api'

interface Props { ir: SemanticKernelIR }

export default function RNETPanel({ ir }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 text-sm">
      {/* R Core */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded bg-blue-600 px-2 py-0.5 text-xs font-bold text-white">R</span>
          <span className="font-semibold text-blue-800">语义坐标</span>
        </div>
        <div className="space-y-1 text-blue-900">
          <div><span className="font-medium">domain：</span>{ir.r.domain}</div>
          <div><span className="font-medium">type：</span>{ir.r.object_type}</div>
          <div className="text-xs text-blue-700 mt-1">{ir.r.semantic_space}</div>
        </div>
      </div>

      {/* N Core */}
      <div className="rounded-lg border border-green-200 bg-green-50 p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded bg-green-600 px-2 py-0.5 text-xs font-bold text-white">N</span>
          <span className="font-semibold text-green-800">知识注册</span>
        </div>
        <div className="space-y-1 text-green-900">
          <div><span className="font-medium">结构：</span>{ir.n.structure}</div>
          <div><span className="font-medium">约束 ({ir.n.constraints.length})：</span></div>
          <ul className="ml-2 text-xs space-y-0.5">
            {ir.n.constraints.slice(0, 3).map((c, i) => <li key={i} className="text-green-700">• {c}</li>)}
            {ir.n.constraints.length > 3 && <li className="text-green-500">+{ir.n.constraints.length - 3} 条...</li>}
          </ul>
          <div><span className="font-medium">引用 ({ir.n.references.length})：</span></div>
          <ul className="ml-2 text-xs space-y-0.5">
            {ir.n.references.map((r, i) => (
              <li key={i} className="text-green-700">• {r.path} <span className="text-green-500">({r.scope})</span></li>
            ))}
          </ul>
        </div>
      </div>

      {/* E Core */}
      <div className="rounded-lg border border-red-200 bg-red-50 p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded bg-red-600 px-2 py-0.5 text-xs font-bold text-white">E</span>
          <span className="font-semibold text-red-800">熵控门禁</span>
        </div>
        <div className="space-y-1 text-red-900">
          <div className="text-xs text-red-700 mb-1">{ir.e.target_entropy}</div>
          <div><span className="font-medium">🔴 硬约束 ({ir.e.hard_constraints.length})：</span></div>
          <ul className="ml-2 text-xs space-y-0.5">
            {ir.e.hard_constraints.map((c, i) => <li key={i} className="text-red-800">• {c}</li>)}
          </ul>
          {ir.e.soft_constraints.length > 0 && <>
            <div className="mt-1"><span className="font-medium">🟡 软约束：</span></div>
            <ul className="ml-2 text-xs space-y-0.5">
              {ir.e.soft_constraints.slice(0, 2).map((c, i) => <li key={i} className="text-orange-700">• {c}</li>)}
            </ul>
          </>}
        </div>
      </div>

      {/* T Core */}
      <div className="rounded-lg border border-purple-200 bg-purple-50 p-3">
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded bg-purple-600 px-2 py-0.5 text-xs font-bold text-white">T</span>
          <span className="font-semibold text-purple-800">执行路径</span>
        </div>
        <div className="space-y-1 text-purple-900">
          <div><span className="font-medium">步骤 ({ir.t.path.length})：</span></div>
          <ol className="ml-2 text-xs space-y-0.5">
            {ir.t.path.map((step, i) => (
              <li key={i} className="text-purple-800">
                {i + 1}. <span className="font-medium">{step.name}</span>
                {step.decision_points.length > 0 && <span className="text-purple-500 ml-1">⟨{step.decision_points.length}分支⟩</span>}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  )
}
