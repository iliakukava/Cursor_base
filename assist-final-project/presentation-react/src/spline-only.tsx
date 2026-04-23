import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './index.css'
import { SplineScene } from '@/components/ui/splite'

/** Та же сцена, что в демо-карточке (робот). */
const SPLINE_SCENE = 'https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <div className="relative h-[100dvh] w-full overflow-hidden bg-black">
      <SplineScene scene={SPLINE_SCENE} className="h-full w-full" />
    </div>
  </StrictMode>
)
