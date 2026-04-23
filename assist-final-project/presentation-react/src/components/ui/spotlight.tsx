'use client'

import { useRef, useState, useCallback, useEffect } from 'react'
import { motion, useSpring, useTransform, type SpringOptions } from 'framer-motion'
import { cn } from '@/lib/utils'

type SpotlightProps = {
  className?: string
  size?: number
  springOptions?: SpringOptions
  /** Меньше blur — дешевле для GPU (например blur-md поверх WebGL). */
  blurClass?: string
}

export function Spotlight({
  className,
  size = 200,
  springOptions = { bounce: 0, stiffness: 320, damping: 36 },
  blurClass = 'blur-xl',
}: SpotlightProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isHovered, setIsHovered] = useState(false)
  const [parentElement, setParentElement] = useState<HTMLElement | null>(null)
  const rafRef = useRef<number | null>(null)
  const pendingRef = useRef({ x: 0, y: 0 })

  const mouseX = useSpring(0, springOptions)
  const mouseY = useSpring(0, springOptions)

  const spotlightLeft = useTransform(mouseX, (x) => `${x - size / 2}px`)
  const spotlightTop = useTransform(mouseY, (y) => `${y - size / 2}px`)

  useEffect(() => {
    if (containerRef.current) {
      const parent = containerRef.current.parentElement
      if (parent) {
        parent.style.position = 'relative'
        parent.style.overflow = 'hidden'
        setParentElement(parent)
      }
    }
  }, [])

  const handleMouseMove = useCallback(
    (event: MouseEvent) => {
      if (!parentElement) return
      pendingRef.current = { x: event.clientX, y: event.clientY }
      if (rafRef.current != null) return
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null
        const { left, top } = parentElement.getBoundingClientRect()
        const { x, y } = pendingRef.current
        mouseX.set(x - left)
        mouseY.set(y - top)
      })
    },
    [mouseX, mouseY, parentElement]
  )

  useEffect(() => {
    if (!parentElement) return

    const handleEnter = () => setIsHovered(true)
    const handleLeave = () => setIsHovered(false)

    parentElement.addEventListener('mousemove', handleMouseMove)
    parentElement.addEventListener('mouseenter', handleEnter)
    parentElement.addEventListener('mouseleave', handleLeave)

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      rafRef.current = null
      parentElement.removeEventListener('mousemove', handleMouseMove)
      parentElement.removeEventListener('mouseenter', handleEnter)
      parentElement.removeEventListener('mouseleave', handleLeave)
    }
  }, [parentElement, handleMouseMove])

  return (
    <motion.div
      ref={containerRef}
      className={cn(
        'pointer-events-none absolute rounded-full bg-[radial-gradient(circle_at_center,var(--tw-gradient-stops),transparent_80%)] transition-opacity duration-200',
        blurClass,
        'from-zinc-50 via-zinc-100 to-zinc-200',
        isHovered ? 'opacity-100' : 'opacity-0',
        className
      )}
      style={{
        width: size,
        height: size,
        left: spotlightLeft,
        top: spotlightTop,
      }}
    />
  )
}
