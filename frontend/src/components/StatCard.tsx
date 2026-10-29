import type { ReactNode } from 'react'

export default function StatCard({label, value, unit, description, icon}: {
  label: string; value: ReactNode; unit?: string; description: string; icon?: ReactNode
}) {
  return <section className="stat-card">
    <div className="stat-label"><span>{label}</span>{icon}</div>
    <div className="stat-value mono">{value}{unit && <span className="stat-unit">{unit}</span>}</div>
    <div className="stat-description">{description}</div>
  </section>
}
