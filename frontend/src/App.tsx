import { useEffect, useState } from 'react'
import { CircleCheck, CircleAlert, CircleX } from 'lucide-react'
import './App.css'

interface JobStatus {
  healthy: boolean
  last_success: string | null
  error: string | null
}

interface SchedulerHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  jobs: Record<string, JobStatus>
}

function App() {
  const [health, setHealth] = useState<SchedulerHealth | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/status')
        const data = await res.json()
        setHealth(data)
      } catch (err) {
        console.error('Failed to fetch health:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
    // Poll every 30 seconds
    const interval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <div>Loading...</div>

  return (
    <div className="status-container">
      <h1>FOV Notification Service</h1>
      <h2>Schedule Retrieval Status</h2>
      <div className={`status-badge ${health?.status}`}>
        {health?.status === 'healthy' && <><CircleCheck size={18} /> Healthy</>}
        {health?.status === 'degraded' && <><CircleAlert size={18} /> Degraded</>}
        {health?.status === 'unhealthy' && <><CircleX size={18} /> Unhealthy</>}
      </div>

      <h2>Observatories</h2>
      {health && Object.entries(health.jobs).map(([jobId, status]) => (
        <div key={jobId} className={`job-card ${status.healthy ? 'healthy' : 'unhealthy'}`}>
          <div className="job-header">
            {status.healthy ? <CircleCheck size={16} /> : <CircleX size={16} />}
            <strong>{jobId}</strong>
          </div>
          <p>Last success: {status.last_success ? new Date(status.last_success).toLocaleString() : 'Never'}</p>
          {status.error && <p className="error">Error: {status.error}</p>}
        </div>
      ))}

      {health && Object.keys(health.jobs).length === 0 && (
        <p>No jobs have run yet.</p>
      )}
    </div>
  )
}

export default App
