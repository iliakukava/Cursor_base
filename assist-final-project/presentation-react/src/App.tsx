import { SplineSceneBasic } from '@/components/ui/demo'
import { Sparkles } from 'lucide-react'

function App() {
  return (
    <main className="min-h-screen bg-black px-4 py-10 text-white md:px-10">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex items-center gap-3 text-sm text-neutral-300">
          <Sparkles className="h-4 w-4 text-cyan-300" />
          <span>TeleFlow Presentation Theme - Spline Edition</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-6">
          <SplineSceneBasic />
        </div>
      </div>
    </main>
  )
}

export default App
