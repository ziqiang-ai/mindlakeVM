import { useState } from 'react'
import { FileText, Play, BarChart2, Cpu } from 'lucide-react'
import CompilePage from './pages/CompilePage'
import RunPage from './pages/RunPage'
import BenchPage from './pages/BenchPage'

type Page = 'compile' | 'run' | 'bench'

const NAV: { id: Page; label: string; icon: React.ReactNode; desc: string }[] = [
  { id: 'compile', label: '编译文档', icon: <FileText size={18} />, desc: 'Doc → SemanticKernelIR' },
  { id: 'run',     label: '执行 Skill', icon: <Play size={18} />,     desc: 'Run + Guardrail' },
  { id: 'bench',   label: 'Bench 评测', icon: <BarChart2 size={18} />, desc: 'L1 vs L2 vs L4' },
]

export default function App() {
  const [page, setPage] = useState<Page>('compile')

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
            <Cpu size={16} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-gray-900 leading-tight">MindLakeOS</div>
            <div className="text-xs text-gray-400 leading-tight">Demo v0.1</div>
          </div>
        </div>
        <div className="ml-4 h-6 w-px bg-gray-200" />
        <nav className="flex gap-1">
          {NAV.map(n => (
            <button
              key={n.id}
              onClick={() => setPage(n.id)}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                page === n.id
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {n.icon}
              {n.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto text-xs text-gray-400 hidden md:block">
          {NAV.find(n => n.id === page)?.desc}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 px-6 py-8">
        {page === 'compile' && <CompilePage />}
        {page === 'run'     && <RunPage />}
        {page === 'bench'   && <BenchPage />}
      </main>
    </div>
  )
}
